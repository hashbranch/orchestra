# Tech Debt Tracker

## Open

- Add CI once this folder lives in a Git repository.
- Validate runner changes with `mise exec -- make all` from `runner/elixir`.
- Add a Homebrew tap or release binary if `pipx install git+...` is not enough.
- Add an optional `orchestra init --from-linear-url` parser for project URLs.
- Replace Orchestra's local runner source patch with a native runner change once
  unresolved blocker filtering applies to every active state in `runner/elixir`.
- Preserve the update contract during any Go CLI migration: the one-line
  installer, `~/.orchestra/source`, and `orchestra update` / `orchestra up`
  must remain stable across the handoff.

## Closed

- Added local validation command.
- Added agent-readable repo map and architecture docs.
- Patched a local runner source tree under `runner/elixir`.
- Added installable `orchestra` CLI for local Orchestra bootstrap.
- Made `orchestra init` collect Linear project, Linear API key, and target repo.
- Patched local runner installs to skip active issues with unresolved Linear blockers.
- Moved the unsupported agent participant prototype out of the package and
  public CLI surface into `docs/archive/`.
- Added first-class generated agent runtime configuration for Codex and Claude.
- Moved the runner into this monorepo under `runner/elixir`.
- Added native runner support for `agent.runtimes`, including Claude Code
  invocation and round-robin scheduling across per-runtime concurrency limits.
- Split generated workflow files into structured `orchestra.yaml` config and
  prompt-only `WORKFLOW.md`.
