import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import db
from blockchain import blockchain
from handlers import router as main_router
from admin_handlers import router as admin_router
from scheduler import init_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def on_startup():
    """Initialize bot on startup"""
    try:
        # Validate configuration
        Config.validate_config()
        logger.info("Configuration validated")
        
        # Initialize database
        await db.init_db()
        logger.info("Database initialized")
        
        # Generate initial proxy wallets
        await blockchain.create_proxy_wallets(20)
        logger.info("Initial proxy wallets generated")
        
        logger.info("Bot startup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

async def on_shutdown():
    """Cleanup on shutdown"""
    logger.info("Bot shutdown")

async def main():
    """Main bot function"""
    try:
        # Create bot and dispatcher
        bot = Bot(token=Config.BOT_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Include routers
        dp.include_router(main_router)
        dp.include_router(admin_router)
        
        # Set up startup and shutdown handlers
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Set bot instance in blockchain manager for notifications
        from blockchain import blockchain
        blockchain.set_bot_instance(bot)
        
        # Initialize and start scheduler
        task_scheduler = init_scheduler(bot)
        task_scheduler.start()
        
        logger.info("Starting bot...")
        
        try:
            # Start polling
            await dp.start_polling(bot)
        finally:
            # Stop scheduler on exit
            task_scheduler.stop()
            await bot.session.close()
    
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")