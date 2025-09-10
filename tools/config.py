# ==================== FILE: config.py ====================
"""
Configuration management for the Email Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Centralized configuration management"""
    
    # LLM API Configuration
    LLM_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    LLM_API_KEY = os.getenv("OPENAI_API_KEY")
    LLM_MODEL = "Gemini 2.5 Flash"
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Email Configuration
    DATABASE_PATH = "email_bot.db"
    
    # Security
    VERIFICATION_CODE_EXPIRY = 300  # 5 minutes
    
    # Email check intervals
    EMAIL_CHECK_INTERVAL = 60  # Check every minute
    ERROR_RETRY_INTERVAL = 300  # Retry after 5 minutes on error
    
    # Email limits
    MAX_EMAILS_PER_CHECK = 5
    MAX_EMAIL_BODY_LENGTH = 2000
    MAX_SUMMARY_LENGTH = 150
