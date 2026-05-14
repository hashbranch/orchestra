# Install Orchestra

This is the install path for another machine that should run its own local
Orchestra instance with its own Linear token and Codex agents.

## Prerequisites

- Python 3.10+
- Git
- GitHub CLI (`gh`), authenticated for PR creation
- Codex CLI, already authenticated
- `mise` for Elixir/Erlang; the Orchestra installer installs it if missing
- Linear personal API key

## Install Orchestra

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/hashbranch/orchestra/main/scripts/install | bash
```

This clones or updates Orchestra under `~/.orchestra/source`, installs the
Python package, builds the monorepo runner from
`~/.orchestra/source/runner/elixir`, and adds Python's user script directory to
your shell profile when needed. The directory is computed from your active
Python install, not hardcoded. Open a new terminal after install, or run the
`export PATH=...` line printed by the installer for the current terminal.

To install somewhere other than `~/.orchestra`, set `ORCHESTRA_INSTALL_HOME`.
`ORCHESTRA_HOME` is a runtime override for testing/running an alternate home and
is intentionally ignored by the installer.

By default the installer tracks the latest `v*` release tag. If no release tag
exists yet, it falls back to `main`. To pin a version or dogfood `main`:

```bash
ORCHESTRA_VERSION=v0.4.1 curl -fsSL https://raw.githubusercontent.com/hashbranch/orchestra/main/scripts/install | bash
ORCHESTRA_VERSION=main curl -fsSL https://raw.githubusercontent.com/hashbranch/orchestra/main/scripts/install | bash
```

Authenticated/private fallback:

```bash
sh -c 'd="${ORCHESTRA_INSTALL_DIR:-$HOME/.orchestra/source}"; mkdir -p "$(dirname "$d")"; if [ -d "$d/.git" ]; then git -C "$d" pull --ff-only; else gh repo clone hashbranch/orchestra "$d"; fi; "$d/scripts/install"'
```

From an existing checkout:

```bash
scripts/install
```

This performs the same install using your local checkout.

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
~/.orchestra/source/
~/.orchestra/traces/
~/.orchestra/workspaces/
```

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

The generated `WORKFLOW.md` always contains `api_key: $LINEAR_API_KEY`. If you
entered a key during init, `orchestra run` injects it into Orchestra's environment
from `config.json`; it is not written into `WORKFLOW.md`.

The GitHub repo for PRs is the configured target repo. Orchestra writes a
`hooks.after_create` step that runs `git clone <target repo> .`, so every Codex
workspace has that repo as `origin`. GitHub PR commands use that `origin` remote.
Generated workflows require branches to use `feature/`, `bugfix/`, or `hotfix/`
followed by the Linear issue identifier and a short kebab-case summary; branches
must not include a person's name or username.

Generated workflows also require Codex to assign `vector-hb` and
`nathaniel-hb` as PR reviewers, check Gemini and GitHub PR review feedback,
address valid comments, reply to comments, and resolve threads before moving the
Linear issue to the complete state. Agents use deterministic GitHub helpers for
reviewer assignment and feedback collection:

```bash
orchestra github reviewers ensure --reviewer vector-hb --reviewer nathaniel-hb
```

Agents use the generic helper below as a deterministic wait-and-collect step;
the agent still owns judging and fixing the feedback:

```bash
orchestra github pr-feedback wait --wait-seconds 300 --poll-seconds 15 --format markdown
```

GitHub helpers automatically append structured trace events under
`~/.orchestra/traces/<issue>/events.jsonl` when they can infer the Linear issue
identifier from the PR title. Generated workflows also require agents to write
an explicit completion decision trace before moving Linear to the complete
state:

```bash
orchestra trace event \
  --issue CLA-150 \
  --kind completion_decision \
  --message "PR is ready for Dev Complete after reviewer assignment, feedback handling, and validation." \
  --field pr_url=https://github.com/hashbranch/tera/pull/51 \
  --field validation=passed
```

The Linear state names are configurable at init. Orchestra uses the ready state
to decide what the runner should pick up, the working state while an agent is
running, and the complete state after a PR exists and validation is complete.
The complete state is a handoff state, not active work. Orchestra does not tell
agents to move Linear issues to terminal states such as `Done`.

After upgrading Orchestra, regenerate the local workflow from config without
re-entering secrets:

```bash
orchestra refresh-workflow
```

The generated Codex policy is intentionally broad: `danger-full-access` with
approval policy `never`. This is necessary for the local runner to write `.git`,
use the network, push branches, and create GitHub PRs without a human approval
prompt.

During install and `orchestra run`, Orchestra patches the local runner source
to honor Linear dependency order before dispatch. Issues with unresolved
non-terminal `blocked by` relations are skipped even if their state is otherwise
active.

To rotate or add the key later:

```bash
orchestra set-linear-key
```

## Check Machine

```bash
orchestra doctor
```

## Run

```bash
orchestra up
```

`orchestra up` checks whether the installed Orchestra release channel has a
newer version available, offers to apply it, regenerates `WORKFLOW.md` from
config after a successful update, then starts the local runner.

Use `orchestra run` when you want to skip the update check.

To check or apply updates directly:

```bash
orchestra update --check
orchestra update --yes
```

The first goal is local Orchestra + local Codex agents.
