import sys
try:
    import cgi
except ImportError:
    import html
    class cgi:
        @staticmethod
        def escape(s, quote=False):
            return html.escape(s, quote=quote)
    sys.modules['cgi'] = cgi

import feedparser
import requests
from bs4 import BeautifulSoup
import boto3
import json
import time
import logging
from datetime import datetime, timedelta
from database import get_db, Article, Feed, Topic, Category
import yaml
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load IAM role configuration from YAML
def load_iam_config():
    config_path = os.path.join(os.path.dirname(__file__), 'ec2_service_role.yml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config['aws']
    except Exception as e:
        logger.warning(f"Could not load ec2_service_role.yml: {e}. Using defaults.")
        return {'iam_role_name': 'devops-genai-dna-dev-engineer-role', 'default_region': 'us-east-1', 'use_instance_role': 'auto'}

def is_running_on_ec2():
    """Detect if running on EC2 by checking instance metadata and IAM role"""
    # Check explicit environment variable first
    env_override = os.environ.get('USE_EC2_ROLE', '').lower()
    if env_override == 'true':
        return True
    elif env_override == 'false':
        return False
    
    try:
        # Check if we can access EC2 metadata service
        response = requests.get(
            'http://169.254.169.254/latest/meta-data/instance-id',
            timeout=1
        )
        if response.status_code == 200:
            return True
    except:
        pass
    
    # Fallback: Check if IAM role credentials are available
    try:
        import boto3
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials:
            # Check if credentials are from EC2 instance role
            # Instance role credentials have specific provider names
            provider = credentials.method
            if provider in ['iam-role', 'container-role']:
                return True
    except:
        pass
    
    return False

IAM_CONFIG = load_iam_config()

class RSSFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_feed(self, feed_url, access_key=None):
        try:
            request_headers = self.headers.copy()
            if access_key:
                request_headers['Authorization'] = access_key
                # Also try adding as API-Key header just in case
                request_headers['API-Key'] = access_key
                
            # Use requests to fetch first if we have custom headers
            if access_key:
                response = requests.get(feed_url, headers=request_headers)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
            else:
                feed = feedparser.parse(feed_url)
            return feed.entries
        except Exception as e:
            logger.error(f"Error fetching feed {feed_url}: {e}")
            return []
    
    def get_article_content(self, entry):
        return getattr(entry, 'description', '') or getattr(entry, 'summary', '')

class AIService:
    def __init__(self, api_key=None):
        # Load environment variables to ensure they're available
        from dotenv import load_dotenv
        load_dotenv()
        
        try:
            # Get model configuration from database
            from database import SessionLocal, SystemConfig
            import os
            
            db = SessionLocal()
            try:
                model_config = db.query(SystemConfig).filter(SystemConfig.key == 'llm_model').first()
                self.model_id = model_config.value if model_config else "anthropic.claude-3-haiku-20240307-v1:0"
            finally:
                db.close()
            
            # Determine if we should use profile or instance role
            profile_name = None
            use_instance_role = IAM_CONFIG.get('use_instance_role', 'auto')
            
            if use_instance_role == 'auto':
                on_ec2 = is_running_on_ec2()
            else:
                on_ec2 = use_instance_role in [True, 'true', 'True']
            
            if on_ec2:
                # On EC2: Use instance role (profile_name stays None)
                logger.info("Detected EC2 environment, using IAM instance role")
            else:
                # Local: Try AWS_PROFILE from env, then fall back to config
                profile_name = os.environ.get('AWS_PROFILE', '').strip() or None
                if not profile_name:
                    profile_name = IAM_CONFIG.get('iam_role_name', '').strip() or None
                if profile_name:
                    logger.info(f"Using AWS profile: {profile_name}")
                else:
                    logger.info("Using default AWS credential chain")
            
            region_name = os.environ.get('AWS_DEFAULT_REGION', IAM_CONFIG.get('default_region', 'us-east-1')).strip()
            
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
            else:
                session = boto3.Session()
            self.bedrock_client = session.client('bedrock-runtime', region_name=region_name)
            self.aws_available = True
            logger.info(f"AWS Bedrock initialized with model: {self.model_id}, profile: {profile_name}, region: {region_name}")
        except Exception as e:
            logger.warning(f"AWS Bedrock not available: {e}")
            self.bedrock_client = None
            self.aws_available = False
            self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    def analyze_article(self, title, author, content, url, categories):
        categories_list = [cat.name for cat in categories]
        categories_text = ", ".join(categories_list)
        
        prompt = f"""Create an executive briefing from this article.
Merge the key facts, direct quotes, and overall summary into a unified list of 4-5 bulleted statements.
Include direct quotes as is inside the bullets where relevant.
Avoid redundant information.
Also extract the author name if available in the text.

Title: {title}
Author: {author}
Content: {content[:2500]}

Match against Categories: {categories_text}

Return JSON with:
- "bullets": list of summary bullets
- "category": the single best matching category name from the list provided.
- "relevancy_score": integer (0-100) representing how relevant the article is to that category.
- "author": extracted author name (use provided Author if valid, otherwise try to extract from Content)

Return JSON:
{{"bullets": ["Bullet 1", "Bullet 2", ...], "category": "category_name", "relevancy_score": 85, "author": "Author Name"}}"""
        
        try:
            payload = {
                "max_tokens": 1200,
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}]
            }
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(payload).encode('utf-8')
            )
            response_body = json.loads(response['body'].read())
            response_text = response_body['content'][0]['text']
            result = json.loads(response_text)
            
            if isinstance(result, dict):
                bullets = result.get("bullets", [])
                if isinstance(bullets, list):
                    # Clean up redundant bullets and remove duplicates
                    cleaned_bullets = []
                    seen_content = set()
                    for b in bullets:
                        # Remove existing bullet char if present
                        clean_b = b.strip()
                        if clean_b.startswith('•'):
                            clean_b = clean_b[1:].strip()
                        elif clean_b.startswith('-'):
                            clean_b = clean_b[1:].strip()
                        
                        # Check for duplicates using normalized text
                        normalized = clean_b.lower().replace('"', '').replace("'", '').strip()
                        if normalized and normalized not in seen_content:
                            seen_content.add(normalized)
                            cleaned_bullets.append(clean_b)
                    
                    full_summary = "\n".join([f"• {b}" for b in cleaned_bullets])
                else:
                    full_summary = str(bullets)

                return {
                    "summary": full_summary,
                    "quotes": "", 
                    "category": result.get("category", ""),
                    "relevancy_score": result.get("relevancy_score", 0),
                    "author": result.get("author", "")
                }
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
        return {"summary": "Analysis failed", "quotes": "", "category": "", "relevancy_score": 0}

