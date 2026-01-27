from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from dotenv import load_dotenv
import os
import yaml
import requests

# Load environment variables FIRST before any AWS imports
load_dotenv()

# Load IAM configuration from YAML
def load_iam_config():
    config_path = os.path.join(os.path.dirname(__file__), 'ec2_service_role.yml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config['aws']
    except Exception as e:
        print(f"Warning: Could not load ec2_service_role.yml: {e}")
        return {'default_region': 'us-east-1'}

def is_running_on_ec2():
    """Detect if running on EC2 by checking instance metadata and IAM role"""
    # Check explicit environment variable first
    env_override = os.environ.get('USE_EC2_ROLE', '').lower()
    if env_override == 'true':
        return True
    elif env_override == 'false':
        return False
    
    try:
        # Try IMDSv2 first
        token_response = requests.put(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            timeout=1
        )
        if token_response.status_code == 200:
            token = token_response.text
            response = requests.get(
                'http://169.254.169.254/latest/meta-data/instance-id',
                headers={'X-aws-ec2-metadata-token': token},
                timeout=1
            )
            return response.status_code == 200
    except:
        pass
    
    try:
        # Fallback to IMDSv1
        response = requests.get('http://169.254.169.254/latest/meta-data/instance-id', timeout=1)
        return response.status_code == 200
    except:
        return False

iam_config = load_iam_config()

# Detect EC2 early
on_ec2 = is_running_on_ec2()

if on_ec2:
    # On EC2: Remove AWS_PROFILE from environment to force instance role usage
    if 'AWS_PROFILE' in os.environ:
        del os.environ['AWS_PROFILE']
    print("Running on EC2: Using instance IAM role for authentication")
else:
    # Local: Ensure AWS_PROFILE is set
    if not os.environ.get('AWS_PROFILE'):
        profile = iam_config.get('iam_role_name', '')
        if profile:
            os.environ['AWS_PROFILE'] = profile
    print(f"Local development: AWS_PROFILE set to {os.environ.get('AWS_PROFILE', 'default')}")

# Set region if not already set
if not os.environ.get('AWS_DEFAULT_REGION'):
    region = iam_config.get('default_region', 'us-east-1')
    os.environ['AWS_DEFAULT_REGION'] = region
    print(f"AWS_DEFAULT_REGION set to: {region}")

import threading
from sqlalchemy.orm import joinedload
from database import SessionLocal, Feed, Topic, Article, Category, SystemConfig
from sqlalchemy import func
from collections import Counter
from services import NewsProcessor
from scheduler import init_scheduler, rss_scheduler
from output_generators import OutputGenerator
import pytz
from datetime import datetime, date
import re

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Disable caching for development and ensure fresh content
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    response.headers['X-Content-Version'] = str(datetime.now().timestamp())
    return response

def slugify(s):
    s = str(s).lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s

app.jinja_env.filters['slugify'] = slugify

# Initialize news processor (no API key needed for AWS Bedrock)
news_processor = NewsProcessor()
output_generator = OutputGenerator()

# Initialize scheduler
init_scheduler()

@app.route('/')
def dashboard():
    db = SessionLocal()
    try:
        articles = db.query(Article).options(
            joinedload(Article.topic).joinedload(Topic.category),
            joinedload(Article.feed)
        ).order_by(Article.relevancy_score.desc(), Article.published_date.desc()).limit(200).all()
        
        categories = db.query(Category).filter(Category.active == True).all()
        
        total_articles = db.query(Article).count()
        
        latest_article = db.query(Article).order_by(Article.created_at.desc()).first()
        last_refresh = None
        if latest_article and latest_article.created_at:
            pst = pytz.timezone('US/Pacific')
            last_refresh = latest_article.created_at.replace(tzinfo=pytz.UTC).astimezone(pst)
        
        # Calculate stats from the actually fetched articles to ensure links match content
        category_names = [a.category_name for a in articles if a.category_name]
        category_stats = dict(Counter(category_names))
        
        return render_template('dashboard.html', 
                             articles=articles, 
                             categories=categories,
                             last_refresh=last_refresh,
                             category_stats=category_stats,
                             total_articles=total_articles)
    finally:
        db.close()

@app.route('/admin')
def admin():
    return redirect(url_for('admin_feeds'))

@app.route('/admin/feeds')
def admin_feeds():
    db = SessionLocal()
    try:
        feeds = db.query(Feed).all()
        return render_template('admin_feeds.html', feeds=feeds, active_tab='feeds')
    finally:
        db.close()

@app.route('/admin/topics')
def admin_topics():
    db = SessionLocal()
    try:
        topics = db.query(Topic).options(joinedload(Topic.category)).all()
        categories = db.query(Category).filter(Category.active == True).all()
        return render_template('admin_topics.html', topics=topics, categories=categories, active_tab='topics')
    finally:
        db.close()

@app.route('/admin/categories')
def admin_categories():
    db = SessionLocal()
    try:
        categories = db.query(Category).all()
        return render_template('admin_categories.html', categories=categories, active_tab='categories')
    finally:
        db.close()

@app.route('/admin/llm')
def admin_llm():
    db = SessionLocal()
    try:
        config_items = db.query(SystemConfig).all()
        config = {item.key: item.value for item in config_items}
        return render_template('admin_llm.html', config=config, active_tab='llm')
    finally:
        db.close()

@app.route('/update_llm_config', methods=['POST'])
def update_llm_config():
    db = SessionLocal()
    try:
        provider = request.form.get('llm_provider', 'bedrock_iam')
        
        # Determine which model field to use
        if provider in ['bedrock_iam', 'bedrock_api']:
            model = request.form.get('llm_model', 'anthropic.claude-3-haiku-20240307-v1:0')
        else:
            model = request.form.get('llm_model_custom', '')
        
        api_key = request.form.get('llm_api_key', '')
        api_base = request.form.get('llm_api_base', '')
        
        # Update provider
        config_item = db.query(SystemConfig).filter(SystemConfig.key == 'llm_provider').first()
        if config_item:
            config_item.value = provider
        else:
            db.add(SystemConfig(key='llm_provider', value=provider))
        
        # Update model
        config_item = db.query(SystemConfig).filter(SystemConfig.key == 'llm_model').first()
        if config_item:
            config_item.value = model
        else:
            db.add(SystemConfig(key='llm_model', value=model))
        
        # Update API key (only for non-IAM providers)
        if provider != 'bedrock_iam':
            config_item = db.query(SystemConfig).filter(SystemConfig.key == 'llm_api_key').first()
            if config_item:
                config_item.value = api_key
            else:
                db.add(SystemConfig(key='llm_api_key', value=api_key))
        
        # Update API base (only for custom providers)
        if provider == 'custom':
            config_item = db.query(SystemConfig).filter(SystemConfig.key == 'llm_api_base').first()
            if config_item:
                config_item.value = api_base
            else:
                db.add(SystemConfig(key='llm_api_base', value=api_base))
        
        db.commit()
        flash('LLM configuration updated successfully')
    finally:
        db.close()
    return redirect(url_for('admin_llm'))

@app.route('/update_processing_settings', methods=['POST'])
def update_processing_settings():
    db = SessionLocal()
    try:
        threshold = request.form.get('relevancy_threshold', '60')
        
        # Validate threshold is a number between 0 and 100
        try:
            threshold_int = int(threshold)
            if threshold_int < 0 or threshold_int > 100:
                flash('Relevancy threshold must be between 0 and 100', 'error')
                return redirect(url_for('admin_llm'))
        except ValueError:
            flash('Invalid relevancy threshold value', 'error')
            return redirect(url_for('admin_llm'))
        
        # Update threshold
        config_item = db.query(SystemConfig).filter(SystemConfig.key == 'relevancy_threshold').first()
        if config_item:
            config_item.value = threshold
        else:
            db.add(SystemConfig(key='relevancy_threshold', value=threshold))
        
        db.commit()
        flash(f'Relevancy threshold updated to {threshold}. Run "Refresh News" to apply the new filter.')
    finally:
        db.close()
    return redirect(url_for('admin_llm'))

@app.route('/test_bedrock_connection', methods=['POST'])
def test_bedrock_connection():
    import boto3
    import json
    
    try:
        data = request.json
        model_id = data.get('model_id', 'anthropic.claude-3-haiku-20240307-v1:0')
        
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1').strip()
        if not region or len(region) > 20:
            region = 'us-east-1'
        
        # Determine if we should use profile or instance role
        on_ec2_now = is_running_on_ec2()
        
        if on_ec2_now:
            # On EC2: Use instance role (no profile) - ensure AWS_PROFILE is not set
            if 'AWS_PROFILE' in os.environ:
                del os.environ['AWS_PROFILE']
            print(f"Testing Bedrock on EC2 - Using instance role, Region: '{region}'")
            session = boto3.Session()
        else:
            # Local: Use profile from YAML config
            profile_name = iam_config.get('iam_role_name', '').strip()
            print(f"Testing Bedrock locally - Profile: '{profile_name}', Region: '{region}'")
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
            else:
                session = boto3.Session()
        
        # Get caller identity first to verify credentials
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS Identity: {identity['Arn']}")
        
        bedrock_client = session.client('bedrock-runtime', region_name=region)
        
        payload = {
            "max_tokens": 100,
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": "Say 'Connection successful' if you can read this."}]
        }
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(payload).encode('utf-8')
        )
        
        response_body = json.loads(response['body'].read())
        response_text = response_body['content'][0]['text']
        
        env_info = "EC2 Instance Role" if on_ec2 else f"Profile: {os.environ.get('AWS_PROFILE', 'Default credentials')}"
        return jsonify({
            "success": True,
            "message": f"Connected successfully!\nModel: {model_id}\nIdentity: {identity['Arn']}\nResponse: {response_text[:100]}"
        })
    except Exception as e:
        error_msg = str(e)
        print(f"Bedrock connection error: {error_msg}")
        env_info = "EC2 Instance Role" if 'on_ec2' in locals() and on_ec2 else f"Profile: {os.environ.get('AWS_PROFILE', 'Not set')}"
        return jsonify({
            "success": False,
            "message": f"Connection failed: {error_msg}\n\n{env_info}\nRegion: {os.environ.get('AWS_DEFAULT_REGION', 'Not set')}"
        }), 500

