import os
import asyncio
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger("DiscoveryService")

class DiscoveryResult(BaseModel):
    success: bool
    discovered_urls: Dict[str, str]
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


async def run_autodiscovery() -> DiscoveryResult:
    """Run all settings autodiscovery checks and return results."""
    try:
        urls = await discover_network_services()
        return DiscoveryResult(
            success=True,
            discovered_urls=urls
        )
    except Exception as e:
        logger.exception("Autodiscovery run failed")
        return DiscoveryResult(
            success=False,
            discovered_urls={},
            error=str(e)
        )
