#!/usr/bin/env python3
"""Create an Alembic autogeneration revision for schema changes."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config


DEFAULT_SYNC_URL = "postgresql+psycopg2://vision:vision_pass@localhost:5432/vision_pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Alembic migration via autogenerate")
    parser.add_argument(
        "-m",
        "--message",
        default=os.getenv("MIGRATION_MESSAGE", "schema update"),
        help="Migration message (default: env MIGRATION_MESSAGE or 'schema update')",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    alembic_ini = repo_root / "src" / "alembic.ini"
    if not alembic_ini.exists():
        print(f"Missing Alembic config: {alembic_ini}", file=sys.stderr)
        return 2

    db_url = os.getenv("MIGRATION_DB_URL", DEFAULT_SYNC_URL)

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", db_url)

    revision_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    try:
        command.revision(
            cfg,
            message=args.message.strip() or "schema update",
            autogenerate=True,
            rev_id=revision_id,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Failed to create migration: {exc}", file=sys.stderr)
        return 1

    print("Migration generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
