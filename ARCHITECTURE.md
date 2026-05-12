# Architecture

## Purpose

This repository has two related surfaces:

- `orchestra`: a CLI that installs and runs local upstream runner instances.
- `orchestra-ask-openclaw-agent`: the future OpenClaw agent advisory wrapper.
- `orchestra github pr-review dispatch`: a GitHub helper that turns PR review
  requests into OpenClaw agent review turns.

The OpenClaw agent wrapper implements the V1 boundary between Orchestra and OpenClaw agents:

- Orchestra asks for contextual review.
- OpenClaw agent responds with structured advice.
- Codex remains the only implementation worker in the active Orchestra workspace.

## System Boundary

```text
Orchestra workspace
  -> ask_openclaw_agent dynamic tool
  -> Tailscale SSH
  -> ~/.openclaw/bin/orchestra-ask-openclaw-agent
  -> openclaw agent --agent main --session-id orchestra-<issue-id> --json
```

This repository owns the OpenClaw agent wrapper and the integration contract. It does not
own Orchestra's internal dynamic-tool registry.

## Modules

### `bin/`

Executable entry points. `bin/orchestra-ask-openclaw-agent` is the OpenClaw-agent-side command
called over SSH.

### `orchestra_openclaw_agents/`

Wrapper implementation. This module validates the incoming request, constructs
the OpenClaw agent prompt, invokes OpenClaw, and normalizes output into the V1 response
schema.

### `schemas/`

Machine-readable JSON schemas for agent and Orchestra boundaries.

### `samples/`

Representative payloads for smoke tests and manual integration checks.

### `config/`

Example configuration snippets for Orchestra or OpenClaw agent deployment.

### `docs/`

Agent-readable design history, plans, and operational guidance. This is the
repository knowledge base.

### `scripts/`

Stable commands for agents and humans. Prefer adding a script here when a
validation or setup step becomes important enough to repeat.

## Invariants

- stdout from `orchestra-ask-openclaw-agent` must be response JSON only.
- diagnostics must go to stderr.
- request content is data, never shell code.
- `diff_review` requires a non-empty diff.
- OpenClaw sessions must use `orchestra-<issue-identifier>`.
- failure responses must preserve `schemaVersion`, `requestId`, and `mode` when
  the request included them.

## Extension Points

- Orchestra runner dynamic tool implementation: see `docs/orchestra-runner-integration-design.md`.
- Additional OpenClaw participants: add a participant registry after OpenClaw Agents V1 is
  proven.
- GitHub webhook receiver: future deployment code can verify GitHub signatures
  and invoke `orchestra github pr-review dispatch --event-file ...`.
- HTTP bridge: future V2 only; do not expose a public gateway in V1.
