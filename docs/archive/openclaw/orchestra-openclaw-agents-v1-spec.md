# Orchestra x OpenClaw V1: OpenClaw Agent Review Participant

Status: Draft v1  
Owner: Hashbranch  
Primary goal: Let a locally running Orchestra instance ask configured OpenClaw agents for memory-bearing design/context/diff review over Tailscale, while Codex remains the implementation worker.

---

## 1. Problem

Orchestra is useful as a Codex-centered issue runner, but fresh Codex workers lack durable local context:

- operator/product/company preferences
- prior architectural decisions
- Hashbranch/OpenClaw conventions
- judgment from prior work

OpenClaw agents can have that context, but should not become uncontrolled editors in the same Orchestra workspace.

V1 should let Orchestra ask OpenClaw agents for structured review/advice without giving them write access to the active Codex workspace.

---

## 2. V1 Principle

**Codex edits. OpenClaw agents review.**

OpenClaw agents are contextual participants, not implementation workers.

V1 must avoid:

- shared workspace writes
- multi-agent file stomping
- public Gateway exposure
- sending Orchestra chatter into a normal human-facing chat session
- involving Forge/Meridian/ClawdActual yet

---

## 3. Target Architecture

```text
operator machine
  └─ Orchestra
       ├─ Linear/GitHub orchestration
       ├─ Codex app-server worker(s)
       └─ dynamic tool: ask_openclaw_agent
              |
              | Tailscale SSH
              v
OpenClaw agent host
  └─ ~/.openclaw/bin/orchestra-ask-openclaw-agent
       └─ openclaw agent --agent main --session-id orchestra-<issue-id> --json
```

V1 uses **Tailscale SSH** rather than HTTP/Gateway APIs. It is simpler, private, and good enough for a prototype.

---

## 4. Capabilities

### `ask_openclaw_agent`

Ask an OpenClaw agent for contextual review.

Supported modes:

- `plan_review`: before implementation
- `diff_review`: after Codex produces changes
- `context_lookup`: when Codex needs project/company/context guidance
- `risk_review`: when design/product/ops risk is unclear

OpenClaw agents return structured JSON only.

---

## 5. Non-Goals for V1

Do not implement yet:

- ClawdActual / Ken's OpenClaw integration
- Forge or Meridian routing
- OpenClaw agents editing code
- OpenClaw agents opening PRs
- shared workspace sync
- HTTP participant bridge
- long-running remote OpenClaw jobs
- bidirectional chat delivery
- public internet exposure

---

## 6. Tailscale Requirements

### operator machine

Must be able to SSH to the OpenClaw agent host over Tailscale without interaction.

Required checks:

```bash
tailscale status
ssh openclaw@<agent-tailnet-hostname> 'hostname'
ssh openclaw@<agent-tailnet-hostname> 'openclaw status'
```

SSH must be key-based, no password prompt.

### OpenClaw agent host

Must have:

- Tailscale online
- SSH enabled/reachable over Tailscale
- `openclaw` available in noninteractive SSH shell
- Gateway running
- model/auth working
- wrapper script installed at `~/.openclaw/bin/orchestra-ask-openclaw-agent`

If `openclaw` is not in PATH over SSH, wrapper should set PATH explicitly.

---

## 7. Session Isolation

Do not use an OpenClaw agent host's normal human-facing session.

Use deterministic session IDs:

```text
orchestra-<issue-identifier>
```

Examples:

```text
orchestra-CLA-123
orchestra-HB-456
```

The wrapper should pass this into OpenClaw via `--session-id`.

Purpose:

- keep Orchestra context out of normal chat
- preserve per-issue continuity
- allow follow-up reviews on the same issue

---

## 8. Request Schema

Orchestra runner sends JSON to OpenClaw agent wrapper over stdin.

```json
{
  "schemaVersion": "1.0",
  "requestId": "uuid-or-run-id",
  "mode": "plan_review",
  "issue": {
    "id": "linear-id",
    "identifier": "CLA-123",
    "title": "Issue title",
    "description": "Issue description",
    "url": "https://linear.app/...",
    "labels": ["backend", "billing"],
    "state": "In Progress"
  },
  "repo": {
    "name": "hashbranch/admin",
    "root": "/path/to/orchestra/workspace",
    "branch": "cla-123-example"
  },
  "plan": "Optional implementation plan from Codex",
  "diff": "Optional unified diff or summarized diff",
  "question": "What should Codex know before implementing this?",
  "constraints": [
    "Codex owns edits in this workspace",
    "OpenClaw agents should not modify files",
    "Return JSON only"
  ]
}
```

Fields:

