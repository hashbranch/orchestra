import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestra_cli.main import (
    apply_update,
    check_update_status,
    ensure_elixir_toolchain,
    ensure_runner_blocker_patch,
    main,
    redacted_config,
    run_env,
)
from orchestra_cli.paths import upstream_elixir_app_dir
from orchestra_cli.workflow import workflow_text


ORCHESTRATOR_WITH_TODO_BLOCKER = """defmodule OrchestraRunner.Orchestrator do
  defp should_dispatch_issue?(issue, terminal_states) do
    !todo_issue_blocked_by_non_terminal?(issue, terminal_states)
  end

  defp todo_issue_blocked_by_non_terminal?(
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
end
"""


class OrchestraCliTests(unittest.TestCase):
    def test_init_writes_config_and_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"

            exit_code = main(
                [
                    "--home",
                    str(home),
                    "init",
                    "--linear-project-slug",
                    "orchestra-test",
                    "--target-repo",
                    "git@github.com:example/repo.git",
                    "--codex-command",
                    "codex --config 'model=\"gpt-5.5\"' app-server",
                ]
            )

            self.assertEqual(exit_code, 0)

            config = json.loads((home / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["linear_project_slug"], "orchestra-test")
            self.assertEqual(config["target_repo"], "git@github.com:example/repo.git")
            self.assertEqual(config["states"]["ready"], "Todo")
            self.assertEqual(config["states"]["complete"], "Dev Complete")
            self.assertEqual(config["pr_reviewers"], ["vector-hb", "nathaniel-hb"])
            self.assertEqual(config["codex_thread_sandbox"], "danger-full-access")
            self.assertEqual(config["codex_turn_sandbox_policy"], {"type": "dangerFullAccess"})
            self.assertTrue((home / "workspaces").is_dir())
            self.assertTrue((home / "traces").is_dir())

            workflow = (home / "WORKFLOW.md").read_text(encoding="utf-8")
            self.assertIn("project_slug: \"orchestra-test\"", workflow)
            self.assertIn("api_key: $LINEAR_API_KEY", workflow)
            self.assertNotIn("lin_api", workflow)
            self.assertIn("git clone --depth 1", workflow)
            self.assertIn("codex --config", workflow)
            self.assertIn('thread_sandbox: "danger-full-access"', workflow)
            self.assertIn('type: "dangerFullAccess"', workflow)
            self.assertIn("Always open a GitHub PR", workflow)
            self.assertIn("Branch names must use exactly one of these prefixes", workflow)
            self.assertIn("feature/{{ issue.identifier }}-add-login-form", workflow)
            self.assertIn("Never include a person's name", workflow)
            self.assertIn("The PR title must start with the Linear issue identifier", workflow)
            self.assertIn("{{ issue.identifier }}: {{ issue.title }}", workflow)
            self.assertIn("Assign these PR reviewers before claiming completion: `vector-hb`, `nathaniel-hb`", workflow)
            self.assertIn("orchestra github reviewers ensure --reviewer vector-hb --reviewer nathaniel-hb", workflow)
            self.assertIn("orchestra github pr-feedback wait --wait-seconds 300 --poll-seconds 15", workflow)
            self.assertIn("required wait for automated reviewers such as Gemini", workflow)
            self.assertIn("automated Gemini code review feedback", workflow)
            self.assertIn("read it, evaluate whether it is valid, incorporate changes when valid", workflow)
            self.assertIn("move the Linear issue to `Dev Complete`", workflow)
            self.assertIn("`Dev Complete` as a non-active PR handoff state", workflow)
            self.assertNotIn("Human Review", workflow)
            self.assertIn("Never move the Linear issue to any terminal state", workflow)
            self.assertIn("The only successful handoff state is `Dev Complete`", workflow)
            self.assertIn("orchestra trace event --issue {{ issue.identifier }} --kind completion_decision", workflow)
            self.assertIn("feedback_items_reviewed", workflow)
            self.assertIn("After moving the Linear issue to `Dev Complete`, stop work", workflow)
            self.assertIn("Respect Linear dependency ordering", workflow)

    def test_workflow_always_uses_linear_api_key_env_reference(self):
        text = workflow_text(
            {
                "linear_project_slug": "project",
                "linear_api_key": "lin_api_secret",
                "workspace_root": "/tmp/workspaces",
                "after_create": "git clone repo .",
                "codex_command": "codex app-server",
            }
        )

        self.assertIn("api_key: $LINEAR_API_KEY", text)
        self.assertNotIn("lin_api_secret", text)
        self.assertIn("workspace:\n  root: \"/tmp/workspaces\"", text)

    def test_workflow_uses_configured_linear_states(self):
        text = workflow_text(
            {
                "linear_project_slug": "project",
                "workspace_root": "/tmp/workspaces",
                "after_create": "git clone repo .",
                "codex_command": "codex app-server",
                "states": {
                    "ready": "Ready for Dev",
                    "working": "Building",
                    "complete": "Ready for QA",
                    "blocked": "Blocked",
                    "terminal": ["Done", "Canceled"],
                },
            }
        )

        self.assertIn(
            '  active_states:\n    - "Ready for Dev"\n    - "Building"\n    - "Merging"\n    - "Rework"\n',
            text,
        )
        self.assertNotIn(
            '  active_states:\n    - "Ready for Dev"\n    - "Building"\n    - "Ready for QA"\n',
            text,
        )
        self.assertIn("move the Linear issue to `Ready for QA`", text)
        self.assertIn("otherwise leave it in `Building`", text)
        self.assertIn("do not start or continue implementation on an issue with unresolved `blocked by` relations", text)
        self.assertIn('    - "Done"', text)
        self.assertIn('    - "Canceled"', text)

    def test_init_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            args = [
                "--home",
                str(home),
                "init",
                "--linear-project-slug",
                "orchestra-test",
                "--target-repo",
                "git@github.com:example/repo.git",
            ]

            self.assertEqual(main(args), 0)
            self.assertEqual(main(args), 2)

    def test_init_prompts_for_missing_project_repo_and_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"

            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "builtins.input", side_effect=["prompted-project", "git@github.com:example/prompted.git", ""]
            ), mock.patch("getpass.getpass", return_value="lin_api_prompted"):
                exit_code = main(["--home", str(home), "init"])

            self.assertEqual(exit_code, 0)
            config = json.loads((home / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["linear_project_slug"], "prompted-project")
            self.assertEqual(config["target_repo"], "git@github.com:example/prompted.git")
            self.assertEqual(config["linear_api_key"], "lin_api_prompted")
            self.assertEqual(config["max_concurrent_agents"], 1)
            workflow = (home / "WORKFLOW.md").read_text(encoding="utf-8")
            self.assertIn("api_key: $LINEAR_API_KEY", workflow)
            self.assertNotIn("lin_api_prompted", workflow)

    def test_init_prompts_for_key_project_then_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            events = []

            def prompt_input(prompt):
                events.append(prompt)
                return {
                    "Linear project slug: ": "prompted-project",
                    "Target GitHub repo URL: ": "git@github.com:example/prompted.git",
                    "Max concurrent agents [1]: ": "3",
                }[prompt]

            def prompt_key(prompt):
                events.append(prompt)
                return "lin_api_prompted"

            with mock.patch("sys.stdin.isatty", return_value=True), mock.patch(
                "builtins.input", side_effect=prompt_input
            ), mock.patch("getpass.getpass", side_effect=prompt_key):
                exit_code = main(["--home", str(home), "init"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                events,
                [
                    "Linear API key: ",
                    "Linear project slug: ",
                    "Target GitHub repo URL: ",
                    "Max concurrent agents [1]: ",
                ],
            )

            config = json.loads((home / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["max_concurrent_agents"], 3)

    def test_init_accepts_max_concurrent_agents_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"

            exit_code = main(
                [
                    "--home",
                    str(home),
                    "init",
                    "--linear-project-slug",
                    "project",
                    "--github-repo",
                    "git@github.com:example/repo.git",
                    "--max-concurrent-agents",
                    "4",
                ]
            )

            self.assertEqual(exit_code, 0)
            config = json.loads((home / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["max_concurrent_agents"], 4)

    def test_run_env_loads_linear_key_from_config_without_requiring_workflow_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            home.mkdir()
            (home / "config.json").write_text(
                json.dumps({"linear_api_key": "lin_api_configured"}),
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {}, clear=True):
                env = run_env(home)

            self.assertEqual(env["LINEAR_API_KEY"], "lin_api_configured")

    def test_run_handles_keyboard_interrupt_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            (home / "runner" / "elixir").mkdir(parents=True)
            orchestrator = home / "runner" / "elixir" / "lib" / upstream_elixir_app_dir() / "orchestrator.ex"
            orchestrator.parent.mkdir(parents=True)
            orchestrator.write_text(ORCHESTRATOR_WITH_TODO_BLOCKER, encoding="utf-8")
            (home / "WORKFLOW.md").write_text("---\n---\n", encoding="utf-8")
            (home / "config.json").write_text("{}", encoding="utf-8")

            with mock.patch("orchestra_cli.main.subprocess.call", side_effect=KeyboardInterrupt), mock.patch(
                "orchestra_cli.main.find_executable", return_value=None
            ):
                exit_code = main(["--home", str(home), "run"])

            self.assertEqual(exit_code, 130)

    def test_redacted_config_hides_stored_linear_key(self):
        self.assertEqual(
            redacted_config({"linear_api_key": "lin_api_configured", "linear_project_slug": "project"}),
            {"linear_api_key": "<redacted>", "linear_project_slug": "project"},
        )

    def test_set_linear_key_updates_config_without_rewriting_workflow_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            self.assertEqual(
                main(
                    [
                        "--home",
                        str(home),
                        "init",
                        "--linear-project-slug",
                        "project",
                        "--target-repo",
                        "git@github.com:example/repo.git",
                    ]
                ),
                0,
            )

            self.assertEqual(
                main(["--home", str(home), "set-linear-key", "--linear-api-key", "lin_api_rotated"]),
                0,
            )

            config = json.loads((home / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["linear_api_key"], "lin_api_rotated")
            workflow = (home / "WORKFLOW.md").read_text(encoding="utf-8")
            self.assertIn("api_key: $LINEAR_API_KEY", workflow)
            self.assertNotIn("lin_api_rotated", workflow)

    def test_refresh_workflow_regenerates_from_existing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            home.mkdir()
            (home / "config.json").write_text(
                json.dumps(
                    {
                        "linear_project_slug": "project",
                        "linear_api_key": "lin_api_configured",
                        "target_repo": "git@github.com:example/repo.git",
                        "workspace_root": str(home / "workspaces"),
                        "after_create": "git clone git@github.com:example/repo.git .",
                        "states": {
                            "ready": "Todo",
                            "working": "In Progress",
                            "complete": "Dev Complete",
                            "blocked": "Blocked",
                            "terminal": ["Done"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (home / "WORKFLOW.md").write_text("stale workflow\n", encoding="utf-8")

            exit_code = main(["--home", str(home), "refresh-workflow"])

            self.assertEqual(exit_code, 0)
            workflow = (home / "WORKFLOW.md").read_text(encoding="utf-8")
            self.assertIn("project_slug: \"project\"", workflow)
            self.assertIn("api_key: $LINEAR_API_KEY", workflow)
            self.assertNotIn("lin_api_configured", workflow)
            self.assertIn("Never move the Linear issue to any terminal state", workflow)

    def test_version_subcommand_succeeds(self):
        self.assertEqual(main(["version"]), 0)

    def test_update_check_returns_zero_when_update_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"

            with mock.patch(
                "orchestra_cli.main.check_update_status",
                return_value={"ok": True, "available": True, "current": "abc1234", "latest": "def5678"},
            ):
                exit_code = main(["--home", str(home), "update", "--check"])

            self.assertEqual(exit_code, 0)

    def test_update_status_tracks_latest_release_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            work = root / "work"
            home = root / "home"
            source = home / "source"

            subprocess.run(
                ["git", "init", "--bare", "--initial-branch=main", str(remote)],
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=work, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=work, check=True)
            (work / "README.md").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=work, check=True)
            subprocess.run(["git", "commit", "-m", "one"], cwd=work, check=True, capture_output=True)
            subprocess.run(["git", "tag", "v0.1.0"], cwd=work, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=work, check=True)
            subprocess.run(["git", "push", "-u", "origin", "main", "--tags"], cwd=work, check=True, capture_output=True)

            subprocess.run(["git", "clone", str(remote), str(source)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(source), "checkout", "v0.1.0"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(source), "config", "orchestra.installRef", "latest"], check=True)

            (work / "README.md").write_text("two\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=work, check=True)
            subprocess.run(["git", "commit", "-m", "two"], cwd=work, check=True, capture_output=True)
            subprocess.run(["git", "tag", "v0.2.0"], cwd=work, check=True)
            subprocess.run(["git", "push", "origin", "main", "--tags"], cwd=work, check=True, capture_output=True)

            status = check_update_status(home)

            self.assertTrue(status["ok"])
            self.assertTrue(status["available"])
            self.assertEqual(status["current"], "v0.1.0")
            self.assertEqual(status["latest"], "v0.2.0")
            self.assertEqual(status["track"], "latest")

            self.assertEqual(apply_update(home, skip_install=True), 0)
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(source), "describe", "--tags", "--exact-match"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                "v0.2.0",
            )

    def test_up_can_skip_update_check_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"
            with mock.patch("orchestra_cli.main.check_update_status") as check_update, mock.patch(
                "orchestra_cli.main.cmd_run", return_value=0
            ) as run_command:
                exit_code = main(["--home", str(home), "up", "--no-update"])

            self.assertEqual(exit_code, 0)
            check_update.assert_not_called()
            run_command.assert_called_once()

    def test_init_noninteractive_requires_project_and_target_repo_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"

            with mock.patch("sys.stdin.isatty", return_value=False):
                exit_code = main(["--home", str(home), "init"])

            self.assertEqual(exit_code, 2)

    def test_init_accepts_github_repo_alias_for_target_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "orchestra"

            exit_code = main(
                [
                    "--home",
                    str(home),
                    "init",
                    "--linear-project-slug",
                    "project",
                    "--github-repo",
                    "git@github.com:example/repo.git",
                ]
            )

            self.assertEqual(exit_code, 0)
            config = json.loads((home / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["target_repo"], "git@github.com:example/repo.git")

    def test_ensure_elixir_toolchain_uses_existing_mise(self):
        with mock.patch("orchestra_cli.main.find_executable", return_value="/fake/mise"):
            self.assertEqual(ensure_elixir_toolchain(), ("mise", "/fake/mise"))

    def test_ensure_elixir_toolchain_uses_existing_mix_when_mise_missing(self):
        with mock.patch("orchestra_cli.main.find_executable", side_effect=[None, "/fake/mix"]):
            self.assertEqual(ensure_elixir_toolchain(), ("mix", "/fake/mix"))

    def test_ensure_elixir_toolchain_installs_mise_when_missing(self):
        with mock.patch("orchestra_cli.main.find_executable", side_effect=[None, None, "/fake/mise"]), mock.patch(
            "orchestra_cli.main.install_mise_binary", return_value=True
        ) as install_mise:
            self.assertEqual(ensure_elixir_toolchain(), ("mise", "/fake/mise"))

        install_mise.assert_called_once_with()

    def test_ensure_elixir_toolchain_can_skip_mise_install(self):
        with mock.patch("orchestra_cli.main.find_executable", side_effect=[None, None]), mock.patch(
            "orchestra_cli.main.install_mise_binary"
        ) as install_mise:
            self.assertIsNone(ensure_elixir_toolchain(install_mise=False))

        install_mise.assert_not_called()

    def test_install_runner_skip_build_clones_local_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            home = Path(tmp) / "home"
            (source / "elixir").mkdir(parents=True)
            orchestrator = source / "elixir" / "lib" / upstream_elixir_app_dir() / "orchestrator.ex"
            orchestrator.parent.mkdir(parents=True)
            (source / "README.md").write_text("source\n", encoding="utf-8")
            (source / "elixir" / "README.md").write_text("elixir\n", encoding="utf-8")
            orchestrator.write_text(ORCHESTRATOR_WITH_TODO_BLOCKER, encoding="utf-8")

            subprocess.run(["git", "init", "-b", "main"], cwd=source, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=source, check=True)
            subprocess.run(["git", "add", "."], cwd=source, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=source, check=True, capture_output=True)

            with mock.patch.dict(os.environ, {"ORCHESTRA_QUIET": "1"}):
                exit_code = main(
                    [
                        "--home",
                        str(home),
                        "repair-runner",
                        "--source",
                        str(source),
                        "--skip-build",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue((home / "runner" / "elixir").is_dir())
            patched = (home / "runner" / "elixir" / "lib" / upstream_elixir_app_dir() / "orchestrator.ex").read_text(
                encoding="utf-8"
            )
            self.assertIn("issue_blocked_by_non_terminal?", patched)
            self.assertNotIn("todo_issue_blocked_by_non_terminal?", patched)

    def test_runner_blocker_patch_skips_any_state_with_unresolved_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            elixir = Path(tmp) / "elixir"
            orchestrator = elixir / "lib" / upstream_elixir_app_dir() / "orchestrator.ex"
            orchestrator.parent.mkdir(parents=True)
            orchestrator.write_text(ORCHESTRATOR_WITH_TODO_BLOCKER, encoding="utf-8")

            self.assertTrue(ensure_runner_blocker_patch(elixir))

            patched = orchestrator.read_text(encoding="utf-8")
            self.assertIn("!issue_blocked_by_non_terminal?(issue, terminal_states)", patched)
            self.assertNotIn('normalize_issue_state(issue_state) == "todo"', patched)
            self.assertNotIn("todo_issue_blocked_by_non_terminal?", patched)


if __name__ == "__main__":
    unittest.main()
