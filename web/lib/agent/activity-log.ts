type Event = Record<string, unknown> & { type: string };
export type ActivityEntry = { state: "started" | "completed" | "failed"; message: string };

const started: Record<string, string> = {
  discover_music_candidates: "분위기에 맞는 음악 세계를 살펴보는 중",
  expand_similar_artists: "새로운 음악의 범위를 넓히는 중",
  verify_music_tracks: "아티스트와 실제 곡 정보를 확인하는 중",
  compose_playlist: "감정 흐름에 맞게 곡 순서를 정리하는 중",
};
const completed: Record<string, string> = {
  discover_music_candidates: "관련 음악 후보를 찾았어요",
  expand_similar_artists: "새로운 음악 후보를 더 찾았어요",
  verify_music_tracks: "곡 정보 확인을 마쳤어요",
  compose_playlist: "플레이리스트 구성을 마쳤어요",
};

export function activityEntry(event: Event): ActivityEntry | null {
  if (event.type === "activity" && typeof event.message === "string") {
    const generic = event.service === "nvidia" ? (event.state === "completed" ? "추천 방향을 정리했어요" : "마음의 흐름을 음악 언어로 바꾸는 중") : event.message;
    return { state: event.state === "completed" ? "completed" : "started", message: generic };
  }
  if (event.type === "tool" && typeof event.name === "string") return { state: "started", message: started[event.name] ?? "추천 단계를 시작했어요" };
  if (event.type === "tool_result" && typeof event.name === "string") return event.state === "failed" ? { state: "failed", message: "음악 확인 단계에서 문제가 생겼어요" } : { state: "completed", message: completed[event.name] ?? "추천 단계를 마쳤어요" };
  if (event.type === "error" && typeof event.message === "string") return { state: "failed", message: event.message };
  if (event.type === "done") return event.ok === false ? { state: "failed", message: "요청을 완료하지 못했어요" } : { state: "completed", message: "요청 처리가 끝났어요" };
  return null;
}
