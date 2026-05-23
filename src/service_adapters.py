import os
import requests
from dotenv import load_dotenv

load_dotenv()

class HomeboxAdapter:
    def __init__(self):
        self.api_url = os.getenv("HOMEBOX_URL", "http://homebox:7745/api/v1")
        self.api_key = os.getenv("HOMEBOX_API_KEY")
        self.username = os.getenv("HOMEBOX_USERNAME")
        self.password = os.getenv("HOMEBOX_PASSWORD")
        self._token = None

    def login(self):
        """Login to Homebox to get a session token."""
        if not self.username or not self.password:
            return None
        
        try:
            # Homebox login endpoint expects form-urlencoded
            payload = {
                "username": self.username,
                "password": self.password
            }
            response = requests.post(f"{self.api_url}/users/login", data=payload, timeout=5)
            response.raise_for_status()
            token = response.json().get("token")
            # Ensure Bearer prefix is present
            if token and not token.startswith("Bearer "):
                token = f"Bearer {token}"
            self._token = token
            return self._token
        except Exception as e:
            print(f"Homebox login error: {e}")
            return None

    def get_headers(self):
        """Get the appropriate authorization headers."""
        if self.api_key and not self.api_key.startswith("your_"):
            token = self.api_key
            if not token.startswith("Bearer "):
                token = f"Bearer {token}"
            return {"Authorization": token}
        
        if not self._token:
            self.login()
            
        if self._token:
            return {"Authorization": self._token}
        
        return {}

    def search_items(self, query):
        """Search for items in Homebox."""
        headers = self.get_headers()
        if not headers:
            return []
        
        try:
            params = {"q": query}
            response = requests.get(f"{self.api_url}/items", headers=headers, params=params, timeout=5)
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            print(f"Homebox search error: {e}")
            return []

    def list_locations(self):
        """List all locations in Homebox."""
        headers = self.get_headers()
        if not headers:
            return []
        try:
            response = requests.get(f"{self.api_url}/locations", headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            # Homebox v0.25+ returns a bare list of locations
            if isinstance(data, list):
                return data
            return data.get("locations", [])
        except Exception as e:
            print(f"Homebox list locations error: {e}")
            return []

    def find_or_create_location(self, name):
        """Find a location by name or create it if missing."""
        locations = self.list_locations()
        for loc in locations:
            if loc['name'].lower() == name.lower():
                return loc['id']
        
        # Create it
        headers = self.get_headers()
        try:
            payload = {"name": name}
            response = requests.post(f"{self.api_url}/locations", headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            return response.json().get("id")
        except Exception as e:
            print(f"Homebox create location error: {e}")
            return None

    def create_item(self, name, description, location_id=None, quantity=1, unit=None, msrp=None, product_url=None, 
                    manufacturer=None, model_number=None, serial_number=None, purchase_price=0, notes=None, technical_details=None):
        """Create a new item in Homebox with full fidelity metadata."""
        headers = self.get_headers()
        if not headers:
            return None
        
        try:
            full_description = description or ""
            
            metadata_parts = []
            if msrp: metadata_parts.append(f"MSRP: {msrp}")
            if product_url: metadata_parts.append(f"Link: {product_url}")
            if technical_details: metadata_parts.append(f"Specs: {technical_details}")
            
            if metadata_parts:
                full_description += "\n\n--- Metadata ---\n" + "\n".join(metadata_parts)

            payload = {
                "name": name,
                "description": full_description,
                "quantity": quantity,
                "manufacturer": manufacturer or "",
                "modelNumber": model_number or "",
                "serialNumber": serial_number or "",
                "purchasePrice": float(purchase_price or 0),
                "notes": notes or ""
            }
            if location_id:
                payload["locationId"] = location_id
            if unit:
                payload["unit"] = unit
            
            response = requests.post(f"{self.api_url}/items", headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Homebox creation error: {e}")
            return None

    def get_item(self, item_id):
        """Get a specific item by ID from Homebox."""
        headers = self.get_headers()
        if not headers:
            return None
        try:
            response = requests.get(f"{self.api_url}/items/{item_id}", headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Homebox get error: {e}")
            return None

    def update_item(self, item_id, item_data):
        """Update an existing item in Homebox."""
        headers = self.get_headers()
        if not headers:
            return None
        try:
            # Fetch current to ensure we don't wipe fields
            current = self.get_item(item_id)
            if not current:
                return None
            
            current.update(item_data)
            
            response = requests.put(f"{self.api_url}/items/{item_id}", headers=headers, json=current, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Homebox update error: {e}")
            return None

class PriceBuddyAdapter:
    def __init__(self):
        self.api_url = os.getenv("PRICEBUDDY_URL", "http://10.0.0.10:8420/api")
        self.api_key = os.getenv("PRICEBUDDY_API_KEY")

    def add_product(self, url, name=None):
        """Add a product URL to PriceBuddy for tracking."""
        if not self.api_key:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
            payload = {"url": url}
            if name:
                payload["name"] = name
            response = requests.post(f"{self.api_url}/products", headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"PriceBuddy error: {e}")
            return None

class ChangeDetectionAdapter:
    def __init__(self):
        self.api_url = os.getenv("CHANGEDETECTION_URL", "http://10.0.0.10:8407/api/v1")
        self.api_key = os.getenv("CHANGEDETECTION_API_KEY")

    def add_watch(self, url, tag=None):
        """Add a URL watch to ChangeDetection."""
        if not self.api_key:
            return None

        try:
            headers = {"x-api-key": self.api_key}
            payload = {
                "url": url,
                "tag": tag or "vision-pipeline"
            }
            response = requests.post(f"{self.api_url}/watch", headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"ChangeDetection error: {e}")
            return None

class MealieAdapter:
    def __init__(self):
        self.api_url = os.getenv("MEALIE_URL", "http://10.0.0.10:8430/api")
        self.api_token = os.getenv("MEALIE_API_TOKEN")

    def search_recipes(self, query):
        """Search for recipes in Mealie."""
        if not self.api_token:
            return []
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            params = {"query": query}
            response = requests.get(f"{self.api_url}/recipes", headers=headers, params=params, timeout=5)
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            print(f"Mealie search error: {e}")
            return []

    def create_recipe(self, recipe_data):
        """Create a new recipe in Mealie."""
        if not self.api_token:
            return None
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            response = requests.post(f"{self.api_url}/recipes", headers=headers, json=recipe_data, timeout=5)
            if not response.ok:
                print(f"Mealie creation failed ({response.status_code}): {response.text}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Mealie creation error: {e}")
            return None

    def search_foods(self, query):
        """Search for food items in Mealie."""
        if not self.api_token:
            return []
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            params = {"perPage": 10, "query": query}
            response = requests.get(f"{self.api_url}/foods", headers=headers, params=params, timeout=5)
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            print(f"Mealie food search error: {e}")
            return []

    def create_food(self, food_data):
        """Create a new food item in Mealie."""
        if not self.api_token:
            return None
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            response = requests.post(f"{self.api_url}/foods", headers=headers, json=food_data, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Mealie food creation error: {e}")
            return None

    def get_food(self, food_id):
        """Get a specific food item by ID."""
        if not self.api_token:
            return None
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            response = requests.get(f"{self.api_url}/foods/{food_id}", headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Mealie get food error: {e}")
            return None

    def update_food(self, food_id, food_data):
        """Update an existing food item in Mealie. Safe read-modify-write with dict merging."""
        if not self.api_token:
            return None
        try:
            # 1. Fetch existing data
            current_food = self.get_food(food_id)
            if not current_food:
                return None
            
            # 2. Merge extras if present
            new_extras = food_data.pop('extras', {})
            if 'extras' not in current_food or current_food['extras'] is None:
                current_food['extras'] = {}
            current_food['extras'].update(new_extras)
            
            # 3. Merge rest of the data
            current_food.update(food_data)
            
            # 4. PUT back
            headers = {"Authorization": f"Bearer {self.api_token}"}
            response = requests.put(f"{self.api_url}/foods/{food_id}", headers=headers, json=current_food, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Mealie food update error: {e}")
            return None

    def add_shopping_list_item(self, item_name, quantity=1, note=None):
        """Add an item to the Mealie shopping list."""
        if not self.api_token:
            return None
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            # Note: Mealie v1.0+ often uses /api/households/shopping/items
            # We'll try the common path or handle versioning if needed.
            payload = {
                "note": item_name,
                "quantity": quantity,
                "display": f"{quantity} x {item_name}" if not note else f"{quantity} x {item_name} ({note})"
            }
            # Trying household-based shopping list endpoint
            response = requests.post(f"{self.api_url}/households/shopping/items", headers=headers, json=payload, timeout=5)
            if response.status_code == 404:
                # Fallback to legacy path
                response = requests.post(f"{self.api_url}/shopping-list/items", headers=headers, json=payload, timeout=5)
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Mealie shopping list error: {e}")
            return None
