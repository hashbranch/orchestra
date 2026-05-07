# Symphony x OpenClaw V1: Vector Review Participant

Status: Draft v1  
Owner: Tom  
Primary goal: Let a locally running Symphony instance ask Vector for memory-bearing design/context/diff review over Tailscale, while Codex remains the implementation worker.

---

## 1. Problem

Symphony is useful as a Codex-centered issue runner, but fresh Codex workers lack durable local context:

- Tom/product/company preferences
- prior architectural decisions
- Hashbranch/OpenClaw conventions
- judgment from prior work

Vector has that context, but should not become another uncontrolled editor in the same Symphony workspace.

V1 should let Symphony ask Vector for structured review/advice without giving Vector write access to the active Codex workspace.

---

## 2. V1 Principle

**Codex edits. Vector reviews.**

Vector is a contextual participant, not an implementation worker.

V1 must avoid:

- shared workspace writes
- multi-agent file stomping
- public Gateway exposure
- sending Symphony chatter into Tom's normal Telegram session
- involving Forge/Meridian/ClawdActual yet

---

## 3. Target Architecture

```text
Tom's machine
  └─ Symphony
       ├─ Linear/GitHub orchestration
       ├─ Codex app-server worker(s)
       └─ dynamic tool: ask_vector
              |
              | Tailscale SSH
              v
Vector MacBook Air
  └─ ~/.openclaw/bin/symphony-ask-vector
       └─ openclaw agent --agent main --session-id symphony-<issue-id> --json
```

V1 uses **Tailscale SSH** rather than HTTP/Gateway APIs. It is simpler, private, and good enough for a prototype.

---

## 4. Capabilities

### `ask_vector`

Ask Vector for contextual review.

Supported modes:

- `plan_review`: before implementation
- `diff_review`: after Codex produces changes
- `context_lookup`: when Codex needs project/company/context guidance
- `risk_review`: when design/product/ops risk is unclear

Vector returns structured JSON only.

---

## 5. Non-Goals for V1

Do not implement yet:

- ClawdActual / Ken's OpenClaw integration
- Forge or Meridian routing
- Vector editing code
- Vector opening PRs
- shared workspace sync
- HTTP participant bridge
- long-running remote OpenClaw jobs
- bidirectional chat delivery
- public internet exposure

---

## 6. Tailscale Requirements

### Tom's machine

Must be able to SSH to Vector over Tailscale without interaction.

Required checks:

```bash
tailscale status
ssh vector@<vector-tailnet-hostname> 'hostname'
ssh vector@<vector-tailnet-hostname> 'openclaw status'
```

SSH must be key-based, no password prompt.

### Vector MacBook Air

Must have:

- Tailscale online
- SSH enabled/reachable over Tailscale
- `openclaw` available in noninteractive SSH shell
- Gateway running
- model/auth working
- wrapper script installed at `~/.openclaw/bin/symphony-ask-vector`

If `openclaw` is not in PATH over SSH, wrapper should set PATH explicitly.

---

## 7. Session Isolation

Do not use Vector's normal Telegram/main session.

Use deterministic session IDs:

```text
symphony-<issue-identifier>
```

Examples:

```text
symphony-CLA-123
symphony-HB-456
```

The wrapper should pass this into OpenClaw via `--session-id`.

Purpose:

- keep Symphony context out of normal chat
- preserve per-issue continuity
- allow follow-up reviews on the same issue

---

## 8. Request Schema

