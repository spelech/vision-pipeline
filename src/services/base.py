from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseService(ABC):
    """Base interface for all external services (Homebox, Mealie, etc.)."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The identifier of the service (e.g., 'homebox')."""
        pass

    @abstractmethod
    async def execute(self, data: Dict[str, Any], image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the service-specific logic.
        :param data: The extracted metadata from the core pipeline or user overrides.
        :param image_path: Path to the original image if needed for upload.
        :return: Result dict with success/failure and any relevant metadata.
        """
        pass

    @abstractmethod
    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform any service-specific search or validation before execution.
        (e.g., searching for existing items in Homebox/Mealie).
        """
        pass
