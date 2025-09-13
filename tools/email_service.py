# ==================== FILE: email_service.py ====================
"""
Email handling service
"""
import imaplib
import email
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime

from tools.models import User, EmailSummary
from tools.llm_service import LLMService
from tools.config import Config
from tools.database_manager import DatabaseManager

class EmailService:
    """Service for email operations"""
    def __init__(self, db_manager, llm_service: Optional[LLMService] = None):
        self.db: DatabaseManager = db_manager
        self.llm = llm_service or LLMService()
        self.logger = logging.getLogger(__name__)

    # Send email using credentials stored in DB
    def send_email(self, telegram_id: int, to: str, subject: str, body: str) -> bool:
        print("Using DB file:", self.db.db_path)
        user_data = self.db.get_user(telegram_id)
        #if not user_data:
            #self.logger.error(f"No email account found for telegram_id {telegram_id}")
            #return False
        
        email_address = user_data[1]
        email_password = user_data[2]
        smtp_server = user_data[5]
        smtp_port = user_data[6]

        try:
            msg = MIMEMultipart()
            msg['From'] = email_address
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(email_address, email_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to send email for {email_address}: {e}")
            return False

    # IMAP connection to check inbox
    def connect_to_email(self, telegram_id: int) -> Optional[imaplib.IMAP4_SSL]:
        user_data = self.db.get_user(telegram_id)
        if not user_data:
            return None
        try:
            mail = imaplib.IMAP4_SSL(user_data[3], user_data[4])  # email_server, email_port
            mail.login(user_data[1], user_data[2])  # email_address, email_password
            return mail
        except Exception as e:
            self.logger.error(f"Email connection failed for {user_data[1]}: {e}")
            return None
    
    def connect_to_email(self, user: User) -> Optional[imaplib.IMAP4_SSL]:
        """
        Connect to user's email account via IMAP
        
        Args:
            user: User object with email credentials
            
        Returns:
            IMAP connection object or None if failed
        """
        try:
            mail = imaplib.IMAP4_SSL(user.imap_server, user.imap_port)
            mail.login(user.email, user.password)
            return mail
        except Exception as e:
            self.logger.error(f"Email connection failed for {user.email}: {e}")
            return None
    
    def check_new_emails(self, user: User) -> List[EmailSummary]:
        """
        Check for new emails and return summaries
        
        Args:
            user: User object
            
        Returns:
            List of EmailSummary objects
        """
        mail = self.connect_to_email(user)
        if not mail:
            return []
        
        try:
            mail.select('inbox')
            
            # Search for unread emails from today
            today = datetime.now().strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(UNSEEN SINCE "{today}")')
            
            email_summaries = []
            
            if messages[0]:
                # Process last N emails
                email_ids = messages[0].split()[-Config.MAX_EMAILS_PER_CHECK:]
                
                for num in email_ids:
                    summary = self._process_single_email(mail, num, user)
                    if summary:
                        email_summaries.append(summary)
            
            mail.logout()
            return email_summaries
            
        except Exception as e:
            self.logger.error(f"Error checking emails for {user.email}: {e}")
            self._safe_logout(mail)
            return []
    
    def _process_single_email(self, mail: imaplib.IMAP4_SSL, email_num: bytes, user: User) -> Optional[EmailSummary]:
        """Process a single email and return summary"""
        try:
            status, msg_data = mail.fetch(email_num, '(RFC822)')
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extract email details
                    sender = msg.get('From', 'Unknown')
                    subject = msg.get('Subject', 'No Subject')
                    email_id = msg.get('Message-ID', str(email_num))
                    
                    # Check if already processed
                    if self.db.is_email_processed(user.telegram_id, email_id):
                        return None
                    
                    # Extract body
                    body = self.extract_email_body(msg)
                    
                    # Generate summary
                    summary_text = self.llm.summarize_email(sender, subject, body)
                    
                    # Create EmailSummary object
                    summary = EmailSummary(
                        sender=sender,
                        subject=subject,
                        summary=summary_text,
                        email_id=email_id,
                        body=body,
                        timestamp=datetime.now()
                    )
                    
                    # Store in database
                    self.db.add_processed_email(
                        user.telegram_id, 
                        email_id, 
                        sender, 
                        subject, 
                        summary_text, 
                        body
                    )
                    
                    return summary
                    
        except Exception as e:
            self.logger.error(f"Error processing email {email_num}: {e}")
            return None
    
    def extract_email_body(self, msg: email.message.Message) -> str:
        """Extract text content from email message"""
        body = ""
        
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode('utf-8', errors='ignore')
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"Error extracting email body: {e}")
            body = "Could not extract email content"
        
        return body.strip()
    
    def send_reply_email(self, user: User, recipient_email: str, subject: str, body: str) -> bool:
        """Send reply email on behalf of user"""
        try:
            msg = MIMEMultipart()
            msg['From'] = user.email
            msg['To'] = recipient_email
            msg['Subject'] = f"Re: {subject}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(user.smtp_server, user.smtp_port)
            server.starttls()
            server.login(user.email, user.password)
            
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email from {user.email}: {e}")
            return False
    
    def _safe_logout(self, mail: Optional[imaplib.IMAP4_SSL]):
        """Safely logout from email connection"""
        if mail:
            try:
                mail.logout()
            except:
                pass
