from __future__ import annotations

from pathlib import Path
from typing import Any


def workflow_text(config: dict[str, Any]) -> str:
    states = workflow_states(config)
    reviewers = config.get("pr_reviewers", ["vector-hb", "nathaniel-hb"])

    lines = [
        "---",
        "tracker:",
        "  kind: linear",
        "  api_key: $LINEAR_API_KEY",
        f"  project_slug: {yaml_scalar(config['linear_project_slug'])}",
        "  active_states:",
        *yaml_list([states["ready"], states["working"], "Merging", "Rework"]),
        "  terminal_states:",
        *yaml_list(states["terminal"]),
        "polling:",
        f"  interval_ms: {int(config.get('poll_interval_ms', 5000))}",
        "workspace:",
        f"  root: {yaml_scalar(config['workspace_root'])}",
        "hooks:",
        "  after_create: |",
        indent_block(config["after_create"], 4),
        "  before_remove: |",
        indent_block(config.get("before_remove", "true"), 4),
        "agent:",
        f"  max_concurrent_agents: {int(config.get('max_concurrent_agents', 1))}",
        f"  max_turns: {int(config.get('max_turns', 20))}",
        "codex:",
        f"  command: {yaml_scalar(config.get('codex_command', 'codex app-server'))}",
        f"  approval_policy: {yaml_scalar(config.get('codex_approval_policy', 'never'))}",
        f"  thread_sandbox: {yaml_scalar(config.get('codex_thread_sandbox', 'danger-full-access'))}",
        "  turn_sandbox_policy:",
        *yaml_map(config.get("codex_turn_sandbox_policy", {"type": "dangerFullAccess"}), 4),
        "---",
        "",
        prompt_body(states, reviewers),
    ]

    return "\n".join(lines) + "\n"


def write_workflow(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow_text(config), encoding="utf-8")


def default_after_create(repo_url: str) -> str:
    return "\n".join(
        [
            f"git clone --depth 1 {shell_single_quote(repo_url)} .",
            "if command -v mise >/dev/null 2>&1; then",
            "  mise trust || true",
            "  mise install || true",
            "fi",
        ]
    )


def workflow_states(config: dict[str, Any]) -> dict[str, Any]:
    states = config.get("states") or {}
    return {
        "ready": states.get("ready", "Todo"),
        "working": states.get("working", "In Progress"),
        "complete": states.get("complete", "Dev Complete"),
        "blocked": states.get("blocked", "Blocked"),
        "terminal": states.get("terminal", ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]),
    }


def prompt_body(states: dict[str, Any], reviewers: list[str]) -> str:
    reviewer_list = ", ".join(f"`{reviewer}`" for reviewer in reviewers)
    reviewer_cli_args = " ".join(f"--add-reviewer {reviewer}" for reviewer in reviewers)

    return f"""You are working on a Linear ticket `{{{{ issue.identifier }}}}`.

Issue context:
Identifier: {{{{ issue.identifier }}}}
Title: {{{{ issue.title }}}}
Current status: {{{{ issue.state }}}}
Labels: {{{{ issue.labels }}}}
URL: {{{{ issue.url }}}}

Description:
{{% if issue.description %}}
{{{{ issue.description }}}}
{{% else %}}
No description provided.
{{% endif %}}

Instructions:

1. This is an unattended orchestration session. Never ask a human to perform follow-up actions.
2. Only stop early for a true blocker: missing required auth, permissions, secrets, or tools.
3. Work only in the provided repository copy.
4. Final message must report completed actions, PR URL, validation, and blockers only.
5. Treat `{states["ready"]}` as ready for work, `{states["working"]}` as actively running, `{states["complete"]}` as a non-active PR handoff state, and `{states["blocked"]}` as blocked when that state exists.
6. Respect Linear dependency ordering: do not start or continue implementation on an issue with unresolved `blocked by` relations or a blocked status. If dependencies are unresolved, leave the issue out of active work, document the blocker, and do not create a PR for dependent work.

GitHub delivery requirements:

- Always create a branch for the issue before committing changes.
- Branch names must use exactly one of these prefixes: `feature/`, `bugfix/`, or `hotfix/`.
- Branch names must be formatted as `<prefix>{{{{ issue.identifier }}}}-short-kebab-summary`, for example `feature/{{{{ issue.identifier }}}}-add-login-form`.
- Choose `bugfix/` for defects, `hotfix/` for urgent production fixes, and `feature/` for all other work.
- Never include a person's name, username, initials, or owner prefix in a branch name.
- Always commit completed changes.
- Always push the branch to origin.
- Always open a GitHub PR against the repository's default branch.
- The PR title must start with the Linear issue identifier, for example `{{{{ issue.identifier }}}}: {{{{ issue.title }}}}`.
- Add or attach the PR link to the Linear issue.
- Assign these PR reviewers before claiming completion: {reviewer_list}. With GitHub CLI, use `gh pr edit <PR> {reviewer_cli_args}`.
- After opening the PR and assigning reviewers, run `orchestra github pr-feedback wait --wait-seconds 300 --poll-seconds 15 --format markdown` from the PR branch. This is a required wait for automated reviewers such as Gemini to post feedback.
- Use the PR feedback helper output as the source of truth for GitHub PR review comments, review threads, status checks, and automated Gemini code review feedback.
- For every review comment or Gemini recommendation: read it, evaluate whether it is valid, incorporate changes when valid, reply with what changed or why no change was made, and resolve the thread when GitHub allows it.
- If you push follow-up commits after review feedback, run `orchestra github pr-feedback wait --wait-seconds 300 --poll-seconds 15 --format markdown` again before claiming completion.
- Do not claim completion while valid review feedback remains unaddressed.
- Never move the Linear issue to any terminal state, including `Done`, `Closed`, `Cancelled`, `Canceled`, or `Duplicate`. The only successful handoff state is `{states["complete"]}`.
- When the PR exists, validation is complete, required reviewers are assigned, and review feedback has been handled, move the Linear issue to `{states["complete"]}`.
- After moving the Linear issue to `{states["complete"]}`, stop work on that issue and do not advance it again.
- If you cannot push or create a PR, move the issue to `{states["blocked"]}` if that state exists; otherwise leave it in `{states["working"]}` and document the blocker.
- Do not claim completion unless a GitHub PR exists and all PR review requirements above are complete.

Use `linear_graphql` when you need to update the Linear workpad or inspect issue context.
Keep progress in a single persistent issue comment when your workflow requires one.
Run the validation required by the ticket before marking work complete.
"""


def yaml_list(values: list[str]) -> list[str]:
    seen = set()
    lines = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        lines.append(f"    - {yaml_scalar(value)}")
    return lines


def yaml_map(values: dict[str, Any], spaces: int) -> list[str]:
    prefix = " " * spaces
    return [f"{prefix}{key}: {yaml_scalar(value)}" for key, value in values.items()]


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text.startswith("$") and text.count("$") == 1 and text[1:].replace("_", "A").isalnum():
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def indent_block(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


def shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"
