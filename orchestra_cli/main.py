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
    DEFAULT_RUNNER_REPO,
    config_path,
    default_home,
    legacy_runner_path,
    source_path,
    upstream_elixir_app_dir,
    upstream_runner_bin,
    runner_elixir_path,
    runner_path,
    traces_path,
    workflow_path,
    workspaces_path,
)
from orchestra_cli.pr_feedback import (
    FeedbackOptions,
    PrFeedbackError,
    ReviewerOptions,
    ensure_pr_reviewers,
    format_feedback,
    format_reviewer_result,
    wait_for_pr_feedback,
)
from orchestra_cli.trace import (
    TraceError,
    format_trace_event,
    infer_issue_identifier,
    parse_fields,
    parse_payload_json,
    write_trace_event,
)
from orchestra_cli.version import __version__
from orchestra_cli.workflow import default_after_create, write_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestra", description="Bootstrap and run a local Orchestra runner.")
    parser.add_argument("--home", type=Path, default=default_home(), help="Orchestra home directory.")
    parser.add_argument("--version", action="version", version=f"orchestra {__version__}")

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
        help="GitHub repo URL the runner should clone for each issue workspace; this becomes origin for PRs.",
    )
    init_parser.add_argument("--codex-command", default="codex app-server")
    init_parser.add_argument("--max-concurrent-agents", type=int)
    init_parser.add_argument("--max-turns", type=int, default=20)
    init_parser.add_argument("--ready-state", default="Todo", help="Linear state the runner should pick up as ready work.")
    init_parser.add_argument("--working-state", default="In Progress", help="Linear state used while an agent is working.")
    init_parser.add_argument("--complete-state", default="Dev Complete", help="Linear state used after PR creation and validation.")
    init_parser.add_argument("--blocked-state", default="Blocked", help="Linear state used for blockers when it exists.")
    init_parser.add_argument(
        "--terminal-states",
        default="Closed,Cancelled,Canceled,Duplicate,Done",
        help="Comma-separated Linear terminal states that the runner should ignore/clean up.",
    )
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing config.")
    init_parser.set_defaults(func=cmd_init)

    install_parser = subcommands.add_parser("repair-runner", help=argparse.SUPPRESS)
    install_parser.add_argument("--source", default=DEFAULT_RUNNER_REPO)
    install_parser.add_argument("--ref", help="Optional git ref to checkout after clone/fetch.")
    install_parser.add_argument("--force", action="store_true", help="Replace existing runner checkout.")
    install_parser.add_argument("--skip-build", action="store_true", help="Clone/update the runner without running mix build.")
    install_parser.add_argument(
        "--no-install-mise",
        action="store_true",
        help="Do not bootstrap mise automatically when no Elixir toolchain is found.",
    )
    install_parser.set_defaults(func=cmd_install_runner)
    install_alias_parser = subcommands.add_parser("install-runner", help=argparse.SUPPRESS)
    install_alias_parser.add_argument("--source", default=DEFAULT_RUNNER_REPO)
    install_alias_parser.add_argument("--ref", help="Optional git ref to checkout after clone/fetch.")
    install_alias_parser.add_argument("--force", action="store_true", help="Replace existing runner checkout.")
    install_alias_parser.add_argument("--skip-build", action="store_true", help="Clone/update the runner without running mix build.")
    install_alias_parser.add_argument(
        "--no-install-mise",
        action="store_true",
        help="Do not bootstrap mise automatically when no Elixir toolchain is found.",
    )
    install_alias_parser.set_defaults(func=cmd_install_runner)

    doctor_parser = subcommands.add_parser("doctor", help="Check local prerequisites and install state.")
    doctor_parser.set_defaults(func=cmd_doctor)

    run_parser = subcommands.add_parser("run", help="Run the local Orchestra service.")
    run_parser.add_argument("--workflow", type=Path, help="Override workflow path.")
    run_parser.add_argument("--extra-arg", action="append", default=[], help="Extra argument passed to the runner binary.")
    run_parser.set_defaults(func=cmd_run)

    up_parser = subcommands.add_parser("up", help="Check for Orchestra updates, then run the local service.")
    up_parser.add_argument("--workflow", type=Path, help="Override workflow path.")
    up_parser.add_argument("--extra-arg", action="append", default=[], help="Extra argument passed to the runner binary.")
    up_parser.add_argument("--yes-update", action="store_true", help="Apply an available Orchestra update without prompting.")
    up_parser.add_argument("--no-update", action="store_true", help="Skip the Orchestra update check.")
    up_parser.set_defaults(func=cmd_up)

    update_parser = subcommands.add_parser("update", help="Update Orchestra from its source checkout.")
    update_parser.add_argument("--check", action="store_true", help="Only check whether an update is available.")
    update_parser.add_argument("--yes", action="store_true", help="Apply an available update without prompting.")
    update_parser.add_argument("--skip-install", action="store_true", help=argparse.SUPPRESS)
    update_parser.set_defaults(func=cmd_update)

    version_parser = subcommands.add_parser("version", help="Show Orchestra version.")
    version_parser.set_defaults(func=cmd_version)

    show_parser = subcommands.add_parser("show", help="Show generated paths or config.")
    show_parser.add_argument("what", choices=["paths", "config", "workflow"])
    show_parser.set_defaults(func=cmd_show)

    refresh_parser = subcommands.add_parser("refresh-workflow", help="Regenerate WORKFLOW.md from config.")
    refresh_parser.set_defaults(func=cmd_refresh_workflow)

    github_parser = subcommands.add_parser("github", help="GitHub helper commands for agents.")
    github_subcommands = github_parser.add_subparsers(dest="github_command", required=True)
    github_pr_feedback_parser = github_subcommands.add_parser("pr-feedback", help="GitHub PR feedback helpers.")
    github_pr_feedback_subcommands = github_pr_feedback_parser.add_subparsers(
        dest="github_pr_feedback_command",
        required=True,
    )
    add_pr_feedback_wait_parser(github_pr_feedback_subcommands)
    github_reviewers_parser = github_subcommands.add_parser("reviewers", help="GitHub PR reviewer helpers.")
    github_reviewers_subcommands = github_reviewers_parser.add_subparsers(
        dest="github_reviewers_command",
        required=True,
    )
    add_reviewers_ensure_parser(github_reviewers_subcommands)

    pr_feedback_parser = subcommands.add_parser(
        "pr-feedback",
        help="Deprecated alias for `orchestra github pr-feedback`.",
    )
    pr_feedback_subcommands = pr_feedback_parser.add_subparsers(dest="pr_feedback_command", required=True)
    add_pr_feedback_wait_parser(pr_feedback_subcommands)

    trace_parser = subcommands.add_parser("trace", help="Write or inspect Orchestra trace events.")
    trace_subcommands = trace_parser.add_subparsers(dest="trace_command", required=True)
    trace_event_parser = trace_subcommands.add_parser("event", help="Append a structured trace event.")
    trace_event_parser.add_argument("--issue", help="Issue identifier such as CLA-150.")
    trace_event_parser.add_argument("--kind", required=True, help="Event kind, such as completion_decision.")
    trace_event_parser.add_argument("--source", default="agent", help="Event source.")
    trace_event_parser.add_argument("--message", help="Human-readable decision note.")
    trace_event_parser.add_argument("--field", action="append", default=[], help="Payload field as key=value. Repeatable.")
    trace_event_parser.add_argument("--payload-json", help="Additional JSON object payload.")
    trace_event_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    trace_event_parser.set_defaults(func=cmd_trace_event)

    set_key_parser = subcommands.add_parser("set-linear-key", help="Store or update the Linear API key in config.")
    set_key_parser.add_argument("--linear-api-key", help="Linear API key. Omit to prompt securely.")
    set_key_parser.set_defaults(func=cmd_set_linear_key)

    args = parser.parse_args(argv)
    return args.func(args)


