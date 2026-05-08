# Agent Guide

This repository is optimized for agentic work. Keep this file short: it is a map,
not the source of truth.

## Start Here

- Product/spec source: `symphony-openclaw-agents-v1-spec.md`
- Architecture map: `ARCHITECTURE.md`
- Documentation index: `docs/index.md`
- Install guide: `docs/install-orchestra.md`
- Validation command: `scripts/validate`

## Working Rules

- Codex owns edits in this workspace.
- OpenClaw agents are advisory only and must not modify the active workspace.
- Treat request and response JSON schemas as boundary contracts.
- Prefer small vertical slices with tests over broad speculative scaffolding.
- Keep diagnostics on stderr and machine-readable responses on stdout.
- Do not introduce network exposure for OpenClaw agents in V1; use Tailscale SSH only.
- Record durable product, workflow, and architecture decisions in `docs/decisions/`
  when implementation behavior changes. Do not leave decisions only in chat,
  generated prompts, or code comments.
- Keep Linear `Dev Complete` as a non-active PR handoff state. Agents must not
  move issues to terminal states such as `Done`; see
  `docs/decisions/0004-dev-complete-is-linear-handoff.md`.
- Preserve the GitHub PR delivery contract: branch names use only
  `feature/`, `bugfix/`, or `hotfix/`; required reviewers are `vector-hb` and
  `nathaniel-hb`; Gemini/GitHub review feedback must be handled before Linear
  handoff. See `docs/decisions/0005-standardize-github-pr-delivery.md`.

## Agent Skills

### Issue Tracker

No external issue tracker is configured for this folder. Track local execution
plans under `docs/plans/`. See `docs/agents/issue-tracker.md`.

### Triage Labels

This folder does not currently use tracker labels. If issues move to GitHub,
Linear, or another tracker, map labels in `docs/agents/triage-labels.md`.

### Domain Docs

Single-context repo. Read `ARCHITECTURE.md`, then `docs/index.md`, then the
specific plan or decision doc needed for the task. See `docs/agents/domain.md`.

## Validation

Before handing work back, run:

```bash
scripts/validate
```

If validation fails, fix the harness or document the blocker before returning.