- `schemaVersion`: required, currently `1.0`
- `requestId`: required for tracing
- `mode`: required
- `issue.identifier`: required and used for session id
- `question`: required
- `plan`: optional
- `diff`: optional, but required for `diff_review`

---

## 9. Response Schema

OpenClaw agent wrapper returns JSON to stdout.

```json
{
  "schemaVersion": "1.0",
  "requestId": "same-request-id",
  "status": "completed",
  "mode": "plan_review",
  "blocking": false,
  "summary": "Short answer",
  "risks": [
    {
      "severity": "medium",
      "title": "Risk title",
      "detail": "Why it matters"
    }
  ],
  "recommendations": [
    "Concrete recommendation"
  ],
  "instructionsForCodex": [
    "Specific instruction Codex should follow"
  ],
  "needsHuman": false,
  "error": null
}
```

On failure:

```json
{
  "schemaVersion": "1.0",
  "requestId": "same-request-id",
  "status": "failed",
  "mode": "plan_review",
  "blocking": false,
  "summary": "OpenClaw agent review failed",
  "risks": [],
  "recommendations": [],
  "instructionsForCodex": [],
  "needsHuman": false,
  "error": {
    "code": "OPENCLAW_TIMEOUT",
    "message": "openclaw agent timed out"
  }
}
```

---

## 10. OpenClaw Agent Wrapper Script

Path on an OpenClaw agent host:

```bash
~/.openclaw/bin/orchestra-ask-openclaw-agent
```

Responsibilities:

1. Read JSON request from stdin.
2. Validate required fields.
3. Build a prompt for OpenClaw agent.
4. Call OpenClaw CLI with isolated session id.
5. Enforce timeout.
6. Parse/normalize OpenClaw agent output into response schema.
7. Print response JSON to stdout.
8. Print diagnostics only to stderr.

Suggested CLI call:

```bash
openclaw agent \
  --agent main \
  --session-id "orchestra-${ISSUE_IDENTIFIER}" \
  --message-file "$PROMPT_FILE" \
  --json \
  --timeout 180
```

If `--message-file -` works, stdin piping is fine. Otherwise use temp files.

Wrapper should never use `--deliver`.

---

## 11. Prompt Contract for OpenClaw Agents

The wrapper should include this instruction block in every prompt:

```text
You are an OpenClaw agent participating in a Orchestra coding workflow.

Role:
- You are an OpenClaw coding/context agent.
- Codex owns implementation in the active Orchestra workspace.
- Your job is to review, advise, surface context, and produce instructions for Codex.

Hard rules:
- Do not message the human operator.
- Do not modify files.
- Do not run external actions.
- Do not assume you can access the Orchestra workspace unless explicitly given files/diffs.
- Return JSON only matching the response schema.
- If you need more information, set needsHuman=true or include a recommendation for what Orchestra/Codex should provide next.
```

Then append the request payload.

---

## 12. Orchestra Dynamic Tool

Add a dynamic tool in Orchestra, probably next to current `linear_graphql` support.

Tool name:

```text
ask_openclaw_agent
```

Description:

```text
Ask a configured OpenClaw coding/context agent for plan, design, context, or diff review. OpenClaw agents are advisory only and must not modify the active workspace.
```

Tool input schema should mirror the request schema, with a smaller surface available to Codex:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["mode", "question"],
  "properties": {
    "mode": {
      "type": "string",
      "enum": ["plan_review", "diff_review", "context_lookup", "risk_review"]
    },
    "question": { "type": "string" },
    "plan": { "type": ["string", "null"] },
    "diff": { "type": ["string", "null"] }
  }
}
```

Orchestra runner should enrich the tool call with:

- current issue
- repo/workspace metadata
- branch
- request id
- standard constraints

Codex should not have to manually pass all metadata.

---

## 13. SSH Invocation from Orchestra

Config:

```yaml
openclaw_participants:
  main:
    kind: ssh
    host: openclaw@<agent-tailnet-hostname>
    command: ~/.openclaw/bin/orchestra-ask-openclaw-agent
    timeout_ms: 240000
```

Execution pattern:

```bash
ssh -T openclaw@<agent-tailnet-hostname> '~/.openclaw/bin/orchestra-ask-openclaw-agent' < request.json
```

Recommended SSH options:

```bash
ssh \
  -T \
  -o BatchMode=yes \
  -o ConnectTimeout=10 \
  openclaw@<agent-tailnet-hostname> \
  '~/.openclaw/bin/orchestra-ask-openclaw-agent'
```

Timeout should be enforced by Orchestra as well as by the wrapper.

---

## 14. WORKFLOW.md Guidance

Add guidance to the repo workflow prompt:

```md
## OpenClaw Agent Review

