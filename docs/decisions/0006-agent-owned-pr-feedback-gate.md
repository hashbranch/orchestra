# 0006: Keep PR feedback handling agent-owned

## Status

Accepted

## Context

Automated Gemini review feedback can arrive several minutes after a PR is
opened. A prompt that simply says "check PR feedback" lets the builder agent
check too early, find no comments, and move Linear to the complete state before
Gemini posts.

The builder agent has the most implementation context, so it should evaluate and
respond to PR feedback. Moving that judgment into the harness would make
Orchestra encode project workflow logic that may not generalize.

## Decision

Orchestra provides a generic `orchestra pr-feedback wait` helper. The helper is
an orchestration primitive:

- resolve the current PR
- wait for a configured observation window
- poll GitHub for PR comments, review threads, reviews, automated comments, and
  status checks
- print normalized markdown or JSON feedback for the agent

The helper does not decide whether feedback is valid, modify code, reply to
comments, resolve threads, or move Linear. Generated workflows instruct the
builder agent to run the helper after PR creation, handle valid feedback with its
existing implementation context, rerun validation, and only then move Linear to
the configured complete state.

## Consequences

PR feedback handling remains agent-owned while the waiting and collection step is
deterministic and testable. Project-specific policy stays in generated
`WORKFLOW.md`; the helper remains reusable for other workflows that need a PR
feedback observation window.

