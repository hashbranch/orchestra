from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from orchestra_cli.paths import (
    DEFAULT_SYMPHONY_REPO,
    config_path,
    default_home,
    symphony_elixir_path,
    symphony_path,
    workflow_path,
    workspaces_path,
)
from orchestra_cli.workflow import default_after_create, write_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestra", description="Bootstrap and run a local Symphony instance.")
    parser.add_argument("--home", type=Path, default=default_home(), help="Orchestra home directory.")

    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init", help="Create local Orchestra config and WORKFLOW.md.")
    init_parser.add_argument("--linear-project-slug")
    init_parser.add_argument(
        "--linear-api-key",
        help="Linear API key to write into config. Omit or enter blank interactively to use $LINEAR_API_KEY.",
    )
    init_parser.add_argument(
        "--target-repo",
        "--github-repo",
        dest="target_repo",
        help="GitHub repo URL Symphony should clone for each issue workspace; this becomes origin for PRs.",
    )
    init_parser.add_argument("--codex-command", default="codex app-server")
    init_parser.add_argument("--max-concurrent-agents", type=int)
    init_parser.add_argument("--max-turns", type=int, default=20)
    init_parser.add_argument("--ready-state", default="Todo", help="Linear state Symphony should pick up as ready work.")
    init_parser.add_argument("--working-state", default="In Progress", help="Linear state used while an agent is working.")
    init_parser.add_argument("--complete-state", default="Dev Complete", help="Linear state used after PR creation and validation.")
    init_parser.add_argument("--blocked-state", default="Blocked", help="Linear state used for blockers when it exists.")
    init_parser.add_argument(
        "--terminal-states",
        default="Closed,Cancelled,Canceled,Duplicate,Done",
        help="Comma-separated Linear terminal states that Symphony should ignore/clean up.",
    )
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config.")
    init_parser.set_defaults(func=cmd_init)

    install_parser = subcommands.add_parser("install-symphony", help="Clone and build OpenAI Symphony.")
    install_parser.add_argument("--source", default=DEFAULT_SYMPHONY_REPO)
    install_parser.add_argument("--ref", help="Optional git ref to checkout after clone/fetch.")
    install_parser.add_argument("--force", action="store_true", help="Replace existing Symphony checkout.")
    install_parser.add_argument("--skip-build", action="store_true", help="Clone/update Symphony without running mix build.")
    install_parser.add_argument(
        "--no-install-mise",
        action="store_true",
        help="Do not bootstrap mise automatically when no Elixir toolchain is found.",
    )
    install_parser.set_defaults(func=cmd_install_symphony)

    doctor_parser = subcommands.add_parser("doctor", help="Check local prerequisites and install state.")
    doctor_parser.set_defaults(func=cmd_doctor)

    run_parser = subcommands.add_parser("run", help="Run the local Symphony service.")
    run_parser.add_argument("--workflow", type=Path, help="Override workflow path.")
    run_parser.add_argument("--extra-arg", action="append", default=[], help="Extra argument passed to ./bin/symphony.")
    run_parser.set_defaults(func=cmd_run)

    show_parser = subcommands.add_parser("show", help="Show generated paths or config.")
    show_parser.add_argument("what", choices=["paths", "config", "workflow"])
    show_parser.set_defaults(func=cmd_show)

    set_key_parser = subcommands.add_parser("set-linear-key", help="Store or update the Linear API key in config.")
    set_key_parser.add_argument("--linear-api-key", help="Linear API key. Omit to prompt securely.")
    set_key_parser.set_defaults(func=cmd_set_linear_key)

    args = parser.parse_args(argv)
    return args.func(args)


