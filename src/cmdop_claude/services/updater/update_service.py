"""Auto-update service — checks PyPI and runs pip upgrade in background."""
from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

_PYPI_URL = "https://pypi.org/pypi/cmdop-claude/json"
_TIMEOUT = 5  # seconds


def get_installed_version() -> str:
    """Return currently installed version of cmdop-claude."""
    return importlib.metadata.version("cmdop-claude")


def fetch_latest_version(timeout: int = _TIMEOUT) -> str | None:
    """Fetch latest version from PyPI JSON API. Returns None on any error."""
    try:
        with urlopen(_PYPI_URL, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data["info"]["version"]
    except Exception:
        return None


def is_newer(latest: str, installed: str) -> bool:
    """Return True if latest semver > installed semver."""
    def _t(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.lstrip("v").split("."))
        except Exception:
            return (0,)
    return _t(latest) > _t(installed)


def launch_upgrade(log_path: Path) -> None:
    """Start pip upgrade as a detached non-blocking background process."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    subprocess.Popen(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "cmdop-claude"],
        stdout=log_file,
        stderr=log_file,
        close_fds=True,
    )
