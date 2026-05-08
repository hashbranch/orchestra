# 0008: Capture auditable workflow traces

## Status

Accepted

## Context

Workflow debugging needs to answer why an agent moved forward: which helpers it
called, what PR feedback it saw, which reviewers were requested, what validation
passed, and why it believed Linear was ready for handoff.

Hidden model reasoning is not a reliable trace source. It may be unavailable,
summarized differently by runtime, or include sensitive internal content. The
debugging source of truth should be explicit execution evidence and agent-written
decision notes.

## Decision

Orchestra writes structured JSONL trace events under:

```text
~/.orchestra/traces/<issue>/events.jsonl
```

GitHub helpers append trace events automatically when they can infer the issue
identifier from the PR title. Orchestra also exposes:

```bash
orchestra trace event
```

Generated workflows require the builder agent to write a
`completion_decision` trace before moving Linear to the configured complete
state. The event should include the PR URL, branch, requested reviewers, feedback
reviewed, validation result, and handoff state.

## Consequences

Debugging depends on concrete, replayable evidence instead of hidden
chain-of-thought. The builder agent still owns engineering judgment, but it must
make the final handoff decision auditable.

