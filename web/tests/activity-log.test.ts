import { describe, expect, it } from "vitest";
import { activityEntry } from "@/lib/agent/activity-log";

describe("activityEntry", () => {
  it("turns agent events into user-safe logs without API names", () => {
    expect(activityEntry({ type: "activity", service: "nvidia", state: "completed", message: "raw" })).toEqual({ state: "completed", message: "추천 방향을 정리했어요" });
    expect(activityEntry({ type: "tool", name: "discover_music_candidates", state: "started" })).toEqual({ state: "started", message: "분위기에 맞는 음악 세계를 살펴보는 중" });
    expect(activityEntry({ type: "tool_result", name: "verify_music_tracks", state: "completed" })).toEqual({ state: "completed", message: "곡 정보 확인을 마쳤어요" });
    expect(activityEntry({ type: "text_delta", delta: "hidden" })).toBeNull();
    expect(activityEntry({ type: "done", ok: false })).toEqual({ state: "failed", message: "요청을 완료하지 못했어요" });
  });
});
