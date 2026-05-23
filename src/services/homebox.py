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

    @property
    def name(self) -> str:
        return "homebox"

    def _get_headers(self):
        if not self.api_key:
            return None
        return {"Authorization": f"Bearer {self.api_key}"}

    def find_or_create_location(self, name: str) -> Optional[str]:
        headers = self._get_headers()
        if not headers: return None
        try:
            # 1. Search for existing location
            resp = requests.get(f"{self.api_url}/locations", headers=headers, params={"q": name}, timeout=5)
            resp.raise_for_status()
            locations = resp.json()
            for loc in locations:
                if loc['name'].lower() == name.lower():
                    return loc['id']
            
            # 2. Create if not found
            resp = requests.post(f"{self.api_url}/locations", headers=headers, json={"name": name}, timeout=5)
            resp.raise_for_status()
            return resp.json()['id']
        except Exception as e:
            logger.error(f"Homebox location error: {e}")
            return None

    async def execute(self, data: Dict[str, Any], image_path: Optional[str] = None) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        try:
            # Step 1: Create basic item
            location_id = None
            if data.get('location'):
                location_id = self.find_or_create_location(data['location'])

            create_payload = {
                "name": data.get('product_name') or data.get('name'),
                "quantity": int(data.get('quantity', 1)),
                "description": data.get('description', ''),
                "locationId": location_id
            }
            
            # Note: Homebox API often doesn't accept tagIds in create if they don't exist yet, 
            # so we'll skip tags in step 1 or just pass them if they are IDs.
            if data.get('tag_ids'):
                create_payload['tagIds'] = data['tag_ids']

            resp = requests.post(f"{self.api_url}/items", headers=headers, json=create_payload, timeout=5)
            resp.raise_for_status()
            item = resp.json()
            item_id = item['id']

            # Step 2: Update with extended metadata (Homebox v0.22+ pattern)
            update_payload = {
                "manufacturer": data.get('manufacturer') or data.get('brand') or "",
                "modelNumber": data.get('model_number') or "",
                "serialNumber": data.get('serial_number') or "",
                "purchasePrice": float(data.get('purchase_price') or 0),
                "notes": data.get('notes') or ""
            }
            
            # Also append technical details to description if needed, or put in notes
            if data.get('technical_details'):
                if update_payload['notes']:
                    update_payload['notes'] += f"\n\n--- Specs ---\n{data['technical_details']}"
                else:
                    update_payload['notes'] = f"--- Specs ---\n{data['technical_details']}"

            update_resp = requests.put(f"{self.api_url}/items/{item_id}", headers=headers, json=update_payload, timeout=5)
            update_resp.raise_for_status()

            # Step 3: Upload attachment if image_path exists
            if image_path and os.path.exists(f"data/uploads/{image_path}"):
                with open(f"data/uploads/{image_path}", "rb") as f:
                    files = {"file": (image_path, f, "image/jpeg")}
                    attach_data = {"type": "photo", "name": "Vision Capture"}
                    # The endpoint might be /items/{id}/attachments
                    requests.post(f"{self.api_url}/items/{item_id}/attachments", headers=headers, files=files, data=attach_data, timeout=10)

            return {"success": True, "item_id": item_id}
        except Exception as e:
            logger.error(f"Homebox execution failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Search for existing items to prevent duplicates."""
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
        """Return the combined payload for Homebox (Create + Update)."""
        return {
            "step_1_create": {
                "name": data.get('product_name') or data.get('name'),
                "quantity": int(data.get('quantity', 1)),
                "description": data.get('description', ''),
                "location": data.get('location', 'pantry')
            },
            "step_2_update": {
                "manufacturer": data.get('manufacturer') or data.get('brand') or "",
                "modelNumber": data.get('model_number') or "",
                "serialNumber": data.get('serial_number') or "",
                "purchasePrice": float(data.get('purchase_price') or 0),
                "notes": data.get('notes') or "",
                "technical_details": data.get('technical_details', '')
            }
        }
