# Quality

## Current Grade

Prototype harness: usable for local Orchestra install and runner workflow work.

## Strengths

- Boundary contracts are explicit and machine-readable.
- Wrapper behavior has focused tests.
- Validation is available through one stable script.
- Design decisions are documented in repo-local markdown.

## Gaps

- No CI runner is configured yet.
- Runner changes should be validated against the local `runner/elixir` test
  suite.
- Claude Code runtime support is implemented, but real-world mixed Codex/Claude
  runs should continue to be exercised against live Linear/GitHub projects.

## Bar For Future Changes

- Add or update tests for wrapper behavior changes.
- Update decision docs when changing authority, transport, or session isolation.
- Keep `scripts/validate` passing.
- Prefer repo-local docs over relying on chat context.
