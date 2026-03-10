"""Auto-update service."""
from .update_service import fetch_latest_version, get_installed_version, is_newer, launch_upgrade

__all__ = ["fetch_latest_version", "get_installed_version", "is_newer", "launch_upgrade"]
