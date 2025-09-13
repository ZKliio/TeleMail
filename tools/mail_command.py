# ==================== FILE: mail_command.py ====================
import logging
from telegram import Update
from telegram.ext import ContextTypes
from tools.llm_service import LLMService
from tools.email_service import EmailService

class MailCommand:
    def __init__(self, email_service: EmailService, llm_service: LLMService):
        self.email_service = email_service
        self.llm_service = llm_service
        self.logger = logging.getLogger(__name__)
        # Temporary storage for drafts (keyed by Telegram user_id)
        self.pending_drafts = {}

    async def handle_mail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mail formal|informal <recipient> <message>"""
        user_id = update.effective_user.id
        args = context.args

        if len(args) < 3:
            await update.message.reply_text(
                "Usage: /mail formal|informal <recipient> <message>"
            )
            return

        style = args[0].lower()
        recipient = args[1]
        user_message = " ".join(args[2:])

        if style not in ["formal", "informal"]:
            await update.message.reply_text("Please choose either 'formal' or 'informal'.")
            return

        try:
            # Generate email body
            rewritten_body = self.llm_service.generate_email(user_message, style)
            # Generate email subject
            generated_subject = self.llm_service.generate_email_subject(user_message, style)
        except Exception as e:
            self.logger.error(f"LLM error: {e}")
            await update.message.reply_text("❌ Could not generate the email.")
            return

        # Save draft
        self.pending_drafts[user_id] = {
            "recipient": recipient,
            "subject": generated_subject,
            "body": rewritten_body
        }

        preview_text = (
            f"📧 **Email Draft**\n"
            f"**To:** {recipient}\n"
            f"**Subject:** {generated_subject}\n\n"
            f"{rewritten_body}\n\n"
            f"Send this email with /send"
        )

        await update.message.reply_text(preview_text, parse_mode="Markdown")

    async def handle_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /send to actually send the last draft"""
        user_id = update.effective_user.id

        draft = self.pending_drafts.get(user_id)
        if not draft:
            await update.message.reply_text("❌ No draft found. Use /mail first.")
            return

        try:
            success = self.email_service.send_email(
                user_id,  # Telegram ID for DB lookup
                draft["recipient"],
                draft["subject"],
                draft["body"]
            )
            if success:
                await update.message.reply_text("✅ Email sent successfully!")
                del self.pending_drafts[user_id]
            else:
                await update.message.reply_text("❌ Failed to send email.")
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            await update.message.reply_text("❌ Failed to send email.")
