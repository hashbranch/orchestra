from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
VALID_MODES = {"plan_review", "diff_review", "context_lookup", "risk_review"}
DEFAULT_TIMEOUT_SECONDS = 180

PROMPT_CONTRACT = """You are an OpenClaw agent participating in an Orchestra coding workflow.

Role:
- You are an advisory OpenClaw coding/context agent.
- Codex owns implementation in the active Orchestra workspace.
- Your job is to review, advise, surface context, and produce instructions for Codex.

Hard rules:
- Do not message the human operator.
- Do not modify files.
- Do not run external actions.
- Do not assume you can access the Orchestra workspace unless explicitly given files/diffs.
- Return JSON only matching the response schema.
- If you need more information, set needsHuman=true or include a recommendation for what Orchestra/Codex should provide next.
"""


@dataclass
class WrapperConfig:
    openclaw_bin: str = "openclaw"
    agent: str = "main"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


class RequestError(Exception):
    code = "INVALID_REQUEST"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask an OpenClaw agent for Orchestra review.")
    parser.add_argument("--openclaw-bin", default=os.environ.get("OPENCLAW_BIN", "openclaw"))
    parser.add_argument("--agent", default=os.environ.get("OPENCLAW_AGENT", "main"))
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("OPENCLAW_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
    )
    args = parser.parse_args(argv)

    config = WrapperConfig(
        openclaw_bin=args.openclaw_bin,
        agent=args.agent,
        timeout_seconds=args.timeout,
    )

    response = handle_stdin(sys.stdin.read(), config)
    print(json.dumps(response, separators=(",", ":"), sort_keys=True))
    return 0


def handle_stdin(stdin: str, config: WrapperConfig) -> dict[str, Any]:
    try:
        request = parse_request(stdin)
        validate_request(request)
        prompt = build_prompt(request)
        openclaw_output = call_openclaw(request, prompt, config)
        return normalize_success_response(request, openclaw_output)
    except RequestError as error:
        return failed_response_from_partial(stdin, error.code, str(error))
    except subprocess.TimeoutExpired:
        request = parse_partial_request(stdin)
        return failed_response(request, "OPENCLAW_TIMEOUT", "openclaw agent timed out")
    except FileNotFoundError as error:
        request = parse_partial_request(stdin)
        return failed_response(request, "OPENCLAW_FAILED", str(error))
    except subprocess.CalledProcessError as error:
        request = parse_partial_request(stdin)
        message = (error.stderr or error.stdout or str(error)).strip()
        return failed_response(request, "OPENCLAW_FAILED", message)
    except json.JSONDecodeError as error:
        request = parse_partial_request(stdin)
        return failed_response(request, "MALFORMED_RESPONSE", str(error))
    except Exception as error:
        request = parse_partial_request(stdin)
        return failed_response(request, "UNKNOWN_ERROR", str(error))


def parse_request(stdin: str) -> dict[str, Any]:
    try:
        value = json.loads(stdin)
    except json.JSONDecodeError as error:
        raise RequestError(f"request body is not valid JSON: {error}") from error

    if not isinstance(value, dict):
        raise RequestError("request body must be a JSON object")
    return value


def parse_partial_request(stdin: str) -> dict[str, Any]:
    try:
        value = json.loads(stdin)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def validate_request(request: dict[str, Any]) -> None:
    require_equal(request, "schemaVersion", SCHEMA_VERSION)
    require_string(request, "requestId")
    mode = require_string(request, "mode")
    if mode not in VALID_MODES:
        raise RequestError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")

    issue = require_object(request, "issue")
    require_string(issue, "identifier", path="issue.identifier")
    require_string(request, "question")

    if mode == "diff_review" and not request.get("diff"):
        raise RequestError("diff is required for diff_review")


def require_equal(value: dict[str, Any], key: str, expected: str) -> None:
    actual = value.get(key)
    if actual != expected:
        raise RequestError(f"{key} must be {expected!r}")


def require_string(value: dict[str, Any], key: str, path: str | None = None) -> str:
    actual = value.get(key)
    if not isinstance(actual, str) or not actual.strip():
        raise RequestError(f"{path or key} must be a non-empty string")
    return actual


def require_object(value: dict[str, Any], key: str) -> dict[str, Any]:
    actual = value.get(key)
    if not isinstance(actual, dict):
        raise RequestError(f"{key} must be an object")
    return actual


def build_prompt(request: dict[str, Any]) -> str:
    payload = json.dumps(request, indent=2, sort_keys=True)
    return f"{PROMPT_CONTRACT}\nRequest payload:\n{payload}\n"


def call_openclaw(request: dict[str, Any], prompt: str, config: WrapperConfig) -> str:
    issue_identifier = request["issue"]["identifier"]
    session_id = f"orchestra-{issue_identifier}"

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as prompt_file:
        prompt_file.write(prompt)
        prompt_path = Path(prompt_file.name)

    try:
        completed = subprocess.run(
            [
                config.openclaw_bin,
                "agent",
                "--agent",
                config.agent,
                "--session-id",
                session_id,
                "--message-file",
                str(prompt_path),
                "--json",
                "--timeout",
                str(config.timeout_seconds),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds + 5,
        )
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return completed.stdout
    finally:
        try:
            prompt_path.unlink()
        except FileNotFoundError:
            pass


def normalize_success_response(request: dict[str, Any], output: str) -> dict[str, Any]:
    parsed = json.loads(output)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("openclaw output must be a JSON object", output, 0)

    response = base_response(request)
    response.update(
        {
            "status": "completed",
            "blocking": bool(parsed.get("blocking", False)),
            "summary": string_or_default(parsed.get("summary"), "OpenClaw agent review completed"),
            "risks": list_or_empty(parsed.get("risks")),
            "recommendations": list_or_empty(parsed.get("recommendations")),
            "instructionsForCodex": list_or_empty(parsed.get("instructionsForCodex")),
            "needsHuman": bool(parsed.get("needsHuman", False)),
            "error": None,
        }
    )
    return response


def failed_response_from_partial(stdin: str, code: str, message: str) -> dict[str, Any]:
    return failed_response(parse_partial_request(stdin), code, message)


def failed_response(request: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    response = base_response(request)
    response.update(
        {
            "status": "failed",
            "blocking": False,
            "summary": "OpenClaw agent review failed",
            "risks": [],
            "recommendations": [],
            "instructionsForCodex": [],
            "needsHuman": False,
            "error": {"code": code, "message": message},
        }
    )
    return response


def base_response(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "requestId": request.get("requestId"),
        "mode": request.get("mode"),
    }


def string_or_default(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
