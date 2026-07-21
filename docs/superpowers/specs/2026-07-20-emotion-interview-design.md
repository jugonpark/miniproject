# MOODWAVE 감정 인터뷰 및 음악 검증 개선 설계

## 범위

기존 한 화면 조건 나열을 한 질문씩 진행하는 감정 인터뷰로 바꾼다. 웹검색 API는 추가하지 않으며, 음악 사실 정보는 Last.fm, iTunes, MusicBrainz 결과만 사용한다.

## 사용자 흐름

`INTRO → BROAD_STATE → EMOTION_DETAIL → INTENSITY → REGULATION_GOAL → 조건부 질문 → FLOW_PREVIEW → GENERATING → RESULT` 순서다. 목적이 `FOCUS`, `RELAXATION`, `REVIVAL`, `DIVERSION`일 때만 각각 필요한 추가 질문을 표시한다. 뒤로 이동하면 기존 선택을 복원하고, 앞 답을 바꾸면 더 이상 유효하지 않은 조건부 값만 지운다.

## 구현 구조

- `web/lib/emotion/flow.ts`: 상태 타입, 선택지, 경로 계산, 기존 API 요청 변환을 소유한다.
- `web/components/EmotionInterview.tsx`: 한 질문 렌더링, 단계 히스토리, 전환 잠금과 포커스를 담당한다.
- `web/app/page.tsx`: 추천 스트림과 결과 저장은 유지하고 인터뷰가 만든 요청만 받는다.
- CSS transition만 사용하며 reduced-motion을 지원한다.

## 음악 검증

Last.fm `artist.gettoptracks`의 원본 artist/title을 유지한다. 정규화는 NFKC, 공백, 대소문자, feat 표기를 처리하되 live/remix/instrumental/remaster/OST 등 버전 표시는 보존한다. iTunes와 MusicBrainz는 첫 결과가 아니라 제목·아티스트·버전 점수로 선택하고, 검증된 곡만 구성 도구에 전달한다.

## 오류와 검증

최종 확인 전에는 API를 호출하지 않는다. 로딩 중 중복 제출을 막고 오류가 나도 인터뷰 선택을 유지한다. 상태 전이·요청 변환·후보 검증 단위 테스트와 전체 Python/TypeScript 테스트, 타입 검사, 빌드를 실행한다.
