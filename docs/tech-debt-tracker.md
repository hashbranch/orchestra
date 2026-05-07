# Tech Debt Tracker

## Open

- Add a response JSON schema and validate wrapper responses against it.
- Add CI once this folder lives in a Git repository.
- Run the install script against the real OpenClaw agent host Tailscale hostname.
- Run the real SSH smoke test after the OpenClaw agent host tailnet hostname is known.
- Validate the patched Symphony checkout with `mise exec -- make all`.
- Add a Homebrew tap or release binary if `pipx install git+...` is not enough.
- Decide whether Orchestra should pin upstream Symphony by commit or track a fork.
- Add an optional `orchestra init --from-linear-url` parser for project URLs.

## Closed

- Added executable wrapper for OpenClaw Agents V1.
- Added local validation command.
- Added agent-readable repo map and architecture docs.
- Added install and smoke-test scripts for OpenClaw agent.
- Patched a local OpenAI Symphony checkout under `vendor/openai-symphony/elixir`.
- Added installable `orchestra` CLI for local Symphony bootstrap.
- Made `orchestra init` collect Linear project, Linear API key, and target repo.
