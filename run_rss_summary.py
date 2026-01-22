# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import NewsProcessor
from output_generators import OutputGenerator
import time

def run_full_summary():
    try:
        print("Starting RSS Summary Process")
        
        # Initialize processors
        news_processor = NewsProcessor()
        output_generator = OutputGenerator()
        
        # Process RSS feeds
        print("Processing RSS feeds...")
        result = news_processor.process_feeds()
        print(f"Processing result: {result}")
        
        # Wait a moment for processing to complete
        time.sleep(2)
        
        # Generate outputs
        print("Generating Markdown summary...")
        md_file = output_generator.generate_markdown()
        print(f"Markdown file: {md_file}")
        
        print("Generating HTML summary...")
        html_file = output_generator.generate_html()
        print(f"HTML file: {html_file}")
        
        print("RSS Summary Complete")
        return md_file, html_file
    except Exception as e:
        print(f"Error: {e}")
        return None, None

if __name__ == "__main__":
    run_full_summary()