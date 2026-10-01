"""Email analysis routed through the shared LLM client (fast model + cache)."""

import json
from typing import Dict, List
from datetime import datetime

from app.services.llm_client import generate, generate_json


class EmailAnalyzer:
    """Analyze emails to extract action items, dates, and other information."""

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        """Initialize email analyzer.

        Args:
            ollama_host: retained for backwards compatibility; routing is
                handled by llm_client via task="email".
        """
        self.ollama_host = ollama_host
    
    async def extract_action_items(self, email_body: str, email_subject: str) -> Dict:
        """Extract action items and dates from email using Qwen2.5:14b.
        
        Args:
            email_body: Email body text
            email_subject: Email subject
            
        Returns:
            Dictionary with action_items, dates, contacts, priority, summary
        """
        
        prompt = f"""Analyze this email and extract structured information:

Subject: {email_subject}

Body:
{email_body[:1000]}

Extract and respond ONLY with valid JSON (no markdown, no code blocks):
{{
    "action_items": ["item1", "item2"],
    "dates": ["2025-12-15", "2025-12-20"],
    "contacts": ["name@email.com"],
    "priority": "high",
    "summary": "Brief summary"
}}

Rules:
- action_items: List of things the user needs to do
- dates: List of dates in YYYY-MM-DD format
- contacts: List of email addresses mentioned
- priority: high, medium, or low
- summary: One sentence summary
- If no action items, use empty arrays
- Respond ONLY with JSON, nothing else"""

        try:
            data = await generate_json(prompt, task="email", timeout=60)
            if isinstance(data, dict):
                return data
            return self._default_response("")
        except Exception as e:
            print(f"Error analyzing email: {e}")
            return self._default_response("")
    
    async def generate_reminder(self, email: Dict) -> str:
        """Generate a concise reminder message.
        
        Args:
            email: Email dictionary with from, subject, body
            
        Returns:
            Reminder message
        """
        
        prompt = f"""Generate a brief, actionable reminder for this email:

From: {email['from']}
Subject: {email['subject']}
Body: {email['body'][:500]}

Keep it under 50 words and focus on what needs to be done. Respond with only the reminder text."""

        try:
            text = await generate(prompt, task="email", timeout=30, temperature=0.4)
            return text.strip() if text else f"Reminder: {email['subject']}"
        except Exception as e:
            print(f"Error generating reminder: {e}")
            return f"Reminder: {email['subject']}"
    
    def _default_response(self, text: str) -> Dict:
        """Return default response structure.
        
        Args:
            text: Text to use as summary
            
        Returns:
            Default response dictionary
        """
        return {
            "action_items": [],
            "dates": [],
            "contacts": [],
            "priority": "medium",
            "summary": text[:200] if text else "Email requires review"
        }
