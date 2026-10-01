"""Schoology integration for grades, assignments, and courses."""

import httpx
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SchoologyIntegration:
    """Handle Schoology OAuth2 and API interactions."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.auth_url = "https://app.schoology.com/oauth/authorize"
        self.token_url = "https://app.schoology.com/oauth/token"
        self.api_url = "https://api.schoology.com/v1"
    
    def get_auth_url(self, state: str) -> str:
        """Generate OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "read"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"
    
    def get_access_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        try:
            response = httpx.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                },
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get Schoology access token: {e}")
            raise
    
    async def get_courses(self, access_token: str) -> List[Dict[str, Any]]:
        """Fetch user's courses."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/users/me/courses",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("course", [])
        except Exception as e:
            logger.error(f"Failed to fetch Schoology courses: {e}")
            return []
    
    async def get_assignments(self, access_token: str, course_id: str) -> List[Dict[str, Any]]:
        """Fetch assignments for a course."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/courses/{course_id}/assignments",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("assignment", [])
        except Exception as e:
            logger.error(f"Failed to fetch Schoology assignments: {e}")
            return []
    
    async def get_grades(self, access_token: str, course_id: str) -> Dict[str, Any]:
        """Fetch grades for a course."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_url}/courses/{course_id}/grades",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Schoology grades: {e}")
            return {}
