# 0005: Standardize GitHub PR delivery

## Status

Accepted

## Context

The first Orchestra runs opened PRs successfully, but the generated branch names
included a person's name. The desired branch naming convention is independent of
the operator running Symphony and should be predictable for downstream GitHub
and Linear automation.

The project also uses automated Gemini code review. Agents should not treat a PR
as complete until review feedback has been checked and handled.

## Decision

Generated workflows require agent-created branches to use only these prefixes:

- `feature/`
- `bugfix/`
- `hotfix/`

Branch names must be formatted as `<prefix><Linear issue id>-short-kebab-summary`
and must not include names, usernames, initials, or owner prefixes.

Generated workflows also require agents to assign `vector-hb` and
`nathaniel-hb` as PR reviewers through `orchestra github reviewers ensure`.
Before moving a Linear issue to the configured complete state, agents must check
GitHub PR comments, review threads, status checks, and automated Gemini review
feedback. They must read, evaluate, incorporate valid changes, reply to
comments, and resolve threads when GitHub allows it.

## Consequences

The GitHub branch and PR handoff behavior is now part of Orchestra's generated
workflow contract. A run is not complete just because a PR exists; review
feedback must be handled first. Linear still moves only to the configured
complete state, not terminal states such as `Done`.
