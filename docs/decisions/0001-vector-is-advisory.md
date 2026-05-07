# 0001: Vector Is Advisory In V1

Date: 2026-05-07

## Status

Accepted

## Context

Symphony needs durable product, architecture, and company context during Codex-led
implementation. Vector has that memory, but sharing the active workspace would
create file-stomping and authority problems.

## Decision

V1 treats Vector as an advisory reviewer only.

- Codex edits.
- Vector reviews.
- Vector receives plans, questions, and diffs as data.
- Vector returns structured JSON instructions for Codex.
- Vector does not modify files, open PRs, deliver messages, or access the active
  Symphony workspace directly.

## Consequences

The wrapper prompt repeats the advisory-only role on every request. The response
schema includes `blocking`, `needsHuman`, and `instructionsForCodex` so Symphony
and Codex can act on advice without granting edit authority.
