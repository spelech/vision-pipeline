import os
from typing import List
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import ConfigSecret

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

ORIGINAL_ENV = dict(os.environ)

# Get or create encryption key
MASTER_KEY = os.getenv("ENCRYPTION_KEY")
if not MASTER_KEY:
    MASTER_KEY = Fernet.generate_key().decode()
    ENV_PATH = ".env" if os.path.exists(".env") else "../.env"
    with open(ENV_PATH, "a", encoding="utf-8") as f:
        f.write(f"\nENCRYPTION_KEY={MASTER_KEY}\n")
    os.environ["ENCRYPTION_KEY"] = MASTER_KEY

cipher = Fernet(MASTER_KEY.encode())


def encrypt_secret(val: str) -> str:
    return cipher.encrypt(val.encode()).decode()


def decrypt_secret(val: str) -> str:
    return cipher.decrypt(val.encode()).decode()


CONFIG_SECRET_KEYS: List[str] = [
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "OPENROUTER_API_KEY",
    "SEARXNG_URL",
    "HOMEBOX_URL",
    "MEALIE_URL",
    "PRICEBUDDY_URL",
    "CHANGEDETECTION_URL",
    "HOMEBOX_USERNAME",
    "HOMEBOX_PASSWORD",
    "MEALIE_API_TOKEN",
    "PRICEBUDDY_API_KEY",
    "CHANGEDETECTION_API_KEY",
    "GWS_CLIENT_ID",
    "GWS_CLIENT_SECRET",
    "GWS_REFRESH_TOKEN",
    "UPCITEMDB_API_KEY",
    "RECEIPT_WRANGLER_URL",
    "RECEIPT_WRANGLER_API_TOKEN",
    "RECEIPT_WRANGLER_API_KEY",
    "RECEIPT_WRANGLER_GROUP_ID",
    "GMAIL_OCR_BACKEND",
    "GMAIL_OCR_VISION_MODEL",
    "VISION_MODEL_DEFAULT",
    "REFINE_MODEL_DEFAULT",
]


def get_secret_value(key: str) -> str:
    direct_value = os.getenv(key)
    if direct_value:
        return direct_value

    aliases = {
        "LLM_API_KEY": "OPENROUTER_API_KEY",
        "OPENROUTER_API_KEY": "LLM_API_KEY",
        "RECEIPT_WRANGLER_API_KEY": "RECEIPT_WRANGLER_API_TOKEN",
        "RECEIPT_WRANGLER_API_TOKEN": "RECEIPT_WRANGLER_API_KEY",
    }
    alias_key = aliases.get(key)
    if alias_key:
        return os.getenv(alias_key) or ""
    return ""


def set_secret_value(key: str, val: str) -> None:
    os.environ[key] = val


async def upsert_secret(db: AsyncSession, key: str, value: str) -> None:
    set_secret_value(key, value)
    encrypted = encrypt_secret(value)
    result = await db.execute(select(ConfigSecret).where(ConfigSecret.key == key))
    secret_obj = result.scalar_one_or_none()
    if secret_obj:
        secret_obj.encrypted_value = encrypted  # type: ignore
    else:
        db.add(ConfigSecret(key=key, encrypted_value=encrypted))

async def refresh_secrets_from_db(db: AsyncSession) -> None:
    """
    Reloads all secrets from the database into the environment.
    """
    res = await db.execute(select(ConfigSecret))
    secrets = res.scalars().all()
    for secret in secrets:
        try:
            os.environ[secret.key] = decrypt_secret(secret.encrypted_value)
        except Exception:
            pass
