# ==================== FILE: models.py ====================
"""
Data models and types
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class User:
    """User data model"""
    telegram_id: int
    email: str
    password: str
    imap_server: str
    imap_port: int
    smtp_server: str
    smtp_port: int
    is_verified: bool = False
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'User':
        """Create User from database row"""
        return cls(
            telegram_id=row[0],
            email=row[1],
            password=row[2],
            imap_server=row[3],
            imap_port=row[4],
            smtp_server=row[5],
            smtp_port=row[6],
            is_verified=bool(row[8]) if len(row) > 8 else False,
            created_at=row[9] if len(row) > 9 else None
        )

@dataclass
class EmailSummary:
    """Email summary data model"""
    sender: str
    subject: str
    summary: str
    email_id: str
    body: Optional[str] = None
    timestamp: Optional[datetime] = None

@dataclass
class EmailConfig:
    """Email server configuration"""
    provider: str
    imap_server: str
    imap_port: int
    smtp_server: str
    smtp_port: int
    
    @classmethod
    def for_provider(cls, email: str) -> Optional['EmailConfig']:
        """Get configuration for email provider"""
        domain = email.split('@')[1].lower()
        
        configs = {
            'gmail.com': cls('Gmail', 'imap.gmail.com', 993, 'smtp.gmail.com', 587),
            'outlook.com': cls('Outlook', 'outlook.office365.com', 993, 'smtp.office365.com', 587),
            'hotmail.com': cls('Hotmail', 'outlook.office365.com', 993, 'smtp.office365.com', 587),
        }
        
        return configs.get(domain)