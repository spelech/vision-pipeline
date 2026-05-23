# Service Integrations Guide

Vision Pipeline can dispatch identified data to various home services.

## Adding a New Service

1. **Create Service Wrapper**: Create a new file in `src/services/your_service.py`.
2. **Inherit from BaseService**:
```python
from .base import BaseService

class YourService(BaseService):
    def get_payload(self, data: dict) -> dict:
        # Convert internal data to service-specific JSON
        return {"name": data.get("product_name")}
        
    async def execute(self, data: dict, image_path: str = None) -> dict:
        # Perform the actual API call
        return {"success": True}
```
3. **Register in `app.py`**:
```python
from services.your_service import YourService
SERVICES["yourservice"] = YourService()
```

## Existing Services
- **Homebox**: Full inventory management.
- **Mealie**: Recipe and pantry tracking.
- **PriceBuddy**: Price monitoring.
- **ChangeDetection**: Web visual/JSON-LD change tracking.