@app.route('/add_feed', methods=['POST'])
def add_feed():
    name = request.form['name']
    url = request.form['url']
    access_key = request.form.get('access_key')
    
    db = SessionLocal()
    try:
        feed = Feed(name=name, url=url, access_key=access_key)
        db.add(feed)
        db.commit()
        flash('Feed added successfully')
    finally:
        db.close()
    return redirect(url_for('admin_feeds'))

@app.route('/add_topic', methods=['POST'])
def add_topic():
    name = request.form['name']
    keywords = request.form['keywords']
    category_id = request.form.get('category_id')
    
    db = SessionLocal()
    try:
        topic = Topic(name=name, keywords=keywords, category_id=category_id if category_id else None)
        db.add(topic)
        db.commit()
        flash('Topic added successfully')
    finally:
        db.close()
    return redirect(url_for('admin_topics'))

@app.route('/add_category', methods=['POST'])
def add_category():
    name = request.form['name']
    description = request.form.get('description', '')
    color = request.form.get('color', '#007bff')
    
    db = SessionLocal()
    try:
        category = Category(name=name, description=description, color=color)
        db.add(category)
        db.commit()
        flash('Category added successfully')
    finally:
        db.close()
    return redirect(url_for('admin_categories'))

@app.route('/edit_topic/<int:topic_id>', methods=['POST'])
def edit_topic(topic_id):
    name = request.form['name']
    keywords = request.form['keywords']
    category_id = request.form.get('category_id')
    
    db = SessionLocal()
    try:
        topic = db.get(Topic, topic_id)
        if topic:
            topic.name = name
            topic.keywords = keywords
            topic.category_id = category_id if category_id else None
            db.commit()
            flash('Topic updated successfully')
    finally:
        db.close()
    return redirect(url_for('admin_topics'))

