import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestra_cli.main import main
from orchestra_cli.pr_review_dispatch import PrReviewDispatchError, PrReviewDispatchOptions, dispatch_pr_review


def review_requested_payload(reviewer="clawd-reviewer"):
    return {
        "action": "review_requested",
        "requested_reviewer": {"login": reviewer},
        "repository": {"full_name": "hashbranch/demo"},
        "pull_request": {
            "number": 42,
            "html_url": "https://github.com/hashbranch/demo/pull/42",
            "title": "CLA-42: Add PR review dispatch",
            "draft": False,
            "user": {"login": "tom"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/CLA-42-dispatch", "sha": "abc123"},
        },
    }


class PrReviewDispatchTests(unittest.TestCase):
    def test_dry_run_explicit_dispatch_builds_local_openclaw_command(self):
        result = dispatch_pr_review(
            PrReviewDispatchOptions(
                repo="hashbranch/demo",
                pr=42,
                url="https://github.com/hashbranch/demo/pull/42",
                title="CLA-42: Add PR review dispatch",
                requested_reviewer="clawd-reviewer",
                dry_run=True,
            )
        )

        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["transport"], "local")
        self.assertEqual(result["session_id"], "github-pr-review-hashbranch-demo-42")
        self.assertEqual(result["request"]["repo"], "hashbranch/demo")
        self.assertIn("--message", result["openclaw_command"])
        self.assertIn("<prompt>", result["openclaw_command"])

    def test_webhook_dispatch_uses_ssh_transport_for_matching_reviewer(self):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout='{"ok":true}\n', stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "event.json"
            payload_path.write_text(json.dumps(review_requested_payload()), encoding="utf-8")

            with mock.patch("orchestra_cli.pr_review_dispatch.subprocess.run", return_value=completed) as run:
                result = dispatch_pr_review(
                    PrReviewDispatchOptions(
                        event_file=str(payload_path),
                        match_reviewers=["@clawd-reviewer"],
                        openclaw_host="clawd-openclaw",
                        agent="main",
                    )
                )

        self.assertEqual(result["status"], "dispatched")
        self.assertEqual(result["transport"], "ssh")
        command = run.call_args.args[0]
        self.assertEqual(command[:7], ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-T", "clawd-openclaw"])
        self.assertIn("openclaw agent", command[-1])
        self.assertIn("--session-id github-pr-review-hashbranch-demo-42", command[-1])

    def test_webhook_dispatch_skips_nonmatching_reviewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "event.json"
            payload_path.write_text(json.dumps(review_requested_payload("other-reviewer")), encoding="utf-8")

            with mock.patch("orchestra_cli.pr_review_dispatch.subprocess.run") as run:
                result = dispatch_pr_review(
                    PrReviewDispatchOptions(
                        event_file=str(payload_path),
                        match_reviewers=["clawd-reviewer"],
                    )
                )

        self.assertEqual(result["status"], "skipped")
        self.assertIn("allowlist", result["reason"])
        run.assert_not_called()

    def test_ready_for_review_matches_current_requested_reviewers(self):
        payload = review_requested_payload()
        payload["action"] = "ready_for_review"
        payload.pop("requested_reviewer")
        payload["pull_request"]["requested_reviewers"] = [{"login": "clawd-reviewer"}]

        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "event.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            result = dispatch_pr_review(
                PrReviewDispatchOptions(
                    event_file=str(payload_path),
                    match_reviewers=["clawd-reviewer"],
                    dry_run=True,
                )
            )

        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["request"]["review_targets"], ["clawd-reviewer"])

    def test_ready_for_review_matches_current_requested_teams(self):
        payload = review_requested_payload()
        payload["action"] = "ready_for_review"
        payload.pop("requested_reviewer")
        payload["pull_request"]["requested_teams"] = [{"slug": "openclaw-agents"}]

        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "event.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            result = dispatch_pr_review(
                PrReviewDispatchOptions(
                    event_file=str(payload_path),
                    match_reviewers=["team/openclaw-agents"],
                    dry_run=True,
                )
            )

        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["request"]["review_targets"], ["team/openclaw-agents"])

    def test_unreadable_event_file_returns_dispatch_error(self):
        with self.assertRaises(PrReviewDispatchError) as caught:
            dispatch_pr_review(PrReviewDispatchOptions(event_file="/no/such/github-event.json"))

        self.assertIn("Could not read GitHub event payload", str(caught.exception))

    def test_invalid_event_file_encoding_returns_dispatch_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "event.json"
            payload_path.write_bytes(b"\xff")

            with self.assertRaises(PrReviewDispatchError) as caught:
                dispatch_pr_review(PrReviewDispatchOptions(event_file=str(payload_path)))

        self.assertIn("Could not read GitHub event payload", str(caught.exception))

    def test_cli_pr_review_dispatch_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch("orchestra_cli.pr_review_dispatch.subprocess.run") as run, mock.patch("sys.stdout") as stdout:
                exit_code = main(
                    [
                        "--home",
                        str(home),
                        "github",
                        "pr-review",
                        "dispatch",
                        "--repo",
                        "hashbranch/demo",
                        "--pr",
                        "42",
                        "--url",
                        "https://github.com/hashbranch/demo/pull/42",
                        "--dry-run",
                    ]
                )

            self.assertEqual(exit_code, 0)
            run.assert_not_called()
            output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
            self.assertEqual(json.loads(output)["request"]["pull_number"], 42)
            trace = json.loads((home / "traces" / "unknown" / "events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(trace["kind"], "github.pr_review.dispatch.planned")
            self.assertEqual(trace["payload"]["request"]["pull_number"], 42)


if __name__ == "__main__":
    unittest.main()
