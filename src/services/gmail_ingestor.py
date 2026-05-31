import logging
import base64
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
PRICE_PATTERN = re.compile(r"\$?\d{1,6}\.\d{2}")
IGNORE_LINE_PREFIXES = (
    "subtotal",
    "tax",
    "shipping",
    "total",
    "order total",
    "discount",
)


class GmailIngestor:
    """Gmail OAuth and search helper for receipt ingestion."""

    def __init__(self, secret_getter: Callable[[str], str]):
        self._get_secret = secret_getter

    def oauth_configured(self) -> bool:
        return bool(self._get_secret("GWS_CLIENT_ID") and self._get_secret("GWS_CLIENT_SECRET"))

    def connected(self) -> bool:
        return bool(self._get_secret("GWS_REFRESH_TOKEN"))

    def receipt_wrangler_configured(self) -> bool:
        return bool(
            self._get_secret("RECEIPT_WRANGLER_URL")
            and self._get_secret("RECEIPT_WRANGLER_API_KEY")
        )

    def build_auth_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        client_id = self._get_secret("GWS_CLIENT_ID")
        if not client_id:
            raise ValueError("Missing GWS_CLIENT_ID")
        if not redirect_uri:
            raise ValueError("Missing redirect_uri")

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        if state:
            params["state"] = state
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        client_id = self._get_secret("GWS_CLIENT_ID")
        client_secret = self._get_secret("GWS_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ValueError("Gmail OAuth is not configured")
        if not code:
            raise ValueError("Missing authorization code")
        if not redirect_uri:
            raise ValueError("Missing redirect_uri")

        response = requests.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def _get_access_token(self) -> str:
        client_id = self._get_secret("GWS_CLIENT_ID")
        client_secret = self._get_secret("GWS_CLIENT_SECRET")
        refresh_token = self._get_secret("GWS_REFRESH_TOKEN")
        if not client_id or not client_secret or not refresh_token:
            raise ValueError("Missing Gmail OAuth client credentials or refresh token")

        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ValueError("Failed to obtain Gmail access token")
        return str(token)

    def _api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = self._get_access_token()
        response = requests.get(
            f"{GMAIL_API_BASE}/{path.lstrip('/')}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _decode_base64url(data: str) -> bytes:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8"))

    @staticmethod
    def _extract_header(headers: List[Dict[str, str]], name: str) -> str:
        lower_name = name.lower()
        for header in headers:
            key = str(header.get("name", "")).lower()
            if key == lower_name:
                return str(header.get("value", ""))
        return ""

    @staticmethod
    def _collect_attachment_parts(payload: Dict[str, Any]) -> List[Dict[str, str]]:
        attachments: List[Dict[str, str]] = []

        def visit(part: Dict[str, Any]) -> None:
            filename = str(part.get("filename") or "").strip()
            body_raw = part.get("body")
            body = body_raw if isinstance(body_raw, dict) else {}
            attachment_id = str(body.get("attachmentId") or "").strip()
            if filename and attachment_id:
                attachments.append(
                    {
                        "filename": filename,
                        "attachment_id": attachment_id,
                        "mime_type": str(part.get("mimeType") or ""),
                    }
                )
            sub_parts = part.get("parts")
            if isinstance(sub_parts, list):
                for sub_part in sub_parts:
                    if isinstance(sub_part, dict):
                        visit(sub_part)

        visit(payload)
        return attachments

    @staticmethod
    def _collect_plain_text(payload: Dict[str, Any]) -> str:
        text_parts: List[str] = []

        def decode_part_data(part: Dict[str, Any]) -> str:
            body_raw = part.get("body")
            body = body_raw if isinstance(body_raw, dict) else {}
            encoded = body.get("data")
            if not isinstance(encoded, str) or not encoded:
                return ""
            try:
                decoded = GmailIngestor._decode_base64url(encoded)
                return decoded.decode("utf-8", errors="ignore")
            except (ValueError, UnicodeDecodeError):
                return ""

        def visit(part: Dict[str, Any]) -> None:
            mime_type = str(part.get("mimeType") or "")
            if mime_type.startswith("text/plain"):
                text_value = decode_part_data(part)
                if text_value:
                    text_parts.append(text_value)
            sub_parts_raw = part.get("parts")
            sub_parts = sub_parts_raw if isinstance(sub_parts_raw, list) else []
            for sub_part in sub_parts:
                if isinstance(sub_part, dict):
                    visit(sub_part)

        visit(payload)
        merged = "\n".join(text_parts).strip()
        return merged[:10000]

    @staticmethod
    def _parse_message(message: Dict[str, Any]) -> Dict[str, Any]:
        payload_raw = message.get("payload")
        payload: Dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}

        headers_raw = payload.get("headers")
        headers = headers_raw if isinstance(headers_raw, list) else []
        headers_list = [h for h in headers if isinstance(h, dict)]

        subject = GmailIngestor._extract_header(headers_list, "Subject")
        sender = GmailIngestor._extract_header(headers_list, "From")
        date_raw = GmailIngestor._extract_header(headers_list, "Date")

        sent_at = ""
        if date_raw:
            try:
                parsed = parsedate_to_datetime(date_raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                sent_at = parsed.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                sent_at = ""

        attachments = GmailIngestor._collect_attachment_parts(payload)
        plain_text = GmailIngestor._collect_plain_text(payload)

        return {
            "message_id": str(message.get("id") or ""),
            "thread_id": str(message.get("threadId") or ""),
            "subject": subject,
            "from": sender,
            "snippet": str(message.get("snippet") or ""),
            "sent_at": sent_at,
            "internal_date": str(message.get("internalDate") or ""),
            "attachments": attachments,
            "has_attachments": len(attachments) > 0,
            "plain_text": plain_text,
        }

    @staticmethod
    def extract_line_items_from_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        # pylint: disable=too-many-locals
        subject = str(message.get("subject") or "").strip()
        snippet = str(message.get("snippet") or "").strip()
        plain_text = str(message.get("plain_text") or "").strip()

        candidate_lines: List[str] = []
        for source_text in [plain_text, snippet]:
            if not source_text:
                continue
            for line in source_text.splitlines():
                normalized = " ".join(line.split()).strip()
                if normalized:
                    candidate_lines.append(normalized)

        items: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for line in candidate_lines:
            line_lower = line.lower()
            if any(line_lower.startswith(prefix) for prefix in IGNORE_LINE_PREFIXES):
                continue
            has_price = bool(PRICE_PATTERN.search(line))
            if not has_price and len(line) < 12:
                continue

            product_name = line
            price_match = PRICE_PATTERN.search(line)
            price_value: Optional[str] = None
            if price_match:
                price_value = price_match.group(0)
                product_name = line[:price_match.start()].strip(" -:") or line

            normalized_key = product_name.lower()
            if normalized_key in seen:
                continue
            seen.add(normalized_key)

            items.append(
                {
                    "name": product_name,
                    "line_text": line,
                    "price": price_value,
                }
            )
            if len(items) >= 50:
                break

        if items:
            return items

        fallback_name = subject or snippet or "Receipt Item"
        return [{"name": fallback_name, "line_text": fallback_name, "price": None}]

    def search_receipts(
        self,
        query: str,
        max_results: int,
        exclude_message_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        exclude_ids = exclude_message_ids or set()
        safe_max = max(1, min(int(max_results), 100))

        listing = self._api_get(
            "messages",
            params={
                "q": query,
                "maxResults": safe_max,
                "includeSpamTrash": "false",
            },
        )

        messages_raw = listing.get("messages")
        minimal_messages = messages_raw if isinstance(messages_raw, list) else []
        detailed_messages: List[Dict[str, Any]] = []
        for item in minimal_messages:
            if not isinstance(item, dict):
                continue
            message_id = str(item.get("id") or "")
            if not message_id or message_id in exclude_ids:
                continue
            try:
                detailed = self._api_get(f"messages/{message_id}", params={"format": "full"})
                detailed_messages.append(self._parse_message(detailed))
            except requests.RequestException as exc:
                logger.warning("Skipping Gmail message %s: %s", message_id, exc)

        return {
            "query": query,
            "message_count": len(detailed_messages),
            "messages": detailed_messages,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_message(self, message_id: str) -> Dict[str, Any]:
        if not message_id:
            raise ValueError("Missing Gmail message id")
        detailed = self._api_get(f"messages/{message_id}", params={"format": "full"})
        return self._parse_message(detailed)

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        if not message_id:
            raise ValueError("Missing Gmail message id")
        if not attachment_id:
            raise ValueError("Missing Gmail attachment id")

        attachment = self._api_get(
            f"messages/{message_id}/attachments/{attachment_id}",
            params=None,
        )
        encoded = attachment.get("data")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("Gmail attachment payload missing data")
        return self._decode_base64url(encoded)
