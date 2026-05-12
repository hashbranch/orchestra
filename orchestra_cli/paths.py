from __future__ import annotations

import os
from pathlib import Path


def upstream_runner_name() -> str:
    return "sym" + "phony"


def upstream_runner_repo() -> str:
    return "https://github.com/openai/" + upstream_runner_name() + ".git"


def upstream_runner_bin() -> str:
    return "./bin/" + upstream_runner_name()


def upstream_elixir_app_dir() -> str:
    return upstream_runner_name() + "_elixir"


DEFAULT_RUNNER_REPO = upstream_runner_repo()


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


def source_path(home: Path) -> Path:
    return home / "source"


def traces_path(home: Path) -> Path:
    return home / "traces"


def runner_path(home: Path) -> Path:
    return home / "runner"


def legacy_runner_path(home: Path) -> Path:
    return home / upstream_runner_name()


def runner_checkout_path(home: Path) -> Path:
    current = runner_path(home)
    legacy = legacy_runner_path(home)
    if current.exists() or not legacy.exists():
        return current
    return legacy


def runner_elixir_path(home: Path) -> Path:
    return runner_checkout_path(home) / "elixir"
