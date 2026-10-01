"""Gmail integration for fetching and analyzing emails."""

import httpx
import json
import base64
from typing import Optional, List, Dict
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow


class GmailIntegration:
    """Gmail API integration for fetching and parsing emails."""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, credentials_file: str, redirect_uri: str):
        """Initialize Gmail integration.
        
        Args:
            credentials_file: Path to Google OAuth2 credentials JSON
            redirect_uri: OAuth2 redirect URI
        """
        self.credentials_file = credentials_file
        self.redirect_uri = redirect_uri
    
    def get_auth_url(self, state: str) -> str:
        """Generate OAuth2 authorization URL.
        
        Args:
            state: State parameter for OAuth2 flow
            
        Returns:
            Authorization URL
        """
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        auth_url, state = flow.authorization_url(state=state)
        return auth_url
    
    def get_access_token(self, code: str) -> Dict[str, str]:
        """Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth2 callback
            
        Returns:
            Dictionary with access_token, refresh_token, etc.
        """
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        credentials = flow.fetch_token(code=code)
        return {
            'access_token': credentials['access_token'],
            'refresh_token': credentials.get('refresh_token'),
            'token_expiry': credentials.get('expires_in')
        }
    
    async def get_unread_emails(self, access_token: str, limit: int = 10) -> List[Dict]:
        """Fetch unread emails from Gmail.
        
        Args:
            access_token: Gmail API access token
            limit: Maximum number of emails to fetch
            
        Returns:
            List of email dictionaries
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get unread message IDs
            response = await client.get(
                "https://www.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params={
                    "q": "is:unread",
                    "maxResults": min(limit, 50)
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Gmail API error: {response.text}")
            
            messages = response.json().get('messages', [])
            emails = []
            
            for msg in messages:
                try:
                    # Get full message
                    msg_response = await client.get(
                        f"https://www.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
                        headers=headers,
                        params={"format": "full"}
                    )
                    
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        email = self._parse_email(msg_data)
                        emails.append(email)
                except Exception as e:
                    print(f"Error parsing email {msg['id']}: {e}")
                    continue
            
            return emails
    
    def _parse_email(self, message: Dict) -> Dict:
        """Parse email from Gmail API response.
        
        Args:
            message: Message object from Gmail API
            
        Returns:
            Parsed email dictionary
        """
        headers = message['payload'].get('headers', [])
        
        def get_header(name: str) -> str:
            for h in headers:
                if h['name'] == name:
                    return h['value']
            return ""
        
        body = self._get_email_body(message['payload'])
        
        return {
            'id': message['id'],
            'from': get_header('From'),
            'subject': get_header('Subject'),
            'date': get_header('Date'),
            'body': body,
            'snippet': message.get('snippet', '')
        }
    
    def _get_email_body(self, payload: Dict) -> str:
        """Extract email body from payload.
        
        Args:
            payload: Message payload from Gmail API
            
        Returns:
            Email body text
        """
        try:
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data', '')
                        if data:
                            return base64.urlsafe_b64decode(data).decode('utf-8')
            else:
                data = payload['body'].get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
        except Exception as e:
            print(f"Error extracting email body: {e}")
        
        return ""
