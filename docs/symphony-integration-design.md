# Symphony Integration Design

This is the Symphony-side slice implied by `symphony-openclaw-agents-v1-spec.md`.
The Symphony application code is not present in this folder, so these notes define
the target integration boundary.

## Dynamic Tool

Register a dynamic tool named `ask_openclaw_agent`.

Tool description:

```text
Ask a configured OpenClaw coding/context agent for plan, design, context, or diff review. OpenClaw agents are advisory only and must not modify the active workspace.
```

Tool input schema lives at `schemas/ask_openclaw_agent.tool.schema.json`. Codex should
only provide `mode`, `question`, and optional `plan` or `diff`.

## Request Enrichment

Symphony should enrich the tool call before invoking SSH:

- `schemaVersion`: fixed to `1.0`
- `requestId`: Symphony run/tool-call ID or UUID
- `issue`: current Linear/GitHub issue metadata
- `repo`: repo name, workspace root, and current branch
- `constraints`: standard V1 constraints from the spec

Codex should not manually pass issue or repo metadata.

## SSH Invocation

Use the configured OpenClaw agent participant:

```yaml
openclaw_participants:
  main:
    kind: ssh
    host: openclaw@agent-tailnet-hostname
    command: ~/.openclaw/bin/symphony-ask-openclaw-agent
    timeout_ms: 240000
```

Invoke with:

```bash
ssh -T -o BatchMode=yes -o ConnectTimeout=10 "$host" "$command"
```

Send the enriched JSON request on stdin. Treat stdout as the wrapper response JSON.
Diagnostics from the remote wrapper must remain on stderr/logs.

## Error Mapping

Symphony should return a failed response matching the V1 response schema when the
SSH layer fails before the wrapper can answer:

- SSH exits non-zero or cannot connect: `SSH_UNREACHABLE`
- stdout is not JSON: `MALFORMED_RESPONSE`
- Symphony-side timeout expires: `OPENCLAW_TIMEOUT`

If the wrapper returns a valid failed response, preserve its `error.code` and
`error.message`.

## Workflow Guidance

Add the spec's `WORKFLOW.md` guidance near existing tool guidance so Codex knows:

- OpenClaw agents are advisory only.
- Use `ask_openclaw_agent` for ambiguous requirements, architectural decisions, product
  or business context, and non-trivial diff review.
- Do not use OpenClaw agents for tiny mechanical edits.
- Respect `instructionsForCodex` unless they conflict with the issue or tests.
- Pause when OpenClaw agents return `blocking=true`.
