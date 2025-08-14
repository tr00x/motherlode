import asyncio
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from config import Config, TRANSLATIONS
from database import db
from blockchain import blockchain

class TaskScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """Start the scheduler"""
        # Daily report at 21:00
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=21, minute=0),
            id='daily_report'
        )
        
        # Process payouts every 10 minutes
        self.scheduler.add_job(
            self.process_payouts,
            CronTrigger(minute='*/10'),
            id='process_payouts'
        )
        
        # Generate proxy wallets every hour
        self.scheduler.add_job(
            self.generate_proxy_wallets,
            CronTrigger(minute=0),
            id='generate_wallets'
        )
        
        self.scheduler.start()
        print("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        print("Scheduler stopped")
    
    async def send_daily_report(self):
        """Send daily report to admin"""
        try:
            # Get admin user data
            admin_data = await db.get_user(Config.ADMIN_ID)
            lang = admin_data.get('language_code', 'ru') if admin_data else 'ru'
            t = TRANSLATIONS[lang]
            
            # Get today's stats
            today = datetime.now().strftime('%Y-%m-%d')
            stats = await db.get_daily_stats(today)
            
            report_text = t['report_text'].format(
                date=datetime.now().strftime('%d.%m.%Y'),
                new_investors=stats['new_investors'],
                total_investments=stats['total_investments'],
                total_payouts=stats['total_payouts'],
                profit=stats['profit']
            )
            
            await self.bot.send_message(
                Config.ADMIN_ID,
                report_text
            )
            
            print(f"Daily report sent to admin {Config.ADMIN_ID}")
            
        except Exception as e:
            print(f"Error sending daily report: {e}")
    
    async def process_payouts(self):
        """Process pending payouts"""
        try:
            await blockchain.process_payouts()
            
            # Get processed payouts to notify users
            pending_payouts = await db.get_pending_payouts()
            
            for payout in pending_payouts:
                if payout['status'] == 'paid' and payout['payout_tx_hash']:
                    try:
                        # Get user data
                        user_data = await db.get_user(payout['user_id'])
                        lang = user_data.get('language_code', 'ru') if user_data else 'ru'
                        t = TRANSLATIONS[lang]
                        
                        # Send payout notification
                        await self.bot.send_message(
                            payout['user_id'],
                            t['payout_sent'].format(
                                amount=payout['payout_amount'],
                                address=payout['payout_address'],
                                tx_hash=payout['payout_tx_hash']
                            ),
                            parse_mode='Markdown'
                        )
                        
                    except Exception as e:
                        print(f"Error notifying user {payout['user_id']}: {e}")
            
        except Exception as e:
            print(f"Error processing payouts: {e}")
    
    async def generate_proxy_wallets(self):
        """Generate proxy wallets for future use"""
        try:
            await blockchain.create_proxy_wallets(10)  # Generate 10 wallets
            print("Generated 10 new proxy wallets")
            
        except Exception as e:
            print(f"Error generating proxy wallets: {e}")

# Global scheduler instance
scheduler = None

def init_scheduler(bot: Bot):
    """Initialize scheduler"""
    global scheduler
    scheduler = TaskScheduler(bot)
    return scheduler