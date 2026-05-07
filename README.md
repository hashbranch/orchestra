# Orchestra

Orchestra is a small bootstrap CLI for installing and running a local OpenAI
Symphony instance on another machine. The Vector/OpenClaw wrapper remains in this
repo, but it is not required for the first install path.

## Implemented

- Installable `orchestra` CLI
- Local config and `WORKFLOW.md` generation
- Symphony clone/build/run commands
- Local prerequisite checks via `orchestra doctor`
- Vector-side wrapper executable: `bin/symphony-ask-vector`
- Request validation for the V1 schema
- Prompt contract that keeps Vector advisory only
- OpenClaw invocation with deterministic `symphony-<issue-identifier>` session IDs
- Response normalization into the V1 JSON response schema
- Failure wrapping for invalid requests, OpenClaw timeout/failure, and malformed output
- Sample request payload: `samples/sample-request.json`
- Symphony-facing tool schema: `schemas/ask_vector.tool.schema.json`
- Example participant config: `config/openclaw-participants.example.yaml`
- Integration design note: `docs/symphony-integration-design.md`
- Try-it-out runbook: `docs/try-it-out.md`
- Unit tests for the wrapper behavior

## Local Test

```bash
scripts/validate
```

For the test suite only:

```bash
scripts/test
```

## Install On Another Machine

From a Git checkout:

```bash
scripts/install-orchestra
```

This wraps `pip install --user .` and adds Python's user script directory to your
shell profile when needed.

Or, once this repo is pushed somewhere reachable:

```bash
pipx install git+https://github.com/your-org/orchestra.git
```

Initialize a local Symphony install:

```bash
orchestra init

orchestra doctor
orchestra install-symphony
orchestra run
```

`orchestra init` prompts for the Linear project slug, Linear API key, and target
repo URL. The key is stored in `~/.orchestra/config.json` but the generated
`WORKFLOW.md` always uses `$LINEAR_API_KEY`; `orchestra run` injects the stored
key into Symphony's environment. You can also pass setup values as flags.

The target repo is also the GitHub PR destination: Orchestra clones it into each
issue workspace, so its `origin` remote is where `gh pr create` points.

Linear state names are configurable during `orchestra init`, including ready,
working, blocked, complete, and terminal states. The default complete state is
`Dev Complete`.

Orchestra's generated workflow runs Codex with `danger-full-access`. That is
required for unattended GitHub delivery because the agent has to write Git
metadata, reach GitHub, push branches, and open PRs from the local machine.

To update the stored Linear key later:

```bash
orchestra set-linear-key
```

`orchestra install-symphony` installs `mise` automatically if no Elixir toolchain
is found. Use `--skip-build` when you only want to verify clone layout.

By default Orchestra writes to `~/.orchestra`:

```text
~/.orchestra/
  config.json
  WORKFLOW.md
  workspaces/
  symphony/
```

To run against a real Vector/OpenClaw install:

```bash
bin/symphony-ask-vector < samples/sample-request.json
```

The wrapper accepts optional overrides:

```bash
OPENCLAW_BIN=/path/to/openclaw OPENCLAW_AGENT=main OPENCLAW_TIMEOUT_SECONDS=180 \
  bin/symphony-ask-vector < samples/sample-request.json
```

## Install On Vector

Copy this folder to Vector or package the wrapper into `~/.openclaw/bin`. The target
entry point from the spec is:

```bash
~/.openclaw/bin/symphony-ask-vector
```

If `openclaw` is not available in noninteractive SSH shells, set `OPENCLAW_BIN` in
the wrapper environment or update Vector's shell profile for noninteractive SSH.

## Symphony Integration Boundary

The Symphony codebase is not present in this folder, so the dynamic tool is not
implemented here. The next implementation slice in Symphony should:

- Add `openclaw_participants.vector` config with host, command, and timeout.
- Expose `ask_vector` with the smaller tool schema from the spec.
- Enrich tool calls with issue metadata, repo metadata, request ID, branch, and
  standard constraints.
- Invoke SSH with `BatchMode=yes`, `ConnectTimeout=10`, and `-T`.
- Normalize SSH failures as `SSH_UNREACHABLE` and malformed wrapper responses as
  `MALFORMED_RESPONSE`.
