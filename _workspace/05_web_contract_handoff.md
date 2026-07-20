# Task 5 Web Contract Handoff

Status: review fixes complete, pending re-review
Owner: task5_implementer
Commits: `22fe32b` and `fix: harden web contracts and MCP retries` (this commit)
Owned paths: `web/`, `mcp-server/moodwave_mcp/models.py` (`MusicRequest` only), `mcp-server/tests/test_models.py`, `.superpowers/sdd/task-5-report.md`, `_workspace/05_web_contract_handoff.md`
Consumer: Task 6 Agent Loop and Task 8 library UI

Tests: `npm.cmd test -- --run` -> 3 files passed, 36 tests passed; `npm.cmd run typecheck` -> exit 0; `python -m pytest -q -p no:cacheprovider` -> 48 passed.

Contracts: import `musicRequestSchema` from `web/lib/schemas/music.ts`; import `playlistDraftSchema` and `savedPlaylistSchema` from `web/lib/schemas/playlist.ts`; call MCP tools through `callTool<T>(name, args)` in `web/lib/mcp/client.ts`.

Review fixes: free-text-only requests are valid in TypeScript and Python; URLs are HTTP(S)-only; typed MCP tool/response errors are non-retryable and map to 502 except typed missing playlists; transport failures retry once with exact-promise cleanup; IDs are canonical positive safe decimals.

Routes: `POST/GET /api/playlists` and `GET/DELETE /api/playlists/[id]` validate both inputs and MCP results. POST requires a non-empty `idempotency_key`.

Concerns: npm reports a moderate transitive PostCSS advisory through Next.js with no compatible remediation offered; live FastMCP interoperability is not part of this automated branch verification.