def cmd_init(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    cfg_path = config_path(home)
    wf_path = workflow_path(home)

    if cfg_path.exists() and not args.force:
        print(f"Config already exists at {cfg_path}. Use --force to overwrite.", file=sys.stderr)
        return 2

    print_init_intro()
    print_init_step(1, 4, "Linear API key", "Authenticate Symphony to read and update Linear issues.")
    linear_api_key = resolve_linear_api_key(args.linear_api_key)
    print_init_step(2, 4, "Linear project", "Choose which Linear project Symphony should watch for work.")
    linear_project_slug = resolve_required_value(
        args.linear_project_slug,
        "Linear project slug",
        "Use the slug from the Linear project URL.",
    )
    print_init_step(3, 4, "GitHub target", "Choose the repo Codex agents will clone, edit, push, and open PRs against.")
    target_repo = resolve_required_value(
        args.target_repo,
        "Target GitHub repo URL",
        "This is the repository Codex agents clone, edit, push to, and open PRs against.",
    )
    print_init_step(4, 4, "Agent capacity", "Set how many Linear issues may run at the same time.")
    max_concurrent_agents = resolve_int_value(
        args.max_concurrent_agents,
        "Max concurrent agents",
        1,
        "How many Linear issues Symphony may work on at the same time.",
    )

    if linear_project_slug is None or target_repo is None or linear_api_key is None or max_concurrent_agents is None:
        return 2

    config = {
        "linear_project_slug": linear_project_slug,
        "linear_api_key": linear_api_key,
        "target_repo": target_repo,
        "workspace_root": str(workspaces_path(home)),
        "after_create": default_after_create(target_repo),
        "before_remove": "true",
        "codex_command": args.codex_command,
        "codex_approval_policy": "never",
        "codex_thread_sandbox": "danger-full-access",
        "codex_turn_sandbox_policy": {"type": "dangerFullAccess"},
        "max_concurrent_agents": max_concurrent_agents,
        "max_turns": args.max_turns,
        "states": {
            "ready": args.ready_state,
            "working": args.working_state,
            "complete": args.complete_state,
            "blocked": args.blocked_state,
            "terminal": parse_csv(args.terminal_states),
        },
        "symphony_repo": DEFAULT_SYMPHONY_REPO,
    }

    home.mkdir(parents=True, exist_ok=True)
    workspaces_path(home).mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_workflow(wf_path, config)

    print_init_summary(home, cfg_path, wf_path, config)
    return 0


def cmd_install_symphony(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    checkout = symphony_path(home)

    if checkout.exists() and args.force:
        shutil.rmtree(checkout)

    if checkout.exists():
        run(["git", "-C", str(checkout), "fetch", "--all", "--tags"])
    else:
        home.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", args.source, str(checkout)])

    if args.ref:
        run(["git", "-C", str(checkout), "checkout", args.ref])

    elixir_dir = symphony_elixir_path(home)
    if not elixir_dir.exists():
        print(f"Expected Symphony Elixir directory at {elixir_dir}", file=sys.stderr)
        return 1

    if not ensure_symphony_blocker_patch(elixir_dir):
        return 1

    if args.skip_build:
        print(f"Installed Symphony source at {checkout}; skipped build.")
        return 0

    toolchain = ensure_elixir_toolchain(install_mise=not args.no_install_mise)
    if toolchain is None:
        print("Installed Symphony source, but neither mise nor mix is available to build it.", file=sys.stderr)
        return 1

    build_symphony(elixir_dir, toolchain)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    checks = [
        check_path("home", home, must_exist=True),
        check_path("config", config_path(home), must_exist=True),
        check_path("workflow", workflow_path(home), must_exist=True),
        check_path("workspaces", workspaces_path(home), must_exist=True),
        check_executable("git"),
        check_executable("gh"),
        check_executable("codex"),
        check_elixir_toolchain(),
        check_env_or_config("LINEAR_API_KEY", config_path(home)),
        check_path("symphony checkout", symphony_elixir_path(home), must_exist=True),
    ]

    for check in checks:
        icon = "ok" if check["ok"] else "fail"
        print(f"{icon}: {check['label']} - {check['detail']}")

    return 0 if all(check["ok"] for check in checks) else 1


def cmd_run(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    elixir_dir = symphony_elixir_path(home)
    wf_path = (args.workflow or workflow_path(home)).expanduser()

    if not elixir_dir.exists():
        print(f"Symphony is not installed at {elixir_dir}. Run `orchestra install-symphony` first.", file=sys.stderr)
        return 1
    if not wf_path.exists():
        print(f"Workflow file does not exist at {wf_path}. Run `orchestra init` first.", file=sys.stderr)
        return 1
    if not ensure_symphony_blocker_patch(elixir_dir):
        return 1

    command = ["./bin/symphony", str(wf_path)] + args.extra_arg
    mise = find_executable("mise")
    if mise:
        command = [mise, "exec", "--"] + command

    try:
        return subprocess.call(command, cwd=elixir_dir, env=run_env(home))
    except KeyboardInterrupt:
        print("\nInterrupted; Symphony stopped.", file=sys.stderr)
        return 130


def cmd_show(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    if args.what == "paths":
        print(json.dumps(paths_payload(home), indent=2, sort_keys=True))
    elif args.what == "config":
        print(json.dumps(redacted_config(load_config(home)), indent=2, sort_keys=True))
    elif args.what == "workflow":
        print(workflow_path(home).read_text(encoding="utf-8"), end="")
    return 0


def cmd_set_linear_key(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    cfg_path = config_path(home)

    try:
        config = load_config(home)
    except FileNotFoundError:
        print(f"Config does not exist at {cfg_path}. Run `orchestra init` first.", file=sys.stderr)
        return 1

    linear_api_key = resolve_linear_api_key(args.linear_api_key)
    if linear_api_key is None:
        return 2

    config["linear_api_key"] = linear_api_key
    cfg_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Updated Linear API key in {cfg_path}")
    return 0


def paths_payload(home: Path) -> dict[str, str]:
    return {
        "home": str(home),
        "config": str(config_path(home)),
        "workflow": str(workflow_path(home)),
        "workspaces": str(workspaces_path(home)),
        "symphony": str(symphony_path(home)),
        "symphony_elixir": str(symphony_elixir_path(home)),
    }


def load_config(home: Path) -> dict[str, Any]:
    return json.loads(config_path(home).read_text(encoding="utf-8"))


def redacted_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(config)
    if redacted.get("linear_api_key") and redacted["linear_api_key"] != "$LINEAR_API_KEY":
        redacted["linear_api_key"] = "<redacted>"
    return redacted


def run_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()

    try:
        config = load_config(home)
    except (FileNotFoundError, json.JSONDecodeError):
        return env

    linear_api_key = config.get("linear_api_key")
    if linear_api_key and linear_api_key != "$LINEAR_API_KEY":
        env["LINEAR_API_KEY"] = linear_api_key

    return env


def ensure_elixir_toolchain(install_mise: bool = True) -> tuple[str, str] | None:
    mise = find_executable("mise")
    if mise:
        return ("mise", mise)

    mix = find_executable("mix")
    if mix:
        return ("mix", mix)

    if not install_mise:
        return None

    if not install_mise_binary():
        return None

    mise = find_executable("mise")
    if mise:
        return ("mise", mise)

    return None


def build_symphony(elixir_dir: Path, toolchain: tuple[str, str]) -> None:
    name, executable = toolchain
    if name == "mise":
        run([executable, "trust"], cwd=elixir_dir)
        run([executable, "install"], cwd=elixir_dir)
        run([executable, "exec", "--", "mix", "setup"], cwd=elixir_dir)
        run([executable, "exec", "--", "mix", "build"], cwd=elixir_dir)
    elif name == "mix":
        run([executable, "setup"], cwd=elixir_dir)
        run([executable, "build"], cwd=elixir_dir)
    else:
        raise ValueError(f"unsupported toolchain: {toolchain!r}")


def ensure_symphony_blocker_patch(elixir_dir: Path) -> bool:
    orchestrator = elixir_dir / "lib" / "symphony_elixir" / "orchestrator.ex"
    if not orchestrator.exists():
        print(f"Expected Symphony orchestrator at {orchestrator}", file=sys.stderr)
        return False

    text = orchestrator.read_text(encoding="utf-8")
    if "issue_blocked_by_non_terminal?" in text and "todo_issue_blocked_by_non_terminal?" not in text:
        return True

    updated = text.replace("!todo_issue_blocked_by_non_terminal?(issue, terminal_states)", "!issue_blocked_by_non_terminal?(issue, terminal_states)")
    old_function = """  defp todo_issue_blocked_by_non_terminal?(
         %Issue{state: issue_state, blocked_by: blockers},
         terminal_states
       )
       when is_binary(issue_state) and is_list(blockers) do
    normalize_issue_state(issue_state) == "todo" and
      Enum.any?(blockers, fn
        %{state: blocker_state} when is_binary(blocker_state) ->
          !terminal_issue_state?(blocker_state, terminal_states)

        _ ->
          true
      end)
  end

  defp todo_issue_blocked_by_non_terminal?(_issue, _terminal_states), do: false
"""
    new_function = """  defp issue_blocked_by_non_terminal?(
         %Issue{blocked_by: blockers},
         terminal_states
       )
       when is_list(blockers) do
    Enum.any?(blockers, fn
      %{state: blocker_state} when is_binary(blocker_state) ->
        !terminal_issue_state?(blocker_state, terminal_states)

      _ ->
        true
    end)
  end

  defp issue_blocked_by_non_terminal?(_issue, _terminal_states), do: false
"""
    updated = updated.replace(old_function, new_function)

    if updated == text or "todo_issue_blocked_by_non_terminal?" in updated:
        print("Could not patch Symphony blocker scheduling logic; upstream file shape changed.", file=sys.stderr)
        return False

    orchestrator.write_text(updated, encoding="utf-8")
    print("Patched Symphony to skip any issue with unresolved Linear blockers.")
    return True


def install_mise_binary() -> bool:
    command = mise_install_command()
    if command is None:
        print("Cannot install mise automatically because neither curl nor wget is available.", file=sys.stderr)
        return False

    print("mise was not found; installing mise for Elixir/Erlang toolchain management.")
    run_shell(command)
    return True


def mise_install_command() -> str | None:
    if find_executable("curl"):
        return "curl -fsSL https://mise.run | sh"
    if find_executable("wget"):
        return "wget -qO- https://mise.run | sh"
    return None


def find_executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found

    home = Path.home()
    for candidate in [
        home / ".local" / "bin" / name,
        home / "bin" / name,
        home / ".mise" / "bin" / name,
    ]:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def print_init_intro() -> None:
    print(
        "\n".join(
            [
                "",
                "Orchestra setup",
                "===============",
                "This wizard configures a local Symphony runner for Linear-driven Codex work.",
                "",
                "It will write local config, generate WORKFLOW.md, and create the workspace root.",
                "",
            ]
        )
    )


def print_init_step(step: int, total: int, title: str, detail: str) -> None:
    print(
        "\n".join(
            [
                "",
                f"[{step}/{total}] {title}",
                "-" * (len(str(step)) + len(str(total)) + len(title) + 4),
                detail,
            ]
        )
    )


def print_init_summary(home: Path, cfg_path: Path, wf_path: Path, config: dict[str, Any]) -> None:
    print(
        "\n".join(
            [
                "",
                "Orchestra is configured.",
                "",
                "Settings",
                f"  Linear project:        {config['linear_project_slug']}",
                f"  GitHub target repo:    {config['target_repo']}",
                f"  Max concurrent agents: {config['max_concurrent_agents']}",
                "",
                "Files",
                f"  Home:       {home}",
                f"  Config:     {cfg_path}",
                f"  Workflow:   {wf_path}",
                f"  Workspaces: {workspaces_path(home)}",
                "",
                "Next:",
                "  orchestra doctor",
                "  orchestra install-symphony",
                "  orchestra run --extra-arg=--i-understand-that-this-will-be-running-without-the-usual-guardrails",
            ]
        )
    )


def resolve_required_value(value: str | None, label: str, help_text: str) -> str | None:
    if value and value.strip():
        return value.strip()

    if not sys.stdin.isatty():
        print(f"Missing required init value: {label}. {help_text}", file=sys.stderr)
        return None

    entered = input(f"{label}: ").strip()
    if entered:
        return entered

    print(f"{label} is required.", file=sys.stderr)
    return None


def resolve_int_value(value: int | None, label: str, default: int, help_text: str) -> int | None:
    if value is not None:
        return value

    if not sys.stdin.isatty():
        return default

    entered = input(f"{label} [{default}]: ").strip()
    if not entered:
        return default

    try:
        parsed = int(entered)
    except ValueError:
        print(f"{label} must be an integer.", file=sys.stderr)
        return None

    if parsed < 1:
        print(f"{label} must be at least 1.", file=sys.stderr)
        return None

    return parsed


def resolve_linear_api_key(value: str | None) -> str | None:
    if value and value.strip():
        return value.strip()

    if not sys.stdin.isatty():
        return "$LINEAR_API_KEY"

    print("Stored in config.json and injected at runtime; never written to WORKFLOW.md.")
    print("Press Enter to use $LINEAR_API_KEY from the environment.")
    entered = getpass.getpass("Linear API key: ").strip()
    return entered or "$LINEAR_API_KEY"


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def run(command: list[str], cwd: Path | None = None) -> None:
    if os.environ.get("ORCHESTRA_QUIET") == "1":
        subprocess.run(command, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)
    else:
        print("+ " + " ".join(command))
        subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def run_shell(command: str) -> None:
    if os.environ.get("ORCHESTRA_QUIET") == "1":
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    else:
        print("+ " + command)
        subprocess.run(command, shell=True, check=True)


def check_path(label: str, path: Path, must_exist: bool) -> dict[str, Any]:
    exists = path.exists()
    return {"label": label, "ok": exists if must_exist else True, "detail": str(path)}


def check_executable(name: str) -> dict[str, Any]:
    found = find_executable(name)
    return {"label": name, "ok": found is not None, "detail": found or "not found on PATH"}


def check_any_executable(names: list[str], label: str) -> dict[str, Any]:
    found = next((find_executable(name) for name in names if find_executable(name)), None)
    return {"label": label, "ok": found is not None, "detail": found or "not found on PATH"}


def check_elixir_toolchain() -> dict[str, Any]:
    found = next((find_executable(name) for name in ["mise", "mix"] if find_executable(name)), None)
    if found:
        return {"label": "mise or mix", "ok": True, "detail": found}
    return {
        "label": "mise or mix",
        "ok": False,
        "detail": "not found; `orchestra install-symphony` will try to install mise",
    }


def check_env_or_config(env_name: str, cfg_path: Path) -> dict[str, Any]:
    if os.environ.get(env_name):
        return {"label": env_name, "ok": True, "detail": "set in environment"}

    if cfg_path.exists():
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}
        configured = config.get("linear_api_key")
        if configured and configured != f"${env_name}":
            return {"label": env_name, "ok": True, "detail": "configured in Orchestra config"}

    return {"label": env_name, "ok": False, "detail": "not set; export it or configure a concrete key"}


if __name__ == "__main__":
    raise SystemExit(main())
