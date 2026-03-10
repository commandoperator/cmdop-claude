"""Tests for update_service — version check + background upgrade."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.services.updater.update_service import (
    fetch_latest_version,
    get_installed_version,
    is_newer,
    launch_upgrade,
)


# ── is_newer ──────────────────────────────────────────────────────────────────


def test_is_newer_patch():
    assert is_newer("0.1.65", "0.1.64") is True


def test_is_newer_minor():
    assert is_newer("0.2.0", "0.1.99") is True


def test_is_newer_major():
    assert is_newer("1.0.0", "0.9.9") is True


def test_is_newer_same():
    assert is_newer("0.1.64", "0.1.64") is False


def test_is_newer_older():
    assert is_newer("0.1.63", "0.1.64") is False


def test_is_newer_strips_v_prefix():
    assert is_newer("v0.1.65", "v0.1.64") is True


# ── get_installed_version ─────────────────────────────────────────────────────


def test_get_installed_version_returns_string():
    version = get_installed_version()
    assert isinstance(version, str)
    parts = version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# ── fetch_latest_version ──────────────────────────────────────────────────────


def _mock_urlopen(version: str):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"info": {"version": version}}).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_fetch_latest_version_parses_pypi_response():
    with patch(
        "cmdop_claude.services.updater.update_service.urlopen",
        return_value=_mock_urlopen("0.1.99"),
    ):
        assert fetch_latest_version() == "0.1.99"


def test_fetch_latest_version_returns_none_on_network_error():
    with patch(
        "cmdop_claude.services.updater.update_service.urlopen",
        side_effect=OSError("timeout"),
    ):
        assert fetch_latest_version() is None


def test_fetch_latest_version_returns_none_on_bad_json():
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"not json"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "cmdop_claude.services.updater.update_service.urlopen",
        return_value=mock_resp,
    ):
        assert fetch_latest_version() is None


def test_fetch_latest_version_returns_none_on_missing_key():
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"no_info_key": {}}).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "cmdop_claude.services.updater.update_service.urlopen",
        return_value=mock_resp,
    ):
        assert fetch_latest_version() is None


# ── launch_upgrade ────────────────────────────────────────────────────────────


def test_launch_upgrade_calls_popen(tmp_path: Path):
    log = tmp_path / "update.log"
    with patch("cmdop_claude.services.updater.update_service.subprocess.Popen") as mock_popen:
        launch_upgrade(log)
    mock_popen.assert_called_once()
    cmd = mock_popen.call_args[0][0]
    assert "pip" in cmd
    assert "install" in cmd
    assert "--upgrade" in cmd
    assert "cmdop-claude" in cmd


def test_launch_upgrade_creates_log_dir(tmp_path: Path):
    nested = tmp_path / "a" / "b" / "update.log"
    with patch("cmdop_claude.services.updater.update_service.subprocess.Popen"):
        launch_upgrade(nested)
    assert nested.parent.exists()
