# Try It Out

This is the shortest path to prove the V1 loop with Codex workers in Symphony
and Vector as an advisory OpenClaw participant.

## 1. Install Wrapper On Vector

From this repo:

```bash
scripts/install-on-vector vector@vector-tailnet-hostname
```

## 2. Smoke Test Vector Over Tailscale SSH

```bash
scripts/smoke-vector vector@vector-tailnet-hostname
```

Expected result: valid JSON on stdout. If OpenClaw is unavailable on Vector, the
response should still be valid failed JSON.

## 3. Run Patched Symphony

The local patched Symphony checkout is:

```text
vendor/openai-symphony/elixir
```

Add Vector config to the `WORKFLOW.md` used to launch Symphony:

```yaml
openclaw_participants:
  vector:
    kind: ssh
    host: vector@vector-tailnet-hostname
    command: ~/.openclaw/bin/symphony-ask-vector
    timeout_ms: 240000
```

Then run Symphony from the patched checkout:

```bash
cd vendor/openai-symphony/elixir
mise trust
mise install
mise exec -- mix setup
mise exec -- mix build
mise exec -- ./bin/symphony /path/to/WORKFLOW.md
```

## 4. Prove The Agent Loop

Use a low-risk Linear issue whose workflow prompt asks Codex to call:

```text
ask_vector(mode="plan_review", question="Review the plan before implementation.", plan="...")
```

A successful loop is:

1. Codex sees `ask_vector` in app-server dynamic tools.
2. Codex calls `ask_vector`.
3. Symphony enriches the request with issue/workspace metadata.
4. Symphony SSHs to Vector and receives response JSON.
5. Codex incorporates `instructionsForCodex`.
6. No Telegram message is sent.
7. Vector does not modify the active workspace.
