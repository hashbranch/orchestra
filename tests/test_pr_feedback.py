import json
import subprocess
import unittest
from unittest import mock

from cli.main import main
from cli.helpers.github.pr_feedback import FeedbackOptions, ReviewerOptions, ensure_pr_reviewers, format_feedback, wait_for_pr_feedback


def completed(payload):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(payload), stderr="")


class PrFeedbackTests(unittest.TestCase):
    def test_wait_collects_gemini_feedback_and_status_checks(self):
        pr_view = {
            "number": 149,
            "title": "CLA-149: Build todo app",
            "url": "https://github.com/hashbranch/demo/pull/149",
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": "REVIEW_REQUIRED",
        }
        graphql = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 149,
                        "title": "CLA-149: Build todo app",
                        "url": "https://github.com/hashbranch/demo/pull/149",
                        "state": "OPEN",
                        "isDraft": False,
                        "reviewDecision": "REVIEW_REQUIRED",
                        "comments": {
                            "nodes": [
                                {
                                    "author": {"login": "gemini-code-assist"},
                                    "body": "Consider extracting this into a helper.",
                                    "url": "https://github.com/hashbranch/demo/pull/149#issuecomment-1",
                                    "createdAt": "2026-05-08T00:00:00Z",
                                    "updatedAt": "2026-05-08T00:00:00Z",
                                    "isMinimized": False,
                                }
                            ]
                        },
                        "reviews": {"nodes": []},
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "thread-1",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "resolvedBy": None,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "comment-1",
                                                "author": {"login": "gemini-code-assist"},
                                                "body": "This branch misses a validation test.",
                                                "url": "https://github.com/hashbranch/demo/pull/149#discussion_r1",
                                                "path": "src/app.ts",
                                                "line": 12,
                                                "originalLine": 12,
                                                "diffHunk": "@@",
                                                "createdAt": "2026-05-08T00:01:00Z",
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                        "commits": {
                            "nodes": [
                                {
                                    "commit": {
                                        "oid": "abc123",
                                        "statusCheckRollup": {
                                            "state": "SUCCESS",
                                            "contexts": {
                                                "nodes": [
                                                    {
                                                        "__typename": "CheckRun",
                                                        "name": "test",
                                                        "status": "COMPLETED",
                                                        "conclusion": "SUCCESS",
                                                        "detailsUrl": "https://github.com/hashbranch/demo/actions/runs/1",
                                                        "startedAt": "2026-05-08T00:00:00Z",
                                                        "completedAt": "2026-05-08T00:02:00Z",
                                                    }
                                                ]
                                            },
                                        },
                                    }
                                }
                            ]
                        },
                    }
                }
            }
        }

        with mock.patch("cli.helpers.github.pr_feedback.subprocess.run", side_effect=[completed(pr_view), completed(graphql)]):
            snapshot = wait_for_pr_feedback(FeedbackOptions(wait_seconds=0), now=lambda: 10.0)

        self.assertEqual(snapshot["repo"], "hashbranch/demo")
        self.assertEqual(snapshot["summary"]["feedback_count"], 2)
        self.assertEqual(snapshot["summary"]["actionable_count"], 2)
        self.assertEqual(snapshot["summary"]["automated_count"], 2)
        self.assertEqual(snapshot["summary"]["status_rollup_state"], "SUCCESS")
        self.assertIn("Consider extracting", format_feedback(snapshot, "markdown"))

    def test_cli_pr_feedback_wait_outputs_json(self):
        pr_view = {
            "number": 1,
            "title": "CLA-1: Test",
            "url": "https://github.com/hashbranch/demo/pull/1",
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": None,
        }
        graphql = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 1,
                        "title": "CLA-1: Test",
                        "url": "https://github.com/hashbranch/demo/pull/1",
                        "state": "OPEN",
                        "isDraft": False,
                        "reviewDecision": None,
                        "comments": {"nodes": []},
                        "reviews": {"nodes": []},
                        "reviewThreads": {"nodes": []},
                        "commits": {"nodes": []},
                    }
                }
            }
        }

        with mock.patch("cli.helpers.github.pr_feedback.subprocess.run", side_effect=[completed(pr_view), completed(graphql)]):
            with mock.patch("sys.stdout") as stdout:
                exit_code = main(["github", "pr-feedback", "wait", "--wait-seconds", "0", "--format", "json"])

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertEqual(json.loads(output)["pr"]["number"], 1)

    def test_deprecated_cli_pr_feedback_alias_still_outputs_json(self):
        pr_view = {
            "number": 1,
            "title": "CLA-1: Test",
            "url": "https://github.com/hashbranch/demo/pull/1",
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": None,
        }
        graphql = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 1,
                        "title": "CLA-1: Test",
                        "url": "https://github.com/hashbranch/demo/pull/1",
                        "state": "OPEN",
                        "isDraft": False,
                        "reviewDecision": None,
                        "comments": {"nodes": []},
                        "reviews": {"nodes": []},
                        "reviewThreads": {"nodes": []},
                        "commits": {"nodes": []},
                    }
                }
            }
        }

        with mock.patch("cli.helpers.github.pr_feedback.subprocess.run", side_effect=[completed(pr_view), completed(graphql)]):
            with mock.patch("sys.stdout") as stdout:
                exit_code = main(["pr-feedback", "wait", "--wait-seconds", "0", "--format", "json"])

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertEqual(json.loads(output)["pr"]["number"], 1)

    def test_reviewers_ensure_requests_reviewers_for_current_pr(self):
        pr_view = {
            "number": 150,
            "title": "CLA-150: Capture tests",
            "url": "https://github.com/hashbranch/demo/pull/150",
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": None,
        }

        with mock.patch(
            "cli.helpers.github.pr_feedback.subprocess.run",
            side_effect=[completed(pr_view), subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""), completed(pr_view)],
        ) as run:
            result = ensure_pr_reviewers(ReviewerOptions(reviewers=["vector-hb", "nathaniel-hb", "vector-hb"]))

        self.assertEqual(result["requested_reviewers"], ["vector-hb", "nathaniel-hb"])
        edit_command = run.call_args_list[1].args[0]
        self.assertEqual(
            edit_command,
            [
                "gh",
                "pr",
                "edit",
                "--add-reviewer",
                "vector-hb",
                "--add-reviewer",
                "nathaniel-hb",
            ],
        )

    def test_cli_reviewers_ensure_outputs_json(self):
        pr_view = {
            "number": 150,
            "title": "CLA-150: Capture tests",
            "url": "https://github.com/hashbranch/demo/pull/150",
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": None,
        }

        with mock.patch(
            "cli.helpers.github.pr_feedback.subprocess.run",
            side_effect=[completed(pr_view), subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""), completed(pr_view)],
        ):
            with mock.patch("sys.stdout") as stdout:
                exit_code = main(
                    [
                        "github",
                        "reviewers",
                        "ensure",
                        "--reviewer",
                        "vector-hb",
                        "--reviewer",
                        "nathaniel-hb",
                        "--format",
                        "json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertEqual(json.loads(output)["requested_reviewers"], ["vector-hb", "nathaniel-hb"])


if __name__ == "__main__":
    unittest.main()
