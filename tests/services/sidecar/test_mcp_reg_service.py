"""Tests for MCPRegService."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import cmdop_claude.services.sidecar.mcp_reg_service as _mcp_module


def _make_run_fn(get_rc: int = 1, add_rc: int = 0, remove_rc: int = 0):
    def run(cmd, **kwargs):
        if "get" in cmd:
            return SimpleNamespace(returncode=get_rc, stdout="", stderr="")
        if "add" in cmd:
            return SimpleNamespace(returncode=add_rc, stdout="", stderr="")
        if "remove" in cmd:
            return SimpleNamespace(returncode=remove_rc, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


def test_register_mcp_creates_entry(service, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    base = _make_run_fn(get_rc=1, add_rc=0)

    def tracking(cmd, **kwargs):
        calls.append(cmd)
        return base(cmd, **kwargs)

    monkeypatch.setattr(_mcp_module.subprocess, "run", tracking)
    assert service.register_mcp() is True
    assert any("add" in c for c in calls)


def test_register_mcp_idempotent(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=0))
    assert service.register_mcp() is False


def test_unregister_mcp_removes_entry(service, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    base = _make_run_fn(get_rc=0, remove_rc=0)

    def tracking(cmd, **kwargs):
        calls.append(cmd)
        return base(cmd, **kwargs)

    monkeypatch.setattr(_mcp_module.subprocess, "run", tracking)
    assert service.unregister_mcp() is True
    assert any("remove" in c for c in calls)


def test_unregister_mcp_not_registered(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=1))
    assert service.unregister_mcp() is False


def test_is_mcp_registered_true(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=0))
    assert service.is_mcp_registered() is True


def test_is_mcp_registered_false(service, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_mcp_module.subprocess, "run", _make_run_fn(get_rc=1))
    assert service.is_mcp_registered() is False
