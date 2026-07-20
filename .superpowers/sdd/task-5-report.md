# Task 5 Report: Web contracts and playlist proxy routes

Status: complete, pending reviewer gate
Commit: `feat: add web contracts and MCP playlist routes` (this commit)

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
