# ==================== FILE: monitoring_manager.py ====================
"""
Email monitoring management
"""
import asyncio
import logging
from typing import Dict, Optional
from telegram import Bot

from tools.models import User, EmailSummary
from tools.config import Config

class MonitoringManager:
    """Manages email monitoring tasks for all users"""
    
    def __init__(self, db_manager, email_service):
        self.db = db_manager
        self.email_service = email_service
        self.monitoring_tasks: Dict[int, asyncio.Task] = {}
        self.logger = logging.getLogger(__name__)
    
    async def start_monitoring(self, telegram_id: int):
        """Start monitoring emails for a specific user"""
        if telegram_id not in self.monitoring_tasks:
            task = asyncio.create_task(self._monitor_user_emails(telegram_id))
            self.monitoring_tasks[telegram_id] = task
            self.logger.info(f"Started monitoring for user {telegram_id}")
    
    def stop_monitoring(self, telegram_id: int) -> bool:
        """Stop monitoring emails for a specific user"""
        if telegram_id in self.monitoring_tasks:
            self.monitoring_tasks[telegram_id].cancel()
            del self.monitoring_tasks[telegram_id]
            self.logger.info(f"Stopped monitoring for user {telegram_id}")
            return True
        return False
    
    def is_monitoring(self, telegram_id: int) -> bool:
        """Check if monitoring is active for a user"""
        return telegram_id in self.monitoring_tasks
    
    async def start_all_verified_users(self):
        """Start monitoring for all verified users"""
        verified_users = self.db.get_all_verified_users()
        
        for user_data in verified_users:
            telegram_id = user_data[0]
            await self.start_monitoring(telegram_id)
        
        self.logger.info(f"Started monitoring for {len(verified_users)} verified users")
    
    async def _monitor_user_emails(self, telegram_id: int):
        """Background task to monitor emails for a specific user"""
        try:
            while True:
                try:
                    user_data = self.db.get_user(telegram_id)
                    if not user_data or not user_data[8]:  # not verified
                        self.logger.warning(f"User {telegram_id} not verified, stopping monitoring")
                        break
                    
                    user = User.from_db_row(user_data)
                    
                    # Check for new emails
                    summaries = self.email_service.check_new_emails(user)
                    
                    # Send summaries via Telegram
                    if summaries:
                        await self._send_summaries_to_user(telegram_id, summaries)
                        self.logger.info(f"Found {len(summaries)} new emails for user {telegram_id}")


                    # Wait before checking again
                    await asyncio.sleep(Config.EMAIL_CHECK_INTERVAL)
                    
                except asyncio.CancelledError:
                    self.logger.info(f"Email monitoring cancelled for user {telegram_id}")
                    break
                except Exception as e:
                    self.logger.error(f"Email monitoring error for user {telegram_id}: {e}")
                    await asyncio.sleep(Config.ERROR_RETRY_INTERVAL)
        
        finally:
            # Clean up the task reference
            if telegram_id in self.monitoring_tasks:
                del self.monitoring_tasks[telegram_id]
    
    async def _send_summaries_to_user(self, telegram_id: int, summaries: list[EmailSummary]):
        """Send email summaries to user via Telegram"""
        bot = Bot(Config.TELEGRAM_BOT_TOKEN)
        
        for summary in summaries:
            message = f"📧 **{summary.sender[:50]}**\n\n{summary.summary}"
            
            try:
                await bot.send_message(
                    chat_id=telegram_id, 
                    text=message, 
                    parse_mode='Markdown'
                )
            except Exception as e:
                self.logger.error(f"Error sending message to {telegram_id}: {e}")
    
    def cleanup(self):
        """Cancel all monitoring tasks"""
        for task in self.monitoring_tasks.values():
            task.cancel()
        self.monitoring_tasks.clear()
        self.logger.info("Cleaned up all monitoring tasks")
