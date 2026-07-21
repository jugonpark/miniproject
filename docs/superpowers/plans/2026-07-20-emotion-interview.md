# MOODWAVE Emotion Interview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 감정 인터뷰 UI와 검증 가능한 음악 후보 검색을 기존 API 계약을 유지하며 제공한다.

**Architecture:** 감정 흐름 규칙과 API 변환을 순수 TypeScript 모듈에 두고 Client Component는 렌더링과 단계 이동만 담당한다. 검색 파이프라인은 기존 Provider를 유지하면서 버전 인식 정규화와 점수 선택만 강화한다.

**Tech Stack:** Next.js 15, React 19, TypeScript, CSS, Vitest, Python 3.13, FastMCP, Pydantic, pytest

## Global Constraints

- 웹검색 API와 새 UI 라이브러리를 추가하지 않는다.
- 검증되지 않은 곡을 최종 결과에 포함하지 않는다.
- 한 화면에는 핵심 질문 하나만 표시하고 reduced-motion 및 키보드 접근성을 지원한다.

---

### Task 1: 감정 흐름 모델과 요청 변환

**Files:**
- Create: `web/lib/emotion/flow.ts`
- Test: `web/tests/emotion-flow.test.ts`

**Interfaces:**
- Produces: `EmotionFlowState`, `nextStep(state)`, `pathFor(state)`, `toMusicRequest(state)`

- [ ] 테스트에 조건부 경로, 이전 답 변경 시 정리, 기존 `MusicRequest` 변환을 작성한다.
- [ ] `npm.cmd test -- --run tests/emotion-flow.test.ts`가 실패하는지 확인한다.
- [ ] 설정 객체와 순수 함수만으로 최소 구현한다.
- [ ] 같은 명령이 통과하는지 확인한다.

### Task 2: 단계형 인터뷰 UI

**Files:**
- Create: `web/components/EmotionInterview.tsx`
- Modify: `web/app/page.tsx`
- Modify: `web/app/globals.css`
- Test: `web/tests/emotion-interview.test.ts`

**Interfaces:**
- Consumes: `toMusicRequest(state)`
- Produces: `onSubmit(request: MusicRequest)` 한 번 호출

- [ ] 시작, 분기, 뒤로 가기, 최종 확인 전 미호출 테스트를 작성한다.
- [ ] 테스트 실패를 확인한다.
- [ ] 한 질문 렌더링, 단계 히스토리, 300ms 선택 잠금, 질문 포커스를 구현한다.
- [ ] CSS 전환, 상태별 배경, 모바일 1열, reduced-motion을 구현한다.
- [ ] 인터뷰 및 기존 웹 테스트를 실행한다.

### Task 3: 음악 후보 정규화와 버전 매칭

**Files:**
- Modify: `mcp-server/moodwave_mcp/services/normalization.py`
- Modify: `mcp-server/moodwave_mcp/providers/itunes.py`
- Modify: `mcp-server/moodwave_mcp/providers/musicbrainz.py`
- Test: `mcp-server/tests/test_itunes.py`
- Test: `mcp-server/tests/test_providers.py`

**Interfaces:**
- Produces: 원본 제목을 유지하는 정규화 키와 버전 일치 점수

- [ ] live/remix/instrumental/remaster가 원곡과 합쳐지지 않는 실패 테스트를 작성한다.
- [ ] 관련 pytest가 실패하는지 확인한다.
- [ ] 제목·아티스트·버전 점수로 최적 결과를 선택한다.
- [ ] 관련 pytest가 통과하는지 확인한다.

### Task 4: 회귀 검증

**Files:**
- Modify: 필요한 테스트 파일만

- [ ] `python -m pytest -q -p no:cacheprovider tests`를 실행해 전부 통과시킨다.
- [ ] `npm.cmd test -- --run`을 실행해 전부 통과시킨다.
- [ ] `npm.cmd run typecheck`, `npm.cmd run lint`, `npm.cmd run build`를 실행한다.
- [ ] 로컬 브라우저에서 대표 감정 분기와 추천 요청을 확인한다.
