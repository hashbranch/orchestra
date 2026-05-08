# 0004: Dev Complete is the Linear handoff state

## Status

Accepted

## Context

Orchestra opens GitHub PRs from Linear issues and then updates Linear so the
project workflow can continue outside the local agent runner. In practice, the
expected post-PR state is `Dev Complete`. Issues should not be advanced directly
to terminal states such as `Done`, because those states are owned by the
project's review, merge, and release workflow.

Keeping `Dev Complete` in Symphony's active states also causes handoff issues to
remain eligible for agent dispatch after the PR exists.

## Decision

Generated workflows must treat the configured complete state as a non-active PR
handoff state. Orchestra will include ready and working states in
`active_states`, but not the complete state.

Generated prompts must explicitly tell Codex agents to:

- open a GitHub PR before claiming completion
- move Linear issues to the configured complete state only after the PR exists
  and validation is complete
- never move Linear issues to terminal states, including `Done`
- stop work after moving the issue to the configured complete state

## Consequences

Linear issues in `Dev Complete` are no longer picked up for additional agent
work by default. If a ticket moves from `Dev Complete` to `Done`, that should be
treated as either external Linear automation or a prompt violation to diagnose,
not normal Orchestra behavior.

