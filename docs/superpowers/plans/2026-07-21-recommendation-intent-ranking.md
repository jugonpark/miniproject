# Recommendation Intent And Track Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve free-text constraints through discovery, verification, deterministic track scoring, and candidate-ID-only playlist composition.

**Architecture:** The Agent Host obtains one schema-validated `RecommendationIntent`, then passes it unchanged to MCP tools. MCP performs grouped Last.fm discovery, evidence accumulation, hard filtering, neutral-aware scoring, and deterministic candidate-ID composition; NVIDIA may only order known IDs and provide roles/reasons.

**Tech Stack:** Next.js 15, TypeScript, Zod, NVIDIA OpenAI-compatible API, FastMCP, Python 3.13, Pydantic, pytest, Vitest.

## Global Constraints

- `VERIFIED_FOREIGN` is rejected; `UNKNOWN` is retained unless another explicit hard constraint fails.
- Unknown vocal, energy, genre, or language evidence is never inferred.
- Missing score dimensions are omitted and available weights are renormalized.
- Candidate IDs are deterministic and immutable across verification and composition.
- Zero verified candidates skip final NVIDIA and `compose_playlist`.
- No hard constraint is relaxed to fill the requested count.
- Request data and derived intent remain traceable by `requestId` without logging secrets.

---

### Task 1: Structured recommendation intent

**Files:**
- Create: `web/lib/agent/recommendation-intent.ts`
- Modify: `web/lib/agent/agent-loop.ts`
- Test: `web/tests/recommendation-intent.test.ts`

**Interfaces:**
- Produces: `recommendationIntentSchema`, `RecommendationIntent`, `fallbackIntent(request)`.
- Consumes: `MusicRequest`.

- [ ] Write failing tests for domestic, JP exclusion, low vocals, hidden gems, UI preservation, and absent-condition neutrality.
- [ ] Run `npm.cmd test -- --run tests/recommendation-intent.test.ts` and confirm missing schema/helpers fail.
- [ ] Implement Zod schema, bounded NVIDIA structured parsing, and deterministic fallback.
- [ ] Pass the validated intent unchanged to every MCP call and log it with `requestId`.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Grouped Last.fm discovery evidence

**Files:**
- Modify: `mcp-server/moodwave_mcp/models.py`
- Modify: `mcp-server/moodwave_mcp/services/constraints.py`
- Modify: `mcp-server/moodwave_mcp/providers/lastfm.py`
- Modify: `mcp-server/moodwave_mcp/services/discovery.py`
- Modify: `mcp-server/moodwave_mcp/server.py`
- Test: `mcp-server/tests/test_discovery_intent.py`

**Interfaces:**
- Consumes: serialized `RecommendationIntent`.
- Produces: `CandidateArtist` with `matched_tags`, `matched_categories`, and `appearance_count`.

- [ ] Write failing tests proving all non-empty tag groups execute and repeated artists accumulate evidence.
- [ ] Run the focused pytest and confirm evidence fields/grouped API are missing.
- [ ] Implement category tag mapping and quotas `scene=12, mood=8, activity=6, genre=6, vocal=4` with limited redistribution only among preference groups.
- [ ] Preserve required scene tags and merge normalized artists without early exit.
- [ ] Log requested tags, per-tag counts, evidence, and deduplicated counts by `requestId`.
- [ ] Re-run the focused pytest and confirm it passes.

### Task 3: Hard constraints and neutral-aware scoring

**Files:**
- Create: `mcp-server/moodwave_mcp/services/scoring.py`
- Modify: `mcp-server/moodwave_mcp/models.py`
- Modify: `mcp-server/moodwave_mcp/services/verification.py`
- Modify: `mcp-server/moodwave_mcp/services/recommendation.py`
- Test: `mcp-server/tests/test_scoring.py`

**Interfaces:**
- Produces: `TrackRecommendationFeatures`, `score_track(track, intent)`, and `hard_constraint_result(track, intent)`.
- `chatIntentScore` allocation: scene/genre 6, activity 4, vocal/lyrics 4, familiarity/popularity 3, explicit include/exclude alignment 3.

- [ ] Write failing tests for foreign rejection, unknown-origin retention, excluded artists/genres/countries, live/remix rejection, low-vocal neutral handling, hidden-gem ordering, and different-chat ordering.
- [ ] Run focused pytest and confirm scoring module is missing.
- [ ] Implement hard filtering before scoring.
- [ ] Score scene 25, chat 20, emotional arc 20, activity 15, vocal 10, novelty 5, popularity 5; omit unknown dimensions and renormalize remaining weights to 100.
- [ ] Generate evidence-based reasons and role sequence `EMPATHY, GROUNDING, TRANSITION, TARGET, CLOSURE`.
- [ ] Re-run focused pytest and confirm it passes.

### Task 4: Candidate-ID-only final composition

**Files:**
- Modify: `web/lib/agent/agent-loop.ts`
- Modify: `web/lib/agent/system-prompt.ts`
- Modify: `web/lib/schemas/playlist.ts`
- Modify: `mcp-server/moodwave_mcp/server.py`
- Test: `web/tests/agent-loop.test.ts`
- Test: `mcp-server/tests/test_recommendation.py`

**Interfaces:**
- Consumes: verified candidates with deterministic `candidate_id` and features.
- Produces: validated ordered IDs, roles, reasons, and `SUCCESS | PARTIAL | INSUFFICIENT_MATCHING_TRACKS`.

- [ ] Write failing tests for unknown IDs, duplicates, invalid roles/counts/JSON, zero-candidate short circuit, and partial results.
- [ ] Run focused tests and confirm current free-form composition fails them.
- [ ] Restrict NVIDIA output to candidate IDs and validate against the candidate map.
- [ ] Hydrate final metadata only from verified candidates and reject generated track data.
- [ ] Re-run focused tests and confirm they pass.

### Task 5: End-to-end verification

**Files:**
- Modify only failing implementation or test files from Tasks 1-4.

- [ ] Run Python tests with a workspace `--basetemp` path.
- [ ] Run Web Vitest, typecheck, lint, production build, and `git diff --check`.
- [ ] Restart local MCP and Next.js servers.
- [ ] Execute the three approved UI scenarios and capture structured intent, tags, evidence, verified IDs, scored candidates, and final tracks.
- [ ] Compare identical UI state with chat A/B and confirm tags, scores, ordering, and reasons differ.
