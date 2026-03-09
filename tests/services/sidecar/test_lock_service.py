"""Tests for SidecarState lock behavior."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from .conftest import mock_llm_review


def test_lock_prevents_concurrent_run(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()

    service._ensure_dirs()
    lock = service._sidecar_dir / ".lock"
    lock.write_text("99999", encoding="utf-8")

    with pytest.raises(RuntimeError, match="lock held"):
        service.generate_review(scan_result=sample_scan)


def test_stale_lock_is_ignored(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()

    service._ensure_dirs()
    lock = service._sidecar_dir / ".lock"
    lock.write_text("99999", encoding="utf-8")
    old_time = time.time() - 120
    os.utime(lock, (old_time, old_time))

    result = service.generate_review(scan_result=sample_scan)
    assert len(result.items) == 2


def test_lock_released_after_review(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()

    service.generate_review(scan_result=sample_scan)

    assert not (service._sidecar_dir / ".lock").exists()


def test_lock_released_on_error(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.side_effect = Exception("API error")

    with pytest.raises(Exception, match="API error"):
        service.generate_review(scan_result=sample_scan)

    assert not (service._sidecar_dir / ".lock").exists()
