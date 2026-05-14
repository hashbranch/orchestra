# Orchestra

Orchestra installs and runs a local Linear-driven Codex automation harness. It
watches a configured Linear project, picks up eligible issues, creates isolated
workspaces from a target GitHub repo, runs Codex agents locally, and drives work
to pull requests.

Orchestra is intended for teams that want repository-local implementation agents
running on their own machine or workstation, with their own GitHub, Linear, and
Codex credentials. It was inspired by OpenAI Symphony. The CLI and runner now
live together in this repository so installs, releases, and runner behavior move
as one product.

## What Orchestra Does

- Installs a local runner and CLI under `~/.orchestra`
- Initializes a Linear project, Linear API key, target GitHub repo, and agent
  concurrency setting
- Generates a local `WORKFLOW.md` from config
- Starts a local issue runner with `orchestra up`
- Creates one workspace per active issue under `~/.orchestra/workspaces`
- Instructs Codex agents to commit, push, open PRs, request reviewers, wait for
  PR feedback, and move Linear issues to the configured handoff state
- Honors Linear blockers before dispatch so dependent tickets do not run out of
  order
- Provides GitHub helpers for reviewer assignment, PR feedback collection, and
  PR review dispatch
- Records structured trace events for workflow debugging
- Updates itself through `orchestra update` or the startup flow in `orchestra up`

## Install

Run the one-line installer from any directory:

```bash
curl -fsSL https://raw.githubusercontent.com/hashbranch/orchestra/main/scripts/install | bash
```

That clones or updates Orchestra under `~/.orchestra/source`, installs the
Python package, builds the monorepo runner from
`~/.orchestra/source/runner/elixir`, installs `mise` if no Elixir toolchain is
available, and adds Python's user script directory to your shell profile when
needed.

Open a new terminal after install, or run the `export PATH=...` line printed by
the installer for the current terminal.

To install somewhere other than `~/.orchestra`, set `ORCHESTRA_INSTALL_HOME`.
`ORCHESTRA_HOME` is a runtime override for testing/running an alternate home and
is intentionally ignored by the installer.

By default the installer tracks the latest `v*` release tag. To pin a version or
dogfood `main`:

```bash
ORCHESTRA_VERSION=v0.4.2 curl -fsSL https://raw.githubusercontent.com/hashbranch/orchestra/main/scripts/install | bash
ORCHESTRA_VERSION=main curl -fsSL https://raw.githubusercontent.com/hashbranch/orchestra/main/scripts/install | bash
```

From an existing Git checkout:

```bash
scripts/install
```

## Configure

Run:

```bash
orchestra init
```

The initializer asks for:

- Linear API key
- Linear project slug
- target GitHub repo URL
- max concurrent agents

The Linear API key is stored in `~/.orchestra/config.json` and injected into the
runner environment at runtime. It is not written into `WORKFLOW.md`.

The target repo is the repo Codex clones for each issue workspace and the repo
where PRs are opened. The intended mapping is one Orchestra configuration per
Linear project/repo pair.

By default Orchestra configures Codex. To generate the long-term mixed runtime
contract for Codex and Claude:

```bash
orchestra init \
  --agent-runtime both \
  --max-concurrent-agents 6
```

Claude is configured without a model override by default, so the signed-in Claude
CLI account controls the default model. Add `--claude-model` only when you want
to pin one explicitly. Native execution of non-Codex runtimes requires runner
support for `agent.runtimes`; current runner compatibility still uses the legacy
Codex block when Codex is configured.

## Run

Check the install and start Orchestra:

```bash
orchestra doctor
orchestra up
```

`orchestra up` checks the installed release channel for an update, offers to
apply it or skip it, regenerates `WORKFLOW.md` from config after a successful
update, then starts the local runner.

Use `orchestra run` only when you want to skip the update check.

## Update

Explicit update commands:

```bash
orchestra update --check
orchestra update
orchestra update --yes
```

Future CLI implementations must preserve this update contract. The stable
boundary is the one-line installer, `~/.orchestra/source`, and the
`orchestra update` / `orchestra up` commands.

## Files

By default Orchestra writes to:

```text
~/.orchestra/
  source/
  source/runner/
  config.json
  WORKFLOW.md
  workspaces/
  traces/
```

## Validation

For local development:

```bash
scripts/validate
```

For the test suite only:

```bash
scripts/test
```
