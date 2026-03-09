"""Tests for ActivityLogger."""
from pathlib import Path

import pytest

from cmdop_claude.sidecar.activity.activity import ActivityLogger


@pytest.fixture
def logger(tmp_path: Path) -> ActivityLogger:
    return ActivityLogger(tmp_path)


def test_log_creates_file(logger: ActivityLogger, tmp_path: Path) -> None:
    logger.log("init", tokens=100, model="deepseek/v3.2")
    assert (tmp_path / "activity.jsonl").exists()


def test_log_appends(logger: ActivityLogger) -> None:
    logger.log("init", tokens=100)
    logger.log("review", tokens=200)
    entries = logger.read()
    assert len(entries) == 2
    assert entries[0].action == "init"
    assert entries[1].action == "review"


def test_read_empty(logger: ActivityLogger) -> None:
    assert logger.read() == []


def test_read_limit(logger: ActivityLogger) -> None:
    for i in range(10):
        logger.log("action", tokens=i)
    entries = logger.read(limit=3)
    assert len(entries) == 3
    assert entries[0].tokens == 7
    assert entries[2].tokens == 9


def test_log_with_details(logger: ActivityLogger) -> None:
    logger.log("init", tokens=500, model="test", files_created=["CLAUDE.md"])
    entries = logger.read()
    assert entries[0].details == {"files_created": ["CLAUDE.md"]}


def test_rotation(logger: ActivityLogger, tmp_path: Path) -> None:
    """Auto-rotates when exceeding 1000 lines, keeps last 500."""
    log_file = tmp_path / "activity.jsonl"
    # Write 1001 lines directly
    for i in range(1001):
        logger.log("action", tokens=i)
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 500
    # Last entry should be tokens=1000
    entries = logger.read(limit=1)
    assert entries[0].tokens == 1000


def test_read_skips_corrupt_lines(logger: ActivityLogger, tmp_path: Path) -> None:
    logger.log("good", tokens=100)
    log_file = tmp_path / "activity.jsonl"
    with open(log_file, "a") as f:
        f.write("not valid json\n")
    logger.log("also_good", tokens=200)
    entries = logger.read()
    assert len(entries) == 2
    assert entries[0].action == "good"
    assert entries[1].action == "also_good"


def test_last_action_age_none_when_empty(logger: ActivityLogger) -> None:
    assert logger.last_action_age("review") is None


def test_last_action_age_none_when_action_missing(logger: ActivityLogger) -> None:
    logger.log("init", tokens=100)
    assert logger.last_action_age("review") is None


def test_last_action_age_returns_seconds(logger: ActivityLogger) -> None:
    logger.log("review", tokens=200)
    age = logger.last_action_age("review")
    assert age is not None
    assert age < 5  # just logged, should be near zero
