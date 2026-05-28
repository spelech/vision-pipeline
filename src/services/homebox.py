import asyncio
import logging
import os
from typing import Any, Dict, Optional

import requests
from .base import BaseService

logger = logging.getLogger(__name__)


class HomeboxService(BaseService):
    def __init__(self):
        self.api_url = os.getenv("HOMEBOX_URL", "http://homebox:7745/api/v1")
        self.username = os.getenv(
            "HOMEBOX_USERNAME") or os.getenv("HOMEBOX_EMAIL")
        self.password = os.getenv("HOMEBOX_PASSWORD")
        self._cached_token = None

    @property
    def name(self) -> str:
        return "homebox"

    def _get_headers(self):
        if self.username and self.password:
            if not self._cached_token:
                try:
                    payloads = [
                        {"username": self.username, "password": self.password}]
                    if "@" in self.username:
                        payloads.append(
                            {"email": self.username, "password": self.password})

                    for payload in payloads:
                        resp = requests.post(
                            f"{self.api_url}/users/login", json=payload, timeout=5)
                        if resp.ok:
                            self._cached_token = resp.json().get('token')
                            break
                except requests.RequestException as e:
                    logger.error("Homebox login failed: %s", e)
                    return None
            if self._cached_token:
                return {"Authorization": f"Bearer {self._cached_token}"}

        return None

    def get_headers(self) -> Optional[Dict[str, str]]:
        """Public wrapper for authenticated request headers."""
        return self._get_headers()

    async def _get_headers_async(self) -> Optional[Dict[str, str]]:
        return await asyncio.to_thread(self._get_headers)

    def find_or_create_location(self, name: str) -> Optional[str]:
        headers = self._get_headers()
        if not headers:
            return None
        try:
            resp = requests.get(f"{self.api_url}/locations",
                                headers=headers, params={"q": name}, timeout=5)
            resp.raise_for_status()
            locations = resp.json()
            for loc in locations:
                if loc['name'].lower() == name.lower():
                    return loc['id']

            resp = requests.post(
                f"{self.api_url}/locations", headers=headers, json={"name": name}, timeout=5)
            resp.raise_for_status()
            return resp.json()['id']
        except requests.RequestException as e:
            logger.error("Homebox location error: %s", e)
            return None

    async def find_or_create_location_async(self, name: str) -> Optional[str]:
        return await asyncio.to_thread(self.find_or_create_location, name)

    async def _request(self, method: str, endpoint: str, **
                       kwargs: Any) -> requests.Response:
        request_method = getattr(requests, method.lower())
        return await asyncio.to_thread(request_method, f"{self.api_url}{endpoint}", **kwargs)

    # pylint: disable=too-many-locals
    async def execute(self,
                      data: Dict[str,
                                 Any],
                      image_path: Optional[str] = None,
                      external_id: Optional[str] = None) -> Dict[str,
                                                                 Any]:
        headers = await self._get_headers_async()
        if not headers:
            return {
                "success": False,
                "error": "Homebox credentials are missing or invalid"}

        try:
            item_id = external_id

            # Check if item exists if external_id provided
            if item_id:
                check = await self._request("GET", f"/items/{item_id}", headers=headers, timeout=5)
                if check.status_code == 404:
                    item_id = None  # Force recreation

            location_id = None
            if data.get('location'):
                location_id = await self.find_or_create_location_async(data['location'])

            base_payload = {
                "name": data.get('product_name') or data.get('name'),
                "quantity": int(data.get('quantity', 1)),
                "description": data.get('description', ''),
                "locationId": location_id,
                "manufacturer": data.get('manufacturer') or data.get('brand') or "",
                "modelNumber": data.get('model_number') or "",
                "serialNumber": data.get('serial_number') or "",
                "purchasePrice": float(data.get('purchase_price') or 0),
                "notes": data.get('notes') or ""
            }

            if data.get('technical_details'):
                details = data['technical_details']
                if base_payload['notes']:
                    base_payload['notes'] += f"\n\n--- Specs ---\n{details}"
                else:
                    base_payload['notes'] = f"--- Specs ---\n{details}"

            if item_id:
                # Update existing
                resp = await self._request(
                    "PUT",
                    f"/items/{item_id}",
                    headers=headers,
                    json=base_payload,
                    timeout=5,
                )
                resp.raise_for_status()
            else:
                # Create new
                # Step 1: Create basic
                resp = await self._request("POST", "/items", headers=headers, json={
                    "name": base_payload["name"],
                    "quantity": base_payload["quantity"],
                    "description": base_payload["description"],
                    "locationId": base_payload["locationId"]
                }, timeout=5)
                resp.raise_for_status()
                item = resp.json()
                item_id = item['id']

                # Step 2: Update extended
                await self._request(
                    "PUT",
                    f"/items/{item_id}",
                    headers=headers,
                    json=base_payload,
                    timeout=5,
                )

            # Upload attachment if image_path exists
            if image_path and os.path.exists(f"data/uploads/{image_path}"):
                with open(f"data/uploads/{image_path}", "rb") as f:
                    files = {"file": (image_path, f, "image/jpeg")}
                    attach_data = {"type": "photo", "name": "Vision Capture"}
                    await self._request(
                        "POST",
                        f"/items/{item_id}/attachments",
                        headers=headers,
                        files=files,
                        data=attach_data,
                        timeout=10,
                    )

            return {
                "success": True,
                "item_id": item_id,
                # Best guess at UI URL
                "url": f"{self.api_url.replace('/api/v1', '')}/items/{item_id}"
            }
        except (requests.RequestException, OSError) as e:
            logger.error("Homebox execution failed: %s", e)
            return {"success": False, "error": str(e)}

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = await self._get_headers_async()
        if not headers:
            return {}
        name = data.get('product_name') or data.get('name')
        if not name:
            return {}
        try:
            resp = await self._request(
                "GET",
                "/items",
                headers=headers,
                params={"q": name},
                timeout=5,
            )
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict):
                items = payload.get('items', [])
            elif isinstance(payload, list):
                items = payload
            else:
                items = []
            return {
                "existing_items": items[:5],
                "existing_items_total": len(items),
            }
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            return {}

    def get_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": data.get('product_name') or data.get('name'),
            "quantity": int(data.get('quantity', 1)),
            "description": data.get('description', ''),
            "location": data.get('location', 'pantry'),
            "manufacturer": data.get('manufacturer') or data.get('brand') or "",
            "modelNumber": data.get('model_number') or "",
            "serialNumber": data.get('serial_number') or "",
            "purchasePrice": float(data.get('purchase_price') or 0),
            "notes": data.get('notes') or "",
            "technical_details": data.get('technical_details', '')
        }
