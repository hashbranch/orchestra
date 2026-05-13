# Agent Guide

This repository is optimized for agentic work. Keep this file short: it is a map,
not the source of truth.

## Start Here

- Product/spec source: `README.md` and `docs/install-orchestra.md`
- Architecture map: `ARCHITECTURE.md`
- Documentation index: `docs/index.md`
- Install guide: `docs/install-orchestra.md`
- CLI source: `cli/`
- Runner source: `runner/elixir/`
- Validation command: `scripts/validate`

## Working Rules

- Codex owns edits in this workspace.
- Treat request and response JSON schemas as boundary contracts.
- Prefer small vertical slices with tests over broad speculative scaffolding.
- Keep diagnostics on stderr and machine-readable responses on stdout.
- Record durable product, workflow, and architecture decisions in `docs/decisions/`
  when implementation behavior changes. Do not leave decisions only in chat,
  generated prompts, or code comments.
- Treat Orchestra as a monorepo. Do not add or depend on a separate runner repo
  for core behavior; see `docs/decisions/0012-runner-lives-in-monorepo.md`.
- Keep Linear `Dev Complete` as a non-active PR handoff state. Agents must not
  move issues to terminal states such as `Done`; see
  `docs/decisions/0004-dev-complete-is-linear-handoff.md`.
- Preserve the GitHub PR delivery contract: branch names use only
  `feature/`, `bugfix/`, or `hotfix/`; required reviewers are `vector-hb` and
  `nathaniel-hb`; agents must use `orchestra github reviewers ensure`; Gemini
  and GitHub review feedback must be handled before Linear handoff. See
  `docs/decisions/0005-standardize-github-pr-delivery.md`.
- Keep PR feedback judgment with the builder agent. The helper
  `orchestra github pr-feedback wait` may wait and collect feedback, but must
  not decide validity, modify code, resolve comments, or move Linear; see
  `docs/decisions/0006-agent-owned-pr-feedback-gate.md`.
- Add built-in helpers under provider/domain namespaces such as
  `orchestra github ...`, `orchestra linear ...`, `orchestra git ...`, or
  `orchestra validation ...`; see
  `docs/decisions/0007-provider-scoped-helper-commands.md`.
- Capture workflow debugging evidence as structured trace events and explicit
  agent decision notes, not hidden reasoning. Use `orchestra trace event` for
  auditable handoff decisions; see
  `docs/decisions/0008-auditable-workflow-traces.md`.
- Keep archived prototype work out of the public CLI and package until it is
  supported as a first-class agent runtime. Archived notes live under
  `docs/archive/`.

## Agent Skills

### Issue Tracker

No external issue tracker is configured for this folder. Track local execution
plans under `docs/plans/`. See `docs/agents/issue-tracker.md`.

### Triage Labels

This folder does not currently use tracker labels. If issues move to GitHub,
Linear, or another tracker, map labels in `docs/agents/triage-labels.md`.

### Domain Docs

Single-context repo. Read `ARCHITECTURE.md`, then `docs/index.md`, then the
specific decision doc needed for the task. See `docs/agents/domain.md`.

## Validation

Before handing work back, run:

```bash
scripts/validate
```

If validation fails, fix the harness or document the blocker before returning.
