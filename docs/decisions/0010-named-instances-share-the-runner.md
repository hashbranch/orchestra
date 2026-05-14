# 0010: Named Instances Share The Runner

Date: 2026-05-12

## Status

Accepted

## Context

Companies may want Orchestra to watch many Linear projects and many target repos.
The common happy path is one Linear project per repo, where users assign todos
and Orchestra picks up eligible work automatically.

A single workflow should not try to route work across unrelated repos. When a
Linear project contains issues for multiple target repos, the agent has to infer
repository ownership from issue text, labels, or conventions. That is fragile
and can create PRs in the wrong repository.

## Decision

Orchestra should have one global install and runner under `~/.orchestra`, with
named instances for configuration and runtime state.

Each named instance should own:

- Linear project slug
- target GitHub repo
- generated `orchestra.yaml`
- generated prompt-only `WORKFLOW.md`
- workspaces
- traces
- concurrency limits
- Linear state mapping

The runner code and CLI package should be shared by all instances. Running
multiple instances means running multiple runner processes, each pointed at its
own instance workflow files.

The target command shape should be:

```bash
orchestra init --instance tera-api
orchestra up --instance tera-api
orchestra up --all
orchestra instances list
```

## Consequences

The recommended mapping is one Orchestra instance per Linear project/repo pair.
Multiple Linear projects can point at the same repo by using separate instances.
Multiple repos in one Linear project should be split into separate Linear
projects or otherwise mapped into separate instances before automation.

This keeps scheduling, traces, workspaces, and concurrency isolated while still
letting the machine share one installed runner.
