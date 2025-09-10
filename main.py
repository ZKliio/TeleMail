"""
Entry point for the Email Telegram Bot application
"""
import logging
import sys
from tools.config import Config
from tools.bot import EmailTelegramBot

def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('email_bot.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def validate_config() -> bool:
    """Validate required configuration"""
    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ Please configure your Telegram bot token in .env file")
        return False
    
    if not Config.LLM_API_KEY:
        print("⚠️  Please configure your LLM API key in .env file")
        print("The bot will run but email summarization won't work properly")
    
    return True

def main():
    """Main function to run the bot"""
    setup_logging()
    
    if not validate_config():
        return
    
    try:
        bot = EmailTelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Bot crashed: {e}", exc_info=True)

if __name__ == "__main__":
    main()  