Symphony sends JSON to Vector wrapper over stdin.

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
    "root": "/path/to/symphony/workspace",
    "branch": "cla-123-example"
  },
  "plan": "Optional implementation plan from Codex",
  "diff": "Optional unified diff or summarized diff",
  "question": "What should Codex know before implementing this?",
  "constraints": [
    "Codex owns edits in this workspace",
    "Vector should not modify files",
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

Vector wrapper returns JSON to stdout.

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
  "summary": "Vector review failed",
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

## 10. Vector Wrapper Script

Path on Vector:

```bash
~/.openclaw/bin/symphony-ask-vector
```

Responsibilities:

1. Read JSON request from stdin.
2. Validate required fields.
3. Build a prompt for Vector.
4. Call OpenClaw CLI with isolated session id.
5. Enforce timeout.
6. Parse/normalize Vector output into response schema.
7. Print response JSON to stdout.
8. Print diagnostics only to stderr.

Suggested CLI call:

```bash
openclaw agent \
  --agent main \
  --session-id "symphony-${ISSUE_IDENTIFIER}" \
  --message-file "$PROMPT_FILE" \
  --json \
  --timeout 180
```

If `--message-file -` works, stdin piping is fine. Otherwise use temp files.

Wrapper should never use `--deliver`.

---

## 11. Prompt Contract for Vector

The wrapper should include this instruction block in every prompt:

```text
You are Vector participating in a Symphony coding workflow.

Role:
- You are Tom's OpenClaw coding/context agent.
- Codex owns implementation in the active Symphony workspace.
- Your job is to review, advise, surface context, and produce instructions for Codex.

Hard rules:
- Do not message Tom.
- Do not modify files.
- Do not run external actions.
- Do not assume you can access the Symphony workspace unless explicitly given files/diffs.
- Return JSON only matching the response schema.
- If you need more information, set needsHuman=true or include a recommendation for what Symphony/Codex should provide next.
```

Then append the request payload.

---

## 12. Symphony Dynamic Tool

Add a dynamic tool in Symphony, probably next to current `linear_graphql` support.

Tool name:

```text
ask_vector
```

Description:

```text
Ask Vector, Tom's OpenClaw coding/context agent, for plan, design, context, or diff review. Vector is advisory only and must not modify the active workspace.
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

Symphony should enrich the tool call with:

- current issue
- repo/workspace metadata
- branch
- request id
- standard constraints

Codex should not have to manually pass all metadata.

---

## 13. SSH Invocation from Symphony

Config:

```yaml
openclaw_participants:
  vector:
    kind: ssh
    host: vector@<vector-tailnet-hostname>
    command: ~/.openclaw/bin/symphony-ask-vector
    timeout_ms: 240000
```

Execution pattern:

```bash
ssh -T vector@<vector-tailnet-hostname> '~/.openclaw/bin/symphony-ask-vector' < request.json
```

Recommended SSH options:

```bash
ssh \
  -T \
  -o BatchMode=yes \
  -o ConnectTimeout=10 \
  vector@<vector-tailnet-hostname> \
  '~/.openclaw/bin/symphony-ask-vector'
```

Timeout should be enforced by Symphony as well as by the wrapper.

---

## 14. WORKFLOW.md Guidance

Add guidance to the repo workflow prompt:

```md
## Vector Review

You have access to `ask_vector`, an advisory tool that asks Tom's OpenClaw agent for contextual review.

Use `ask_vector` when:
- requirements are ambiguous
- product/business intent matters
- implementation plan may conflict with existing Hashbranch/OpenClaw preferences
- you are about to make a meaningful architectural decision
- before requesting human review on a non-trivial diff

Do not use `ask_vector` for tiny mechanical edits.
Do not ask Vector to edit files. Codex owns implementation in this workspace.
When Vector returns `instructionsForCodex`, incorporate them unless they conflict with the ticket or tests.
If Vector marks `blocking=true`, pause and resolve the issue before continuing.
```

---

## 15. Error Handling

Symphony behavior:

- If `ask_vector` fails during optional review, continue but log warning.
- If `ask_vector` fails during required gate, mark issue blocked or ask human.
- If response is malformed JSON, wrap as failed response and expose stderr/logs.
- If SSH fails, return `VECTOR_UNREACHABLE`.
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

- Use Tailscale only. Do not expose Vector Gateway publicly.
- Use SSH key auth, no password prompts.
- Use `BatchMode=yes` for noninteractive safety.
- Wrapper must not run arbitrary commands from request payload.
- Wrapper must treat request content as data, not shell input.
- Quote all shell variables or avoid shell interpolation entirely.
- Do not pass secrets in request payload.
- Do not allow Vector to send external messages from this workflow.
- Do not allow Vector to mutate Symphony workspace in V1.

---

## 17. Acceptance Criteria

V1 is complete when:

1. From Tom's machine:
   ```bash
   ssh vector@<vector-tailnet-hostname> '~/.openclaw/bin/symphony-ask-vector' < sample-request.json
   ```
   returns valid response JSON.

2. Symphony exposes `ask_vector` to Codex.

3. Codex can call `ask_vector` during a test issue.

4. Vector response appears in Symphony logs/tool output.

5. Codex can incorporate `instructionsForCodex` into its next step.

6. No message is sent to Tom's Telegram during the workflow.

7. Vector does not modify the active workspace.

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
    "root": "/tmp/symphony/workspaces/TEST-001",
    "branch": "test-001-account-routing"
  },
  "plan": "Add an accountAlias field to integration calls and default to explicit aliases in workflow config.",
  "diff": null,
  "question": "Review this plan for context/design risks before Codex implements it.",
  "constraints": [
    "Codex owns edits in this workspace",
    "Vector should not modify files",
    "Return JSON only"
  ]
}
```

---

## 19. Future V2

After V1 works:

- Add ClawdActual as second OpenClaw participant.
- Generalize `ask_vector` into `ask_openclaw_participant`.
- Add participant registry to `WORKFLOW.md`.
- Add diff summarization if raw diffs get too large.
- Add optional required review gates by label/state.
- Add HTTP bridge over Tailscale instead of SSH.
- Add isolated execution mode where Vector/ClawdActual work in separate clones and return PRs or patches.

---

## 20. Suggested Build Order

1. Confirm Tailscale SSH from Tom machine to Vector.
2. Create `~/.openclaw/bin/symphony-ask-vector` on Vector.
3. Test wrapper manually with sample payload.
4. Add Symphony config for OpenClaw participant SSH target.
5. Add `ask_vector` dynamic tool implementation.
6. Update `WORKFLOW.md` prompt guidance.
7. Run a fake Linear issue through Symphony.
8. Run one real low-risk issue.
