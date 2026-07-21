# MOODWAVE

사용자의 감정, 활동, 음악 목적과 추가 요청을 바탕으로 실제 곡을 검증해 플레이리스트를 만드는 AI 음악 큐레이터입니다. NVIDIA Qwen이 Agent Loop를 수행하고, FastMCP 서버가 Last.fm·MusicBrainz·Cover Art Archive와 데이터베이스 작업을 담당합니다. 음원은 직접 재생하지 않고 YouTube Music 검색 링크를 제공합니다.

## 저장소와 서비스

- GitHub: https://github.com/jugonpark/miniproject
- MCP 서버: https://premier-coral-pony.fastmcp.app/mcp
- 웹 배포: Vercel 배포 주소 제출 시 함께 기재

## 주요 기능

- 감정 인터뷰와 추가 채팅을 반영한 음악 추천
- NVIDIA Qwen의 판단 → MCP Tool → Observation → 재판단 Agent Loop
- Last.fm 후보 탐색 및 MusicBrainz 실제 곡 검증
- 앨범 이미지와 YouTube Music 검색 링크 제공
- 추천 진행 상태와 최종 설명 스트리밍
- 플레이리스트 수동 저장, 목록·상세 조회 및 삭제

## 구조

```text
사용자 → Next.js/Vercel → NVIDIA Qwen → FastMCP/Horizon
                                         ├─ Last.fm
                                         ├─ MusicBrainz
                                         ├─ Cover Art Archive
                                         └─ Neon PostgreSQL
```

MCP Tool은 `discover_music_candidates`, `expand_similar_artists`, `verify_music_tracks`, `compose_playlist`, `save_playlist`, `list_playlists`, `get_playlist`, `delete_playlist`입니다.

## 로컬 실행

### 1. 저장소 내려받기

```bash
git clone https://github.com/jugonpark/miniproject.git
cd miniproject
```

### 2. FastMCP 서버

Python 3.13 이상이 필요합니다.

```bash
cd mcp-server
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m moodwave_mcp.server
```

macOS/Linux:

```bash
. .venv/bin/activate
pip install -e .
cp .env.example .env
python -m moodwave_mcp.server
```

로컬 MCP 주소는 `http://127.0.0.1:8000/mcp`입니다.

### 3. Next.js 웹

새 터미널에서 실행합니다.

```bash
cd miniproject/web
npm install
```

`web/.env.local.example`을 `web/.env.local`로 복사하고 API 키를 입력한 후:

```bash
npm run dev
```

브라우저에서 http://localhost:3000 을 엽니다.

로컬 MCP 서버를 사용할 때는 `MCP_SERVER_URL=http://127.0.0.1:8000/mcp`로 설정합니다.

## 환경변수

### Next.js (`web/.env.local`)

```dotenv
NVIDIA_API_KEY=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=qwen/qwen3-next-80b-a3b-instruct
MCP_SERVER_URL=https://premier-coral-pony.fastmcp.app/mcp
```

### FastMCP (`mcp-server/.env`)

```dotenv
LASTFM_API_KEY=
MUSICBRAINZ_USER_AGENT=MOODWAVE/0.1
MUSICBRAINZ_CONTACT=
DATABASE_URL=
```

실제 API 키와 `DATABASE_URL`은 Git에 커밋하지 않습니다. `.env`, `.env.local`, `node_modules`, `.next`는 `.gitignore`에서 제외됩니다.

## 배포

### FastMCP / Prefect Horizon

- Entrypoint: `mcp-server/server.py:mcp`
- Dependencies: `mcp-server/pyproject.toml`
- 환경변수: `LASTFM_API_KEY`, `MUSICBRAINZ_USER_AGENT`, `MUSICBRAINZ_CONTACT`, `DATABASE_URL`

### Next.js / Vercel

- Root Directory: `web`
- 환경변수: `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`, `MCP_SERVER_URL`
- `MCP_SERVER_URL`에는 배포된 HTTPS MCP 주소를 입력합니다.

### Database / Neon

Neon의 pooled PostgreSQL 연결 문자열을 FastMCP 서버의 `DATABASE_URL`에 설정합니다. 연결 문자열은 공개 저장소에 올리지 않습니다.

## 테스트 명령

```powershell
cd mcp-server
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests

cd ..\web
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
```

## 시연 예시

현재 상태와 세부 감정, 음악 목적, 강도와 범위를 선택한 뒤 추가 요청을 입력합니다.

> 새벽에 코딩하면서 오래 들어도 피곤하지 않은 음악을 추천해줘. 너무 유명한 곡만 나오지는 않았으면 좋겠어.

추천 결과는 자동 저장되지 않습니다. `플레이리스트 저장` 버튼을 눌러야 보관함에 저장됩니다.

## 알려진 제한사항

- NVIDIA와 Last.fm API 키가 없으면 추천 전체 흐름을 실행할 수 없습니다.
- 외부 API 지연이나 호출 제한으로 요청한 곡 수보다 적게 반환될 수 있습니다.
- 확인되지 않은 곡을 임의로 추가하지 않습니다.
- 앨범 표지가 없거나 조회에 실패하면 기본 이미지를 표시합니다.
- YouTube Music 영상 ID를 직접 조회하지 않고 곡명과 아티스트명의 검색 URL을 생성합니다.

## 저작권

MOODWAVE는 음원이나 가사 전문을 저장·배포·재생하지 않습니다. 곡 정보와 외부 검색 링크만 제공하며, 실제 음악 이용은 연결된 서비스의 정책을 따릅니다.

## 제출 형식

```text
GitHub 저장소:
https://github.com/jugonpark/miniproject

배포 사이트:
Vercel 배포 주소

MCP 서버:
https://premier-coral-pony.fastmcp.app/mcp

실행 방법:
저장소 README 참고
```

저장소가 비공개라면 평가자 GitHub 계정을 collaborator로 추가해야 합니다.
