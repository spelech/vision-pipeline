from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseService(ABC):
    """Base interface for all external services (Homebox, Mealie, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The identifier of the service (e.g., 'homebox')."""
        return None  # type: ignore[return-value]

    @abstractmethod
    async def execute(self,
                      data: Dict[str,
                                 Any],
                      image_path: Optional[str] = None,
                      external_id: Optional[str] = None) -> Dict[str,
                                                                 Any]:
        """
        Execute the service-specific logic.
        :param data: The extracted metadata from the core pipeline or user overrides.
        :param image_path: Path to the original image if needed for upload.
        :param external_id: Optional ID to update instead of creating.
        :return: Result dict with success/failure and any relevant metadata.
        """
        return None  # type: ignore[return-value]

    @abstractmethod
    async def get_pre_enrichment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform any service-specific search or validation before execution.
        (e.g., searching for existing items in Homebox/Mealie).
        """
        return None  # type: ignore[return-value]

    @abstractmethod
    def get_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return the exact payload that will be sent to the service's API.
        Used for UI previews.
        """
        return None  # type: ignore[return-value]
