# 0003: Honor Linear Blockers Before Dispatch

Date: 2026-05-07

## Status

Accepted

## Context

Orchestra runs unattended against Linear projects. Linear issue state
alone is not enough to determine safe execution order because a ticket can be in
an active state while still having unresolved `blocked by` relationships.

Running those tickets early can create out-of-order PRs, duplicate work, or
changes based on incomplete upstream decisions.

The upstream runner already reads Linear blocker relations, but the local behavior
only skipped blocked issues in the `Todo` state. Orchestra supports configurable
ready and working states, so blocker handling must apply to every active state,
not just a hard-coded `Todo`.

## Decision

Orchestra treats unresolved Linear blockers as a dispatch-level guard.

- Issues with non-terminal `blocked by` relations must not be dispatched to
  Codex, even if their Linear state is active.
- The guard applies before an agent starts, rather than relying only on prompt
  compliance after dispatch.
- Generated workflows also instruct Codex not to continue implementation when
  unresolved blockers are discovered during an active run.
- Until the upstream runner applies this behavior for every active state,
  Orchestra patches the local runner checkout during install and `run`.

## Consequences

Orchestra will leave blocked dependent work idle until its blockers reach a
terminal state. This reduces throughput in the short term but preserves project
order and prevents invalid PRs.

The local source patch is intentionally tracked as tech debt. Once the upstream
runner release enforces blocker filtering across all active states, Orchestra
should remove the patch and depend on the upstream behavior.
