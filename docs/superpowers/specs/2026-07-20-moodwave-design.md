# MOODWAVE 설계

## 목표와 범위

MOODWAVE는 활동, 분위기, 보컬 선호, 국내외 범위, 곡 수와 자유 요청을 입력받아 NVIDIA Qwen이 FastMCP Tool을 선택하고, 외부 음악 데이터로 검증된 곡만 추천하는 단일 사용자용 localhost 웹앱이다. 앱은 음원을 재생하지 않고 YouTube Music 검색 링크만 제공한다. 추천 결과는 사용자가 저장 버튼을 누를 때만 SQLite에 저장한다.

제외 범위는 로그인, OAuth, 앱 내부 재생, 자동 취향 학습, 멀티에이전트와 자동 배포다.

## 현재 저장소와 배치

작업 공간에는 기존 애플리케이션 코드나 Git 이력이 없다. 신규 Git 저장소인 `moodwave/` 아래에 `web/`, `mcp-server/`, `docs/`를 둔다. 확인된 실행 환경은 Node.js 24.18.0, npm 11.16.0, Python 3.13.14다.

## 기술 스택

- Web: Next.js App Router, TypeScript, Tailwind CSS, Zod, React 내장 상태 관리
- LLM: NVIDIA OpenAI 호환 Chat Completions API, Qwen, `tool_choice="auto"`, temperature 0.2
- MCP: 공식 TypeScript MCP Client와 Python FastMCP, localhost HTTP transport
- Data: Last.fm, MusicBrainz, Cover Art Archive, YouTube Music 검색 URL
- DB: Python 표준 `sqlite3`; FastMCP 서버만 DB에 접근
- Test: pytest, Vitest; 핵심 브라우저 검증은 필요할 때 Playwright 사용

ORM, shadcn/ui, 별도 전역 상태 라이브러리와 영구 API 캐시는 첫 구현에 추가하지 않는다.

## 아키텍처와 요청 흐름

1. 사용자가 Next.js 조건 선택 UI에서 요청을 제출한다.
2. `POST /api/agent`가 입력을 Zod로 검증하고 한국어 system prompt와 user message를 만든다.
3. Next.js Agent Loop가 Qwen을 호출한다.
4. Qwen의 Tool 호출을 Next.js MCP Client가 Python FastMCP 서버에 전달한다.
5. FastMCP가 외부 API를 호출하고 정규화된 Observation만 반환한다.
6. Agent Loop가 Observation을 Qwen에 추가해 최대 8회 재호출한다.
7. Tool 단계, 최종 텍스트 delta와 `PlaylistDraft`를 NDJSON으로 브라우저에 전송한다.
8. UI는 임시 플레이리스트를 표시한다. 저장 버튼을 눌러야만 DB Tool이 호출된다.

Qwen은 Tool 결과에 없는 곡을 최종 결과에 추가할 수 없다. 구조화된 플레이리스트의 기준 데이터는 `compose_playlist` 결과이며 Qwen 텍스트는 설명만 담당한다.

## MCP Tool 계약

Agent가 호출하는 Tool:

- `discover_music_candidates`: 조건과 Last.fm 태그로 후보 아티스트 탐색
- `expand_similar_artists`: 발견 비율 또는 후보 수가 부족할 때 유사 아티스트 확장
- `verify_music_tracks`: MusicBrainz 식별자로 실제 곡 검증 및 Cover Art 보강
- `compose_playlist`: 검증 후보만 사용해 곡 수, 60:40 목표, 아티스트당 최대 2곡을 적용

사용자 동작으로 직접 호출하는 Tool:

- `save_playlist`
- `list_playlists`
- `get_playlist`
- `delete_playlist`

외부 HTTP 요청, 재시도, 캐시, 중복 제거, 태그 정규화, 점수 계산과 YouTube URL 생성은 공개 Tool이 아닌 내부 함수다.

## 데이터 모델과 DB

Python Pydantic 모델과 TypeScript Zod schema는 `MusicRequest`, `CandidateArtist`, `VerifiedTrack`, `RecommendedTrack`, `PlaylistDraft`, `SavedPlaylist` 구조를 동일하게 유지한다.