You have access to `ask_openclaw_agent`, an advisory tool that asks an OpenClaw agent for contextual review.

Use `ask_openclaw_agent` when:
- requirements are ambiguous
- product/business intent matters
- implementation plan may conflict with existing Hashbranch/OpenClaw preferences
- you are about to make a meaningful architectural decision
- before requesting human review on a non-trivial diff

Do not use `ask_openclaw_agent` for tiny mechanical edits.
Do not ask OpenClaw agents to edit files. Codex owns implementation in this workspace.
When OpenClaw agents return `instructionsForCodex`, incorporate them unless they conflict with the ticket or tests.
If an OpenClaw agent marks `blocking=true`, pause and resolve the issue before continuing.
```

---

## 15. Error Handling

Orchestra runner behavior:

- If `ask_openclaw_agent` fails during optional review, continue but log warning.
- If `ask_openclaw_agent` fails during required gate, mark issue blocked or ask human.
- If response is malformed JSON, wrap as failed response and expose stderr/logs.
- If SSH fails, return `SSH_UNREACHABLE`.
- If OpenClaw times out, return `OPENCLAW_TIMEOUT`.

Suggested failure codes:

- `INVALID_REQUEST`
- `SSH_UNREACHABLE`
- `OPENCLAW_TIMEOUT`
- `OPENCLAW_FAILED`
- `MALFORMED_RESPONSE`
- `UNKNOWN_ERROR`

---

## 16. Security / Safety

- Use Tailscale only. Do not expose OpenClaw agent Gateway publicly.
- Use SSH key auth, no password prompts.
- Use `BatchMode=yes` for noninteractive safety.
- Wrapper must not run arbitrary commands from request payload.
- Wrapper must treat request content as data, not shell input.
- Quote all shell variables or avoid shell interpolation entirely.
- Do not pass secrets in request payload.
- Do not allow OpenClaw agent to send external messages from this workflow.
- Do not allow OpenClaw agent to mutate Orchestra workspace in V1.

---

## 17. Acceptance Criteria

V1 is complete when:

1. From operator machine:
   ```bash
   ssh openclaw@<agent-tailnet-hostname> '~/.openclaw/bin/orchestra-ask-openclaw-agent' < sample-request.json
   ```
   returns valid response JSON.

2. Orchestra exposes `ask_openclaw_agent` to Codex.

3. Codex can call `ask_openclaw_agent` during a test issue.

4. OpenClaw agent response appears in Orchestra logs/tool output.

5. Codex can incorporate `instructionsForCodex` into its next step.

6. No message is sent to the operator's chat during the workflow.

7. OpenClaw agents do not modify the active workspace.

---

## 18. Test Payload

```json
{
  "schemaVersion": "1.0",
  "requestId": "test-001",
  "mode": "plan_review",
  "issue": {
    "id": "test-linear-id",
    "identifier": "TEST-001",
    "title": "Add account routing for external tools",
    "description": "Implement explicit account alias selection for external CRM/email integrations.",
    "url": "https://linear.app/example/issue/TEST-001",
    "labels": ["backend", "integrations"],
    "state": "In Progress"
  },
  "repo": {
    "name": "example/repo",
    "root": "/tmp/orchestra/workspaces/TEST-001",
    "branch": "test-001-account-routing"
  },
  "plan": "Add an accountAlias field to integration calls and default to explicit aliases in workflow config.",
  "diff": null,
  "question": "Review this plan for context/design risks before Codex implements it.",
  "constraints": [
    "Codex owns edits in this workspace",
    "OpenClaw agents should not modify files",
    "Return JSON only"
  ]
}
```

---

## 19. Future V2

After V1 works:

- Add ClawdActual as second OpenClaw participant.
- Generalize `ask_openclaw_agent` into `ask_openclaw_participant`.
- Add participant registry to `WORKFLOW.md`.
- Add diff summarization if raw diffs get too large.
- Add optional required review gates by label/state.
- Add HTTP bridge over Tailscale instead of SSH.
- Add isolated execution mode where OpenClaw agent/ClawdActual work in separate clones and return PRs or patches.

---

## 20. Suggested Build Order

1. Confirm Tailscale SSH from operator machine to OpenClaw agent.
2. Create `~/.openclaw/bin/orchestra-ask-openclaw-agent` on OpenClaw agent.
3. Test wrapper manually with sample payload.
4. Add Orchestra config for OpenClaw participant SSH target.
5. Add `ask_openclaw_agent` dynamic tool implementation.
6. Update `WORKFLOW.md` prompt guidance.
7. Run a fake Linear issue through Orchestra.
8. Run one real low-risk issue.
