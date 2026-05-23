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

    async def execute(self, data: Dict[str, Any], image_path: Optional[str] = None, external_id: Optional[str] = None) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        try:
            recipe_id = external_id
            
            # Check if exists
            if recipe_id:
                check = requests.get(f"{self.api_url}/recipes/{recipe_id}", headers=headers, timeout=5)
                if check.status_code == 404:
                    recipe_id = None

            ingredients = data.get('recipe_ingredients', [])
            if not ingredients and data.get('recipe_ingredients_raw'):
                ingredients = data['recipe_ingredients_raw'].split('\n')
                
            instructions = data.get('recipe_instructions', [])
            if not instructions and data.get('recipe_instructions_raw'):
                instructions = data['recipe_instructions_raw'].split('\n')

            recipe_payload = {
                "name": data.get('product_name') or data.get('name'),
                "description": data.get('description', ''),
                "recipeIngredients": [{"note": i} for i in ingredients if i.strip()],
                "recipeInstructions": [{"text": i} for i in instructions if i.strip()],
                "yield": data.get('yield', '1 serving')
            }

            if recipe_id:
                resp = requests.put(f"{self.api_url}/recipes/{recipe_id}", headers=headers, json=recipe_payload, timeout=10)
                resp.raise_for_status()
            else:
                resp = requests.post(f"{self.api_url}/recipes", headers=headers, json=recipe_payload, timeout=10)
                resp.raise_for_status()
                recipe = resp.json()
                recipe_id = recipe.get('id')
            
            # TODO: Handle image upload
            
            return {
                "success": True, 
                "item_id": recipe_id,
                "url": f"{self.api_url.replace('/api', '')}/recipe/{recipe_id}" # UI URL
            }
        except Exception as e:
            logger.error(f"Mealie execution failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers: return {}
        name = data.get('product_name') or data.get('name')
        if not name: return {}
        try:
            resp = requests.get(f"{self.api_url}/recipes", headers=headers, params={"query": name}, timeout=5)
            recipes = resp.json().get('items', []) if resp.status_code == 200 else []
            return {"existing_recipes": recipes}
        except Exception:
            return {}

    def get_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ingredients = data.get('recipe_ingredients', [])
        if not ingredients and data.get('recipe_ingredients_raw'):
            ingredients = data['recipe_ingredients_raw'].split('\n')
            
        instructions = data.get('recipe_instructions', [])
        if not instructions and data.get('recipe_instructions_raw'):
            instructions = data['recipe_instructions_raw'].split('\n')

        return {
            "name": data.get('product_name') or data.get('name'),
            "description": data.get('description', ''),
            "recipeIngredients": [{"note": i} for i in ingredients if i.strip()],
            "recipeInstructions": [{"text": i} for i in instructions if i.strip()],
            "yield": data.get('yield', '1 serving')
        }
