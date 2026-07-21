import { describe, expect, it } from "vitest";
import { safeFinalNarrative } from "@/lib/agent/final-narrative";
import { playlistDraftSchema } from "@/lib/schemas/playlist";

const playlist = playlistDraftSchema.parse({
  title: "x",
  request: { conditions: ["focus"], region: "domestic", free_text: null, count: 5, familiar_artists: [] },
  recommendation_status: "PARTIAL" as const,
  tracks: [{ position: 1, recording_id: "one", candidate_id: "candidate:one", title: "Allowed", artist: "Korean", tags: [], discovery_type: "discovery" as const, youtube_music_url: "https://music.youtube.com/search?q=x", familiar: false }],
});

describe("safe final narrative", () => {
  it("replaces wrong counts and unselected verified names", () => {
    expect(safeFinalNarrative("총 7곡이며 Foreign Song도 포함합니다.", playlist, [{ artist_name: "Foreign", track_title: "Song" }])).toBe("필수 조건을 지키며 확인된 1곡만 담았어요. Korean의 Allowed");
  });

  it("keeps a grounded narrative", () => {
    expect(safeFinalNarrative("검증된 1곡을 담았습니다.", playlist, [])).toBe("검증된 1곡을 담았습니다.");
  });
});