@app.route('/edit_category/<int:category_id>', methods=['POST'])
def edit_category(category_id):
    name = request.form['name']
    description = request.form.get('description', '')
    color = request.form.get('color', '#007bff')
    
    db = SessionLocal()
    try:
        category = db.get(Category, category_id)
        if category:
            category.name = name
            category.description = description
            category.color = color
            db.commit()
            flash('Category updated successfully')
    finally:
        db.close()
    return redirect(url_for('admin_categories'))

@app.route('/refresh_news')
def refresh_news():
    # Immediate pre-flight check: Verify LLM connectivity before starting
    connected, message = news_processor.check_llm_connectivity()
    if not connected:
        return jsonify({"status": "error", "message": f"Cannot start refresh: {message}"}), 503
    
    def background_refresh():
        result = news_processor.process_feeds()
        print(f"Background refresh result: {result}")
    
    if not news_processor.processing:
        thread = threading.Thread(target=background_refresh)
        thread.daemon = True
        thread.start()
        return jsonify({"status": "started", "message": "News refresh started in background"})
    else:
        return jsonify({"status": "busy", "message": "Already processing"})

@app.route('/processing_status')
def processing_status():
    return jsonify({
        "processing": news_processor.processing,
        "total": news_processor.progress.get('total', 0),
        "processed": news_processor.progress.get('processed', 0),
        "saved": news_processor.progress.get('saved', 0),
        "current_article": news_processor.progress.get('current_article', '')
    })

