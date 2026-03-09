"""Tests for StatusService (get_status, generate_map, get_current_map)."""
from __future__ import annotations

from .conftest import mock_llm_review


def test_get_status_no_review(service) -> None:
    status = service.get_status()

    assert status.enabled is True
    assert status.last_run is None
    assert status.pending_items == 0


def test_get_status_with_review(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()
    service.generate_review(scan_result=sample_scan)

    status = service.get_status()

    assert status.last_run is not None
    assert status.pending_items == 2
    assert status.tokens_today == 150


def test_get_status_with_suppression(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()
    service.generate_review(scan_result=sample_scan)
    service.acknowledge("some_item", days=30)

    status = service.get_status()

    assert status.suppressed_items == 1
