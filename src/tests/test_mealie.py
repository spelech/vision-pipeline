import pytest
from unittest.mock import patch
from services.mealie import MealieService

@pytest.mark.asyncio
async def test_mealie_execution_new_recipe():
    service = MealieService()
    service.api_key = "test_key"

    data = {
        "product_name": "Test Recipe",
        "description": "A delicious test",
        "recipe_ingredients_raw": "1 cup sugar\n2 cups flour",
        "recipe_instructions_raw": "Mix.\nBake."
    }

    with patch("requests.post") as mock_post, patch("requests.put") as mock_put:
        # Mock creating recipe
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "recipe-id-123"}
        mock_post.return_value.raise_for_status.return_value = None

        # Mock updating recipe with data
        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status.return_value = None

        result = await service.execute(data)

        assert result["success"] is True
        assert result["item_id"] == "recipe-id-123"
        assert mock_post.called
        # Note: In the actual implementation, it only posts, it doesn't do a secondary put if no external_id is provided.
        assert not mock_put.called

        # Verify post payload
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["name"] == "Test Recipe"
        assert payload["description"] == "A delicious test"
        assert len(payload["recipeInstructions"]) == 2
        assert len(payload["recipeIngredients"]) == 2

@pytest.mark.asyncio
async def test_mealie_pre_enrichment():
    service = MealieService()
    service.api_key = "test_key"

    with patch("requests.get") as mock_get:
        # Mock searching recipe
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "items": [{"id": "recipe-id-123", "name": "Found Recipe"}]
        }

        res = await service.get_pre_enrichment({"product_name": "Found Recipe"})
        assert "existing_recipes" in res
        assert res["existing_recipes"][0]["id"] == "recipe-id-123"


def test_mealie_get_payload():
    service = MealieService()

    payload = service.get_payload(
        {
            "product_name": "Tomato Soup",
            "description": "Simple soup",
            "recipe_ingredients_raw": "2 tomatoes\n1 tsp salt\n",
            "recipe_instructions_raw": "Blend\nSimmer\n",
            "yield": "2 servings",
        }
    )

    assert payload == {
        "name": "Tomato Soup",
        "description": "Simple soup",
        "recipeIngredients": [{"note": "2 tomatoes"}, {"note": "1 tsp salt"}],
        "recipeInstructions": [{"text": "Blend"}, {"text": "Simmer"}],
        "yield": "2 servings",
    }
