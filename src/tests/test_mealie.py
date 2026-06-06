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
        assert res["existing_recipes_total"] == 1


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


@pytest.mark.asyncio
async def test_mealie_execute_without_api_key_returns_error():
    service = MealieService()
    service.api_key = None

    result = await service.execute({"product_name": "No Key"})
    assert result == {"success": False, "error": "No API Key"}


@pytest.mark.asyncio
async def test_mealie_execute_external_id_404_falls_back_to_create():
    service = MealieService()
    service.api_key = "test_key"

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        mock_get.return_value.status_code = 404
        mock_post.return_value.status_code = 201
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"id": "new-id"}

        result = await service.execute({"product_name": "Fallback"}, external_id="old-id")

        assert result["success"] is True
        assert result["item_id"] == "new-id"
        assert mock_get.called
        assert mock_post.called


@pytest.mark.asyncio
async def test_mealie_pre_enrichment_guard_paths():
    service = MealieService()
    service.api_key = None
    assert await service.get_pre_enrichment({"product_name": "Anything"}) == {}

    service.api_key = "test_key"
    assert await service.get_pre_enrichment({}) == {}


@pytest.mark.asyncio
async def test_mealie_pre_enrichment_non_200_returns_empty_items():
    service = MealieService()
    service.api_key = "test_key"

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 500
        mock_get.return_value.json.return_value = {}
        res = await service.get_pre_enrichment({"product_name": "x"})
        assert res == {"existing_recipes": [], "existing_recipes_total": 0}


def test_mealie_name_property():
    service = MealieService()
    assert service.name == "mealie"


@pytest.mark.asyncio
async def test_mealie_execute_update_existing_recipe():
    service = MealieService()
    service.api_key = "test_key"

    data = {
        "product_name": "Existing Recipe",
        "description": "Updated description",
        "recipe_ingredients": ["ingredient A", "ingredient B"],
        "recipe_instructions": ["Step 1", "Step 2"]
    }

    with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None

        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status.return_value = None

        result = await service.execute(data, external_id="recipe-123")

        assert result["success"] is True
        assert result["item_id"] == "recipe-123"
        assert mock_get.called
        assert mock_put.called

        args, kwargs = mock_put.call_args
        payload = kwargs["json"]
        assert payload["name"] == "Existing Recipe"
        assert payload["recipeIngredients"] == [{"note": "ingredient A"}, {"note": "ingredient B"}]
        assert payload["recipeInstructions"] == [{"text": "Step 1"}, {"text": "Step 2"}]


@pytest.mark.asyncio
async def test_mealie_execute_request_exception():
    import requests
    service = MealieService()
    service.api_key = "test_key"

    with patch("requests.get", side_effect=requests.RequestException("connection error")):
        result = await service.execute({"product_name": "Fail"}, external_id="recipe-123")
        assert result["success"] is False
        assert "connection error" in result["error"]


@pytest.mark.asyncio
async def test_mealie_pre_enrichment_request_exception():
    import requests
    service = MealieService()
    service.api_key = "test_key"

    with patch("requests.get", side_effect=requests.RequestException("conn error")):
        res = await service.get_pre_enrichment({"product_name": "x"})
        assert res == {}


def test_mealie_payload_uses_camelcase_recipe_overrides():
    service = MealieService()
    payload = service.get_payload({
        "recipeIngredients": [{"note": "1 tsp vanilla"}, "2 eggs"],
        "recipeInstructions": [{"text": "Stir well"}, "Bake at 350"]
    })
    
    assert payload["recipeIngredients"] == [{"note": "1 tsp vanilla"}, {"note": "2 eggs"}]
    assert payload["recipeInstructions"] == [{"text": "Stir well"}, {"text": "Bake at 350"}]


