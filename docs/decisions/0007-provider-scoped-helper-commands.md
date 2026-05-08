# 0007: Provider-scope helper commands

## Status

Accepted

## Context

Orchestra helpers are deterministic primitives agents can call from workflows.
As helpers grow, a flat command namespace makes it harder for agents and users to
understand which external system a helper touches and what credentials it needs.

The PR feedback helper talks to GitHub, so its command should communicate that
boundary directly.

## Decision

Built-in helper commands are grouped by provider or domain:

- `orchestra github ...` for GitHub-backed helpers
- `orchestra linear ...` for Linear-backed helpers
- `orchestra git ...` for local Git helpers
- `orchestra validation ...` for validation/discovery helpers
- `orchestra helper ...` for custom helpers and generic extension points

The canonical PR feedback command is:

```bash
orchestra github pr-feedback wait
```

The older flat command remains as a compatibility alias for now:

```bash
orchestra pr-feedback wait
```

Generated workflows must use the provider-scoped form.

## Consequences

Agents can infer service boundaries from command names. Future helpers should be
added under their provider/domain namespace rather than at the top level, unless
the top-level command is a core Orchestra lifecycle command such as `init`,
`doctor`, or `run`.

