from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable


PR_VIEW_FIELDS = [
    "author",
    "baseRefName",
    "headRefName",
    "isDraft",
    "number",
    "reviewDecision",
    "state",
    "title",
    "url",
]

PR_FEEDBACK_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      title
      url
      state
      isDraft
      reviewDecision
      comments(first: 100) {
        nodes {
          author { login }
          body
          url
          createdAt
          updatedAt
          isMinimized
        }
      }
      reviews(first: 100) {
        nodes {
          author { login }
          body
          url
          state
          createdAt
          submittedAt
        }
      }
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              author { login }
              body
              url
              path
              line
              originalLine
              diffHunk
              createdAt
            }
          }
        }
      }
      commits(last: 1) {
        nodes {
          commit {
            oid
            statusCheckRollup {
              state
              contexts(first: 100) {
                nodes {
                  __typename
                  ... on CheckRun {
                    name
                    status
                    conclusion
                    detailsUrl
                    startedAt
                    completedAt
                  }
                  ... on StatusContext {
                    context
                    state
                    targetUrl
                    createdAt
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


@dataclass
class FeedbackOptions:
    pr: str | None = None
    repo: str | None = None
    wait_seconds: int = 300
    poll_seconds: int = 15
    output_format: str = "markdown"


class PrFeedbackError(RuntimeError):
    pass


def wait_for_pr_feedback(
    options: FeedbackOptions,
    *,
    cwd: str | None = None,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    started_at = now()
    deadline = started_at + max(options.wait_seconds, 0)
    poll_seconds = max(options.poll_seconds, 1)
    snapshot: dict[str, Any] | None = None

    while True:
        pr_view = fetch_pr_view(options.pr, options.repo, cwd=cwd)
        owner, name = resolve_repo(options.repo, pr_view)
        pr_number = int(pr_view["number"])
        feedback_payload = fetch_pr_feedback(owner, name, pr_number, cwd=cwd)
        snapshot = normalize_feedback(feedback_payload, owner, name, pr_number, started_at, now())

        remaining = deadline - now()
        if remaining <= 0:
            return snapshot

        sleep(min(poll_seconds, remaining))


def fetch_pr_view(pr: str | None, repo: str | None, *, cwd: str | None = None) -> dict[str, Any]:
    command = ["gh", "pr", "view"]
    if pr:
        command.append(pr)
    command.extend(["--json", ",".join(PR_VIEW_FIELDS)])
    if repo:
        command.extend(["--repo", repo])

    return run_json(command, cwd=cwd)


def fetch_pr_feedback(owner: str, name: str, number: int, *, cwd: str | None = None) -> dict[str, Any]:
    return run_json(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={PR_FEEDBACK_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={number}",
        ],
        cwd=cwd,
    )


def run_json(command: list[str], *, cwd: str | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise PrFeedbackError(stderr or f"command failed: {' '.join(command)}")

    try:
        parsed = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as error:
        raise PrFeedbackError(f"command returned invalid JSON: {' '.join(command)}") from error

    if not isinstance(parsed, dict):
        raise PrFeedbackError(f"command returned non-object JSON: {' '.join(command)}")

    return parsed


def resolve_repo(repo: str | None, pr_view: dict[str, Any]) -> tuple[str, str]:
    if repo:
        parts = repo.strip().split("/")
        if len(parts) == 2 and all(parts):
            return parts[0], parts[1]
        raise PrFeedbackError(f"GitHub repo must be owner/name, got {repo!r}")

    url = str(pr_view.get("url") or "")
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/\d+", url)
    if not match:
        raise PrFeedbackError("Could not infer GitHub repo. Pass --repo owner/name.")

    return match.group(1), match.group(2)


def normalize_feedback(
    payload: dict[str, Any],
    owner: str,
    name: str,
    number: int,
    started_at: float,
    completed_at: float,
) -> dict[str, Any]:
    pr = (((payload.get("data") or {}).get("repository") or {}).get("pullRequest") or {})
    feedback = []

    for comment in nodes_at(pr, "comments"):
        body = string_value(comment.get("body"))
        if body:
            feedback.append(
                {
                    "kind": "issue_comment",
                    "author": author_login(comment),
                    "body": body,
                    "url": comment.get("url"),
                    "created_at": comment.get("createdAt"),
                    "updated_at": comment.get("updatedAt"),
                    "is_minimized": bool(comment.get("isMinimized")),
                    "automated": is_automated_author(author_login(comment)),
                    "requires_agent_review": True,
                }
            )

    for review in nodes_at(pr, "reviews"):
        body = string_value(review.get("body"))
        if body:
            feedback.append(
                {
                    "kind": "review",
                    "author": author_login(review),
                    "body": body,
                    "url": review.get("url"),
                    "state": review.get("state"),
                    "created_at": review.get("createdAt"),
                    "submitted_at": review.get("submittedAt"),
                    "automated": is_automated_author(author_login(review)),
                    "requires_agent_review": True,
                }
            )

    for thread in nodes_at(pr, "reviewThreads"):
        is_resolved = bool(thread.get("isResolved"))
        for comment in nodes_at(thread, "comments"):
            body = string_value(comment.get("body"))
            if body:
                feedback.append(
                    {
                        "kind": "review_thread_comment",
                        "thread_id": thread.get("id"),
                        "thread_resolved": is_resolved,
                        "thread_outdated": bool(thread.get("isOutdated")),
                        "resolved_by": login_at(thread.get("resolvedBy")),
                        "author": author_login(comment),
                        "body": body,
                        "url": comment.get("url"),
                        "path": comment.get("path"),
                        "line": comment.get("line"),
                        "original_line": comment.get("originalLine"),
                        "diff_hunk": comment.get("diffHunk"),
                        "created_at": comment.get("createdAt"),
                        "automated": is_automated_author(author_login(comment)),
                        "requires_agent_review": not is_resolved,
                    }
                )

    status = status_summary(pr)
    actionable = [item for item in feedback if item["requires_agent_review"]]

    return {
        "schema_version": 1,
        "repo": f"{owner}/{name}",
        "pr": {
            "number": pr.get("number", number),
            "title": pr.get("title"),
            "url": pr.get("url"),
            "state": pr.get("state"),
            "is_draft": pr.get("isDraft"),
            "review_decision": pr.get("reviewDecision"),
        },
        "observation": {
            "requested_wait_seconds": max(int(completed_at - started_at), 0),
            "started_monotonic": started_at,
            "completed_monotonic": completed_at,
        },
        "summary": {
            "feedback_count": len(feedback),
            "actionable_count": len(actionable),
            "automated_count": len([item for item in feedback if item["automated"]]),
            "unresolved_thread_comment_count": len(
                [item for item in feedback if item["kind"] == "review_thread_comment" and not item["thread_resolved"]]
            ),
            "status_rollup_state": status["state"],
            "status_check_count": len(status["checks"]),
        },
        "feedback": feedback,
        "status": status,
    }


def format_feedback(snapshot: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(snapshot, indent=2, sort_keys=True)
    if output_format != "markdown":
        raise PrFeedbackError(f"Unsupported output format: {output_format}")

    pr = snapshot["pr"]
    summary = snapshot["summary"]
    lines = [
        f"# PR feedback for {snapshot['repo']}#{pr['number']}",
        "",
        f"- URL: {pr.get('url')}",
        f"- Feedback items: {summary['feedback_count']}",
        f"- Actionable items: {summary['actionable_count']}",
        f"- Automated items: {summary['automated_count']}",
        f"- Status rollup: {summary.get('status_rollup_state') or 'UNKNOWN'}",
        "",
    ]

    if snapshot["feedback"]:
        lines.append("## Feedback")
        lines.append("")
        for index, item in enumerate(snapshot["feedback"], start=1):
            location = item.get("path") or item.get("url") or "PR"
            state = "actionable" if item["requires_agent_review"] else "already resolved"
            lines.extend(
                [
                    f"### {index}. {item['kind']} by {item.get('author') or 'unknown'} ({state})",
                    "",
                    f"- Location: {location}",
                    f"- URL: {item.get('url')}",
                    "",
                    item["body"].strip(),
                    "",
                ]
            )
    else:
        lines.extend(["No PR feedback was found during the observation window.", ""])

    if snapshot["status"]["checks"]:
        lines.extend(["## Status Checks", ""])
        for check in snapshot["status"]["checks"]:
            lines.append(f"- {check['name']}: {check.get('state') or check.get('status') or 'UNKNOWN'}")
        lines.append("")

    return "\n".join(lines)


def nodes_at(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    nodes = (parent.get(key) or {}).get("nodes") or []
    return [node for node in nodes if isinstance(node, dict)]


def author_login(node: dict[str, Any]) -> str | None:
    return login_at(node.get("author"))


def login_at(node: Any) -> str | None:
    if isinstance(node, dict):
        login = node.get("login")
        if isinstance(login, str) and login:
            return login
    return None


def string_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def is_automated_author(author: str | None) -> bool:
    if not author:
        return False
    normalized = author.lower()
    return "bot" in normalized or "gemini" in normalized or "github-actions" in normalized


def status_summary(pr: dict[str, Any]) -> dict[str, Any]:
    commits = nodes_at(pr, "commits")
    if not commits:
        return {"commit": None, "state": None, "checks": []}

    commit = (commits[-1].get("commit") or {}) if isinstance(commits[-1], dict) else {}
    rollup = commit.get("statusCheckRollup") or {}
    checks = []
    for node in nodes_at(rollup, "contexts"):
        typename = node.get("__typename")
        if typename == "CheckRun":
            checks.append(
                {
                    "kind": "check_run",
                    "name": node.get("name"),
                    "status": node.get("status"),
                    "state": node.get("conclusion") or node.get("status"),
                    "details_url": node.get("detailsUrl"),
                    "started_at": node.get("startedAt"),
                    "completed_at": node.get("completedAt"),
                }
            )
        elif typename == "StatusContext":
            checks.append(
                {
                    "kind": "status_context",
                    "name": node.get("context"),
                    "state": node.get("state"),
                    "details_url": node.get("targetUrl"),
                    "created_at": node.get("createdAt"),
                }
            )

    return {"commit": commit.get("oid"), "state": rollup.get("state"), "checks": checks}

