import { describe, expect, it } from "vitest";
import { clearDependentAnswers, pathFor, toMusicRequest, type EmotionFlowState } from "@/lib/emotion/flow";

const base: EmotionFlowState = { currentStep: "FLOW_PREVIEW", broadState: "UNSETTLED", emotion: "ANXIETY", emotionLabel: "막연한 불안", intensity: 4, regulationGoal: "RELAXATION", lyricPreference: "LOW" };

describe("emotion flow", () => {
  it("adds only the question required by the regulation goal", () => {
    expect(pathFor({ ...base, regulationGoal: "FOCUS" })).toContain("CONTEXT");
    expect(pathFor({ ...base, regulationGoal: "RELAXATION" })).toContain("LYRIC_PREFERENCE");
    expect(pathFor({ ...base, regulationGoal: "REVIVAL" })).toContain("REVIVAL_LEVEL");
    expect(pathFor({ ...base, regulationGoal: "SOLACE" })).not.toContain("CONTEXT");
  });
  it("clears answers that no longer belong to the selected goal", () => {
    expect(clearDependentAnswers({ ...base, context: "CODING", lyricPreference: "LOW" }, "REVIVAL")).toMatchObject({ regulationGoal: "REVIVAL", context: undefined, lyricPreference: undefined });
  });
  it("maps the interview to the existing music request contract", () => {
    expect(toMusicRequest(base)).toEqual({ conditions: ["흔들리고 있어요", "막연한 불안", "조금 편안해지고 싶어요", "가사가 적은 음악", "감정 강도 4"], region: "mixed", free_text: expect.stringContaining("막연한 불안"), familiar_artists: [], count: 10 });
  });
  it("passes the selected region and extra request to the LLM", () => {
    expect(toMusicRequest({ ...base, region: "global", extraRequest: "덜 유명한 곡 위주로" })).toMatchObject({ region: "global", free_text: expect.stringContaining("덜 유명한 곡 위주로") });
  });
});
