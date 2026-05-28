import pytest
from typing import Awaitable

from logger import SessionLogger


@pytest.mark.feature("session-logger-core")
def test_session_logger_only_logs_for_active_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: ignore log events for unknown sessions and keep active session logs."""
    logger = SessionLogger()
    printed: list[str] = []

    monkeypatch.setattr("builtins.print", lambda msg: printed.append(str(msg)))

    logger.log("missing", "no-op")
    logger.start_session("s1")
    logger.log("s1", "hello")

    assert logger.get_logs("missing") == []
    assert logger.get_logs("s1") == ["hello"]
    assert any("[SESSION s1] hello" in line for line in printed)


@pytest.mark.feature("session-logger-cleanup")
@pytest.mark.asyncio
async def test_session_logger_delayed_cleanup_handles_removed_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: delayed cleanup is safe even when session is removed before timeout."""
    logger = SessionLogger()
    logger.start_session("s1")

    created_coroutines: list[Awaitable[None]] = []

    def _capture_task(coro):
        created_coroutines.append(coro)
        return None

    async def _fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("logger.asyncio.create_task", _capture_task)
    monkeypatch.setattr("logger.asyncio.sleep", _fast_sleep)

    logger.end_session("s1")
    assert len(created_coroutines) == 1

    # Simulate independent cleanup before delayed cleanup coroutine runs.
    del logger.sessions["s1"]

    await created_coroutines[0]
    assert "s1" not in logger.sessions
