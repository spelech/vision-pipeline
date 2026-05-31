import logging
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class ReceiptWranglerClient:
    """Small API client for selective Receipt Wrangler sync."""

    def __init__(self, secret_getter: Callable[[str], str]):
        self._get_secret = secret_getter

    def configured(self) -> bool:
        return bool(
            self._get_secret("RECEIPT_WRANGLER_URL")
            and self._api_token()
        )

    def _api_token(self) -> str:
        return (
            self._get_secret("RECEIPT_WRANGLER_API_KEY").strip()
            or self._get_secret("RECEIPT_WRANGLER_API_TOKEN").strip()
        )

    def default_group_id(self) -> str:
        return self._get_secret("RECEIPT_WRANGLER_GROUP_ID").strip()

    def _base_url(self) -> str:
        base_url = self._get_secret("RECEIPT_WRANGLER_URL").strip()
        if not base_url:
            raise ValueError("Missing RECEIPT_WRANGLER_URL")
        return base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        api_token = self._api_token()
        if not api_token:
            raise ValueError("Missing RECEIPT_WRANGLER_API_KEY/RECEIPT_WRANGLER_API_TOKEN")
        return {"Authorization": f"Bearer {api_token}"}

    def quick_scan_attachment(
        self,
        file_bytes: bytes,
        filename: str,
        group_id: Optional[str] = None,
        mime_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        if not file_bytes:
            raise ValueError("Attachment bytes are empty")

        selected_group_id = (group_id or self.default_group_id()).strip()
        if not selected_group_id:
            raise ValueError("Missing receipt wrangler group id")

        response = requests.post(
            f"{self._base_url()}/api/receipt/quickScan",
            headers=self._headers(),
            files={
                "files": (filename or "receipt.bin", file_bytes, mime_type),
            },
            data={
                "groupIds": selected_group_id,
            },
            timeout=30,
        )
        response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            logger.warning("Receipt Wrangler quickScan returned non-JSON response")
            return {"success": True}

    def get_pending_receipts(self, limit: int = 50) -> list[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 200))
        response = requests.get(
            f"{self._base_url()}/api/receipt",
            headers=self._headers(),
            params={"status": "OPEN", "take": str(safe_limit)},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        receipts = payload if isinstance(payload, list) else payload.get("receipts", [])
        if isinstance(receipts, list):
            return [item for item in receipts if isinstance(item, dict)]
        return []

    def download_receipt_image(self, image_id: str) -> bytes:
        if not image_id:
            raise ValueError("Missing receipt image id")

        response = requests.get(
            f"{self._base_url()}/api/receipt/image/{image_id}",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    def update_receipt_status(self, receipt_id: str, status: str = "RESOLVED") -> Dict[str, Any]:
        if not receipt_id:
            raise ValueError("Missing receipt id")

        response = requests.patch(
            f"{self._base_url()}/api/receipt/{receipt_id}",
            headers=self._headers(),
            json={"status": status},
            timeout=20,
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"success": True, "receipt_id": receipt_id, "status": status}
