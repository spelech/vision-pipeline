"""Post-deploy smoke checks for API readiness and core receipt paths."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any
from urllib import error, request


def _get_json(url: str, timeout_seconds: float) -> tuple[int, Any]:
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=timeout_seconds) as response:  # nosec B310
        status_code = int(response.getcode())
        payload = response.read().decode("utf-8")
    try:
        parsed = json.loads(payload) if payload else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} did not return JSON: {payload[:200]}") from exc
    return status_code, parsed


def _wait_for_health(base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    health_url = f"{base_url}/api/health"
    last_error = "unknown error"

    while time.time() < deadline:
        try:
            status, payload = _get_json(health_url, timeout_seconds=5)
            if status == 200 and payload.get("status") == "ok":
                return
            last_error = f"status={status}, payload={payload}"
        except (error.URLError, RuntimeError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(2)

    raise RuntimeError(f"Health check did not become ready: {last_error}")


def run_smoke_checks(base_url: str, startup_timeout: int) -> None:
    _wait_for_health(base_url, startup_timeout)

    status, health = _get_json(f"{base_url}/api/health", timeout_seconds=10)
    if status != 200 or health.get("status") != "ok":
        raise RuntimeError(f"Health endpoint failed: {status} {health}")

    status, pipelines = _get_json(f"{base_url}/api/pipelines", timeout_seconds=10)
    if status != 200 or not bool(pipelines.get("success")):
        raise RuntimeError(f"Pipeline listing failed: {status} {pipelines}")
    pipeline_rows = pipelines.get("pipelines")
    if not isinstance(pipeline_rows, list):
        raise RuntimeError(f"Pipeline payload malformed: {pipelines}")
    pipeline_ids = {str(row.get("id") or row.get("pipeline_id") or "") for row in pipeline_rows}
    if "receipt" not in pipeline_ids:
        raise RuntimeError(f"Receipt pipeline missing from registry: {sorted(pipeline_ids)}")

    status, config = _get_json(f"{base_url}/api/config", timeout_seconds=10)
    if status != 200 or "secrets_status" not in config:
        raise RuntimeError(f"Config endpoint failed: {status} {config}")

    status, gmail = _get_json(f"{base_url}/api/gmail/status", timeout_seconds=10)
    if status != 200 or not bool(gmail.get("success")):
        raise RuntimeError(f"Gmail status endpoint failed: {status} {gmail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-deploy smoke checks")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8460",
        help="Base URL for the deployed API",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=90,
        help="Seconds to wait for /api/health to become ready",
    )
    args = parser.parse_args()

    run_smoke_checks(args.base_url.rstrip("/"), args.startup_timeout)
    print("Smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
