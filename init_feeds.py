#!/usr/bin/env python3
"""Initialize Federal Reserve and financial news RSS feeds"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Feed

def init_default_feeds():
    """Create default RSS feeds for Federal Reserve focus"""
    db = SessionLocal()
    
    default_feeds = [
        {"name": "Federal Reserve Board", "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
        {"name": "San Francisco Fed", "url": "https://www.frbsf.org/news-and-media/press-releases/feed/"},
        {"name": "Reuters Economics", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"name": "Wall Street Journal Economics", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
        {"name": "Financial Times", "url": "https://www.ft.com/rss/home/us"},
        {"name": "Bloomberg Economics", "url": "https://feeds.bloomberg.com/markets/news.rss"},
        {"name": "MarketWatch Economy", "url": "https://feeds.marketwatch.com/marketwatch/economy/"},
        {"name": "CNBC Economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069"}
    ]
    
    try:
        for feed_data in default_feeds:
            # Check if feed already exists
            existing = db.query(Feed).filter(Feed.url == feed_data["url"]).first()
            if not existing:
                feed = Feed(**feed_data)
                db.add(feed)
                print(f"Added feed: {feed_data['name']}")
            else:
                print(f"Feed already exists: {feed_data['name']}")
        
        db.commit()
        print("Default RSS feeds initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing feeds: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_default_feeds()