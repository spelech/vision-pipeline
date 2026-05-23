import os
import requests
import logging
from typing import Any, Dict, Optional
from .base import BaseService

logger = logging.getLogger(__name__)

class MealieService(BaseService):
    def __init__(self):
        self.api_url = os.getenv("MEALIE_URL", "http://mealie:9000/api")
        self.api_key = os.getenv("MEALIE_API_KEY")

    @property
    def name(self) -> str:
        return "mealie"

    def _get_headers(self):
        if not self.api_key:
            return None
        return {"Authorization": f"Bearer {self.api_key}"}

    async def execute(self, data: Dict[str, Any], image_path: Optional[str] = None) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        try:
            # We support three modes: Create Recipe, Add Food (Inventory), Add Shopping List
            # Based on the user's intent or some data flag. 
            # For now, let's implement the standard Recipe creation from extracted data.
            
            recipe_payload = {
                "name": data.get('product_name') or data.get('name'),
                "description": data.get('description', ''),
                "recipeIngredients": [{"note": i} for i in data.get('recipe_ingredients', [])],
                "recipeInstructions": [{"text": i} for i in data.get('recipe_instructions', [])],
                "yield": data.get('yield', '1 serving')
            }

            resp = requests.post(f"{self.api_url}/recipes", headers=headers, json=recipe_payload, timeout=10)
            resp.raise_for_status()
            recipe = resp.json()
            
            # TODO: Handle image upload to recipe if needed
            
            return {"success": True, "recipe_id": recipe.get('id')}
        except Exception as e:
            logger.error(f"Mealie execution failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Search for existing recipes or foods."""
        headers = self._get_headers()
        if not headers: return {}
        name = data.get('product_name') or data.get('name')
        if not name: return {}
        try:
            # Search recipes
            resp = requests.get(f"{self.api_url}/recipes", headers=headers, params={"query": name}, timeout=5)
            recipes = resp.json().get('items', []) if resp.status_code == 200 else []
            
            # Search foods
            f_resp = requests.get(f"{self.api_url}/foods", headers=headers, params={"query": name}, timeout=5)
            foods = f_resp.json().get('items', []) if f_resp.status_code == 200 else []

            return {
                "existing_recipes": recipes,
                "existing_foods": foods
            }
        except Exception:
            return {}
            
    async def create_food(self, data: Dict[str, Any]) -> bool:
        """Helper to create a food item directly (Inventory mode)."""
        headers = self._get_headers()
        try:
            payload = {
                "name": data.get('name'),
                "description": data.get('description'),
                "extras": data.get('extras', {})
            }
            if data.get('id'): # Update existing
                resp = requests.put(f"{self.api_url}/foods/{data['id']}", headers=headers, json=payload, timeout=5)
            else: # Create new
                resp = requests.post(f"{self.api_url}/foods", headers=headers, json=payload, timeout=5)
            return resp.status_code in [200, 201]
        except Exception:
            return False
