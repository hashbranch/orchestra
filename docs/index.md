# Documentation Index

This directory is the agent-readable knowledge base for the repository.

## Core Docs

- `../ARCHITECTURE.md`: system map, modules, and invariants.
- `decisions/`: architectural decisions and their consequences.
  - `decisions/0003-honor-linear-blockers-before-dispatch.md`: why Orchestra
    blocks dispatch when Linear dependencies are unresolved.
  - `decisions/0010-named-instances-share-the-runner.md`: how multiple project
    and repo configurations should run on one machine.
  - `decisions/0011-agent-runtimes-are-first-class.md`: how Codex, Claude, and
    future agent CLIs should be configured and scheduled.
  - `decisions/0012-runner-lives-in-monorepo.md`: why runner source lives in
    this repository.
- `archive/`: unsupported prototype notes that are not part of the public CLI
  or package.
- `plans/`: local execution plans when work needs durable task state.
- `tech-debt-tracker.md`: known cleanup and hardening work.
- `quality.md`: current quality bar and verification gaps.
- `install-orchestra.md`: install path for another machine running local Orchestra.

## Reading Order

For implementation work:

1. Read `../AGENTS.md`.
2. Read `../ARCHITECTURE.md`.
3. Read related decisions in `decisions/`.
4. Run `../scripts/validate` before returning.

For design work, start with `../README.md`, then read the architecture and
decision docs.
