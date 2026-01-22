#!/usr/bin/env python3
"""Initialize default categories for RSS news feed"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Category, Topic

def init_default_categories():
    """Create default categories for Federal Reserve and 12th District focus"""
    db = SessionLocal()
    
    default_categories = [
        {"name": "Monetary Policy", "description": "Federal Reserve policy, interest rates, FOMC decisions", "color": "#1f4e79"},
        {"name": "Regional Economics", "description": "12th District economic conditions, West Coast trends", "color": "#28a745"},
        {"name": "Financial System", "description": "Banking, financial stability, credit markets", "color": "#dc3545"},
        {"name": "Technology & Payments", "description": "Fintech, digital payments, cybersecurity, AI", "color": "#007bff"},
        {"name": "Global Trade", "description": "International trade, Pacific Rim, geopolitical impacts", "color": "#6f42c1"},
        {"name": "Economic Indicators", "description": "Inflation, employment, GDP, housing market data", "color": "#17a2b8"},
        {"name": "Regulation", "description": "Banking supervision, regulatory changes, compliance", "color": "#ffc107"}
    ]
    
    try:
        for cat_data in default_categories:
            # Check if category already exists
            existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing:
                category = Category(**cat_data)
                db.add(category)
                print(f"Added category: {cat_data['name']}")
            else:
                print(f"Category already exists: {cat_data['name']}")
        
        db.commit()
        print("Default categories initialized successfully!")
        
        # Initialize topics with category mappings
        init_default_topics(db)
        
    except Exception as e:
        print(f"Error initializing categories: {e}")
        db.rollback()
    finally:
        db.close()

def init_default_topics(db):
    """Create default topics mapped to categories"""
    
    # Get categories for mapping
    categories = {cat.name: cat for cat in db.query(Category).all()}
    
    default_topics = [
        {
            "name": "Federal Reserve Policy",
            "keywords": "federal reserve, fed, fomc, jerome powell, monetary policy, interest rates, fed chair, fed governor, fed official, fed policy, fed meeting, fed minutes",
            "category": "Monetary Policy"
        },
        {
            "name": "12th District Regional",
            "keywords": "california, washington, oregon, arizona, utah, alaska, hawaii, idaho, nevada, san francisco fed, 12th district, west coast, pacific, silicon valley",
            "category": "Regional Economics"
        },
        {
            "name": "Economic Indicators",
            "keywords": "inflation, unemployment, gdp, productivity, labor market, employment, housing market, consumer spending, supply chain, logistics",
            "category": "Economic Indicators"
        },
        {
            "name": "Banking & Financial Stability",
            "keywords": "banking, financial stability, credit, liquidity, capital, stress test, commercial real estate, cre, funding markets, credit spreads",
            "category": "Financial System"
        },
        {
            "name": "Fintech & Digital Payments",
            "keywords": "fintech, digital payments, fednow, cbdc, cryptocurrency, blockchain, cyber security, cloud computing, artificial intelligence, ai risk",
            "category": "Technology & Payments"
        },
        {
            "name": "Pacific Rim Trade",
            "keywords": "china, japan, korea, asean, trade war, tariffs, supply chain, geopolitical, international trade, central bank",
            "category": "Global Trade"
        },
        {
            "name": "Banking Regulation",
            "keywords": "cfpb, fdic, occ, treasury, congress, regulation, supervision",
            "category": "Regulation"
        }
    ]
    
    for topic_data in default_topics:
        # Check if topic already exists
        existing = db.query(Topic).filter(Topic.name == topic_data["name"]).first()
        if not existing:
            category = categories.get(topic_data["category"])
            topic = Topic(
                name=topic_data["name"],
                keywords=topic_data["keywords"],
                category_id=category.id if category else None
            )
            db.add(topic)
            print(f"Added topic: {topic_data['name']} -> {topic_data['category']}")
        else:
            print(f"Topic already exists: {topic_data['name']}")
    
    db.commit()
    print("Default topics with category mappings initialized successfully!")

if __name__ == "__main__":
    init_default_categories()