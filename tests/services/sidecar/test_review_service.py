"""Tests for ReviewService."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from cmdop_claude.models.sidecar import ReviewItem, ReviewResult

from .conftest import SAMPLE_LLM_ITEMS, SAMPLE_PARSED, mock_llm_review, none_llm_response


def test_generate_review_basic(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()

    result = service.generate_review(scan_result=sample_scan)

    assert len(result.items) == 2
    assert result.items[0].category == "staleness"
    assert result.items[1].category == "gap"
    assert result.tokens_used == 150
    assert result.model_used


def test_generate_review_writes_review_md(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()

    service.generate_review(scan_result=sample_scan)

    review_path = service._sidecar_dir / "review.md"
    assert review_path.exists()
    text = review_path.read_text(encoding="utf-8")
    assert "Staleness" in text
    assert "Missing Documentation" in text
    assert "(id: " in text


def test_generate_review_archives(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review()

    service.generate_review(scan_result=sample_scan)

    history_dir = service._sidecar_dir / "history"
    assert history_dir.exists()
    assert len(list(history_dir.glob("*.md"))) == 1


def test_generate_review_tracks_usage(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review(tokens=200)

    service.generate_review(scan_result=sample_scan)

    usage_data = json.loads(service._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 200
    assert usage_data["calls"] == 1


def test_generate_review_accumulates_usage(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = mock_llm_review(tokens=100)

    service.generate_review(scan_result=sample_scan)
    service.generate_review(scan_result=sample_scan)

    usage_data = json.loads(service._usage_file.read_text(encoding="utf-8"))
    assert usage_data["tokens"] == 200
    assert usage_data["calls"] == 2


def test_generate_review_handles_none_parsed(service, mock_sdk, sample_scan) -> None:
    mock_sdk.parse.return_value = none_llm_response(tokens=50)

    result = service.generate_review(scan_result=sample_scan)

    assert result.items == []
    assert result.tokens_used == 50


def test_build_items_converts_llm_items(service) -> None:
    items = service._build_items(SAMPLE_LLM_ITEMS, {})

    assert len(items) == 2
    assert items[0].category == "staleness"
    assert items[1].category == "gap"
    assert items[0].item_id


def test_build_items_filters_suppressed(service) -> None:
    future = datetime.fromtimestamp(time.time() + 86400, tz=timezone.utc).isoformat()
    items_all = service._build_items(SAMPLE_LLM_ITEMS, {})
    first_id = items_all[0].item_id

    items = service._build_items(SAMPLE_LLM_ITEMS, {first_id: future})

    assert len(items) == 1
    assert items[0].category == "gap"


def test_build_items_empty_list(service) -> None:
    assert service._build_items([], {}) == []


def test_review_md_no_items(service) -> None:
    result = ReviewResult(
        generated_at="2026-03-06T00:00:00+00:00",
        items=[],
        tokens_used=50,
        model_used="test/model",
    )
    service._ensure_dirs()
    service._write_review_md(result)

    text = (service._sidecar_dir / "review.md").read_text(encoding="utf-8")
    assert "No issues found" in text


def test_review_md_severity_markers(service) -> None:
    result = ReviewResult(
        generated_at="2026-03-06T00:00:00+00:00",
        items=[
            ReviewItem(
                category="staleness", severity="high", description="Very stale",
                affected_files=["CLAUDE.md"], suggested_action="Update it", item_id="aaa",
            ),
            ReviewItem(
                category="gap", severity="low", description="Minor gap",
                affected_files=[], suggested_action="Consider adding", item_id="bbb",
            ),
        ],
        tokens_used=100,
        model_used="test/model",
    )
    service._ensure_dirs()
    service._write_review_md(result)

    text = (service._sidecar_dir / "review.md").read_text(encoding="utf-8")
    assert "[!]" in text
    assert "[~]" in text


def test_get_current_review_no_file(service) -> None:
    assert service.get_current_review() == ""


def test_get_current_review_with_file(service) -> None:
    service._ensure_dirs()
    (service._sidecar_dir / "review.md").write_text("# Review content", encoding="utf-8")

    assert service.get_current_review() == "# Review content"
