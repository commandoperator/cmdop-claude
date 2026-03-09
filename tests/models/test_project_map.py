"""Tests for project map Pydantic models."""
import pytest
from pydantic import ValidationError

from cmdop_claude.models.docs.project_map import (
    DirAnnotation,
    LLMDirAnnotation,
    LLMMapResponse,
    MapConfig,
    ProjectMap,
)


# ── DirAnnotation ────────────────────────────────────────────────────


def test_dir_annotation_required_fields() -> None:
    a = DirAnnotation(path="src/", annotation="Main source code", file_count=10)
    assert a.has_entry_point is False
    assert a.entry_point_name is None


def test_dir_annotation_with_entry_point() -> None:
    a = DirAnnotation(
        path="src/app/",
        annotation="Next.js routing",
        file_count=5,
        has_entry_point=True,
        entry_point_name="page.tsx",
    )
    assert a.has_entry_point is True
    assert a.entry_point_name == "page.tsx"


def test_dir_annotation_rejects_empty_path() -> None:
    with pytest.raises(ValidationError):
        DirAnnotation(path="", annotation="test", file_count=0)


def test_dir_annotation_rejects_empty_annotation() -> None:
    with pytest.raises(ValidationError):
        DirAnnotation(path="src/", annotation="", file_count=0)


def test_dir_annotation_rejects_negative_file_count() -> None:
    with pytest.raises(ValidationError):
        DirAnnotation(path="src/", annotation="test", file_count=-1)


def test_dir_annotation_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DirAnnotation(path="src/", annotation="test", file_count=0, unknown="x")


# ── ProjectMap ───────────────────────────────────────────────────────


def test_project_map_minimal() -> None:
    pm = ProjectMap(
        generated_at="2026-03-06T00:00:00Z",
        project_type="python-package",
        root_annotation="A CLI tool",
        directories=[],
        tokens_used=100,
        model_used="test/cheap",
    )
    assert pm.entry_points == []
    assert pm.directories == []


def test_project_map_with_dirs() -> None:
    pm = ProjectMap(
        generated_at="2026-03-06T00:00:00Z",
        project_type="nextjs-app",
        root_annotation="E-commerce frontend",
        directories=[
            DirAnnotation(path="src/app/", annotation="Routing", file_count=12),
            DirAnnotation(
                path="src/lib/",
                annotation="Utilities",
                file_count=5,
                has_entry_point=True,
                entry_point_name="prisma.ts",
            ),
        ],
        entry_points=["src/middleware.ts"],
        tokens_used=500,
        model_used="test/cheap",
    )
    assert len(pm.directories) == 2
    assert pm.entry_points == ["src/middleware.ts"]


def test_project_map_serialization() -> None:
    pm = ProjectMap(
        generated_at="2026-03-06T00:00:00Z",
        project_type="go-module",
        root_annotation="API server",
        directories=[],
        tokens_used=0,
        model_used="test",
    )
    data = pm.model_dump()
    assert data["project_type"] == "go-module"
    assert data["directories"] == []


# ── MapConfig ────────────────────────────────────────────────────────


def test_map_config_defaults() -> None:
    c = MapConfig()
    assert c.max_depth == 3
    assert c.max_dirs == 50
    assert c.max_output_lines == 150


def test_map_config_custom() -> None:
    c = MapConfig(max_depth=5, max_dirs=100, max_output_lines=300)
    assert c.max_depth == 5


def test_map_config_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        MapConfig(max_depth=0)
    with pytest.raises(ValidationError):
        MapConfig(max_depth=11)
    with pytest.raises(ValidationError):
        MapConfig(max_dirs=4)


# ── LLM Models ───────────────────────────────────────────────────────


def test_llm_dir_annotation() -> None:
    a = LLMDirAnnotation(
        path="src/api/",
        annotation="REST API routes",
        is_entry_point=False,
    )
    assert a.entry_file is None


def test_llm_dir_annotation_with_entry() -> None:
    a = LLMDirAnnotation(
        path="cmd/",
        annotation="CLI entry points",
        is_entry_point=True,
        entry_file="main.go",
    )
    assert a.entry_file == "main.go"


def test_llm_map_response() -> None:
    resp = LLMMapResponse(
        project_type="python-package",
        root_summary="A documentation librarian",
        directories=[
            LLMDirAnnotation(
                path="src/",
                annotation="Main source",
                is_entry_point=False,
            ),
        ],
    )
    assert resp.project_type == "python-package"
    assert len(resp.directories) == 1


def test_llm_map_response_empty_dirs() -> None:
    resp = LLMMapResponse(
        project_type="monorepo",
        root_summary="Multi-package repo",
        directories=[],
    )
    assert resp.directories == []


def test_llm_map_response_json_schema() -> None:
    schema = LLMMapResponse.model_json_schema()
    assert "project_type" in schema["properties"]
    assert "directories" in schema["properties"]
