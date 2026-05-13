# 0012: Default Runner Is Hashbranch Fork

Date: 2026-05-13

## Status

Accepted

## Context

Orchestra originally installed the OpenAI Symphony repository directly and
patched the local checkout during install and run. That was useful for getting
started, but it makes runner changes ambiguous: Orchestra needs native behavior
for blocker filtering, agent runtime scheduling, and future Claude support.

Keeping those changes as installer patches would make the CLI responsible for
runner internals. That is the wrong long-term boundary.

## Decision

Orchestra installs `https://github.com/hashbranch/orchestra-runner.git` by
default.

The runner fork is based on OpenAI Symphony's Elixir runner and lives outside
this CLI repo. This repo remains responsible for:

- the installer and update contract
- `orchestra init`, generated config, and generated `WORKFLOW.md`
- deterministic helper commands agents can call
- compatibility patches while runner changes are being upstreamed into the fork

The runner repo is responsible for:

- polling Linear
- dispatching issue workspaces
- enforcing scheduling and blocker semantics
- implementing native `agent.runtimes` execution
- managing runner dashboard/runtime behavior

## Consequences

New installs clone the Hashbranch runner fork. Existing installs migrate the
local runner checkout's `origin` remote to the Hashbranch fork the next time the
installer or repair command runs.

OpenAI Symphony remains the inspiration and upstream lineage, but Orchestra
runtime behavior should now be developed in the Hashbranch runner fork instead
of as ad hoc CLI patches.
