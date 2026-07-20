# Task 5 Report: Web contracts and playlist proxy routes

Status: review fixes complete, pending re-review
Commits: `22fe32b` and `fix: harden web contracts and MCP retries` (this commit)

## Implemented

- Added the minimal Next.js, React, TypeScript, Tailwind, Zod, MCP SDK, and Vitest scaffold under `web/`.
- Mirrored the approved Python `MusicRequest`, `RecommendedTrack`, `PlaylistDraft`, and `SavedPlaylist` contracts, including request defaults and one-based track positions.
- Added a lazy singleton streamable-HTTP MCP client using `MCP_SERVER_URL`, one reconnect attempt for transport/call failures, and no retry for tool-declared errors.
- Added thin save/list/get/delete playlist proxy routes with input and MCP response validation, numeric ID checks, 404 mapping, and safe Korean errors.
- Added schema, route, and MCP client tests. No SQLite or Python imports exist under `web/`.

## TDD evidence

- Initial red: `npm.cmd test -- --run` failed with 2 missing production-module suites (`@/lib/schemas/music` and `@/app/api/playlists/[id]/route`).
- MCP client red: `npm.cmd test -- --run tests/mcp-client.test.ts` failed 2/2 because `@/lib/mcp/client` was absent.
- Self-review red: the focused client/route run failed 2 checks, proving malformed save output was mapped to 400 and tool errors retried twice.
- Focused green: `npm.cmd test -- --run tests/mcp-client.test.ts tests/playlist-routes.test.ts` passed 15/15.

## Final verification

`npm.cmd test -- --run`

```text
Test Files  3 passed (3)
Tests       24 passed (24)
Duration    8.49s
```

`npm.cmd run typecheck`

```text
> tsc --noEmit
Exit code: 0
```

## Owned paths

- `web/`
- `.superpowers/sdd/task-5-report.md`
- `_workspace/05_web_contract_handoff.md`

## Concerns

- `npm.cmd audit --json` reports two moderate findings for Next.js's bundled PostCSS `<8.5.10`. npm currently suggests an incompatible Next 9 downgrade, so no breaking audit fix was applied.
- Automated tests mock the MCP connection; live FastMCP interoperability remains for the later integrated smoke test.

## Review rejection fixes

- The singleton retry path now associates failure cleanup with the exact promise used by that call, resets it only while it remains current, and closes it once across concurrent failures.
- Typed `McpToolError`, `McpResponseError`, and `McpTransportError` separate tool/response failures from retryable transport failures. Decode failures never repeat a completed tool call.
- Missing playlists map to 404 only from typed tool errors; transport text containing `Not Found` remains a safe 500.
- TypeScript and Python now accept free-text-only requests and reject only when both condition selections and trimmed free text are empty.
- Playlist URLs accept only HTTP(S), and path IDs accept only canonical positive safe decimal integers.

Review-fix red evidence: focused web tests failed 12 checks covering all five findings; focused Python tests failed free-text-only construction.

Review-fix final verification:

```text
npm.cmd test -- --run -> 3 files passed, 36 tests passed
npm.cmd run typecheck -> exit 0
python -m pytest -q -p no:cacheprovider -> 48 passed in 0.76s
```

Authorized Python paths added to ownership for this fix:

- `mcp-server/moodwave_mcp/models.py` (`MusicRequest` only)
- `mcp-server/tests/test_models.py`
