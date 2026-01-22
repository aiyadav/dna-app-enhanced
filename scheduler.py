import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
import pytz
from services import NewsProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RSSScheduler:
    def __init__(self):
        executors = {'default': ThreadPoolExecutor(20)}
        self.scheduler = BackgroundScheduler(executors=executors, timezone=pytz.timezone('US/Pacific'))
        self.news_processor = NewsProcessor()
        self.is_running = False
    
    def run_rss_summary(self):
        """Execute RSS summary processing"""
        try:
            logger.info(f"Starting scheduled RSS summary at {datetime.now()}")
            result = self.news_processor.process_feeds()
            logger.info(f"Scheduled RSS summary completed: {result}")
        except Exception as e:
            logger.error(f"Error in scheduled RSS summary: {e}")
    
    def schedule_cron(self, minute='0', hour='9', day='*', month='*', day_of_week='*'):
        """Schedule RSS summary using cron-like syntax"""
        self.scheduler.add_job(
            func=self.run_rss_summary,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            ),
            id='rss_summary_cron',
            name='RSS Summary Cron Job',
            replace_existing=True
        )
        logger.info(f"Scheduled RSS summary with cron: {minute} {hour} {day} {month} {day_of_week}")
    
    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("RSS Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("RSS Scheduler stopped")
    
    def get_next_run_time(self):
        """Get next scheduled run time"""
        job = self.scheduler.get_job('rss_summary_cron')
        return job.next_run_time if job else None
    
    def run_once_now(self):
        """Run RSS summary immediately (one-time execution)"""
        logger.info("Running RSS summary once (immediate execution)")
        self.run_rss_summary()

# Global scheduler instance
rss_scheduler = RSSScheduler()

def init_scheduler():
    """Initialize scheduler with default settings"""
    # Default cron schedule: daily at 9 AM PT
    minute = os.getenv('RSS_SCHEDULE_MINUTE', '0')
    hour = os.getenv('RSS_SCHEDULE_HOUR', '9')
    day = os.getenv('RSS_SCHEDULE_DAY', '*')
    month = os.getenv('RSS_SCHEDULE_MONTH', '*')
    day_of_week = os.getenv('RSS_SCHEDULE_DOW', '*')
    
    rss_scheduler.schedule_cron(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)
    rss_scheduler.start()
    
    logger.info(f"Scheduler initialized with cron: {minute} {hour} {day} {month} {day_of_week} PT")
    return rss_scheduler