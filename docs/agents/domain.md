# Domain Docs

This is a single-context repository.

Agents should use:

- `AGENTS.md` as the entry-point map.
- `ARCHITECTURE.md` for system boundaries and invariants.
- `docs/index.md` for the documentation map.
- `docs/decisions/` for durable design choices.
- `docs/plans/` for execution state.

Do not rely on chat history as the source of truth for design decisions. Promote
decisions into `docs/decisions/` or the active plan when they need to guide future
agent runs.
