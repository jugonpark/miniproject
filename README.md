# MOODWAVE

상황·분위기 조건을 NVIDIA Qwen이 해석하고 FastMCP Tool로 Last.fm 후보와 MusicBrainz 곡을 검증해 추천하는 Next.js 앱입니다. 음원은 재생하지 않고 YouTube Music 검색 링크만 제공합니다. 추천은 자동 저장되지 않으며 저장 버튼을 눌렀을 때만 Neon Postgres에 저장됩니다.

## 구성

```text
Next.js (Vercel/v0) → NVIDIA Qwen Agent Loop → FastMCP (Prefect Horizon)
                                              ├─ Last.fm / MusicBrainz / Cover Art Archive
                                              └─ Neon Postgres
```

MCP Tool은 `discover_music_candidates`, `expand_similar_artists`, `verify_music_tracks`, `compose_playlist`, `save_playlist`, `list_playlists`, `get_playlist`, `delete_playlist` 8개입니다. Agent Loop는 최대 8회이며 동일 Tool·인자 반복을 차단합니다. UI에는 내부 추론이 아니라 Tool 진행 단계와 최종 설명만 NDJSON으로 전송합니다.

## 환경변수

실제 키는 Git에 커밋하지 않습니다. `mcp-server/.env.example`을 `.env`로, `web/.env.local.example`을 `.env.local`로 복사한 뒤 값을 넣습니다.

- FastMCP/Horizon: `LASTFM_API_KEY`, `MUSICBRAINZ_USER_AGENT`, `MUSICBRAINZ_CONTACT`, `DATABASE_URL`
- Next.js/Vercel: `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL`, `MCP_SERVER_URL`

`DATABASE_URL`에는 Neon의 pooled PostgreSQL URL과 `sslmode=require`를 사용합니다. Vercel 환경변수는 Development, Preview, Production 각각에 설정하고 값을 바꾼 뒤 재배포합니다.

## 로컬 실행

```powershell
cd mcp-server
python -m pip install -e ".[test]"
fastmcp run fastmcp.json --skip-env

cd ../web
npm.cmd install
npm.cmd run dev
```

기본 주소는 FastMCP `http://127.0.0.1:8000/mcp`, Next.js `http://localhost:3000`입니다.

## 테스트

```powershell
cd mcp-server
python -m pytest -q --basetemp=.pytest-run

cd ../web
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
```

## 배포

1. Neon에서 프로젝트를 만들고 pooled `DATABASE_URL`을 복사합니다.
2. Prefect Horizon에서 Dependencies를 `mcp-server/pyproject.toml`, Entrypoint를 `mcp-server/server.py:mcp`로 지정합니다. 네 가지 FastMCP 환경변수를 설정합니다.
3. Horizon의 공개 HTTPS `/mcp` URL을 Vercel의 `MCP_SERVER_URL`로 설정합니다.
4. Vercel에서 Root Directory를 `web`으로 지정하고 NVIDIA 환경변수를 설정해 배포합니다. 같은 계정의 v0 프로젝트에 연결하면 v0의 Publish 기능으로 동일 Vercel 프로젝트를 갱신할 수 있습니다.

## 시연

활동 `공부`, 분위기 `차분함`·`몽환적`, 보컬 `보컬 적음`, 범위 `해외`, 10곡을 선택하고 “새벽에 코딩하면서 오래 들어도 피곤하지 않은 음악”을 요청합니다. 생성 후 저장 버튼을 눌러 보관함 상세와 삭제까지 확인합니다.

## 제한사항과 저작권

외부 API의 속도 제한과 데이터 누락 때문에 요청 수보다 적은 곡이 반환될 수 있습니다. 검증되지 않은 곡을 채워 넣지 않습니다. Cover Art가 없으면 fallback 이미지를 사용합니다. 앱은 음원이나 가사를 저장·전송하지 않으며 저작권과 서비스 약관을 고려해 YouTube Music 검색 URL만 제공합니다.
