from unittest.mock import AsyncMock, patch

import pytest

import database


@pytest.mark.feature("database-migrations")
def test_to_sync_database_url_handles_async_drivers() -> None:
    assert (
        database.to_sync_database_url("postgresql+asyncpg://u:p@localhost:5432/db")
        == "postgresql+psycopg2://u:p@localhost:5432/db"
    )
    assert database.to_sync_database_url("sqlite+aiosqlite:///./app.db") == "sqlite:///./app.db"
    assert database.to_sync_database_url("postgresql+psycopg2://u:p@localhost:5432/db") == (
        "postgresql+psycopg2://u:p@localhost:5432/db"
    )


@pytest.mark.asyncio
@pytest.mark.feature("database-migrations")
async def test_init_db_runs_migrations_in_thread() -> None:
    with patch("database.run_migrations") as run_migrations, patch(
        "database.asyncio.to_thread", new=AsyncMock()
    ) as to_thread:
        await database.init_db()

    to_thread.assert_awaited_once_with(run_migrations)
