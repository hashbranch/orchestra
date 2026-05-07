# Documentation Index

This directory is the agent-readable knowledge base for the repository.

## Core Docs

- `../ARCHITECTURE.md`: system map, modules, and invariants.
- `symphony-integration-design.md`: Symphony-side dynamic tool boundary.
- `decisions/`: architectural decisions and their consequences.
- `plans/`: active and completed execution plans.
- `tech-debt-tracker.md`: known cleanup and hardening work.
- `quality.md`: current quality bar and verification gaps.
- `try-it-out.md`: wrapper install and end-to-end smoke runbook.
- `install-orchestra.md`: install path for another machine running local Symphony.

## Reading Order

For implementation work:

1. Read `../AGENTS.md`.
2. Read `../ARCHITECTURE.md`.
3. Read the active plan in `plans/active/`.
4. Read related decisions in `decisions/`.
5. Run `../scripts/validate` before returning.

For design work, start with the spec at
`../symphony-openclaw-agents-v1-spec.md`, then read the architecture and decision
docs.