SQLite에는 `playlists`와 `playlist_tracks`를 둔다. `playlist_tracks.playlist_id`는 `ON DELETE CASCADE` 외래키다. 모든 연결에서 foreign key를 활성화하고 저장·삭제는 트랜잭션과 파라미터 바인딩을 사용한다. `position`으로 곡 순서를 보존한다.

저장 API는 클라이언트의 중복 클릭 방지와 서버의 idempotency key를 함께 사용한다. 추천 생성 자체는 DB를 변경하지 않는다.

## 외부 Provider와 캐시

- Last.fm: 태그 기반 후보, 상위 태그, 유사 아티스트
- MusicBrainz: 아티스트·recording·release 검증, User-Agent와 호출 간격 준수
- Cover Art Archive: release 우선, release group 보조, 표지 없음은 정상 처리

모든 네트워크 요청에는 타임아웃과 제한된 재시도를 둔다. 응답은 내부 모델로 정규화하고 크기를 제한한다. TTL 메모리 캐시와 동일 요청 promise 공유로 중복 호출을 막는다. 프로세스 재시작 후 캐시 보존이 실제로 필요할 때만 SQLite 캐시를 추가한다.

## 스트리밍과 UI

`POST /api/agent`는 `application/x-ndjson` ReadableStream으로 다음 이벤트를 보낸다: `status`, `tool`, `tool_result`, `text_delta`, `playlist`, `error`, `done`.

UI에는 요청 분석, 후보 탐색, 유사 아티스트 확장, 실제 곡 검증, 표지 확인, 플레이리스트 구성, 설명 작성 단계만 표시하며 내부 추론은 노출하지 않는다. 메인은 조건 선택과 추천 카드, `/library`는 저장 목록, `/library/[id]`는 상세 화면을 제공한다. 모든 로딩·빈 결과·오류 상태는 화면에 명시적으로 남긴다.

## 오류 정책

- NVIDIA 또는 MCP 실패: 한국어 오류 이벤트를 전송하고 기존 UI 상태 유지
- Cover Art 실패: fallback 이미지로 계속 진행
- 일부 Provider 실패: 확보한 검증 후보로 계속 진행하고 제한 사항 표시
- 요청 수보다 검증 곡이 적음: 실제 곡만 반환하고 부족 수를 알림
- Tool 인자 오류 또는 실행 예외: Observation으로 Qwen에 한 번 이상 수정 기회 제공
- 동일 Tool과 동일 인자 반복: 차단하고 오류 Observation 반환
- 8회 한도 초과: 안전한 오류로 종료

API 키 값은 로그나 오류에 포함하지 않는다.

## 구현 및 검증 순서

1. 환경변수와 공통 데이터 계약
2. FastMCP 모델, Provider, 추천 로직과 SQLite Tool
3. Python 단위 테스트
4. Next.js MCP Client, NVIDIA Client와 Agent Loop
5. NDJSON 이벤트와 Agent 테스트
6. 메인, 보관함, 상세 UI
7. 저장·조회·삭제 API 연결
8. Python 테스트, TypeScript 타입 검사, lint와 production build
9. FastMCP와 Next.js 서버 기동
10. 실제 키가 제공된 경우 대표 요청과 저장·조회·삭제 라이브 검증
11. README, 아키텍처, 테스트 사례와 시연 문서

자동화된 mock 검증과 실제 NVIDIA·Last.fm·MusicBrainz 검증 결과를 분리해 보고한다.

## 주요 위험

- MusicBrainz 속도 제한과 외부 API 지연
- Python 3.13과 선택 FastMCP 버전의 호환성
- Qwen이 Tool을 호출하지 않거나 같은 호출을 반복하는 상황
- 특정 조건에서 검증 후보가 요청 곡 수보다 적은 상황
- 실제 API 키가 없어 라이브 시연을 완료하지 못하는 상황

각 위험은 호출 제한·캐시, 설치 직후 최소 기동 확인, 반복 방지와 강제 결과 검증, 부분 결과 정책, 검증 결과의 명확한 구분으로 대응한다.
