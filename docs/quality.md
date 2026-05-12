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
- The upstream runner patch should be validated against the real runner test
  suite.
- Non-Codex agent runtimes are not supported yet.

## Bar For Future Changes

- Add or update tests for wrapper behavior changes.
- Update decision docs when changing authority, transport, or session isolation.
- Keep `scripts/validate` passing.
- Prefer repo-local docs over relying on chat context.
