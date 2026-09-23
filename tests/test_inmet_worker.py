"""Periodic INMET worker must honor configuration and remain safe on upstream failure."""

import sys

import pytest
from pydantic import ValidationError

from app import sync_inmet
from app.config import Settings
from app.integrations.inmet import InmetError


def test_inmet_interval_is_bounded():
    for interval in (9, 1441):
        with pytest.raises(ValidationError):
            Settings(inmet_sync_interval_minutes=interval)
    assert Settings(inmet_sync_interval_minutes=10).inmet_sync_interval_minutes == 10


def test_inmet_worker_loop_syncs_then_waits_configured_interval(monkeypatch):
    class StopLoop(Exception):
        pass

    calls = []
    monkeypatch.setattr(sys, "argv", ["sync_inmet", "--loop"])
    monkeypatch.setattr(
        sync_inmet,
        "get_settings",
        lambda: Settings(inmet_enabled=True, inmet_sync_interval_minutes=25),
    )
    monkeypatch.setattr(sync_inmet, "sync_once", lambda: calls.append("sync") or True)

    def stop_after_sleep(seconds):
        calls.append(seconds)
        raise StopLoop

    monkeypatch.setattr(sync_inmet.time, "sleep", stop_after_sleep)
    with pytest.raises(StopLoop):
        sync_inmet.main()
    assert calls == ["sync", 25 * 60]


def test_disabled_inmet_worker_does_not_fetch_or_quit_in_loop(monkeypatch, capsys):
    class StopLoop(Exception):
        pass

    monkeypatch.setattr(sys, "argv", ["sync_inmet", "--loop"])
    monkeypatch.setattr(sync_inmet, "get_settings", lambda: Settings(inmet_enabled=False))
    monkeypatch.setattr(
        sync_inmet, "sync_once", lambda: pytest.fail("Worker disabled but fetched INMET")
    )
    monkeypatch.setattr(sync_inmet.time, "sleep", lambda _: (_ for _ in ()).throw(StopLoop))
    with pytest.raises(StopLoop):
        sync_inmet.main()
    assert "desabilitada" in capsys.readouterr().out


def test_inmet_worker_preserves_stored_warnings_on_provider_failure(monkeypatch, capsys):
    class FakeDb:
        did_rollback = False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def rollback(self):
            self.did_rollback = True

    db = FakeDb()
    monkeypatch.setattr(sync_inmet, "SessionLocal", lambda: db)

    def fail(_db, *, actor):
        assert actor is None
        raise InmetError("Serviço indisponível")

    monkeypatch.setattr(sync_inmet, "sync_inmet_warnings", fail)
    assert sync_inmet.sync_once() is False
    assert db.did_rollback is True
    assert "mantendo os avisos armazenados" in capsys.readouterr().out
