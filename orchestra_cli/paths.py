from __future__ import annotations

import os
from pathlib import Path


DEFAULT_SYMPHONY_REPO = "https://github.com/openai/symphony.git"


def default_home() -> Path:
    override = os.environ.get("ORCHESTRA_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".orchestra"


def config_path(home: Path) -> Path:
    return home / "config.json"


def workflow_path(home: Path) -> Path:
    return home / "WORKFLOW.md"


def workspaces_path(home: Path) -> Path:
    return home / "workspaces"


def symphony_path(home: Path) -> Path:
    return home / "symphony"


def symphony_elixir_path(home: Path) -> Path:
    return symphony_path(home) / "elixir"
