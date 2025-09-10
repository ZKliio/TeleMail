# ==================== FILE: verification_service.py ====================
"""
Email verification service
"""
import random
import string
import smtplib
import logging
from email.mime.text import MIMEText
from typing import Optional
from tools.prompts import Prompts

class VerificationService:
    """Service for handling email verification"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
    
    def generate_verification_code(self) -> str:
        """Generate random 6-character verification code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    def send_verification_email(
        self, 
        email_addr: str, 
        password: str, 
        smtp_server: str, 
        smtp_port: int, 
        code: str
    ) -> bool:
        """
        Send verification code via email
        
        Args:
            email_addr: User's email address
            password: Email password
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            code: Verification code to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            msg = MIMEText(Prompts.VERIFICATION_EMAIL_TEMPLATE.format(code=code))
            
            msg['From'] = email_addr
            msg['To'] = email_addr
            msg['Subject'] = "Email Bot Verification Code"
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(email_addr, password)
            server.send_message(msg)
            server.quit()
            
            self.logger.info(f"Verification email sent to {email_addr}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send verification email to {email_addr}: {e}")
            return False
    
    def verify_code(self, telegram_id: int, code: str) -> bool:
        """
        Verify the provided code for a user
        
        Args:
            telegram_id: User's Telegram ID
            code: Verification code to check
            
        Returns:
            True if code is valid, False otherwise
        """
        return self.db.verify_code(telegram_id, code)