class NewsProcessor:
    def __init__(self, api_key=None):
        self.rss_fetcher = RSSFetcher()
        self.ai_service = AIService(api_key)
        self.processing = False
        self.progress = {
            'total': 0,
            'processed': 0,
            'saved': 0,
            'current_article': ''
        }
    
    def check_llm_connectivity(self):
        """Quick test to verify LLM is accessible before processing"""
        try:
            if not self.ai_service.aws_available:
                return False, "AWS Bedrock is not configured or unavailable"
            
            # Determine if we should use profile or instance role
            profile_name = None
            use_instance_role = IAM_CONFIG.get('use_instance_role', 'auto')
            
            if use_instance_role == 'auto':
                on_ec2 = is_running_on_ec2()
            else:
                on_ec2 = use_instance_role in [True, 'true', 'True']
            
            if on_ec2:
                # On EC2: Use instance role (profile_name stays None)
                pass
            else:
                # Local: Try AWS_PROFILE from env, then fall back to config
                profile_name = os.environ.get('AWS_PROFILE', '').strip() or None
                if not profile_name:
                    profile_name = IAM_CONFIG.get('iam_role_name', '').strip() or None
            
            region_name = os.environ.get('AWS_DEFAULT_REGION', IAM_CONFIG.get('default_region', 'us-east-1')).strip()
            
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
            else:
                session = boto3.Session()
            
            bedrock_client = session.client('bedrock-runtime', region_name=region_name)
            
            # Send minimal test prompt
            test_payload = {
                "max_tokens": 5,
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": "hi"}]
            }
            response = bedrock_client.invoke_model(
                modelId=self.ai_service.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(test_payload).encode('utf-8')
            )
            return True, "LLM connected successfully"
        except Exception as e:
            error_msg = str(e)
            if "credentials" in error_msg.lower():
                return False, "AWS credentials not configured or invalid"
            elif "expired" in error_msg.lower():
                return False, "AWS credentials have expired. Please refresh your credentials."
            elif "region" in error_msg.lower():
                return False, "AWS region not configured properly"
            elif "access denied" in error_msg.lower():
                return False, "Access denied to AWS Bedrock service"
            else:
                return False, f"LLM connection failed: {error_msg}"
    
    def cleanup_old_articles(self):
        db = get_db()
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            old_articles = db.query(Article).filter(Article.created_at < cutoff_time).all()
            count = len(old_articles)
            for article in old_articles:
                db.delete(article)
            db.commit()
            if count > 0:
                print(f"Cleaned up {count} articles older than 24 hours")
            return count
        finally:
            db.close()
    
    def clear_all_articles(self):
        db = get_db()
        try:
            count = db.query(Article).count()
            db.query(Article).delete()
            db.commit()
            print(f"Cleared all {count} articles from database")
            return count
        finally:
            db.close()
    
    def process_feeds(self):
        if self.processing:
            return "Already processing"
        
        self.processing = True
        self.progress = {'total': 0, 'processed': 0, 'saved': 0, 'current_article': ''}
        try:
            self.cleanup_old_articles()
            
            db = get_db()
            feeds = db.query(Feed).filter(Feed.active == True).all()
            categories = db.query(Category).filter(Category.active == True).all()
            
            if not categories:
                return "No active categories found"
            
            cutoff_time = datetime.now() - timedelta(hours=24)
            processed_count = 0
            total_entries = 0
            
            print(f"\n=== Starting news processing ===")
            print(f"Active feeds: {len(feeds)}")
            print(f"Active categories: {len(categories)}")
            
            # Check LLM connectivity BEFORE processing articles
            print(f"\nChecking LLM connectivity...")
            connected, message = self.check_llm_connectivity()
            if not connected:
                error_msg = f"LLM connectivity check failed: {message}"
                logger.error(error_msg)
                print(f"ERROR: {error_msg}")
                return error_msg
            print(f"[OK] LLM connected successfully")
            
            processed_urls = set()
            
            # Count total entries first
            for feed in feeds:
                entries = self.rss_fetcher.fetch_feed(feed.url, feed.access_key)
                total_entries += len(entries)
            
            self.progress['total'] = total_entries
            
            for feed in feeds:
                print(f"\nProcessing feed: {feed.name}")
                entries = self.rss_fetcher.fetch_feed(feed.url, feed.access_key)
                print(f"Found {len(entries)} entries in feed")
                
                for entry in entries:
                    try:
                        entry_link = getattr(entry, 'link', '')
                        entry_title = getattr(entry, 'title', 'Untitled')
                        
                        # Type-safe author extraction
                        entry_author = ''
                        if hasattr(entry, 'author'):
                            entry_author = str(entry.author)
                        elif 'authors' in entry and entry.authors:
                            entry_author = str(entry.authors[0].get('name', ''))
                        elif 'dc_creator' in entry:
                            entry_author = str(entry.dc_creator)
                        elif 'author_detail' in entry and hasattr(entry.author_detail, 'name'):
                            entry_author = str(entry.author_detail.name)
                        
                        published_date = datetime.now()
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            try:
                                published_date = datetime(*entry.published_parsed[:6])
                            except:
                                pass
                        
                        if published_date < cutoff_time:
                            continue
                        
                        if not entry_link or entry_link in processed_urls:
                            continue
                        
                        processed_urls.add(entry_link)
                        self.progress['processed'] += 1
                        self.progress['current_article'] = entry_title[:60]
                        print(f"Processing: {entry_title[:60]}...")
                        
                        existing = db.query(Article).filter(Article.url == entry_link).first()
                        if existing:
                            print(f"  -> Already exists, skipping")
                            continue
                        
                        content = self.rss_fetcher.get_article_content(entry)
                        if not content:
                            continue
                        
                        print(f"  -> Analyzing with AI...")
                        time.sleep(1)
                        analysis = self.ai_service.analyze_article(entry_title, entry_author, content, entry_link, categories)
                        
                        # Skip articles with failed analysis
                        if analysis.get("summary", "") == "Analysis failed":
                            print(f"  -> Skipping due to AI analysis failure")
                            continue
                        
                        category_name = analysis.get("category", "")
                        relevancy_score = int(analysis.get("relevancy_score", 0))
                        ai_author = analysis.get("author", "")
                        
                        # Use AI extracted author if original was missing/unknown and AI found one
                        if (not entry_author or entry_author.lower() in ['unknown', '']) and ai_author and ai_author.lower() != "unknown":
                            entry_author = ai_author
                            print(f"  -> Extracted author via AI: {entry_author}")
                        
                        print(f"  -> Category: {category_name} (Score: {relevancy_score})")

                        # Filter articles with low relevancy score
                        if relevancy_score < 75:
                            print(f"  -> Skipping: Low relevancy score ({relevancy_score} < 75)")
                            # We can choose to either not save it, or save it as uncategorized.
                            # "filter articles that are not relevant to the categories" implies discarding or not mapping.
                            # User said: "do not map an article to any category if it's relevancy score is less than 75%."
                            # Usually this means we can leave category_name empty if we still want it, 
                            # or if "filter articles" means exclude, we skip.
                            # Given "filter articles" is a strong term, I will skip saving them effectively acting as a filter.
                            # However, if it's general news, maybe we want it? 
                            # Let's interpret strict filtering: If not relevant enough to ANY category, discard.
                            # Wait, the prompt asks for "the single best matching category". 
                            # If even the best matching is < 75, then it's not relevant to our interests defined by categories.
                            continue
                        
                        category = next((c for c in categories if c.name == category_name), None)
                        
                        # If category name returned by AI doesn't match our DB (hallucination), treat as uncategorized or skip?
                        # If we have a high score but invalid category name, it's weird.
                        # Using default behavior: if category not found but score is high, maybe fallback?
                        # But simpler is to rely on AI returning valid category from the list we gave.
                        
                        final_category_name = category.name if category else None
                        final_category_color = category.color if category else None
                            
                        article = Article(
                            title=entry_title,
                            url=entry_link,
                            content=content,
                            summary=analysis.get("summary", ""),
                            author=entry_author,
                            feed_id=feed.id,
                            published_date=published_date,
                            category_name=final_category_name,
                            category_color=final_category_color,
                            relevancy_score=relevancy_score
                        )
                        
                        db.add(article)
                        db.commit()
                        processed_count += 1
                        self.progress['saved'] += 1
                        print(f"  -> [SAVED] Article saved! Category: {category.name} ({processed_count} total)")
                    
                    except Exception as entry_error:
                        logger.error(f"Error processing entry: {entry_error}")
                        continue
            
            db.close()
            print(f"\n=== Processing complete ===")
            print(f"Total entries processed: {total_entries}")
            print(f"Relevant articles saved: {processed_count}")
            return f"Processed {processed_count} relevant articles from {total_entries} entries"
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return f"Error: {e}"
        finally:
            self.processing = False