def add_pr_feedback_wait_parser(subcommands: argparse._SubParsersAction) -> None:
    wait_parser = subcommands.add_parser(
        "wait",
        help="Wait for GitHub PR feedback and print a normalized summary.",
    )
    wait_parser.add_argument("--pr", help="PR number or URL. Defaults to the PR for the current branch.")
    wait_parser.add_argument("--repo", help="GitHub repo in owner/name form. Inferred from the PR URL when omitted.")
    wait_parser.add_argument(
        "--wait-seconds",
        type=int,
        default=300,
        help="Total observation window before returning feedback.",
    )
    wait_parser.add_argument(
        "--poll-seconds",
        type=int,
        default=15,
        help="How often to poll GitHub during the observation window.",
    )
    wait_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    wait_parser.set_defaults(func=cmd_pr_feedback_wait)


def add_reviewers_ensure_parser(subcommands: argparse._SubParsersAction) -> None:
    ensure_parser = subcommands.add_parser(
        "ensure",
        help="Request GitHub PR reviewers and print a normalized summary.",
    )
    ensure_parser.add_argument("--pr", help="PR number or URL. Defaults to the PR for the current branch.")
    ensure_parser.add_argument("--repo", help="GitHub repo in owner/name form. Inferred from the PR URL when omitted.")
    ensure_parser.add_argument(
        "--reviewer",
        action="append",
        default=[],
        help="Reviewer login to request. Repeat for multiple reviewers.",
    )
    ensure_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ensure_parser.set_defaults(func=cmd_reviewers_ensure)


