import json
import subprocess
import unittest
from unittest import mock

from orchestra_openclaw_agents.wrapper import WrapperConfig, build_prompt, handle_stdin


def sample_request(**overrides):
    request = {
        "schemaVersion": "1.0",
        "requestId": "test-001",
        "mode": "plan_review",
        "issue": {
            "id": "test-linear-id",
            "identifier": "TEST-001",
            "title": "Add account routing for external tools",
            "description": "Implement explicit account alias selection.",
            "url": "https://linear.app/example/issue/TEST-001",
            "labels": ["backend", "integrations"],
            "state": "In Progress",
        },
        "repo": {
            "name": "example/repo",
            "root": "/tmp/orchestra/workspaces/TEST-001",
            "branch": "test-001-account-routing",
        },
        "plan": "Add accountAlias to integration calls.",
        "diff": None,
        "question": "Review this plan before Codex implements it.",
        "constraints": [
            "Codex owns edits in this workspace",
            "OpenClaw agents should not modify files",
            "Return JSON only",
        ],
    }
    request.update(overrides)
    return request


class WrapperTests(unittest.TestCase):
    def test_prompt_contains_contract_and_request_payload(self):
        request = sample_request()

        prompt = build_prompt(request)

        self.assertIn("Codex owns implementation", prompt)
        self.assertIn("Do not modify files", prompt)
        self.assertIn('"identifier": "TEST-001"', prompt)

    @mock.patch("orchestra_openclaw_agents.wrapper.subprocess.run")
    def test_success_response_is_normalized_to_contract(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "summary": "Use explicit account aliases.",
                    "blocking": True,
                    "risks": [{"severity": "medium", "title": "Migration", "detail": "Rollout risk."}],
                    "recommendations": ["Add a migration note."],
                    "instructionsForCodex": ["Keep aliases explicit."],
                    "needsHuman": False,
                }
            ),
            stderr="",
        )

        response = handle_stdin(json.dumps(sample_request()), WrapperConfig(openclaw_bin="fake-openclaw"))

        self.assertEqual(response["status"], "completed")
        self.assertEqual(response["requestId"], "test-001")
        self.assertEqual(response["mode"], "plan_review")
        self.assertTrue(response["blocking"])
        self.assertEqual(response["summary"], "Use explicit account aliases.")
        self.assertEqual(response["instructionsForCodex"], ["Keep aliases explicit."])
        self.assertIsNone(response["error"])

    @mock.patch("orchestra_openclaw_agents.wrapper.subprocess.run")
    def test_openclaw_called_with_isolated_orchestra_session(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"summary": "ok"}),
            stderr="",
        )

        handle_stdin(json.dumps(sample_request()), WrapperConfig(openclaw_bin="fake-openclaw"))

        args = run.call_args.args[0]
        self.assertIn("--session-id", args)
        self.assertIn("orchestra-TEST-001", args)
        self.assertIn("--json", args)

    def test_invalid_request_returns_failed_json(self):
        response = handle_stdin(json.dumps(sample_request(schemaVersion="0.9")), WrapperConfig())

        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(response["requestId"], "test-001")

    def test_diff_review_requires_diff(self):
        response = handle_stdin(json.dumps(sample_request(mode="diff_review", diff=None)), WrapperConfig())

        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")
        self.assertIn("diff is required", response["error"]["message"])

    @mock.patch("orchestra_openclaw_agents.wrapper.subprocess.run")
    def test_malformed_openclaw_json_is_wrapped(self, run):
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr="")

        response = handle_stdin(json.dumps(sample_request()), WrapperConfig(openclaw_bin="fake-openclaw"))

        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["error"]["code"], "MALFORMED_RESPONSE")

    @mock.patch("orchestra_openclaw_agents.wrapper.subprocess.run")
    def test_timeout_is_wrapped(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=["fake-openclaw"], timeout=185)

        response = handle_stdin(json.dumps(sample_request()), WrapperConfig(openclaw_bin="fake-openclaw"))

        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["error"]["code"], "OPENCLAW_TIMEOUT")


if __name__ == "__main__":
    unittest.main()
