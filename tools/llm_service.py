# ==================== FILE: llm_service.py ====================
"""
LLM integration service for email summarization
"""
import logging
import requests
from typing import Optional
from tools.config import Config
from tools.prompts import Prompts

class LLMService:
    """Service for interacting with LLM API"""
    
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url or Config.LLM_API_URL
        self.api_key = api_key or Config.LLM_API_KEY
        self.model = Config.LLM_MODEL
        self.logger = logging.getLogger(__name__)

    ## GEMINI TESTING
    def summarize_email(self, sender: str, subject: str, body: str) -> str:
        try:
            prompt = Prompts.EMAIL_SUMMARY_PROMPT.format(
                sender=sender,
                subject=subject,
                body=body[:Config.MAX_EMAIL_BODY_LENGTH]
            )

            # Gemini requires ?key=API_KEY in URL
            url = f"{self.api_url}?key={self.api_key}"

            headers = {"Content-Type": "application/json"}

            payload = {
                "contents": [
                    {"parts": [{"text": prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": Config.MAX_SUMMARY_LENGTH,
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                return self._fallback_summary(sender, subject)
            else:
                self.logger.error(f"LLM API error: {response.status_code} - {response.text}")
                return self._fallback_summary(sender, subject)

        except Exception as e:
            self.logger.error(f"Error summarizing email: {e}")
            return self._fallback_summary(sender, subject)



    ## OPENAI
    # def summarize_email(self, sender: str, subject: str, body: str) -> str:
    #     """
    #     Summarize email using LLM API
        
    #     Args:
    #         sender: Email sender
    #         subject: Email subject
    #         body: Email body content
            
    #     Returns:
    #         Summary string or fallback if API fails
    #     """
    #     try:
    #         prompt = Prompts.EMAIL_SUMMARY_PROMPT.format(
    #             sender=sender,
    #             subject=subject,
    #             body=body[:Config.MAX_EMAIL_BODY_LENGTH]
    #         )
            
    #         headers = {
    #             "Authorization": f"Bearer {self.api_key}",
    #             "Content-Type": "application/json"
    #         }
            
    #         payload = {
    #             "model": self.model,
    #             "messages": [
    #                 {"role": "user", "content": prompt}
    #             ],
    #             "max_tokens": Config.MAX_SUMMARY_LENGTH,
    #             "temperature": 0.3
    #         }
            
    #         response = requests.post(
    #             self.api_url, 
    #             headers=headers, 
    #             json=payload, 
    #             timeout=30
    #         )
            
    #         if response.status_code == 200:
    #             result = response.json()
    #             summary = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    #             return summary.strip() if summary else self._fallback_summary(sender, subject)
    #         else:
    #             self.logger.error(f"LLM API error: {response.status_code} - {response.text}")
    #             return self._fallback_summary(sender, subject)
                
    #     except Exception as e:
    #         self.logger.error(f"Error summarizing email: {e}")
    #         return self._fallback_summary(sender, subject)
    
    def _fallback_summary(self, sender: str, subject: str) -> str:
        """Create fallback summary when LLM fails"""
        return f"📧 {sender}: {subject}"
