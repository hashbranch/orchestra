# Architecture

## Purpose

This repository has one supported product surface:

- `orchestra`: a CLI that installs and runs local Orchestra runner instances.

## System Boundary

```text
Linear project
  -> Orchestra runner
  -> isolated workspace cloned from target GitHub repo
  -> configured agent runtime
  -> GitHub branch and PR
  -> Linear handoff state
```

This repository owns the installable CLI, generated runner config, prompt
instructions, deterministic helpers, and runner source needed to run Orchestra
safely.

## Modules

### `cli/`

Install, init, run, update, GitHub helper, and trace commands.

Provider-scoped helper command wiring lives under `cli/helpers/`. The root
`cli/main.py` should stay focused on top-level command registration and shared
install/runtime commands.

GitHub helper implementation lives under `cli/helpers/github/`: `commands.py`
owns parser/handler wiring and provider-specific modules such as
`pr_feedback.py` own API/query/formatting behavior.

### `runner/`

Local runner source. The current runner is the Elixir implementation inherited
from OpenAI Symphony and adapted for Orchestra.

### `docs/`

Agent-readable design history, plans, and operational guidance. This is the
repository knowledge base.

### `scripts/`

Stable commands for agents and humans. Prefer adding a script here when a
validation or setup step becomes important enough to repeat.

## Invariants

- diagnostics must go to stderr.
- generated `orchestra.yaml` / `WORKFLOW.md` files must not contain stored
  Linear secrets.
- `orchestra.yaml` is structured runner configuration; `WORKFLOW.md` is
  prompt/instruction text for agents.
- `Dev Complete` is the default non-active handoff state.
- agents must not move Linear issues to terminal states.
- branch names must use `feature/`, `bugfix/`, or `hotfix/`.
- PR titles must start with the Linear issue identifier.

## Extension Points

- Named instances: see `docs/decisions/0010-named-instances-share-the-runner.md`.
- Agent runtime adapters: future work should support non-Codex CLIs through a
  first-class runtime abstraction; see
  `docs/decisions/0011-agent-runtimes-are-first-class.md`.
- Workflow configuration boundary: runner config belongs in `orchestra.yaml`,
  while `WORKFLOW.md` remains prompt-only; see
  `docs/decisions/0013-split-runner-config-from-agent-prompt.md`.
- Archived prototype work lives under `docs/archive/` and is not part of the
  supported package.
