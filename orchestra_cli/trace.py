from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestra_cli.paths import traces_path


ISSUE_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


class TraceError(RuntimeError):
    pass


def infer_issue_identifier(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = ISSUE_RE.search(text)
        if match:
            return match.group(0)
    return None


def parse_fields(fields: list[str]) -> dict[str, str]:
    parsed = {}
    for field in fields:
        if "=" not in field:
            raise TraceError(f"Trace field must be key=value, got {field!r}")
        key, value = field.split("=", 1)
        key = key.strip()
        if not key:
            raise TraceError(f"Trace field must have a non-empty key, got {field!r}")
        parsed[key] = value
    return parsed


def parse_payload_json(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        parsed = json.loads(payload_json)
    except json.JSONDecodeError as error:
        raise TraceError("Trace payload JSON is invalid.") from error
    if not isinstance(parsed, dict):
        raise TraceError("Trace payload JSON must be an object.")
    return parsed


def write_trace_event(
    home: Path,
    *,
    issue: str | None,
    kind: str,
    source: str = "orchestra",
    message: str | None = None,
    payload: dict[str, Any] | None = None,
    cwd: str | None = None,
) -> tuple[dict[str, Any], Path]:
    issue_id = issue or "unknown"
    event = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "issue": issue_id,
        "kind": kind,
        "source": source,
        "cwd": cwd,
        "message": message,
        "payload": payload or {},
    }

    path = trace_file_path(home, issue_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    return event, path


def trace_file_path(home: Path, issue: str) -> Path:
    return traces_path(home) / safe_issue_dir(issue) / "events.jsonl"


def safe_issue_dir(issue: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", issue).strip("-") or "unknown"


def format_trace_event(event: dict[str, Any], path: Path, output_format: str) -> str:
    if output_format == "json":
        return json.dumps({"event": event, "path": str(path)}, indent=2, sort_keys=True)
    if output_format != "markdown":
        raise TraceError(f"Unsupported output format: {output_format}")

    return "\n".join(
        [
            f"# Trace event: {event['kind']}",
            "",
            f"- Issue: {event['issue']}",
            f"- Source: {event['source']}",
            f"- Path: {path}",
            "",
        ]
    )

