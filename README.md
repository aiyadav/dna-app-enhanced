# Daily News AI Assistant

A locally deployable news aggregation system that uses AWS Bedrock Claude AI to analyze and summarize articles based on user-defined topics with per-topic relevancy scoring.

## Features

- **RSS Feed Management**: Add and manage multiple RSS feeds with admin interface
- **Topic-Based Filtering**: Define topics with keywords for AI-powered relevance scoring
- **Per-Topic Analysis**: AI analyzes articles against all topics simultaneously with individual scores (0-100)
- **Smart Content Extraction**: Automatically scrapes full articles when RSS descriptions are too short
- **AWS Bedrock Integration**: Uses Claude 3 Haiku model for fast, cost-effective analysis
- **Admin Interface**: Left navigation panel for managing feeds and topics
- **Auto-refresh Dashboard**: Real-time updates every 10 seconds
- **Automatic Cleanup**: Removes articles older than 24 hours
- **Federal Reserve Branding**: Professional UI with FRB logo integration

## Setup Instructions

### 1. AWS Credentials Setup

Configure AWS credentials for Bedrock access:

**Option A: Environment Variables**
```bash
set AWS_ACCESS_KEY_ID=your_access_key
set AWS_SECRET_ACCESS_KEY=your_secret_key
set AWS_DEFAULT_REGION=us-east-1
```

**Option B: AWS CLI**
```bash
aws configure
```

**Option C: IAM Role** (if running on EC2)
Attach IAM role with `bedrock:InvokeModel` permission

### 2. Installation

```bash
# Clone or download the project
cd DNA_awsbedrock

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file (optional)
copy .env.example .env
```

### 3. Logo Setup (Optional)

Place Federal Reserve Bank logo:
```
static/frb_sf_logo.jpg
```

### 4. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage

### 1. Add RSS Feeds
- Navigate to **Admin → RSS Feeds**
- Add feed URLs (e.g., `https://feeds.bbci.co.uk/news/rss.xml`)
- Toggle feeds active/inactive as needed

### 2. Define Topics
- Navigate to **Admin → Topics**
- Create topics with relevant keywords
- Example: Topic "Technology" with keywords "AI, machine learning, software, tech"

### 3. Process News
- Click **"Refresh News"** on dashboard
- System fetches articles, analyzes against all topics
- Articles with ANY topic score > 75% are saved
- Dashboard auto-refreshes every 10 seconds

## Technical Architecture

### AI Analysis System
- **Model**: Claude 3 Haiku via AWS Bedrock (`anthropic.claude-3-haiku-20240307-v1:0`)
- **Per-Topic Scoring**: Single AI call analyzes article against all topics
- **Selection Criteria**: Articles saved if any topic scores above 75%
- **Response Format**: JSON with summary and individual topic scores

### Database Schema
```sql
-- Feeds table
CREATE TABLE feeds (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200),
    url VARCHAR(500),
    active BOOLEAN DEFAULT TRUE
);

-- Topics table  
CREATE TABLE topics (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    keywords TEXT,
    active BOOLEAN DEFAULT TRUE
);

-- Articles table
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title VARCHAR(500),
    url VARCHAR(500) UNIQUE,
    content TEXT,
    summary TEXT,
    author VARCHAR(200),
    published_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    topic_scores TEXT,  -- JSON: {"Technology": 85, "Finance": 45}
    primary_topic VARCHAR(100)
);
```

### Content Processing Pipeline
1. **RSS Fetching**: Parse feeds for new articles
2. **Content Extraction**: Scrape full articles if description < 500 chars
3. **AI Analysis**: Single Bedrock call for all topics
4. **Scoring**: Individual relevancy scores (0-100) per topic
5. **Storage**: Save articles scoring > 75% on any topic
6. **Cleanup**: Auto-remove articles > 24 hours old

### Rate Limiting & Performance
- **No rate limiting needed**: AWS Bedrock handles scaling automatically
- **Content limits**: Articles truncated to 3000 chars for analysis
- **Efficient processing**: Single AI call per article for all topics
- **Background processing**: Non-blocking news updates

## File Structure

```
DNA_awsbedrock/
├── app.py                 # Flask routes and application logic
├── database.py           # SQLAlchemy models (Feed, Topic, Article)
├── services.py           # RSS fetching, AI analysis, news processing
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
├── README.md            # This file
├── static/
│   └── frb_sf_logo.jpg  # Federal Reserve Bank logo
└── templates/
    ├── base.html        # Main layout with navigation
    ├── dashboard.html   # Article display with auto-refresh
    ├── admin_base.html  # Admin layout with left navigation
    ├── admin_feeds.html # RSS feed management
    └── admin_topics.html # Topic management
```

## Dependencies

```txt
Flask==3.0.0
SQLAlchemy==2.0.23
requests==2.31.0
feedparser==6.0.10
beautifulsoup4==4.12.2
boto3==1.34.0
python-dotenv==1.0.0
```

## Usage Examples

### Adding RSS Feeds
```python
# Common news feeds to try:
BBC News: https://feeds.bbci.co.uk/news/rss.xml
Reuters: https://feeds.reuters.com/reuters/topNews
CNN: http://rss.cnn.com/rss/edition.rss
Federal Reserve: https://www.federalreserve.gov/feeds/press_all.xml
```

### Topic Configuration
```python
# Example topics:
Technology: "AI, artificial intelligence, machine learning, software, tech, digital"
Finance: "banking, federal reserve, interest rates, monetary policy, inflation"
Economics: "GDP, unemployment, economic growth, recession, market"
```

### API Response Format
```json
{
  "summary": "• Federal Reserve announces new monetary policy\n• Interest rates remain unchanged\n• Economic outlook remains stable",
  "topic_scores": {
    "Finance": 95,
    "Economics": 78,
    "Technology": 12
  }
}
```

## Troubleshooting

### AWS Bedrock Issues
- **403 Forbidden**: Check IAM permissions for `bedrock:InvokeModel`
- **Model not found**: Ensure Claude 3 Haiku is available in your region
- **Throttling**: AWS Bedrock handles rate limiting automatically

### No Articles Appearing
1. Verify RSS feeds are active and accessible
2. Check topic keywords are relevant to feed content
3. Ensure AWS credentials are properly configured
4. Review console logs for processing errors

### Database Issues
- Delete `news.db` file to reset database
- Check SQLite file permissions
- Verify database schema with `python -c "from database import init_db; init_db()"`

### Performance Optimization
- Limit number of active feeds to reduce processing time
- Use specific keywords in topics for better relevancy
- Monitor AWS Bedrock costs in CloudWatch

## AWS Bedrock Integration Notes

### Model Configuration
- **Model ID**: `anthropic.claude-3-haiku-20240307-v1:0`
- **Provider Version**: `bedrock-2023-05-31` (configurable via `ANTHROPIC_PROVIDER_VERSION`)
- **Region**: `us-east-1` (configurable in `services.py`)

### Request Format
```python
payload = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 500,
    "messages": [{"role": "user", "content": prompt}]
}
```

### Local Testing
Test Bedrock payload without AWS calls:
```bash
.\.venv\Scripts\activate
python tests/test_bedrock_payload.py
```

### Cost Considerations
- Claude 3 Haiku: ~$0.25 per 1M input tokens
- Typical article analysis: ~500-1000 tokens
- Estimated cost: $0.0005-0.001 per article

## License

This project is for internal use and demonstration purposes.