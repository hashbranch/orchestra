# Architecture

## Purpose

This repository has two related surfaces:

- `orchestra`: a CLI that installs and runs local OpenAI Symphony instances.
- `symphony-ask-openclaw-agent`: the future OpenClaw agent advisory wrapper.

The OpenClaw agent wrapper implements the V1 boundary between Symphony and OpenClaw agents:

- Symphony asks for contextual review.
- OpenClaw agent responds with structured advice.
- Codex remains the only implementation worker in the active Symphony workspace.

## System Boundary

```text
Symphony workspace
  -> ask_openclaw_agent dynamic tool
  -> Tailscale SSH
  -> ~/.openclaw/bin/symphony-ask-openclaw-agent
  -> openclaw agent --agent main --session-id symphony-<issue-id> --json
```

This repository owns the OpenClaw agent wrapper and the integration contract. It does not
own Symphony's internal dynamic-tool registry.

## Modules

### `bin/`

Executable entry points. `bin/symphony-ask-openclaw-agent` is the OpenClaw-agent-side command
called over SSH.

### `symphony_openclaw_agents/`

Wrapper implementation. This module validates the incoming request, constructs
the OpenClaw agent prompt, invokes OpenClaw, and normalizes output into the V1 response
schema.

### `schemas/`

Machine-readable JSON schemas for agent and Symphony boundaries.

### `samples/`

Representative payloads for smoke tests and manual integration checks.

### `config/`

Example configuration snippets for Symphony or OpenClaw agent deployment.

### `docs/`

Agent-readable design history, plans, and operational guidance. This is the
repository knowledge base.

### `scripts/`

Stable commands for agents and humans. Prefer adding a script here when a
validation or setup step becomes important enough to repeat.

## Invariants

- stdout from `symphony-ask-openclaw-agent` must be response JSON only.
- diagnostics must go to stderr.
- request content is data, never shell code.
- `diff_review` requires a non-empty diff.
- OpenClaw sessions must use `symphony-<issue-identifier>`.
- failure responses must preserve `schemaVersion`, `requestId`, and `mode` when
  the request included them.

## Extension Points

- Symphony dynamic tool implementation: see `docs/symphony-integration-design.md`.
- Additional OpenClaw participants: add a participant registry after OpenClaw Agents V1 is
  proven.
- HTTP bridge: future V2 only; do not expose a public gateway in V1.
