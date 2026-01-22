import os
from datetime import datetime, date
from database import get_db, Article, Category
from sqlalchemy import and_
from datetime import datetime
from sqlalchemy.orm import joinedload
from database import SessionLocal, Article, Category

class OutputGenerator:
    def __init__(self):
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    

    def generate_markdown(self, start_date=None, end_date=None):
        #db = get_db()
        db = SessionLocal()
        try:
            query = db.query(Article)
            
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query = query.filter(and_(
                    Article.published_date >= start_dt,
                    Article.published_date <= end_dt
                ))
            
            #articles = query.order_by(Article.published_date.desc()).all()

            
        
            articles = db.query(Article).options(joinedload(Article.feed)).order_by(Article.relevancy_score.desc(), Article.published_date.desc()).all()

            
            content = f"# RSS News Summary\n\n"
            content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            if start_date and end_date:
                content += f"Date Range: {start_date} to {end_date}\n\n"
            content += f"Total Articles: {len(articles)}\n\n"
            
            for article in articles:
                content += f"### [{article.title}]({article.url})\n\n"
                source_name = article.feed.name if article.feed else 'Unknown'
                content += f"**Source:** {source_name} | **Author:** {article.author or 'Unknown'} | **Published:** {article.published_date.strftime('%Y-%m-%d %H:%M')}\n\n"
                
                if article.summary:
                    content += f"{article.summary}\n\n"
                
                if hasattr(article, 'category_name') and article.category_name:
                    content += f"**Category:** {article.category_name} | [Read More]({article.url})\n\n"
                
                content += "---\n\n"
            
            filename = f"{self.output_dir}/rss_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return filename
        finally:
            db.close()
    

    def generate_html(self, start_date=None, end_date=None):
        #db = get_db()
        db = SessionLocal()
        try:
            query = db.query(Article)
            
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query = query.filter(and_(
                    Article.published_date >= start_dt,
                    Article.published_date <= end_dt
                ))
            
            #articles = query.order_by(Article.published_date.desc()).all()
    
            
    
            articles = db.query(Article).options(joinedload(Article.feed)).order_by(Article.relevancy_score.desc(), Article.published_date.desc()).all()

            
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RSS News Summary</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; line-height: 1.6; color: #333; background-color: #f8f9fa; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; background-color: #ffffff; box-shadow: 0 0 20px rgba(0,0,0,0.05); min-height: 100vh; }}
        .header {{ border-bottom: 2px solid #2c3e50; padding-bottom: 20px; margin-bottom: 40px; text-align: center; }}
        .header h1 {{ margin: 0; color: #2c3e50; font-size: 2.5em; }}
        .header p {{ color: #7f8c8d; margin-top: 10px; }}
        .article {{ background: #ffffff; padding: 30px; margin-bottom: 30px; border: 1px solid #e9ecef; border-radius: 8px; transition: transform 0.2s; }}
        .article:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.05); }}
        .article-title {{ font-size: 1.4em; font-weight: 600; margin: 0 0 15px 0; color: #2c3e50; }}
        .article-title a {{ color: #2c3e50; text-decoration: none; }}
        .article-title a:hover {{ color: #3498db; }}
        .meta {{ color: #95a5a6; font-size: 0.9em; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .summary {{ margin-top: 20px; font-size: 1.05em; color: #444; }}
        .summary h5 {{ color: #2c3e50; font-size: 1.1em; font-weight: 600; margin-top: 20px; margin-bottom: 10px; }}
        .summary p {{ margin-bottom: 10px; }}
        .summary blockquote {{ background: #f8f9fa; border-left: 4px solid #3498db; margin: 10px 0; padding: 15px; font-style: italic; color: #555; }}
        .summary ul {{ margin: 0; padding-left: 20px; }}
        .summary li {{ margin-bottom: 8px; }}
        .category-row {{ display: flex; justify-content: space-between; align-items: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #f1f1f1; }}
        .badge {{ padding: 6px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 500; color: white; text-transform: uppercase; letter-spacing: 0.5px; }}
        .read-more-btn {{ padding: 8px 20px; border-radius: 20px; font-size: 0.9em; color: white; text-decoration: none; border: none; transition: opacity 0.2s; }}
        .read-more-btn:hover {{ opacity: 0.9; }}
    </style>
</head>
<body>
    <div class="container">
    <div class="header">
        <h1>RSS News Summary</h1>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        {f'<p>Date Range: {start_date} to {end_date}</p>' if start_date and end_date else ''}
        <p>Total Articles: {len(articles)}</p>
    </div>
"""
            
            for article in articles:
                source_name = article.feed.name if article.feed else 'Unknown'
                html += f'    <div class="article">\n'
                html += f'        <h3 class="article-title"><a href="{article.url}" target="_blank">{article.title}</a></h3>\n'
                html += f'        <div class="meta">\n'
                html += f'            Source: {source_name} | Author: {article.author or "Unknown"} | Published: {article.published_date.strftime("%Y-%m-%d %H:%M")}\n'
                html += f'        </div>\n'
                
                if article.summary:
                    html += f'        <div class="summary">\n'
                    lines = article.summary.split('\n')
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line.startswith('**'):
                            # Header
                            text = clean_line.replace('**', '').replace(':', '')
                            html += f'            <h5>{text}</h5>\n'
                        elif clean_line.startswith('•'):
                            # Bullet point
                            text = clean_line[1:].strip()
                            html += f'            <div style="display: flex; margin-bottom: 5px;"><span style="margin-right: 10px;">•</span><span>{text}</span></div>\n'
                        elif clean_line.startswith('> "'):
                            # Quote
                            text = clean_line[2:-1].strip()
                            html += f'            <blockquote>{text}</blockquote>\n'
                        elif clean_line:
                            # Paragraph
                            html += f'            <p>{clean_line}</p>\n'
                    html += f'        </div>\n'
                
                if hasattr(article, 'category_name') and article.category_name:
                    color = getattr(article, 'category_color', '#3498db')
                    html += f'        <div class="category-row">\n'
                    html += f'            <span class="badge" style="background-color: {color};">{article.category_name}</span>\n'
                    html += f'            <a href="{article.url}" target="_blank" class="read-more-btn" style="background-color: {color};">Read More</a>\n'
                    html += f'        </div>\n'
                
                html += f'    </div>\n'
            
            html += """    </div>
</body>
</html>"""
            
            filename = f"{self.output_dir}/rss_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html)
            
            return filename
        finally:
            db.close()