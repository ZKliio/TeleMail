# ==================== FILE: prompts.py ====================
"""
All prompts used by the bot
"""

class Prompts:
    """Centralized prompt management"""
    
    EMAIL_SUMMARY_PROMPT = """
You are an email summarization assistant. Your task is to convert emails into short, text-message-like summaries that capture the key information.

Guidelines:
- Keep it conversational and brief (like a text message)
- Extract the main action items, requests, or information
- Preserve important details like dates, times, names
- Use casual language but remain professional
- Maximum 2-3 sentences
- Focus on what the recipient needs to know or do

Email to summarize:
From: {sender}
Subject: {subject}
Body: {body}

Provide only the summary, no additional text:
"""

    WELCOME_MESSAGE = """
🤖 **Email Summary Bot**

I'll help you get short summaries of your emails via Telegram!

**Setup Steps:**
1. Use `/setup` to configure your email
2. I'll send a verification code to your email
3. Use `/verify <code>` to confirm
4. Start receiving email summaries!

**Commands:**
- `/setup` - Configure email settings
- `/verify <code>` - Verify your email
- `/status` - Check connection status
- `/stop` - Stop email monitoring

Type any message to reply to the last email.
    """
    
    SETUP_MESSAGE = """
📧 **Email Setup**

**Necessary configurations:**
----------------------------------------------------
Enable 2-Step Verification at
https://myaccount.google.com/u/0/signinoptions/twosv

Create an App Password at 
https://myaccount.google.com/apppasswords

Provide your details as follows:
`email@domain.com app_password`
**Note:** For Gmail, use an App Password, not your regular password!
"""
    VERIFICATION_EMAIL_TEMPLATE = """
Email Summary Bot Verification

Your verification code is: {code}

Use this code in Telegram to complete your setup.
This code expires in 5 minutes.

If you didn't request this, please ignore this email.
    """
