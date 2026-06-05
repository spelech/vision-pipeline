import base64
import io
import os
from typing import Any, Optional
from PIL import Image

REVIEW_IMAGE_MAX_DIM = int(os.getenv("REVIEW_IMAGE_MAX_DIM", "1280"))
REVIEW_IMAGE_JPEG_QUALITY = int(os.getenv("REVIEW_IMAGE_JPEG_QUALITY", "72"))


def encode_image_bytes_to_data_uri(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def decode_data_uri_to_bytes(data_uri: str) -> bytes:
    if not isinstance(data_uri, str) or "," not in data_uri:
        raise ValueError("Invalid data URI")
    encoded = data_uri.split(",", 1)[1]
    return base64.b64decode(encoded)


def build_review_image_data_uri(img: Image.Image) -> str:
    preview_img = img.copy()
    if preview_img.mode in ("RGBA", "P"):
        preview_img = preview_img.convert("RGB")
    preview_img.thumbnail((REVIEW_IMAGE_MAX_DIM, REVIEW_IMAGE_MAX_DIM))

    out = io.BytesIO()
    preview_img.save(
        out,
        format="JPEG",
        quality=REVIEW_IMAGE_JPEG_QUALITY,
        optimize=True,
    )
    return encode_image_bytes_to_data_uri(out.getvalue(), mime="image/jpeg")


def build_seed_image_data_uri() -> str:
    """Generate a tiny placeholder image for text-only receipt items."""
    img = Image.new("RGB", (64, 64), color=(250, 250, 250))
    return build_review_image_data_uri(img)


def item_source_image_data_uri(item: Any) -> Optional[str]:
    raw_value = getattr(item, "raw_image_path", None)
    preview_value = getattr(item, "image_path", None)
    candidates = [raw_value, preview_value]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("data:image"):
            return candidate
    return None
