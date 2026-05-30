#!/usr/bin/env python3
"""Fail when SQLAlchemy metadata has unapplied migration operations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


DEFAULT_SYNC_URL = "postgresql+psycopg2://vision:vision_pass@localhost:5432/vision_pipeline"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    alembic_ini = repo_root / "src" / "alembic.ini"
    if not alembic_ini.exists():
        print(f"Missing Alembic config: {alembic_ini}", file=sys.stderr)
        return 2

    db_url = os.getenv("MIGRATION_DB_URL", DEFAULT_SYNC_URL)

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        command.check(cfg)
    except SystemExit as exc:
        # Alembic check exits non-zero when autogenerate would produce operations.
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Migration drift check failed: {exc}", file=sys.stderr)
        return 1

    print("Migration drift check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