@app.route('/stop_processing')
def stop_processing():
    if news_processor.stop_processing():
        return jsonify({"status": "success", "message": "Stop request sent. Processing will halt after current article."})
    else:
        return jsonify({"status": "error", "message": "No processing is currently running"}), 400

@app.route('/clear_all_news')
def clear_all_news():
    count = news_processor.clear_all_articles()
    return jsonify({"status": "success", "message": f"Cleared {count} articles", "count": count})

@app.route('/toggle_feed/<int:feed_id>')
def toggle_feed(feed_id):
    db = SessionLocal()
    try:
        feed = db.get(Feed, feed_id)
        if feed:
            feed.active = not feed.active
            db.commit()
    finally:
        db.close()
    return redirect(url_for('admin_feeds'))

@app.route('/toggle_topic/<int:topic_id>')
def toggle_topic(topic_id):
    db = SessionLocal()
    try:
        topic = db.get(Topic, topic_id)
        if topic:
            topic.active = not topic.active
            db.commit()
    finally:
        db.close()
    return redirect(url_for('admin_topics'))

@app.route('/toggle_category/<int:category_id>')
def toggle_category(category_id):
    db = SessionLocal()
    try:
        category = db.get(Category, category_id)
        if category:
            category.active = not category.active
            db.commit()
    finally:
        db.close()
    return redirect(url_for('admin_categories'))

@app.route('/delete_feed/<int:feed_id>')
def delete_feed(feed_id):
    db = SessionLocal()
    try:
        feed = db.get(Feed, feed_id)
        if feed:
            db.delete(feed)
            db.commit()
            flash('Feed deleted successfully')
    finally:
        db.close()
    return redirect(url_for('admin_feeds'))

@app.route('/delete_topic/<int:topic_id>')
def delete_topic(topic_id):
    db = SessionLocal()
    try:
        topic = db.get(Topic, topic_id)
        if topic:
            db.delete(topic)
            db.commit()
            flash('Topic deleted successfully')
    finally:
        db.close()
    return redirect(url_for('admin_topics'))

@app.route('/delete_category/<int:category_id>')
def delete_category(category_id):
    db = SessionLocal()
    try:
        category = db.get(Category, category_id)
        if category:
            db.delete(category)
            db.commit()
            flash('Category deleted successfully')
    finally:
        db.close()
    return redirect(url_for('admin_categories'))

@app.route('/admin/scheduler')
def admin_scheduler():
    # Force fresh data by getting next run time directly
    import time
    next_run = rss_scheduler.get_next_run_time()
    print(f"[{time.time()}] Scheduler page loaded - Next run: {next_run}")
    
    # Extract current schedule time from next_run
    current_time = "09:00"
    if next_run:
        current_time = f"{next_run.hour:02d}:{next_run.minute:02d}"
    
    return render_template('admin_scheduler.html', 
                         next_run=next_run, 
                         is_running=rss_scheduler.is_running,
                         active_tab='scheduler',
                         current_time=current_time,
                         timestamp=time.time())

