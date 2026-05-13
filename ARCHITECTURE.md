# Architecture

## Purpose

This repository has one supported product surface:

- `orchestra`: a CLI that installs and runs local Orchestra runner instances.

## System Boundary

```text
Linear project
  -> Orchestra runner
  -> isolated workspace cloned from target GitHub repo
  -> Codex app-server
  -> GitHub branch and PR
  -> Linear handoff state
```

This repository owns the installable CLI, generated workflow, deterministic
helpers, and local patching needed to run the Hashbranch Orchestra runner fork
safely.

## Modules

### `orchestra_cli/`

Install, init, run, update, GitHub helper, and trace commands.

### `docs/`

Agent-readable design history, plans, and operational guidance. This is the
repository knowledge base.

### `scripts/`

Stable commands for agents and humans. Prefer adding a script here when a
validation or setup step becomes important enough to repeat.

## Invariants

- diagnostics must go to stderr.
- generated workflows must not contain stored Linear secrets.
- `Dev Complete` is the default non-active handoff state.
- agents must not move Linear issues to terminal states.
- branch names must use `feature/`, `bugfix/`, or `hotfix/`.
- PR titles must start with the Linear issue identifier.

## Extension Points

- Named instances: see `docs/decisions/0010-named-instances-share-the-runner.md`.
- Agent runtime adapters: future work should support non-Codex CLIs through a
  first-class runtime abstraction; see
  `docs/decisions/0011-agent-runtimes-are-first-class.md`.
- Archived prototype work lives under `docs/archive/` and is not part of the
  supported package.
