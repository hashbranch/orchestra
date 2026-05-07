# Install Orchestra

This is the install path for another machine that should run its own local
Symphony instance with its own Linear token and Codex agents.

## Prerequisites

- Python 3.10+
- Git
- GitHub CLI (`gh`), authenticated for PR creation
- Codex CLI, already authenticated
- `mise` for Elixir/Erlang; `orchestra install-symphony` installs it if missing
- Linear personal API key

## Install CLI

From a checkout:

```bash
scripts/install-orchestra
```

This installs the package and adds Python's user script directory to your shell
profile when needed.

From a hosted Git repo later:

```bash
pipx install git+https://github.com/your-org/orchestra.git
```

## Initialize

Interactive setup:

```bash
export LINEAR_API_KEY=lin_api_...

orchestra init
```

`orchestra init` asks for:

- Linear API key, stored only in `~/.orchestra/config.json`; Enter uses `$LINEAR_API_KEY`
- Linear project slug
- target GitHub repo URL for Codex workspaces and PRs
- max concurrent agents, default `1`

Unattended setup:

```bash
orchestra init \
  --linear-project-slug your-project-slug \
  --linear-api-key "$LINEAR_API_KEY" \
  --github-repo git@github.com:your-org/your-repo.git \
  --max-concurrent-agents 3 \
  --ready-state Todo \
  --working-state "In Progress" \
  --complete-state "Dev Complete" \
  --blocked-state Blocked
```

This creates:

```text
~/.orchestra/config.json
~/.orchestra/WORKFLOW.md
~/.orchestra/workspaces/
```

The generated `WORKFLOW.md` always contains `api_key: $LINEAR_API_KEY`. If you
entered a key during init, `orchestra run` injects it into Symphony's environment
from `config.json`; it is not written into `WORKFLOW.md`.

The GitHub repo for PRs is the configured target repo. Orchestra writes a
`hooks.after_create` step that runs `git clone <target repo> .`, so every Codex
workspace has that repo as `origin`. GitHub PR commands use that `origin` remote.

The Linear state names are configurable at init. Orchestra uses the ready state
to decide what Symphony should pick up, the working state while an agent is
running, and the complete state after a PR exists and validation is complete.

The generated Codex policy is intentionally broad: `danger-full-access` with
approval policy `never`. This is necessary for the local runner to write `.git`,
use the network, push branches, and create GitHub PRs without a human approval
prompt.

To rotate or add the key later:

```bash
orchestra set-linear-key
```

## Check Machine

```bash
orchestra doctor
```

## Install Symphony

```bash
orchestra install-symphony
```

This clones `https://github.com/openai/symphony.git` into
`~/.orchestra/symphony` and builds the Elixir implementation.

If `mise` is not installed, this command installs it first and then uses it to
install the Elixir/Erlang versions required by Symphony. Use
`--no-install-mise` to disable that behavior.

To verify clone layout without building Elixir:

```bash
orchestra install-symphony --skip-build
```

## Run

```bash
orchestra run
```

The first goal is local Symphony + local Codex agents. OpenClaw agents wiring can be added
later by changing the generated `WORKFLOW.md` and using the wrapper docs.
