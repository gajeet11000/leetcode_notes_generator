"""Backward-compatible settings shim. Exports `BaseProjectSettings` from `leetnotes.config`."""

from leetnotes.config import BaseProjectSettings, find_project_root, get_resource_path

__all__ = ["BaseProjectSettings", "find_project_root", "get_resource_path"]
