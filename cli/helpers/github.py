from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from cli.pr_feedback import (
    FeedbackOptions,
    PrFeedbackError,
    ReviewerOptions,
    ensure_pr_reviewers,
    format_feedback,
    format_reviewer_result,
    wait_for_pr_feedback,
)
from cli.trace import infer_issue_identifier, write_trace_event


def add_github_helper_parsers(subcommands: argparse._SubParsersAction) -> None:
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


def add_deprecated_github_helper_aliases(subcommands: argparse._SubParsersAction) -> None:
    pr_feedback_parser = subcommands.add_parser(
        "pr-feedback",
        help="Deprecated alias for `orchestra github pr-feedback`.",
    )
    pr_feedback_subcommands = pr_feedback_parser.add_subparsers(dest="pr_feedback_command", required=True)
    add_pr_feedback_wait_parser(pr_feedback_subcommands)


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
