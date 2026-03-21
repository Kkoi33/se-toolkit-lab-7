"""
LMS API Client.

Handles communication with the LMS backend API.
Uses Bearer token authentication.
"""

import httpx
from typing import Optional


class LMSClient:
    """Client for the LMS backend API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        """
        Initialize the LMS client.

        Args:
            base_url: Base URL of the LMS API (e.g., http://localhost:42002)
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_health(self) -> dict:
        """
        Check backend health by fetching items.

        Returns:
            dict with 'healthy' status and 'item_count' or 'error'

        Raises:
            httpx.RequestError: If the request fails
        """
        url = f"{self.base_url}/items/"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            return {
                "healthy": True,
                "item_count": len(data) if isinstance(data, list) else 0,
            }

    def get_labs(self) -> list:
        """
        Get list of available labs.

        Returns:
            List of lab items from the backend

        Raises:
            httpx.RequestError: If the request fails
        """
        url = f"{self.base_url}/items/"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()
            # Filter for labs (type might be 'lab' or similar)
            if isinstance(data, list):
                return data
            return []

    def get_scores(self, lab_name: str) -> dict:
        """
        Get scores for a specific lab.

        Args:
            lab_name: Name of the lab (e.g., 'lab-04')

        Returns:
            dict with pass rates per task

        Raises:
            httpx.RequestError: If the request fails
        """
        url = f"{self.base_url}/analytics/pass-rates"
        params = {"lab": lab_name}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()


def create_client_from_config() -> LMSClient:
    """Create LMS client from environment configuration."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_config

    base_url = get_config("LMS_API_BASE_URL", "http://localhost:42002")
    api_key = get_config("LMS_API_KEY", "")

    return LMSClient(base_url=base_url, api_key=api_key)
