import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestra_cli.main import main
from orchestra_cli.trace import infer_issue_identifier, parse_fields, write_trace_event


class TraceTests(unittest.TestCase):
    def test_infer_issue_identifier_from_pr_title(self):
        self.assertEqual(infer_issue_identifier("CLA-150: Add contract tests"), "CLA-150")

    def test_parse_fields_requires_key_value(self):
        self.assertEqual(parse_fields(["pr_url=https://example.test", "validation=passed"]), {"pr_url": "https://example.test", "validation": "passed"})

        with self.assertRaises(Exception):
            parse_fields(["missing_equals"])

    def test_write_trace_event_appends_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            event, path = write_trace_event(
                home,
                issue="CLA-150",
                kind="completion_decision",
                source="agent",
                message="Ready for handoff.",
                payload={"validation": "passed"},
                cwd="/workspace",
            )

            self.assertEqual(event["issue"], "CLA-150")
            self.assertEqual(path, home / "traces" / "CLA-150" / "events.jsonl")
            line = path.read_text(encoding="utf-8").strip()
            self.assertEqual(json.loads(line)["payload"]["validation"], "passed")

    def test_cli_trace_event_writes_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            exit_code = main(
                [
                    "--home",
                    str(home),
                    "trace",
                    "event",
                    "--issue",
                    "CLA-150",
                    "--kind",
                    "completion_decision",
                    "--message",
                    "Ready for handoff.",
                    "--field",
                    "pr_url=https://github.com/hashbranch/tera/pull/51",
                    "--format",
                    "json",
                ]
            )

            self.assertEqual(exit_code, 0)
            event = json.loads((home / "traces" / "CLA-150" / "events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(event["payload"]["pr_url"], "https://github.com/hashbranch/tera/pull/51")

    def test_github_feedback_helper_writes_trace_event(self):
        pr_view = {
            "number": 51,
            "title": "CLA-150: Capture tests",
            "url": "https://github.com/hashbranch/tera/pull/51",
            "state": "OPEN",
            "isDraft": False,
            "reviewDecision": None,
        }
        graphql = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 51,
                        "title": "CLA-150: Capture tests",
                        "url": "https://github.com/hashbranch/tera/pull/51",
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

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            completed_view = mock.Mock(returncode=0, stdout=json.dumps(pr_view), stderr="")
            completed_graphql = mock.Mock(returncode=0, stdout=json.dumps(graphql), stderr="")
            with mock.patch("orchestra_cli.pr_feedback.subprocess.run", side_effect=[completed_view, completed_graphql]):
                exit_code = main(
                    [
                        "--home",
                        str(home),
                        "github",
                        "pr-feedback",
                        "wait",
                        "--wait-seconds",
                        "0",
                        "--format",
                        "json",
                    ]
                )

            self.assertEqual(exit_code, 0)
            event = json.loads((home / "traces" / "CLA-150" / "events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(event["kind"], "github.pr_feedback.wait.completed")
            self.assertEqual(event["payload"]["pr"]["number"], 51)


if __name__ == "__main__":
    unittest.main()

