# Tech Debt Tracker

## Open

- Add CI once this folder lives in a Git repository.
- Validate the patched runner checkout with `mise exec -- make all`.
- Add a Homebrew tap or release binary if `pipx install git+...` is not enough.
- Decide whether Orchestra should pin the upstream runner by commit or track a fork.
- Add an optional `orchestra init --from-linear-url` parser for project URLs.
- Replace Orchestra's local runner source patch with an upstream runner release once unresolved blocker filtering applies to every active state upstream.
- Preserve the update contract during any Go CLI migration: the one-line
  installer, `~/.orchestra/source`, and `orchestra update` / `orchestra up`
  must remain stable across the handoff.
- Add native runner support for `agent.runtimes`, including Claude Code
  invocation and round-robin scheduling across per-runtime concurrency limits.

## Closed

- Added local validation command.
- Added agent-readable repo map and architecture docs.
- Patched a local upstream runner checkout under `vendor/orchestra-runner/elixir`.
- Added installable `orchestra` CLI for local Orchestra bootstrap.
- Made `orchestra init` collect Linear project, Linear API key, and target repo.
- Patched local runner installs to skip active issues with unresolved Linear blockers.
- Moved the unsupported agent participant prototype out of the package and
  public CLI surface into `docs/archive/`.
- Added first-class generated agent runtime configuration for Codex and Claude.
