# OpenClaw Agents V1 Harness Plan

## Goal

Make this folder usable by future Codex runs as an agent-legible harness for
installing local Orchestra instances, with OpenClaw agents integration available
as a later add-on.

## Current Slice

- OpenClaw agent wrapper exists and is tested.
- `orchestra` CLI can initialize config, generate `WORKFLOW.md`, clone the
  runner, check prerequisites, and run Orchestra.
- `orchestra github pr-review dispatch` can send PR review requests to an
  OpenClaw agent through the CLI/Tailscale SSH boundary.
- JSON schemas and sample payloads are local.
- Architecture, decisions, and validation commands are now repo-local.
- runner implementation remains outside this folder.

## Acceptance Criteria

- `scripts/validate` passes locally.
- Agents can find the spec, architecture, schemas, and integration boundary from
  `AGENTS.md`.
- Another machine can install Orchestra and run `orchestra init`,
  `orchestra doctor`, and `orchestra up`.
- The wrapper can be smoke-tested without a real OpenClaw install.
- Known gaps are tracked in `docs/tech-debt-tracker.md`.

## Progress

- [x] Add wrapper implementation.
- [x] Add wrapper behavior tests.
- [x] Add Orchestra tool schema and config example.
- [x] Add agent-facing repo map.
- [x] Add architecture and decision docs.
- [x] Add validation harness.
- [x] Patch local runner checkout with `ask_openclaw_agent` dynamic tool support.
- [x] Add OpenClaw agent host install and smoke-test scripts.
- [x] Add installable `orchestra` CLI.
- [x] Add GitHub PR review dispatch helper.
- [x] Test console scripts in a temporary virtualenv.
- [ ] Implement Orchestra runner dynamic tool in the real runner codebase.
- [ ] Run the one-line installer on a machine without preinstalled `mise`.
- [ ] Run a real local Orchestra issue loop with Linear and Codex auth.
- [ ] Run an end-to-end Tailscale SSH test against an OpenClaw agent host.
