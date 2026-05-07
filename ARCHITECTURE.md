# Architecture

## Purpose

This repository has two related surfaces:

- `orchestra`: a CLI that installs and runs local OpenAI Symphony instances.
- `symphony-ask-vector`: the future Vector/OpenClaw advisory wrapper.

The Vector wrapper implements the V1 boundary between Symphony and Vector:

- Symphony asks for contextual review.
- Vector responds with structured advice.
- Codex remains the only implementation worker in the active Symphony workspace.

## System Boundary

```text
Symphony workspace
  -> ask_vector dynamic tool
  -> Tailscale SSH
  -> ~/.openclaw/bin/symphony-ask-vector
  -> openclaw agent --agent main --session-id symphony-<issue-id> --json
```

This repository owns the Vector wrapper and the integration contract. It does not
own Symphony's internal dynamic-tool registry.

## Modules

### `bin/`

Executable entry points. `bin/symphony-ask-vector` is the Vector-side command
called over SSH.

### `symphony_vector/`

Wrapper implementation. This module validates the incoming request, constructs
the Vector prompt, invokes OpenClaw, and normalizes output into the V1 response
schema.

### `schemas/`

Machine-readable JSON schemas for agent and Symphony boundaries.

### `samples/`

Representative payloads for smoke tests and manual integration checks.

### `config/`

Example configuration snippets for Symphony or Vector deployment.

### `docs/`

Agent-readable design history, plans, and operational guidance. This is the
repository knowledge base.

### `scripts/`

Stable commands for agents and humans. Prefer adding a script here when a
validation or setup step becomes important enough to repeat.

## Invariants

- stdout from `symphony-ask-vector` must be response JSON only.
- diagnostics must go to stderr.
- request content is data, never shell code.
- `diff_review` requires a non-empty diff.
- OpenClaw sessions must use `symphony-<issue-identifier>`.
- failure responses must preserve `schemaVersion`, `requestId`, and `mode` when
  the request included them.

## Extension Points

- Symphony dynamic tool implementation: see `docs/symphony-integration-design.md`.
- Additional OpenClaw participants: add a participant registry after Vector V1 is
  proven.
- HTTP bridge: future V2 only; do not expose a public gateway in V1.
