"""Tests for acknowledge/suppress logic in SidecarState."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone


def test_acknowledge_creates_suppression(service) -> None:
    service.acknowledge("abc123", days=7)

    suppressed = json.loads(service._suppress_file.read_text(encoding="utf-8"))
    assert "abc123" in suppressed


def test_acknowledge_multiple_items(service) -> None:
    service.acknowledge("item1", days=30)
    service.acknowledge("item2", days=60)

    suppressed = json.loads(service._suppress_file.read_text(encoding="utf-8"))
    assert "item1" in suppressed
    assert "item2" in suppressed


def test_load_suppressed_prunes_expired(service) -> None:
    service._ensure_dirs()
    expired = datetime.fromtimestamp(time.time() - 86400, tz=timezone.utc).isoformat()
    valid = datetime.fromtimestamp(time.time() + 86400, tz=timezone.utc).isoformat()
    service._suppress_file.write_text(
        json.dumps({"old": expired, "new": valid}), encoding="utf-8"
    )

    result = service._load_suppressed()

    assert "old" not in result
    assert "new" in result
