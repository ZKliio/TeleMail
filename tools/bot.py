# ==================== FILE: bot.py ====================
"""
Main bot application
"""
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from tools.config import Config
from tools.database_manager import DatabaseManager
from tools.llm_service import LLMService
from tools.email_service import EmailService
from tools.monitoring_manager import MonitoringManager
from tools.telegram_handlers import TelegramHandlers

class EmailTelegramBot:
    """Main bot application class"""
    
    def __init__(self):
        # Initialize services
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.llm = LLMService()
        self.email_service = EmailService(self.db, self.llm)
        self.monitoring = MonitoringManager(self.db, self.email_service)
        self.handlers = TelegramHandlers(self.db, self.email_service, self.monitoring)
        
        # Initialize Telegram application
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self._setup_handlers()
        
        self.logger = logging.getLogger(__name__)
    
    def _setup_handlers(self):
        """Setup telegram bot command handlers"""
        self.app.add_handler(CommandHandler("start", self.handlers.start_command))
        self.app.add_handler(CommandHandler("setup", self.handlers.setup_command))
        self.app.add_handler(CommandHandler("verify", self.handlers.verify_command))
        self.app.add_handler(CommandHandler("status", self.handlers.status_command))
        self.app.add_handler(CommandHandler("stop", self.handlers.stop_command))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.handle_message)
        )
    
    async def initialize(self):
        """Initialize the bot and start monitoring existing users"""
        await self.monitoring.start_all_verified_users()
        self.logger.info("Bot initialized successfully")
    
    def run(self):
        """Start the bot"""
        self.logger.info("🤖 Email Summary Bot starting...")
        
        # Create and set event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize monitoring for existing users
            loop.run_until_complete(self.initialize())
            
            # Start the bot
            self.app.run_polling()
        finally:
            # Cleanup
            self.monitoring.cleanup()
            loop.close()
            self.logger.info("Bot shutdown complete")
