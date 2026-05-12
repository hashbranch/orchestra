# 0009: GitHub PR review dispatch uses the OpenClaw CLI

## Status

Accepted

## Context

Orchestra needs a way to notify an OpenClaw agent when GitHub requests that
agent as a pull request reviewer. OpenClaw has webhook ingress support, but this
repository's V1 boundary keeps OpenClaw agents off public HTTP surfaces and uses
Tailscale SSH for agent-host access.

## Decision

Add a provider-scoped helper:

```bash
orchestra github pr-review dispatch
```

The helper accepts either explicit PR metadata or a GitHub `pull_request`
webhook payload. It normalizes the request, filters by requested reviewer or
team when configured, builds a fixed review prompt, and invokes:

```bash
openclaw agent --agent <agent> --session-id <github-pr-review-session> --message <prompt>
```

When `--openclaw-host` is set, the helper wraps that OpenClaw command in:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 -T <host> <openclaw command>
```

The helper does not verify GitHub signatures itself; deployment-facing webhook
receivers must verify signatures before writing payloads to this helper.

## Consequences

- The immediate integration stays compatible with the V1 Tailscale SSH
  boundary.
- Future webhook services can be thin: verify GitHub, dedupe delivery IDs, then
  call this helper.
- OpenClaw HTTP hook dispatch remains a future adapter, not the default V1 path.
- GitHub payloads, PR descriptions, diffs, and comments are treated as untrusted
  data in the generated prompt.