@app.route('/update_schedule', methods=['POST'])
def update_schedule():
    time_str = request.form.get('time', '09:00')
    hour, minute = map(int, time_str.split(':'))
    
    print(f"Updating schedule to {hour:02d}:{minute:02d}")
    rss_scheduler.schedule_cron(minute=str(minute), hour=str(hour))
    
    # Get the updated next run time
    next_run = rss_scheduler.get_next_run_time()
    print(f"Next run time after update: {next_run}")
    
    flash(f'Schedule updated to {hour:02d}:{minute:02d} daily. Next run: {next_run.strftime("%b %d, %H:%M") if next_run else "Not scheduled"}')
    return redirect(url_for('admin_scheduler'))

@app.route('/run_scheduler_now')
def run_scheduler_now():
    print("=== Run Now button clicked ===")
    app.logger.info("Run Now button clicked")
    
    if not news_processor.processing:
        print("=== Starting RSS processing ===")
        result = news_processor.process_feeds()
        print(f"=== RSS processing result: {result} ===")
        flash(f'RSS summary completed: {result}')
    else:
        print("=== RSS processing already in progress ===")
        flash('RSS summary already in progress')
    return redirect(url_for('admin_scheduler'))

@app.route('/generate_markdown')
def generate_markdown():
    try:
        filename = output_generator.generate_markdown()
        return send_file(filename, as_attachment=True, download_name=f"rss_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    except Exception as e:
        flash(f'Error generating markdown: {e}')
        return redirect(url_for('dashboard'))

@app.route('/generate_html')
def generate_html():
    try:
        filename = output_generator.generate_html()
        return send_file(filename, as_attachment=True, download_name=f"rss_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    except Exception as e:
        flash(f'Error generating HTML: {e}')
        return redirect(url_for('dashboard'))

@app.route('/generate_date_range_report', methods=['POST'])
def generate_date_range_report():
    try:
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        format_type = request.form['format']
        
        if format_type == 'markdown':
            filename = output_generator.generate_markdown(start_date=start_date, end_date=end_date)
        else:
            filename = output_generator.generate_html(start_date=start_date, end_date=end_date)
            
        return send_file(filename, as_attachment=True, download_name=f"rss_summary_{start_date}_to_{end_date}.{format_type}")
    except Exception as e:
        flash(f'Error generating date range report: {e}')
        return redirect(url_for('admin_scheduler'))

@app.route('/update_summary/<int:article_id>', methods=['POST'])
def update_summary(article_id):
    data = request.json
    new_summary = data.get('summary')
    
    if not new_summary:
        return jsonify({"success": False, "message": "No summary provided"}), 400
        
    db = SessionLocal()
    try:
        article = db.get(Article, article_id)
        if article:
            article.summary = new_summary
            db.commit()
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Article not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        db.close()

@app.route('/get_new_articles')
def get_new_articles():
    since_id = request.args.get('since_id', 0, type=int)
    db = SessionLocal()
    try:
        new_articles = db.query(Article).options(
            joinedload(Article.feed)
        ).filter(Article.id > since_id).order_by(Article.id.asc()).limit(50).all()
        
        articles_data = []
        for article in new_articles:
            articles_data.append({
                'id': article.id,
                'title': article.title,
                'url': article.url,
                'summary': article.summary,
                'author': article.author or 'Unknown',
                'feed_name': article.feed.name if article.feed else 'Unknown',
                'published_date': article.published_date.strftime('%b %d, %Y at %H:%M'),
                'category_name': article.category_name or '',
                'category_color': article.category_color or '#6c757d',
                'relevancy_score': article.relevancy_score,
                'user_feedback': article.user_feedback
            })
        
        return jsonify({'articles': articles_data})
    finally:
        db.close()

@app.route('/rate_article/<int:article_id>', methods=['POST'])
def rate_article(article_id):
    data = request.json
    feedback = data.get('feedback')  # 1 for like, -1 for dislike, 0 for neutral
    
    if feedback not in [1, -1, 0]:
        return jsonify({"success": False, "message": "Invalid feedback value"}), 400
        
    db = SessionLocal()
    try:
        article = db.get(Article, article_id)
        if article:
            article.user_feedback = feedback
            db.commit()
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Article not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        db.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)