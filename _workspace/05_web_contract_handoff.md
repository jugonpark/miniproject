# Task 5 Web Contract Handoff

Status: complete, pending reviewer gate
Owner: task5_implementer
Commit: `feat: add web contracts and MCP playlist routes` (this commit)
Owned paths: `web/`, `.superpowers/sdd/task-5-report.md`, `_workspace/05_web_contract_handoff.md`
Consumer: Task 6 Agent Loop and Task 8 library UI

Tests: `npm.cmd test -- --run` -> 3 files passed, 24 tests passed; `npm.cmd run typecheck` -> exit 0.

Contracts: import `musicRequestSchema` from `web/lib/schemas/music.ts`; import `playlistDraftSchema` and `savedPlaylistSchema` from `web/lib/schemas/playlist.ts`; call MCP tools through `callTool<T>(name, args)` in `web/lib/mcp/client.ts`.

Routes: `POST/GET /api/playlists` and `GET/DELETE /api/playlists/[id]` validate both inputs and MCP results. POST requires a non-empty `idempotency_key`.

Concerns: npm reports a moderate transitive PostCSS advisory through Next.js with no compatible remediation offered; live FastMCP interoperability is not part of this automated branch verification.
