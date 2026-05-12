# 0001: OpenClaw Agents Are Advisory In V1

Date: 2026-05-07

## Status

Accepted

## Context

Orchestra needs durable product, architecture, and company context during Codex-led
implementation. OpenClaw agents can have that memory, but sharing the active workspace would
create file-stomping and authority problems.

## Decision

V1 treats OpenClaw agents as advisory reviewers only.

- Codex edits.
- OpenClaw agents review.
- OpenClaw agents receive plans, questions, and diffs as data.
- OpenClaw agents return structured JSON instructions for Codex.
- OpenClaw agents do not modify files, open PRs, deliver messages, or access the active
  Orchestra workspace directly.

## Consequences

The wrapper prompt repeats the advisory-only role on every request. The response
schema includes `blocking`, `needsHuman`, and `instructionsForCodex` so Orchestra
and Codex can act on advice without granting edit authority.
