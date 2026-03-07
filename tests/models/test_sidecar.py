"""Tests for sidecar Pydantic models — validation and serialization."""
import pytest
from pydantic import ValidationError

from cmdop_claude.models.sidecar import (
    DocFile,
    DocScanResult,
    LLMReviewItem,
    LLMReviewResponse,
    ReviewCategory,
    ReviewItem,
    ReviewResult,
    ReviewSeverity,
    SidecarStatus,
)


# ── DocFile ───────────────────────────────────────────────────────────


def test_doc_file_required_fields() -> None:
    f = DocFile(path="CLAUDE.md", modified_at="2026-03-06T00:00:00Z", line_count=10)
    assert f.summary is None


def test_doc_file_with_summary() -> None:
    f = DocFile(
        path="rules/api.md",
        modified_at="2026-03-06T00:00:00Z",
        line_count=5,
        summary="# API rules",
    )
    assert f.summary == "# API rules"


def test_doc_file_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        DocFile(
            path="x.md",
            modified_at="2026-03-06T00:00:00Z",
            line_count=1,
            unknown_field="oops",
        )


# ── DocScanResult ─────────────────────────────────────────────────────


def test_doc_scan_result_empty() -> None:
    r = DocScanResult(files=[], dependencies=[], recent_commits=[], top_dirs=[])
    assert r.files == []


def test_doc_scan_result_with_files() -> None:
    r = DocScanResult(
        files=[DocFile(path="a.md", modified_at="2026-01-01T00:00:00Z", line_count=1)],
        dependencies=["flask"],
        recent_commits=["abc init"],
        top_dirs=["src"],
    )
    assert len(r.files) == 1
    assert r.dependencies == ["flask"]


# ── ReviewItem ────────────────────────────────────────────────────────


def test_review_item_all_fields() -> None:
    item = ReviewItem(
        category="staleness",
        severity="high",
        description="Old file",
        affected_files=["CLAUDE.md"],
        suggested_action="Update it",
        item_id="abc123",
    )
    assert item.category == "staleness"
    assert item.item_id == "abc123"


def test_review_item_empty_affected_files() -> None:
    item = ReviewItem(
        category="gap",
        severity="low",
        description="Missing docs",
        affected_files=[],
        suggested_action="Add docs",
        item_id="xyz",
    )
    assert item.affected_files == []


# ── ReviewResult ──────────────────────────────────────────────────────


def test_review_result_serialization() -> None:
    result = ReviewResult(
        generated_at="2026-03-06T00:00:00Z",
        items=[],
        tokens_used=100,
        model_used="test/model",
    )
    data = result.model_dump()
    assert data["tokens_used"] == 100
    assert data["items"] == []


def test_review_result_with_items() -> None:
    result = ReviewResult(
        generated_at="2026-03-06T00:00:00Z",
        items=[
            ReviewItem(
                category="contradiction",
                severity="medium",
                description="REST vs GraphQL",
                affected_files=["CLAUDE.md", "rules/api.md"],
                suggested_action="Clarify",
                item_id="def456",
            )
        ],
        tokens_used=200,
        model_used="test/smart",
    )
    assert len(result.items) == 1
    assert result.items[0].item_id == "def456"


# ── SidecarStatus ─────────────────────────────────────────────────────


def test_sidecar_status_defaults() -> None:
    s = SidecarStatus(enabled=True)
    assert s.last_run is None
    assert s.pending_items == 0
    assert s.suppressed_items == 0
    assert s.tokens_today == 0
    assert s.cost_today_usd == 0.0


# ── LLM Structured Output Models ──────────────────────────────────────


def test_llm_review_item_with_enums() -> None:
    item = LLMReviewItem(
        category=ReviewCategory.staleness,
        severity=ReviewSeverity.high,
        description="CLAUDE.md is stale",
        affected_files=["CLAUDE.md"],
        suggested_action="Update it",
    )
    assert item.category == ReviewCategory.staleness
    assert item.severity == ReviewSeverity.high


def test_llm_review_item_from_string_values() -> None:
    item = LLMReviewItem(
        category="gap",
        severity="low",
        description="Missing docs",
        affected_files=[],
        suggested_action="Add docs",
    )
    assert item.category == ReviewCategory.gap
    assert item.severity == ReviewSeverity.low


def test_llm_review_item_invalid_category() -> None:
    with pytest.raises(ValidationError):
        LLMReviewItem(
            category="invalid",
            severity="high",
            description="x",
            affected_files=[],
            suggested_action="x",
        )


def test_llm_review_response_empty() -> None:
    resp = LLMReviewResponse(items=[])
    assert resp.items == []


def test_llm_review_response_with_items() -> None:
    resp = LLMReviewResponse(items=[
        LLMReviewItem(
            category="contradiction",
            severity="medium",
            description="REST vs GraphQL",
            affected_files=["CLAUDE.md", "rules/api.md"],
            suggested_action="Clarify",
        )
    ])
    assert len(resp.items) == 1
    assert resp.items[0].category == ReviewCategory.contradiction


def test_llm_review_response_json_schema() -> None:
    schema = LLMReviewResponse.model_json_schema()
    assert "items" in schema["properties"]
    assert schema["properties"]["items"]["type"] == "array"


# ── SidecarStatus (continued) ────────────────────────────────────────


def test_sidecar_status_full() -> None:
    s = SidecarStatus(
        enabled=True,
        last_run="2026-03-06T14:00:00Z",
        pending_items=3,
        suppressed_items=1,
        tokens_today=500,
        cost_today_usd=0.000125,
    )
    assert s.pending_items == 3
    assert s.cost_today_usd == 0.000125
