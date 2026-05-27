"""Coverage-focused tests for base abstractions and session logger behavior."""

import asyncio
from typing import Any, cast

import pytest

from logger import SessionLogger
from pipelines.base import BasePipeline
from services.base import BaseService


@pytest.mark.feature("core-abstractions")
def test_base_pipeline_defaults_and_abstract_errors() -> None:
    """Feature: enforce base pipeline abstract contract and default schema behavior."""
    assert not BasePipeline.get_settings_schema()

    with pytest.raises(NotImplementedError):
        BasePipeline.get_id()

    with pytest.raises(NotImplementedError):
        BasePipeline.get_name()

    with pytest.raises(NotImplementedError):
        BasePipeline().run()


@pytest.mark.feature("core-abstractions")
def test_base_service_abstract_bodies_are_well_formed() -> None:
    """Feature: keep base service abstract methods callable for introspection safety."""
    dummy_service = cast(BaseService, object())
    name_property = cast(Any, BaseService.__dict__["name"])

    assert name_property.fget(dummy_service) is None
    assert asyncio.run(BaseService.execute(dummy_service, {})) is None
    assert asyncio.run(BaseService.get_pre_enrichment(dummy_service, {})) is None
    assert BaseService.get_payload(dummy_service, {}) is None


@pytest.mark.feature("session-logging")
def test_session_logger_delayed_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: remove completed session logs when delayed cleanup runs."""
    logger = SessionLogger()
    logger.start_session("s-1")
    logger.log("s-1", "hello")

    async def _no_sleep(_seconds: int) -> None:
        return None

    def _run_task_now(coro):
        asyncio.run(coro)
        return object()

    monkeypatch.setattr("logger.asyncio.sleep", _no_sleep)
    monkeypatch.setattr("logger.asyncio.create_task", _run_task_now)

    logger.end_session("s-1")

    assert logger.get_logs("s-1") == []
