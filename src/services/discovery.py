import os
import json
import base64
import socket
import asyncio
import sqlite3
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("DiscoveryService")

class DiscoveryResult(BaseModel):
    success: bool
    discovered_urls: Dict[str, str]
    discovered_gws: Dict[str, str]
    error: Optional[str] = None


async def probe_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Attempt to open a TCP connection to the specified host and port."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def discover_network_services() -> Dict[str, str]:
    """
    Scans typical Docker container DNS names and default localhost ports
    for integrations, returning found URLs.
    """
    # Map service key to (default container host, default localhost port, URL format)
    services_to_probe = {
        "HOMEBOX_URL": ("homebox", 7745, "http://{host}:7745/api/v1"),
        "MEALIE_URL": ("mealie", 9000, "http://{host}:9000/api"),
        "SEARXNG_URL": ("searxng", 8080, "http://{host}:8080"),
        "CHANGEDETECTION_URL": ("changedetection", 5000, "http://{host}:5000"),
        "PRICEBUDDY_URL": ("pricebuddy", 8010, "http://{host}:8010"),
        "RECEIPT_WRANGLER_URL": ("receipt-wrangler", 3000, "http://{host}:3000"),
    }

    discovered = {}

    for env_key, (container_host, port, url_template) in services_to_probe.items():
        # 1. Probe the container name on the docker network
        if await probe_port(container_host, port):
            discovered[env_key] = url_template.format(host=container_host)
            logger.info("Discovered service %s on container network: %s", env_key, discovered[env_key])
            continue

        # 2. Fallback: Probe localhost on standard port (useful for dev/host setups)
        if await probe_port("127.0.0.1", port):
            discovered[env_key] = url_template.format(host="127.0.0.1")
            logger.info("Discovered service %s on localhost: %s", env_key, discovered[env_key])

    return discovered


def _try_decrypt_gws_bundle(encrypted_payload: str) -> Optional[Dict[str, Any]]:
    """Tries to decrypt the GWS credentials bundle using available encryption keys."""
    # 1. Try decrypting using the cron repository's ConfigEncryption derivation
    password_val = os.getenv("CONFIG_ENCRYPTION_KEY", "spring-cove-fallback-secret")
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'salt_',
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(password_val.encode()))
        cipher = Fernet(derived_key)
        decrypted = cipher.decrypt(encrypted_payload.encode()).decode()
        logger.info("Successfully decrypted GWS bundle using derived CONFIG_ENCRYPTION_KEY")
        return json.loads(decrypted)
    except Exception as e:
        logger.debug("Failed to decrypt GWS bundle with CONFIG_ENCRYPTION_KEY: %s", e)

    # 2. Try using the current app's ENCRYPTION_KEY directly
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        try:
            cipher = Fernet(encryption_key.encode())
            decrypted = cipher.decrypt(encrypted_payload.encode()).decode()
            logger.info("Successfully decrypted GWS bundle using ENCRYPTION_KEY")
            return json.loads(decrypted)
        except Exception as e:
            logger.warning("Failed to decrypt GWS bundle with ENCRYPTION_KEY: %s", e)

    return None


CANDIDATE_DIRS = [
    "/app/data",
    "/app/config",
    "/app/data/gws",
    "/app/data/gws_config",
    "./data",
    "./config",
    os.path.expanduser("~/.config/gws"),
    "/root/.config/gws",
]

DB_CANDIDATES = [
    "/app/data/automation.db",
    "./data/automation.db",
    "/app/config/automation.db",
    "./config/automation.db",
]


def scan_for_gws_credentials() -> Dict[str, str]:
    """
    Scans the filesystem and known configuration DB paths for GWS credentials.
    Returns keys: GWS_CLIENT_ID, GWS_CLIENT_SECRET, GWS_REFRESH_TOKEN (if found).
    """
    discovered_gws: Dict[str, str] = {}

    # 1. Check for client_secret.json or credentials.json on disk
    for directory in CANDIDATE_DIRS:
        if not os.path.isdir(directory):
            continue

        for filename in ["client_secret.json", "credentials.json"]:
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Google client secret files usually wrap inside 'installed' or 'web'
                    root_key = "installed" if "installed" in data else ("web" if "web" in data else None)
                    if root_key:
                        cred_source = data[root_key]
                    else:
                        cred_source = data

                    client_id = cred_source.get("client_id")
                    client_secret = cred_source.get("client_secret")

                    if client_id and client_secret:
                        discovered_gws["GWS_CLIENT_ID"] = str(client_id).strip()
                        discovered_gws["GWS_CLIENT_SECRET"] = str(client_secret).strip()
                        logger.info("Found GWS Client credentials in disk file: %s", path)
                        break
                except Exception as e:
                    logger.warning("Failed to parse credential file %s: %s", path, e)
        
        if "GWS_CLIENT_ID" in discovered_gws:
            break

    # 2. Check for automation.db sqlite database from other app / shared volume
    for db_path in DB_CANDIDATES:
        if os.path.exists(db_path):
            logger.info("Found potential automation database at %s. Attempting to read GWS bundle...", db_path)
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT value FROM app_config WHERE key = 'gws_credentials_bundle'"
                ).fetchone()
                conn.close()

                if row and row[0]:
                    payload = _try_decrypt_gws_bundle(row[0])
                    if payload:
                        # Extract client secret info from bundle
                        client_secret_hex = payload.get("client_secret.json")
                        if client_secret_hex:
                            secret_data = json.loads(bytes.fromhex(client_secret_hex).decode())
                            root_key = "installed" if "installed" in secret_data else ("web" if "web" in secret_data else None)
                            cred_source = secret_data[root_key] if root_key else secret_data
                            
                            client_id = cred_source.get("client_id")
                            client_secret = cred_source.get("client_secret")
                            if client_id:
                                discovered_gws["GWS_CLIENT_ID"] = str(client_id).strip()
                            if client_secret:
                                discovered_gws["GWS_CLIENT_SECRET"] = str(client_secret).strip()

                        # Also look for refresh token if stored in database config
                        # Note: if there is a refresh token or encrypted creds we can extract it if needed
                        logger.info("Successfully recovered GWS Client ID/Secret from GWS bundle in %s", db_path)
            except Exception as e:
                logger.warning("Failed reading credentials bundle from DB %s: %s", db_path, e)

    return discovered_gws


async def run_autodiscovery() -> DiscoveryResult:
    """Run all settings autodiscovery checks and return results."""
    try:
        urls = await discover_network_services()
        gws = await asyncio.to_thread(scan_for_gws_credentials)
        return DiscoveryResult(
            success=True,
            discovered_urls=urls,
            discovered_gws=gws
        )
    except Exception as e:
        logger.exception("Autodiscovery run failed")
        return DiscoveryResult(
            success=False,
            discovered_urls={},
            discovered_gws={},
            error=str(e)
        )
