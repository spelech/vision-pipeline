import asyncio
import logging
import os
from typing import Any, Dict, Optional

import requests
from .base import BaseService

logger = logging.getLogger(__name__)


class MealieService(BaseService):
    def __init__(self):
        self.api_url = os.getenv("MEALIE_URL", "http://mealie:9000/api")
        self.api_key = os.getenv("MEALIE_API_TOKEN")

    @property
    def name(self) -> str:
        return "mealie"

    def _get_headers(self):
        if not self.api_key:
            return None
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _request(self, method: str, endpoint: str, **
                       kwargs: Any) -> requests.Response:
        request_method = getattr(requests, method.lower())
        return await asyncio.to_thread(request_method, f"{self.api_url}{endpoint}", **kwargs)

    async def execute(self,
                      data: Dict[str,
                                 Any],
                      image_path: Optional[str] = None,
                      external_id: Optional[str] = None) -> Dict[str,
                                                                 Any]:
        headers = self._get_headers()
        if not headers:
            return {"success": False, "error": "No API Key"}

        try:
            recipe_id = external_id

            # Check if exists
            if recipe_id:
                check = await self._request(
                    "GET", f"/recipes/{recipe_id}", headers=headers, timeout=5
                )
                if check.status_code == 404:
                    recipe_id = None

            ingredients = self._parse_ingredients(data)
            instructions = self._parse_instructions(data)

            recipe_payload = {
                "name": data.get('product_name') or data.get('name'),
                "description": data.get('description', ''),
                "recipeIngredients": [{"note": i} for i in ingredients if i.strip()],
                "recipeInstructions": [{"text": i} for i in instructions if i.strip()],
                "yield": data.get('yield', '1 serving')
            }

            if recipe_id:
                resp = await self._request(
                    "PUT",
                    f"/recipes/{recipe_id}",
                    headers=headers,
                    json=recipe_payload,
                    timeout=10,
                )
                resp.raise_for_status()
            else:
                resp = await self._request(
                    "POST",
                    "/recipes",
                    headers=headers,
                    json=recipe_payload,
                    timeout=10,
                )
                resp.raise_for_status()
                recipe = resp.json()
                recipe_id = recipe.get('id')

            # Image upload not yet supported by Mealie API integration.

            return {
                "success": True,
                "item_id": recipe_id,
                # UI URL
                "url": f"{self.api_url.replace('/api', '')}/recipe/{recipe_id}"
            }
        except requests.RequestException as e:
            logger.error("Mealie execution failed: %s", e)
            return {"success": False, "error": str(e)}

    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        headers = self._get_headers()
        if not headers:
            return {}
        name = data.get('product_name') or data.get('name')
        if not name:
            return {}
        try:
            resp = await self._request(
                "GET",
                "/recipes",
                headers=headers,
                params={"query": name},
                timeout=5,
            )
            recipes = resp.json().get('items', []) if resp.status_code == 200 else []
            return {
                "existing_recipes": recipes[:5],
                "existing_recipes_total": len(recipes),
            }
        except requests.RequestException:
            return {}

    def get_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ingredients = self._parse_ingredients(data)
        instructions = self._parse_instructions(data)

        return {
            "name": data.get('product_name') or data.get('name'),
            "description": data.get('description', ''),
            "recipeIngredients": [{"note": i} for i in ingredients if i.strip()],
            "recipeInstructions": [{"text": i} for i in instructions if i.strip()],
            "yield": data.get('yield', '1 serving')
        }

    def _parse_ingredients(self, data: Dict[str, Any]) -> list[str]:
        # 1. Check camelCase recipeIngredients (form input)
        raw_ing = data.get('recipeIngredients')
        if isinstance(raw_ing, list):
            parsed = []
            for x in raw_ing:
                if isinstance(x, dict):
                    note = x.get('note') or x.get('text') or ''
                    if note:
                        parsed.append(str(note))
                elif isinstance(x, str):
                    parsed.append(x)
            if parsed:
                return parsed

        # 2. Check snake_case recipe_ingredients
        raw_ing = data.get('recipe_ingredients')
        if isinstance(raw_ing, list):
            return [str(x) for x in raw_ing if x]

        # 3. Check recipe_ingredients_raw string
        raw_ing_str = data.get('recipe_ingredients_raw')
        if isinstance(raw_ing_str, str) and raw_ing_str.strip():
            return [x.strip() for x in raw_ing_str.split('\n') if x.strip()]

        return []

    def _parse_instructions(self, data: Dict[str, Any]) -> list[str]:
        # 1. Check camelCase recipeInstructions (form input)
        raw_inst = data.get('recipeInstructions')
        if isinstance(raw_inst, list):
            parsed = []
            for x in raw_inst:
                if isinstance(x, dict):
                    text = x.get('text') or x.get('note') or ''
                    if text:
                        parsed.append(str(text))
                elif isinstance(x, str):
                    parsed.append(x)
            if parsed:
                return parsed

        # 2. Check snake_case recipe_instructions
        raw_inst = data.get('recipe_instructions')
        if isinstance(raw_inst, list):
            return [str(x) for x in raw_inst if x]

        # 3. Check recipe_instructions_raw string
        raw_inst_str = data.get('recipe_instructions_raw')
        if isinstance(raw_inst_str, str) and raw_inst_str.strip():
            return [x.strip() for x in raw_inst_str.split('\n') if x.strip()]

        return []
