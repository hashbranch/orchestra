# 0002: Use Tailscale SSH For V1

Date: 2026-05-07

## Status

Accepted

## Context

The Vector participant must be reachable from Tom's machine without exposing a
public Gateway or adding a service bridge before the prototype proves value.

## Decision

Use Tailscale SSH to invoke `~/.openclaw/bin/symphony-ask-vector` on Vector.

Symphony sends the enriched request JSON on stdin. The wrapper returns response
JSON on stdout and diagnostics on stderr.

## Consequences

The integration remains private and simple, but Symphony must enforce SSH timeout
and error mapping. V2 can replace this with an HTTP bridge over Tailscale after
the participant contract is stable.
