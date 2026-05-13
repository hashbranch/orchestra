# 0012: Runner Lives In The Orchestra Monorepo

Date: 2026-05-13

## Status

Accepted

## Context

Orchestra originally installed the OpenAI Symphony repository directly and then
briefly moved to a Hashbranch fork. That was useful for getting started, but it
still split one product across multiple repositories. The runner contains much
of the system's behavior: Linear polling, scheduling, workspace lifecycle,
Codex process management, dashboard state, and future runtime adapters.

Keeping that logic in a separate repo creates version skew, confusing updates,
and makes it too easy for future agents to miss where the important code lives.

## Decision

Orchestra is a monorepo.

The Python CLI lives in `cli/`. The runner lives in `runner/`, with the current
Elixir implementation under `runner/elixir/`.

The installer clones one repository into `~/.orchestra/source`, installs the
CLI from that checkout, and builds/runs the runner from
`~/.orchestra/source/runner/elixir`.

The repo is responsible for:

- the installer and update contract
- `orchestra init`, generated config, and generated `WORKFLOW.md`
- deterministic helper commands agents can call
- polling Linear
- dispatching issue workspaces
- enforcing scheduling and blocker semantics
- implementing native `agent.runtimes` execution
- managing runner dashboard/runtime behavior

## Consequences

There is one release train and one update contract. `orchestra update` updates
both CLI and runner behavior together.

OpenAI Symphony remains the inspiration and upstream lineage, but Orchestra
runtime behavior should now be developed inside this repository instead of as ad
hoc patches against an external checkout.

The temporary `hashbranch/orchestra-runner` fork can be archived or left as a
historical fork, but it is not the default install path.
