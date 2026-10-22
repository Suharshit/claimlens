"""Shared settings: config.yaml loader, project paths and the output disclaimer.

Setup infrastructure (not a feature). Every module reads thresholds and paths
through ``load_config()`` so nothing is hard-coded.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = PROJECT_ROOT / "config.yaml"

# Every output shown to users carries this label (01-project-brief, safety rules).
DISCLAIMER: str = "Educational prototype — not insurance, legal or medical advice."


@lru_cache(maxsize=1)
def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config.yaml once and return it as a dict."""
    config_file = Path(path) if path else CONFIG_PATH
    with config_file.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def project_path(key: str) -> Path:
    """Resolve a ``paths.<key>`` entry from config.yaml to an absolute path.

    Example: ``project_path("state_dir")`` -> ``<repo>/state``.
    """
    return PROJECT_ROOT / load_config()["paths"][key]
