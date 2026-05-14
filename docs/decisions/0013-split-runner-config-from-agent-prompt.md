# 0013: Split Runner Config From Agent Prompt

Date: 2026-05-14

## Status

Accepted

## Context

`WORKFLOW.md` originally used YAML front matter for runner configuration and
Markdown body text for the agent prompt. That made the file hard to reason about:
humans expected Markdown to be instructions, while the runner depended on hidden
structured config embedded in the same file.

We want workflow configuration to be deterministic, testable, and parseable
without treating a Markdown prompt as a mixed-format config document.

## Decision

Orchestra splits workflow files:

- `orchestra.yaml` contains structured runner configuration consumed by the
  runner.
- `WORKFLOW.md` contains prompt/instruction text handed to the selected agent
  runtime.

The CLI writes both files from `~/.orchestra/config.json` during `orchestra init`,
`orchestra refresh-workflow`, successful `orchestra update`, and successful
`orchestra up` updates.

The runner still accepts legacy YAML front matter in `WORKFLOW.md` as a fallback
when `orchestra.yaml` is absent. That fallback is compatibility only; new
generated workflows must use the split files.

## Consequences

The runner cache must watch both `WORKFLOW.md` and `orchestra.yaml` so prompt or
configuration edits reload deterministically.

Tests should assert structured config against YAML and prompt instructions
against Markdown. Future agents should not add new runner config fields to
`WORKFLOW.md` front matter.
