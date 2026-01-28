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
        
        self.bedrock_client = None
        self.aws_available = False
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"
        
        try:
            # Get model configuration from database
            from database import SessionLocal, SystemConfig
            import os
            
            db = SessionLocal()
            try:
                model_config = db.query(SystemConfig).filter(SystemConfig.key == 'llm_model').first()
                if model_config:
                    self.model_id = model_config.value
            finally:
                db.close()
            
            # Determine if we should use profile or instance role
            on_ec2 = is_running_on_ec2()
            profile_name = None
            
            if on_ec2:
                # On EC2: Use instance role (profile_name stays None)
                logger.info("AIService: Detected EC2 environment, using IAM instance role")
            else:
                # Local: Try AWS_PROFILE from env, then fall back to config
                profile_name = os.environ.get('AWS_PROFILE', '').strip() or None
                if not profile_name:
                    profile_name = IAM_CONFIG.get('iam_role_name', '').strip() or None
                if profile_name:
                    logger.info(f"AIService: Using AWS profile: {profile_name}")
                else:
                    logger.info("AIService: Using default AWS credential chain")
            
            region_name = os.environ.get('AWS_DEFAULT_REGION', IAM_CONFIG.get('default_region', 'us-east-1')).strip()
            
            from botocore.config import Config
            
            # Configure proxy settings
            proxy_config = {}
            if os.environ.get('HTTP_PROXY'):
                proxy_config['proxies'] = {
                    'http': os.environ.get('HTTP_PROXY'),
                    'https': os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
                }
            
            boto_config = Config(
                read_timeout=30,
                connect_timeout=10,
                retries={'max_attempts': 2},
                **proxy_config
            )
            
            if profile_name:
                session = boto3.Session(profile_name=profile_name)
            else:
                session = boto3.Session()
            
            self.bedrock_client = session.client('bedrock-runtime', region_name=region_name, config=boto_config)
            self.aws_available = True
            logger.info(f"AIService: AWS Bedrock initialized successfully - model: {self.model_id}, region: {region_name}")
        except Exception as e:
            logger.error(f"AIService: Failed to initialize AWS Bedrock: {e}", exc_info=True)
            self.bedrock_client = None
            self.aws_available = False
    
    def analyze_article(self, title, author, content, url, categories, topics=None, stop_check=None):
        categories_list = [cat.name for cat in categories]
        categories_text = ", ".join(categories_list)
        
        # Build relevancy criteria from topics if provided
        relevancy_section = ""
        logger.info("="*80)
        logger.info("KEYWORD & RELEVANCE ANALYSIS LOG")
        logger.info("="*80)
        logger.info(f"Article Title: {title}")
        logger.info(f"Article URL: {url}")
        logger.info(f"Content Length: {len(content)} characters (using first 2500 for analysis)")
        logger.info(f"Available Categories: {categories_list}")
        
        if topics:
            logger.info(f"\nActive Topics Count: {len(topics)}")
            logger.info("\nKEYWORDS BEING USED FOR RELEVANCE:")
            for topic in topics:
                logger.info(f"  Topic: '{topic.name}'")
                logger.info(f"    Keywords: {topic.keywords}")
            
            relevancy_section = "\n\nRELEVANCY CRITERIA:\nThe article should be related to these topics and keywords:\n"
            for topic in topics:
                relevancy_section += f"- {topic.name}: {topic.keywords}\n"
            relevancy_section += "\nScore the relevancy (0-100) based on how well the article relates to these topics. Score 75+ if clearly relevant, 50-74 if somewhat related, below 50 if not related."
        else:
            logger.info("\nNo topics configured - relevance will be based on categories only")
        
        logger.info("\nRELEVANCE CALCULATION METHOD:")
        logger.info("  - Type: AI-driven contextual analysis (NOT simple keyword matching)")
        logger.info("  - Model: AWS Bedrock Claude 3 Haiku")
        logger.info("  - Process: AI performs semantic analysis of article content against topic keywords")
        logger.info("  - Scoring: AI assigns 0-100 score based on contextual relevance")
        
        prompt = f"""Analyze this article and create an executive briefing.

Title: {title}
Author: {author}
Content: {content[:2500]}{relevancy_section}

Create a unified list of 4-5 bulleted statements merging key facts and quotes.
Avoid redundant information.

Match against Categories: {categories_text}

IMPORTANT RULES:
1. Return ONLY valid JSON, no explanatory text before or after
2. The "category" field MUST be EXACTLY one of these values: {categories_text}
3. Do NOT create new category names or use variations
4. If the article doesn't match any category well, use an empty string ""
5. For "author" field: Extract the author name from the content if the provided Author is empty/unknown. Look for bylines like "By [Name]", "Written by [Name]", author attributions, or reporter names. If no author can be found, return empty string ""

Return JSON with:
- "bullets": list of summary bullets (empty array if not relevant)
- "category": MUST be exactly one of [{categories_text}] or empty string
- "relevancy_score": integer (0-100) representing how relevant the article is to the topics and categories
- "author": extracted author name from content (if Author field is empty/unknown), or empty string "" if no author found

Return ONLY this JSON format:
{{"bullets": ["Bullet 1", "Bullet 2", ...], "category": "category_name", "relevancy_score": 85, "author": "Author Name"}}"""
        
        logger.info("\nPROMPT CONTEXT SENT TO AI:")
        logger.info(f"  Prompt length: {len(prompt)} characters")
        logger.info(f"  Article content included: {min(len(content), 2500)} characters")
        logger.info(f"  Topics/Keywords included: {'Yes' if topics else 'No'}")
        
        try:
            payload = {
                "max_tokens": 1200,
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}]
            }
            
            logger.info("\nSending request to AWS Bedrock...")
            
            # Check if stop was requested before making the call
            if stop_check and stop_check():
                logger.info("Stop requested before Bedrock call")
                return {"summary": "Analysis stopped", "quotes": "", "category": "", "relevancy_score": 0, "author": ""}
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(payload).encode('utf-8')
            )
            response_body = json.loads(response['body'].read())
            response_text = response_body['content'][0]['text']
            
            logger.info("\nAI RESPONSE RECEIVED:")
            logger.info(f"  Raw response: {response_text}")
            
            # Extract JSON from response (handle cases where AI adds explanatory text)
            json_str = response_text.strip()
            # Try to find JSON object in the response
            if '{' in json_str:
                start_idx = json_str.find('{')
                end_idx = json_str.rfind('}') + 1
                json_str = json_str[start_idx:end_idx]
            
            # Robust JSON parsing with error recovery
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}. Attempting to fix common issues...")
                # Try to fix common JSON issues
                json_str = json_str.replace("'", '"')  # Replace single quotes
                json_str = json_str.replace('\n', ' ')  # Remove newlines
                json_str = json_str.replace('  ', ' ')  # Remove double spaces
                try:
                    result = json.loads(json_str)
                    logger.info("JSON parsing recovered after cleanup")
                except:
                    logger.error(f"Failed to parse JSON even after cleanup: {json_str[:200]}")
                    return {"summary": "Analysis failed", "quotes": "", "category": "", "relevancy_score": 0, "author": ""}
            
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

                logger.info("\nRELEVANCE CALCULATION RESULTS:")
                logger.info(f"  Assigned Category: '{result.get('category', '')}'")
                logger.info(f"  Relevancy Score: {result.get('relevancy_score', 0)}/100")
                logger.info(f"  Extracted Author: '{result.get('author', '')}'")
                logger.info(f"  Summary Bullets: {len(cleaned_bullets)} items")
                logger.info("\nSCORING CONTEXT:")
                logger.info("  - Score is AI-determined based on semantic understanding")
                logger.info("  - AI considers: topic keywords, article content, context, and meaning")
                logger.info("  - NOT based on simple keyword frequency or exact matching")
                logger.info("="*80)

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
        self.stop_requested = False
        self.progress = {
            'total': 0,
            'processed': 0,
            'saved': 0,
            'current_article': ''
        }
    
    def check_llm_connectivity(self):
        """Quick test to verify LLM is accessible before processing"""
        try:
            if not self.ai_service.aws_available or not self.ai_service.bedrock_client:
                return False, "AWS Bedrock is not configured or unavailable"
            
            # Reuse existing client for faster check
            test_payload = {
                "max_tokens": 5,
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": "hi"}]
            }
            response = self.ai_service.bedrock_client.invoke_model(
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
    
    def stop_processing(self):
        """Request to stop the current processing"""
        if self.processing:
            self.stop_requested = True
            self.processing = False
            logger.info("Stop processing requested by user")
            return True
        return False
    
    def process_feeds(self):
        if self.processing:
            return "Already processing"
        
        self.processing = True
        self.stop_requested = False
        self.progress = {'total': 0, 'processed': 0, 'saved': 0, 'current_article': ''}
        try:
            self.cleanup_old_articles()
            
            db = get_db()
            feeds = db.query(Feed).filter(Feed.active == True).all()
            categories = db.query(Category).filter(Category.active == True).all()
            topics = db.query(Topic).filter(Topic.active == True).all()
            
            # Get relevancy threshold from database
            from database import SystemConfig
            threshold_config = db.query(SystemConfig).filter(SystemConfig.key == 'relevancy_threshold').first()
            min_relevancy_score = int(threshold_config.value) if threshold_config else 60
            print(f"Using relevancy threshold: {min_relevancy_score}")
            
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
                # Check if stop was requested
                if self.stop_requested:
                    print(f"\n=== Processing stopped by user ===")
                    print(f"Processed {processed_count} articles before stopping")
                    return f"Processing stopped by user. Saved {processed_count} articles."
                
                print(f"\nProcessing feed: {feed.name}")
                entries = self.rss_fetcher.fetch_feed(feed.url, feed.access_key)
                print(f"Found {len(entries)} entries in feed")
                
                for entry in entries:
                    # Check if stop was requested
                    if self.stop_requested:
                        print(f"\n=== Processing stopped by user ===")
                        print(f"Processed {processed_count} articles before stopping")
                        return f"Processing stopped by user. Saved {processed_count} articles."
                    
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
                        
                        # Always increment processed count for progress bar
                        self.progress['processed'] += 1
                        self.progress['current_article'] = entry_title[:60]
                        
                        if published_date < cutoff_time:
                            print(f"Skipping: {entry_title[:60]} (older than 24 hours)")
                            continue
                        
                        if not entry_link or entry_link in processed_urls:
                            print(f"Skipping: {entry_title[:60]} (duplicate or no link)")
                            continue
                        
                        processed_urls.add(entry_link)
                        print(f"Processing: {entry_title[:60]}...")
                        
                        existing = db.query(Article).filter(Article.url == entry_link).first()
                        if existing:
                            print(f"  -> Already exists, skipping")
                            continue
                        
                        content = self.rss_fetcher.get_article_content(entry)
                        if not content:
                            continue
                        
                        # Check if stop was requested before AI analysis
                        if self.stop_requested:
                            print(f"\n=== Processing stopped by user ===")
                            print(f"Processed {processed_count} articles before stopping")
                            return f"Processing stopped by user. Saved {processed_count} articles."
                        
                        print(f"  -> Analyzing with AI...")
                        print(f"  -> Available categories: {[c.name for c in categories]}")
                        print(f"  -> Using topics: {[t.name for t in topics]}")
                        if topics:
                            print(f"  -> Keywords for relevance:")
                            for t in topics:
                                print(f"       {t.name}: {t.keywords}")
                        time.sleep(2)
                        analysis = self.ai_service.analyze_article(entry_title, entry_author, content, entry_link, categories, topics, stop_check=lambda: self.stop_requested)
                        
                        # Skip articles with failed analysis
                        if not analysis or analysis.get("summary", "") == "Analysis failed":
                            print(f"  -> Skipping due to AI analysis failure")
                            continue
                        
                        category_name = analysis.get("category", "")
                        relevancy_score = int(analysis.get("relevancy_score", 0))
                        ai_author = analysis.get("author", "")
                        
                        print(f"  -> AI Analysis Results:")
                        print(f"     - Category: '{category_name}'")
                        print(f"     - Relevancy Score: {relevancy_score}")
                        print(f"     - Author: '{ai_author}'")
                        
                        # Use AI extracted author if original was missing/unknown and AI found one
                        final_author = entry_author.strip() if entry_author else ""
                        ai_author_clean = ai_author.strip() if ai_author else ""
                        
                        # Check if RSS author is valid
                        rss_author_valid = final_author and final_author.lower() not in ['unknown', 'none', 'n/a', '']
                        # Check if AI author is valid
                        ai_author_valid = ai_author_clean and ai_author_clean.lower() not in ['unknown', 'none', 'n/a', '', 'not available', 'not specified']
                        
                        if rss_author_valid:
                            # RSS has valid author, use it
                            print(f"  -> Using RSS feed author: {final_author}")
                        elif ai_author_valid:
                            # RSS has no valid author, but AI found one
                            final_author = ai_author_clean
                            print(f"  -> Using AI-extracted author: {final_author}")
                        else:
                            # Neither RSS nor AI has valid author
                            final_author = "Unknown"
                            print(f"  -> No valid author found (RSS: '{entry_author}', AI: '{ai_author}'), using: Unknown")

                        # Filter articles with low relevancy score
                        if relevancy_score < min_relevancy_score:
                            print(f"  -> Skipping: Low relevancy score ({relevancy_score} < {min_relevancy_score})")
                            continue
                        
                        # Case-insensitive category matching with strict validation
                        if not category_name or category_name.strip() == "":
                            print(f"  -> Skipping: No category assigned by AI")
                            continue
                            
                        category = next((c for c in categories if c.name.lower() == category_name.lower()), None)
                        
                        if not category:
                            print(f"  -> WARNING: AI returned invalid category '{category_name}'")
                            print(f"  -> Valid categories are: {[c.name for c in categories]}")
                            print(f"  -> Skipping article due to invalid category")
                            continue
                        
                        final_category_name = category.name
                        final_category_color = category.color
                        print(f"  -> Matched to DB category: {final_category_name} (color: {final_category_color})")
                            
                        article = Article(
                            title=entry_title,
                            url=entry_link,
                            content=content,
                            summary=analysis.get("summary", ""),
                            author=final_author,
                            feed_id=feed.id,
                            published_date=published_date,
                            category_name=final_category_name,
                            category_color=final_category_color,
                            relevancy_score=relevancy_score
                        )
                        
                        db.add(article)
                        db.commit()
                        db.refresh(article)  # Refresh to get the ID assigned by database
                        processed_count += 1
                        self.progress['saved'] += 1
                        print(f"  -> [SAVED] Article ID {article.id} saved! Category: {category.name} ({processed_count} total)")
                    
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