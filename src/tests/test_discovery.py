import os
import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest
from services.discovery import (
    probe_port,
    discover_network_services,
    scan_for_gws_credentials,
    run_autodiscovery,
)
from app import autodiscover_settings


@pytest.mark.asyncio
async def test_probe_port_success_and_failure():
    with patch("asyncio.open_connection") as mock_open_conn:
        # Success path
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open_conn.return_value = (mock_reader, mock_writer)

        res = await probe_port("localhost", 8080)
        assert res is True
        mock_writer.close.assert_called_once()

        # Failure path
        mock_open_conn.side_effect = Exception("failed")
        res = await probe_port("localhost", 8080)
        assert res is False


@pytest.mark.asyncio
async def test_discover_network_services():
    with patch("services.discovery.probe_port") as mock_probe:
        # Mock probe_port returning True only for searxng container and localhost homebox
        def side_effect(host, port):
            if host == "searxng" and port == 8080:
                return True
            if host == "127.0.0.1" and port == 7745:
                return True
            return False
        
        mock_probe.side_effect = side_effect
        res = await discover_network_services()
        
        assert res["SEARXNG_URL"] == "http://searxng:8080"
        assert res["HOMEBOX_URL"] == "http://127.0.0.1:7745/api/v1"
        assert "MEALIE_URL" not in res


def test_scan_for_gws_credentials_file_parsing():
    mock_json_data = {
        "installed": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret"
        }
    }
    
    with patch("os.path.isdir", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(mock_json_data))):
        
        res = scan_for_gws_credentials()
        assert res["GWS_CLIENT_ID"] == "test_client_id"
        assert res["GWS_CLIENT_SECRET"] == "test_client_secret"


def test_scan_for_gws_credentials_sqlite_import_pbkdf2(tmp_path):
    db_file = tmp_path / "automation_pbkdf2.db"
    
    # Setup test sqlite DB
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT)")
    
    # Encrypt using the derived PBKDF2 key
    import base64
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.fernet import Fernet
    
    password = "spring-cove-test-secret"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'salt_',
        iterations=100000,
    )
    derived_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    cipher = Fernet(derived_key)
    
    bundle_data = {
        "client_secret.json": bytes(json.dumps({
            "installed": {
                "client_id": "pbkdf2_client_id",
                "client_secret": "pbkdf2_client_secret"
            }
        }).encode()).hex()
    }
    
    encrypted_bundle = cipher.encrypt(json.dumps(bundle_data).encode()).decode()
    cursor.execute("INSERT INTO app_config (key, value) VALUES ('gws_credentials_bundle', ?)", (encrypted_bundle,))
    conn.commit()
    conn.close()
    
    with patch.dict(os.environ, {"CONFIG_ENCRYPTION_KEY": password}), \
         patch("services.discovery.DB_CANDIDATES", [str(db_file)]), \
         patch("services.discovery.CANDIDATE_DIRS", []):
        
        res = scan_for_gws_credentials()
        assert res["GWS_CLIENT_ID"] == "pbkdf2_client_id"
        assert res["GWS_CLIENT_SECRET"] == "pbkdf2_client_secret"


def test_scan_for_gws_credentials_sqlite_import_direct_fernet(tmp_path):
    db_file = tmp_path / "automation_fernet.db"
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT)")
    
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    cipher = Fernet(key.encode())
    
    bundle_data = {
        "client_secret.json": bytes(json.dumps({
            "installed": {
                "client_id": "sqlite_client_id",
                "client_secret": "sqlite_client_secret"
            }
        }).encode()).hex()
    }
    
    encrypted_bundle = cipher.encrypt(json.dumps(bundle_data).encode()).decode()
    cursor.execute("INSERT INTO app_config (key, value) VALUES ('gws_credentials_bundle', ?)", (encrypted_bundle,))
    conn.commit()
    conn.close()
    
    with patch.dict(os.environ, {"ENCRYPTION_KEY": key}), \
         patch("services.discovery.DB_CANDIDATES", [str(db_file)]), \
         patch("services.discovery.CANDIDATE_DIRS", []):
        
        res = scan_for_gws_credentials()
        assert res["GWS_CLIENT_ID"] == "sqlite_client_id"
        assert res["GWS_CLIENT_SECRET"] == "sqlite_client_secret"


@pytest.mark.asyncio
async def test_run_autodiscovery():
    with patch("services.discovery.discover_network_services", AsyncMock(return_value={"SEARXNG_URL": "http://searxng:8080"})), \
         patch("services.discovery.scan_for_gws_credentials", return_value={"GWS_CLIENT_ID": "client_id"}):
        
        res = await run_autodiscovery()
        assert res.success is True
        assert res.discovered_urls["SEARXNG_URL"] == "http://searxng:8080"
        assert res.discovered_gws["GWS_CLIENT_ID"] == "client_id"


@pytest.mark.asyncio
async def test_discover_endpoint():
    with patch("app.run_autodiscovery") as mock_run:
        from services.discovery import DiscoveryResult
        mock_result = DiscoveryResult(
            success=True,
            discovered_urls={"SEARXNG_URL": "http://searxng:8080"},
            discovered_gws={"GWS_CLIENT_ID": "id"}
        )
        mock_run.return_value = mock_result
        
        res = await autodiscover_settings()
        assert res.success is True
        assert res.discovered_urls["SEARXNG_URL"] == "http://searxng:8080"
        assert res.discovered_gws["GWS_CLIENT_ID"] == "id"