def cmd_init(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    cfg_path = config_path(home)
    wf_path = workflow_path(home)

    if cfg_path.exists() and not args.force:
        print(f"Config already exists at {cfg_path}. Use --force to overwrite.", file=sys.stderr)
        return 2

    print_init_intro()
    print_init_step(1, 4, "Linear API key", "Authenticate Orchestra to read and update Linear issues.")
    linear_api_key = resolve_linear_api_key(args.linear_api_key)
    print_init_step(2, 4, "Linear project", "Choose which Linear project Orchestra should watch for work.")
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
        "How many Linear issues Orchestra may work on at the same time.",
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
        "pr_reviewers": ["vector-hb", "nathaniel-hb"],
        "states": {
            "ready": args.ready_state,
            "working": args.working_state,
            "complete": args.complete_state,
            "blocked": args.blocked_state,
            "terminal": parse_csv(args.terminal_states),
        },
        "runner_repo": DEFAULT_RUNNER_REPO,
    }

    home.mkdir(parents=True, exist_ok=True)
    workspaces_path(home).mkdir(parents=True, exist_ok=True)
    traces_path(home).mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_workflow(wf_path, config)

    print_init_summary(home, cfg_path, wf_path, config)
    return 0


def cmd_install_runner(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    checkout = runner_path(home)
    legacy_checkout = legacy_runner_path(home)

    if checkout.exists() and args.force:
        shutil.rmtree(checkout)

    if legacy_checkout.exists() and not checkout.exists():
        legacy_checkout.rename(checkout)

    if checkout.exists():
        if not (checkout / ".git").is_dir():
            print(f"Replacing non-git runner directory at {checkout}.")
            remove_path(checkout)
            home.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", args.source, str(checkout)])
        else:
            run(["git", "-C", str(checkout), "fetch", "--all", "--tags"])
    else:
        home.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", args.source, str(checkout)])

    if args.ref:
        run(["git", "-C", str(checkout), "checkout", args.ref])

    elixir_dir = runner_elixir_path(home)
    if not elixir_dir.exists():
        print(f"Expected runner Elixir directory at {elixir_dir}", file=sys.stderr)
        return 1

    if not ensure_runner_blocker_patch(elixir_dir):
        return 1

    if args.skip_build:
        print(f"Installed runner source at {checkout}; skipped build.")
        return 0

    toolchain = ensure_elixir_toolchain(install_mise=not args.no_install_mise)
    if toolchain is None:
        print("Installed runner source, but neither mise nor mix is available to build it.", file=sys.stderr)
        return 1

    build_runner(elixir_dir, toolchain)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    checks = [
        check_path("home", home, must_exist=True),
        check_path("config", config_path(home), must_exist=True),
        check_path("workflow", workflow_path(home), must_exist=True),
        check_path("workspaces", workspaces_path(home), must_exist=True),
        check_path("traces", traces_path(home), must_exist=True),
        check_executable("git"),
        check_executable("gh"),
        check_executable("codex"),
        check_elixir_toolchain(),
        check_env_or_config("LINEAR_API_KEY", config_path(home)),
        check_path("runner checkout", runner_elixir_path(home), must_exist=True),
    ]

    for check in checks:
        icon = "ok" if check["ok"] else "fail"
        print(f"{icon}: {check['label']} - {check['detail']}")

    return 0 if all(check["ok"] for check in checks) else 1


def cmd_run(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    elixir_dir = runner_elixir_path(home)
    wf_path = (args.workflow or workflow_path(home)).expanduser()

    if not elixir_dir.exists():
        print(f"Orchestra runner is not installed at {elixir_dir}. Re-run the Orchestra installer.", file=sys.stderr)
        return 1
    if not wf_path.exists():
        print(f"Workflow file does not exist at {wf_path}. Run `orchestra init` first.", file=sys.stderr)
        return 1
    if not ensure_runner_blocker_patch(elixir_dir):
        return 1

    command = [upstream_runner_bin(), str(wf_path)] + args.extra_arg
    mise = find_executable("mise")
    if mise:
        command = [mise, "exec", "--"] + command

    try:
        return subprocess.call(command, cwd=elixir_dir, env=run_env(home))
    except KeyboardInterrupt:
        print("\nInterrupted; Orchestra stopped.", file=sys.stderr)
        return 130


def cmd_up(args: argparse.Namespace) -> int:
    if args.yes_update and args.no_update:
        print("Use only one of --yes-update or --no-update.", file=sys.stderr)
        return 2

    if not args.no_update:
        status = check_update_status(args.home.expanduser())
        if status["ok"] and status.get("available"):
            print(f"Orchestra update available: {status['current']} -> {status['latest']}")
            if args.yes_update or confirm("Update Orchestra now?"):
                result = apply_update(args.home.expanduser(), skip_install=False)
                if result != 0:
                    return result
                refresh_workflow_if_configured(args.home.expanduser())
            else:
                print("Skipping Orchestra update.")
        elif status["ok"]:
            print(f"Orchestra is up to date ({status['current']}).")
        else:
            print(f"Could not check for Orchestra updates: {status['reason']}", file=sys.stderr)

    return cmd_run(args)


def cmd_update(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    status = check_update_status(home)
    if not status["ok"]:
        print(f"Could not check for Orchestra updates: {status['reason']}", file=sys.stderr)
        return 1

    if not status.get("available"):
        print(f"Orchestra is up to date ({status['current']}).")
        return 0

    print(f"Orchestra update available: {status['current']} -> {status['latest']}")
    if args.check:
        return 0

    if not args.yes and not confirm("Update Orchestra now?"):
        print("Skipped Orchestra update.")
        return 0

    result = apply_update(home, skip_install=args.skip_install)
    if result == 0:
        refresh_workflow_if_configured(home)
    return result


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"orchestra {__version__}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    if args.what == "paths":
        print(json.dumps(paths_payload(home), indent=2, sort_keys=True))
    elif args.what == "config":
        print(json.dumps(redacted_config(load_config(home)), indent=2, sort_keys=True))
    elif args.what == "workflow":
        print(workflow_path(home).read_text(encoding="utf-8"), end="")
    return 0


def cmd_refresh_workflow(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    cfg_path = config_path(home)
    wf_path = workflow_path(home)

    try:
        config = load_config(home)
    except FileNotFoundError:
        print(f"Config does not exist at {cfg_path}. Run `orchestra init` first.", file=sys.stderr)
        return 1

    write_workflow(wf_path, config)
    print(f"Regenerated workflow at {wf_path}")
    return 0


def cmd_pr_feedback_wait(args: argparse.Namespace) -> int:
    try:
        snapshot = wait_for_pr_feedback(
            FeedbackOptions(
                pr=args.pr,
                repo=args.repo,
                wait_seconds=args.wait_seconds,
                poll_seconds=args.poll_seconds,
                output_format=args.format,
            )
        )
        trace_helper_event(args.home.expanduser(), snapshot, "github.pr_feedback.wait.completed")
        print(format_feedback(snapshot, args.format))
        return 0
    except PrFeedbackError as error:
        print(f"PR feedback wait failed: {error}", file=sys.stderr)
        return 1


def cmd_reviewers_ensure(args: argparse.Namespace) -> int:
    try:
        result = ensure_pr_reviewers(
            ReviewerOptions(
                pr=args.pr,
                repo=args.repo,
                reviewers=args.reviewer,
                output_format=args.format,
            )
        )
        trace_helper_event(args.home.expanduser(), result, "github.reviewers.ensure.completed")
        print(format_reviewer_result(result, args.format))
        return 0
    except PrFeedbackError as error:
        print(f"Reviewer ensure failed: {error}", file=sys.stderr)
        return 1


def cmd_trace_event(args: argparse.Namespace) -> int:
    home = args.home.expanduser()
    try:
        payload = parse_payload_json(args.payload_json)
        payload.update(parse_fields(args.field))
        event, path = write_trace_event(
            home,
            issue=args.issue,
            kind=args.kind,
            source=args.source,
            message=args.message,
            payload=payload,
            cwd=os.getcwd(),
        )
        print(format_trace_event(event, path, args.format))
        return 0
    except TraceError as error:
        print(f"Trace event failed: {error}", file=sys.stderr)
        return 1


def trace_helper_event(home: Path, result: dict[str, Any], kind: str) -> None:
    pr = result.get("pr") or {}
    issue = infer_issue_identifier(str(pr.get("title") or ""), str(pr.get("url") or ""))
    try:
        write_trace_event(
            home,
            issue=issue,
            kind=kind,
            source="orchestra",
            message=str(result.get("summary") or kind),
            payload=result,
            cwd=os.getcwd(),
        )
    except OSError as error:
        print(f"Warning: could not write trace event: {error}", file=sys.stderr)


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
        "source": str(source_path(home)),
        "workflow": str(workflow_path(home)),
        "workspaces": str(workspaces_path(home)),
        "traces": str(traces_path(home)),
        "runner": str(runner_path(home)),
        "runner_elixir": str(runner_elixir_path(home)),
    }


def check_update_status(home: Path) -> dict[str, Any]:
    source = source_path(home)
    if not (source / ".git").is_dir():
        return {
            "ok": False,
            "reason": f"source checkout not found at {source}; install with the public curl command first",
        }

    install_ref = git_output(source, ["config", "--get", "orchestra.installRef"]) or "main"
    fetch = subprocess.run(["git", "-C", str(source), "fetch", "origin", "--tags"], capture_output=True, text=True)
    if fetch.returncode != 0:
        return {"ok": False, "reason": fetch.stderr.strip() or "git fetch failed"}

    current = git_output(source, ["rev-parse", "HEAD"])
    target = resolve_update_target(source, install_ref)
    if current is None or target is None:
        return {"ok": False, "reason": f"could not resolve update target for {install_ref}"}

    current_label = current_version_label(source, current)
    latest = target["revision"]
    latest_label = target["label"]

    if git_is_ancestor(source, current, latest):
        return {
            "ok": True,
            "available": current != latest,
            "current": current_label,
            "latest": latest_label,
            "track": install_ref,
        }

    return {
        "ok": False,
        "reason": f"source checkout at {source} has diverged from {latest_label}",
        "current": current_label,
        "latest": latest_label,
        "track": install_ref,
    }


def apply_update(home: Path, skip_install: bool = False) -> int:
    source = source_path(home)
    if not (source / ".git").is_dir():
        print(f"Source checkout not found at {source}. Reinstall with the public curl command.", file=sys.stderr)
        return 1

    install_ref = git_output(source, ["config", "--get", "orchestra.installRef"]) or "main"
    fetch = subprocess.run(["git", "-C", str(source), "fetch", "origin", "--tags"], capture_output=True, text=True)
    if fetch.returncode != 0:
        print(fetch.stderr.strip() or fetch.stdout.strip() or "git fetch failed", file=sys.stderr)
        return fetch.returncode

    target = resolve_update_target(source, install_ref)
    if target is None:
        print(f"Could not resolve update target for {install_ref}.", file=sys.stderr)
        return 1

    if target["kind"] == "branch":
        commands = [
            ["git", "-C", str(source), "checkout", target["name"]],
            ["git", "-C", str(source), "pull", "--ff-only", "origin", target["name"]],
        ]
    else:
        commands = [["git", "-C", str(source), "checkout", target["name"]]]

    for command in commands:
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            print(completed.stderr.strip() or completed.stdout.strip() or "update command failed", file=sys.stderr)
            return completed.returncode

    if skip_install:
        print(f"Updated source checkout at {source}; skipped package reinstall.")
        return 0

    installer = source / "scripts" / "install-orchestra"
    completed = subprocess.run([str(installer)])
    return completed.returncode


def resolve_update_target(source: Path, install_ref: str) -> dict[str, str] | None:
    if install_ref == "latest":
        latest_tag = latest_release_tag(source)
        if latest_tag:
            revision = git_output(source, ["rev-parse", latest_tag])
            if revision:
                return {"kind": "tag", "name": latest_tag, "label": latest_tag, "revision": revision}
        install_ref = "main"

    tag_revision = git_output(source, ["rev-parse", f"refs/tags/{install_ref}"])
    if tag_revision:
        return {"kind": "tag", "name": install_ref, "label": install_ref, "revision": tag_revision}

    branch_revision = git_output(source, ["rev-parse", f"origin/{install_ref}"])
    if branch_revision:
        return {
            "kind": "branch",
            "name": install_ref,
            "label": f"origin/{install_ref}",
            "revision": branch_revision,
        }

    return None


def latest_release_tag(source: Path) -> str | None:
    output = git_output(source, ["tag", "--list", "v*", "--sort=-v:refname"])
    if not output:
        return None
    return output.splitlines()[0]


def current_version_label(source: Path, revision: str) -> str:
    tag = git_output(source, ["describe", "--tags", "--exact-match", revision])
    return tag or revision[:7]


def refresh_workflow_if_configured(home: Path) -> None:
    if not config_path(home).exists():
        return
    try:
        write_workflow(workflow_path(home), load_config(home))
        print(f"Regenerated workflow at {workflow_path(home)}")
    except (OSError, json.JSONDecodeError) as error:
        print(f"Warning: could not regenerate workflow after update: {error}", file=sys.stderr)


def git_output(source: Path, args: list[str]) -> str | None:
    completed = subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_is_ancestor(source: Path, older: str, newer: str) -> bool:
    completed = subprocess.run(["git", "-C", str(source), "merge-base", "--is-ancestor", older, newer])
    return completed.returncode == 0


def confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        print("Non-interactive shell; rerun with --yes to apply the update.")
        return False
    return input(f"{prompt} [y/N]: ").strip().lower() in {"y", "yes"}


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


def build_runner(elixir_dir: Path, toolchain: tuple[str, str]) -> None:
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


def ensure_runner_blocker_patch(elixir_dir: Path) -> bool:
    orchestrator = elixir_dir / "lib" / upstream_elixir_app_dir() / "orchestrator.ex"
    if not orchestrator.exists():
        print(f"Expected runner orchestrator at {orchestrator}", file=sys.stderr)
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
        print("Could not patch runner blocker scheduling logic; upstream file shape changed.", file=sys.stderr)
        return False

    orchestrator.write_text(updated, encoding="utf-8")
    print("Patched runner to skip any issue with unresolved Linear blockers.")
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
                "This wizard configures a local Orchestra runner for Linear-driven Codex work.",
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


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


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
        "detail": "not found; the Orchestra installer will try to install mise",
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
