import os
import requests
import logging
from typing import Any, Dict, Optional
from .base import BaseService

logger = logging.getLogger(__name__)

class HomeboxService(BaseService):
    def __init__(self):
        self.api_url = os.getenv("HOMEBOX_URL", "http://homebox:7745/api/v1")
        self.api_key = os.getenv("HOMEBOX_API_KEY")
        self.email = os.getenv("HOMEBOX_EMAIL")
        self.password = os.getenv("HOMEBOX_PASSWORD")
        self._cached_token = None

    @property
    def name(self) -> str:
        return "homebox"

    def _get_headers(self):
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
            
        if self.email and self.password:
            if not self._cached_token:
                try:
                    resp = requests.post(f"{self.api_url}/users/login", json={
                        "email": self.email,
                        "password": self.password
                    }, timeout=5)
                    resp.raise_for_status()
                    self._cached_token = resp.json().get('token')
                except Exception as e:
                    logger.error(f"Homebox login failed: {e}")
                    return None
            if self._cached_token:
                return {"Authorization": f"Bearer {self._cached_token}"}
                
        return None

    def find_or_create_location(self, name: str) -> Optional[str]:
        headers = self._get_headers()
        if not headers: return None
        try:
            resp = requests.get(f"{self.api_url}/locations", headers=headers, params={"q": name}, timeout=5)
            resp.raise_for_status()
            locations = resp.json()
            for loc in locations:
                if loc['name'].lower() == name.lower():
                    return loc['id']
            
            resp = requests.post(f"{self.api_url}/locations", headers=headers, json={"name": name}, timeout=5)
            resp.raise_for_status()
            return resp.json()['id']
        except Exception as e:
            logger.error(f"Homebox location error: {e}")
            return None

    async def execute(self, data: Dict[str, Any], image_path: Optional[str] = None, external_id: Optional[str] = None) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        try:
            item_id = external_id
            
            # Check if item exists if external_id provided
            if item_id:
                check = requests.get(f"{self.api_url}/items/{item_id}", headers=headers, timeout=5)
                if check.status_code == 404:
                    item_id = None # Force recreation
            
            location_id = None
            if data.get('location'):
                location_id = self.find_or_create_location(data['location'])

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
                if base_payload['notes']:
                    base_payload['notes'] += f"\n\n--- Specs ---\n{data['technical_details']}"
                else:
                    base_payload['notes'] = f"--- Specs ---\n{data['technical_details']}"

            if item_id:
                # Update existing
                resp = requests.put(f"{self.api_url}/items/{item_id}", headers=headers, json=base_payload, timeout=5)
                resp.raise_for_status()
            else:
                # Create new
                # Step 1: Create basic
                resp = requests.post(f"{self.api_url}/items", headers=headers, json={
                    "name": base_payload["name"],
                    "quantity": base_payload["quantity"],
                    "description": base_payload["description"],
                    "locationId": base_payload["locationId"]
                }, timeout=5)
                resp.raise_for_status()
                item = resp.json()
                item_id = item['id']
                
                # Step 2: Update extended
                requests.put(f"{self.api_url}/items/{item_id}", headers=headers, json=base_payload, timeout=5)

            # Upload attachment if image_path exists
            if image_path and os.path.exists(f"data/uploads/{image_path}"):
                with open(f"data/uploads/{image_path}", "rb") as f:
                    files = {"file": (image_path, f, "image/jpeg")}
                    attach_data = {"type": "photo", "name": "Vision Capture"}
                    requests.post(f"{self.api_url}/items/{item_id}/attachments", headers=headers, files=files, data=attach_data, timeout=10)

            return {
                "success": True, 
                "item_id": item_id, 
                "url": f"{self.api_url.replace('/api/v1', '')}/items/{item_id}" # Best guess at UI URL
            }
        except Exception as e:
            logger.error(f"Homebox execution failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers: return {}
        name = data.get('product_name') or data.get('name')
        if not name: return {}
        try:
            resp = requests.get(f"{self.api_url}/items", headers=headers, params={"q": name}, timeout=5)
            resp.raise_for_status()
            return {"existing_items": resp.json().get('items', [])}
        except Exception:
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
