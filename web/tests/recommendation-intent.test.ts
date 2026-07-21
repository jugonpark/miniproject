import { describe, expect, it } from "vitest";
import { fallbackIntent, mergeIntent, recommendationIntentSchema } from "@/lib/agent/recommendation-intent";

const request = {
  conditions: ["무언가 꽉 막힌 느낌", "답답함", "차분하게 집중", "공부"],
  region: "domestic" as const,
  free_text: "국내 인디 음악으로 추천해 줘. 일본 노래는 빼고, 보컬이 너무 튀지 않았으면 좋겠어. 너무 유명한 곡보다는 새로운 곡이 좋아.",
  familiar_artists: [],
  count: 10 as const,
};

describe("recommendation intent", () => {
  it("preserves UI values and converts explicit chat constraints", () => {
    const intent = fallbackIntent(request);
    expect(intent.rawRequest).toBe(request.free_text);
    expect(intent.hardConstraints.region).toBe("domestic");
    expect(intent.hardConstraints.allowedCountries).toContain("KR");
    expect(intent.hardConstraints.excludedCountries).toContain("JP");
    expect(intent.hardConstraints.requiredScenes).toContain("KOREAN_INDIE");
    expect(intent.preferences.activities).toContain("STUDY");
    expect(intent.preferences.vocalAmount).toBe("low");
    expect(intent.preferences.popularity).toBe("hidden_gems");
    expect(intent.preferences.familiarity).toBe("discovery");
  });

  it("does not invent constraints absent from the request", () => {
    const intent = fallbackIntent({ ...request, region: "mixed", free_text: "차분한 공부 음악" });
    expect(intent.hardConstraints.allowedCountries).toEqual([]);
    expect(intent.hardConstraints.excludedCountries).toEqual([]);
    expect(intent.hardConstraints.excludedArtists).toEqual([]);
    expect(intent.preferences.vocalAmount).toBeUndefined();
  });

  it("rejects unsupported structured values", () => {
    expect(() => recommendationIntentSchema.parse({ rawRequest: "x", hardConstraints: { region: "mars" } })).toThrow();
  });

  it("lets explicit chat permission override a domestic UI default", () => {
    const intent = fallbackIntent({ ...request, free_text: "일본 음악도 괜찮아" });
    expect(intent.hardConstraints.region).toBe("mixed");
    expect(intent.hardConstraints.allowedCountries).toEqual([]);
    expect(intent.hardConstraints.excludedCountries).toEqual([]);
  });

  it("does not let AI omit explicit exclusions and preferences", () => {
    const explicit = fallbackIntent(request);
    const ai = recommendationIntentSchema.parse({ ...explicit, hardConstraints: { ...explicit.hardConstraints, excludedCountries: [] }, preferences: { ...explicit.preferences, vocalAmount: undefined, popularity: "balanced" } });
    const merged = mergeIntent(ai, explicit);
    expect(merged.hardConstraints.excludedCountries).toEqual(["JP"]);
    expect(merged.preferences.vocalAmount).toBe("low");
    expect(merged.preferences.popularity).toBe("hidden_gems");
  });

  it("lets explicit chat activity override the unchanged UI context", () => {
    const focus = fallbackIntent({ ...request, free_text: "focus music" });
    const workout = fallbackIntent({ ...request, free_text: "workout with strong rhythm" });
    expect(focus.preferences.activities).toEqual(["STUDY"]);
    expect(workout.preferences.activities).toEqual(["WORKOUT"]);
  });

  it("keeps domestic energetic requests country-only when indie is not requested", () => {
    const intent = fallbackIntent({
      ...request,
      conditions: ["에너지가 넘쳐요", "들뜸", "다시 힘을 얻고 싶어요", "확실하게 기분 전환", "감정 강도 4"],
      free_text: null,
    });
    expect(intent.hardConstraints.allowedCountries).toEqual(["KR"]);
    expect(intent.hardConstraints.requiredScenes).toEqual([]);
    expect(intent.preferences.genres).toEqual([]);
    expect(intent.preferences.energy).toBe(0.85);
  });

  it("separates domestic indie, domestic hip-hop, and global indie", () => {
    const domesticIndie = fallbackIntent({ ...request, free_text: "국내 인디 신나는 곡" });
    const domesticHipHop = fallbackIntent({ ...request, free_text: "국내 힙합으로 신나는 곡" });
    const globalIndie = fallbackIntent({ ...request, region: "global", free_text: "해외 인디" });
    expect(domesticIndie.hardConstraints.requiredScenes).toEqual(["KOREAN_INDIE"]);
    expect(domesticIndie.preferences.genres).toEqual(["indie"]);
    expect(domesticHipHop.hardConstraints.requiredScenes).toEqual([]);
    expect(domesticHipHop.preferences.genres).toEqual(["hip-hop"]);
    expect(globalIndie.hardConstraints.allowedCountries).toEqual([]);
    expect(globalIndie.hardConstraints.requiredScenes).toEqual([]);
    expect(globalIndie.preferences.genres).toEqual(["indie"]);
  });
});
