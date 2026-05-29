import os
import logging
from typing import Any, Dict, Optional

import requests

from .base import BaseService

logger = logging.getLogger(__name__)


class PriceBuddyService(BaseService):
    def __init__(self):
        self.api_url = os.getenv(
            "PRICEBUDDY_URL",
            "http://pricebuddy:80/api/v1")
        self.api_key = os.getenv("PRICEBUDDY_API_KEY")

    @property
    def name(self) -> str:
        return "pricebuddy"

    def _get_headers(self):
        if not self.api_key:
            return None
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"}

    async def execute(self,
                      data: Dict[str,
                                 Any],
                      image_path: Optional[str] = None,
                      external_id: Optional[str] = None) -> Dict[str,
                                                                 Any]:
        """Track item price by barcode or name."""
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        payload = self.get_payload(data)
        try:
            resp = requests.post(
                f"{self.api_url}/products", headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            return {
                "success": True,
                "note": "Price tracking initiated",
                "data": resp.json()}
        except requests.RequestException as e:
            logger.error("PriceBuddy execution failed: %s", e)
            return {"success": False, "error": str(e)}

    def get_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format payload for PriceBuddy API."""
        urls = []
        if data.get('product_url'):
            urls.append(data['product_url'])

        for key in ('monitor_urls', 'comparable_urls', 'candidate_urls'):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item and item not in urls:
                        urls.append(item)

        # Add URLs from search results if available
        for res in data.get('searxng_results', []):
            if res.get('url') and res['url'] not in urls:
                # Basic heuristic: ignore non-shopping sites if many results
                if any(
                    x in res['url'].lower() for x in [
                        'amazon',
                        'walmart',
                        'target',
                        'ebay',
                        'bestbuy',
                        'costco']):
                    urls.append(res['url'])

        # Fallback to top results if no shopping sites found
        if not urls and data.get('searxng_results'):
            urls = [r['url'] for r in data['searxng_results'][:3]]

        return {
            "name": data.get('product_name') or data.get('name'),
            "urls": urls[:5],  # Limit to top 5 URLs
            "barcode": data.get('barcode'),
            "tags": [data.get('category')] if data.get('category') else ["Vision Pipeline"]
        }

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Search for existing products in PriceBuddy."""
        headers = self._get_headers()
        if not headers:
            return {}
        name = data.get('product_name') or data.get('name')
        barcode = data.get('barcode')

        try:
            # Search by barcode first
            if barcode:
                resp = requests.get(f"{self.api_url}/products",
                                    headers=headers,
                                    params={"barcode": barcode},
                                    timeout=5)
                if resp.status_code == 200:
                    matches = resp.json()
                    if matches:
                        return {"existing_product": matches[0]}

            # Search by name
            if name:
                resp = requests.get(
                    f"{self.api_url}/products", headers=headers, params={"q": name}, timeout=5)
                if resp.status_code == 200:
                    matches = resp.json()
                    return {"existing_matches": matches[:3]}
        except requests.RequestException:
            pass
        return {}


class ChangeDetectionService(BaseService):
    def __init__(self):
        self.api_url = os.getenv(
            "CHANGEDETECTION_URL",
            "http://changedetection:5000/api/v1")
        self.api_key = os.getenv("CHANGEDETECTION_API_KEY")

    @property
    def name(self) -> str:
        return "changedetection"

    def _get_headers(self):
        if not self.api_key:
            return None
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    async def execute(self,
                      data: Dict[str,
                                 Any],
                      image_path: Optional[str] = None,
                      external_id: Optional[str] = None) -> Dict[str,
                                                                 Any]:
        """Monitor one or more product URLs for changes."""
        # pylint: disable=too-many-locals
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        raw_monitor_urls = data.get('monitor_urls', [])
        monitor_urls: list[str] = []
        if isinstance(raw_monitor_urls, list):
            monitor_urls.extend(
                url
                for url in raw_monitor_urls
                if isinstance(url, str) and url.startswith(('http://', 'https://'))
            )
        primary_url = data.get('product_url')
        if isinstance(primary_url, str) and primary_url.startswith(('http://', 'https://')):
            monitor_urls.insert(0, primary_url)

        # Preserve order while removing duplicates.
        unique_urls: list[str] = []
        for url in monitor_urls:
            if url not in unique_urls:
                unique_urls.append(url)

        if not unique_urls:
            return {"success": False, "error": "No URL to monitor"}

        if len(unique_urls) == 1:
            payload = self.get_payload(data, unique_urls[0])
            try:
                resp = requests.post(f"{self.api_url}/watch",
                                     headers=headers, json=payload, timeout=10)
                resp.raise_for_status()
                return {
                    "success": True,
                    "note": f"Monitoring {unique_urls[0]}",
                    "data": resp.json()}
            except requests.RequestException as e:
                logger.error("ChangeDetection execution failed: %s", e)
                return {"success": False, "error": str(e)}

        successes = []
        failures = []
        for url in unique_urls:
            payload = self.get_payload(data, url)
            try:
                resp = requests.post(
                    f"{self.api_url}/watch",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )
                resp.raise_for_status()
                successes.append({"url": url, "data": resp.json()})
            except requests.RequestException as exc:
                logger.error("ChangeDetection execution failed for %s: %s", url, exc)
                failures.append({"url": url, "error": str(exc)})

        if not successes:
            return {
                "success": False,
                "error": "Failed to create watches for all requested URLs",
                "failures": failures,
            }

        return {
            "success": True,
            "note": f"Monitoring {len(successes)} URLs",
            "data": {
                "created": successes,
                "failed": failures,
            },
        }

    def get_payload(self, data: Dict[str, Any], url: Optional[str] = None) -> Dict[str, Any]:
        """Format payload for ChangeDetection.io API."""
        return {
            "url": url or data.get('product_url'),
            "title": data.get('product_name') or data.get('name'),
            "tag": data.get('category') or "Vision Pipeline",
            "time_between_check": {"hours": 12},
            "fetch_backend": "html_requests",
            "track_ldjson_price_data": True
        }

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if URL is already being watched."""
        headers = self._get_headers()
        if not headers:
            return {}
        url = data.get('product_url')
        if not url:
            return {}

        try:
            resp = requests.get(f"{self.api_url}/watch",
                                headers=headers, timeout=5)
            if resp.status_code == 200:
                watches = resp.json()
                # Check for matching URL
                for uuid, watch in watches.items():
                    if watch.get('url') == url:
                        return {"existing_watch": watch, "uuid": uuid}
        except requests.RequestException:
            pass
        return {}
