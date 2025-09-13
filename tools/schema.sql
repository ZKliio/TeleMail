CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                email_address TEXT UNIQUE,
                email_password TEXT,
                email_server TEXT,
                email_port INTEGER,
                smtp_server TEXT,
                smtp_port INTEGER,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_code TEXT,
                verification_expiry TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email_id TEXT,
                sender TEXT,
                subject TEXT,
                summary TEXT,
                original_body TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            );