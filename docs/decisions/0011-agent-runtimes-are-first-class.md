# 0011: Agent Runtimes Are First Class

Date: 2026-05-13

## Status

Accepted

## Context

Orchestra started with a Codex-specific workflow because the upstream runner
launches Codex in app-server mode. We also want to support Claude CLI and future
agent CLIs without pretending they are Codex commands.

Claude Code supports non-interactive print mode with flags such as `-p`,
`--output-format stream-json`, `--max-turns`, `--permission-mode`, `--bare`,
`--model`, and `--effort`. The model flag should be optional because signed-in
Claude users may have a default model or plan-specific model behavior.

## Decision

Agent runtime configuration belongs in a first-class `agent.runtimes` workflow
section.

Each runtime owns:

- `name`
- `kind`
- launch command
- max concurrency
- runtime-specific invocation settings

The scheduler should select among runtime slots using the configured strategy.
The first supported strategy is `round_robin`.

Codex remains a runtime:

```yaml
agent:
  max_concurrent_agents: 6
  runtime_selection: "round_robin"
  runtimes:
    - name: "codex"
      kind: "codex"
      command: "codex app-server"
      max_concurrent: 3
```

Claude should be configured as its own runtime:

```yaml
agent:
  runtimes:
    - name: "claude"
      kind: "claude_code"
      command: "claude"
      max_concurrent: 3
      print: true
      bare: true
      output_format: "stream-json"
      permission_mode: "bypassPermissions"
```

Orchestra must not set a Claude model by default. If users want a model override,
they can configure one explicitly.

For current runner compatibility, Orchestra may still emit the legacy `codex:`
block when a Codex runtime is configured. That block is compatibility plumbing,
not the long-term runtime model.

## Consequences

The generated workflow can represent Codex-only, Claude-only, or mixed runtime
pools. Native execution of non-Codex runtimes still requires runner support for
`agent.runtimes`; until then, the runtime config is the contract that runner work
should implement.

Round-robin scheduling must respect both global `agent.max_concurrent_agents`
and per-runtime `max_concurrent` limits.
