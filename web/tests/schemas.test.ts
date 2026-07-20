import { describe, expect, test } from "vitest";

import { musicRequestSchema } from "@/lib/schemas/music";
import { playlistDraftSchema, savedPlaylistSchema } from "@/lib/schemas/playlist";

const request = { conditions: ["calm"] };
const track = {
  position: 1,
  recording_id: "recording-1",
  title: "Song",
  artist: "Artist",
  artist_id: null,
  release_id: null,
  release_title: null,
  cover_url: null,
  youtube_music_url: "https://music.youtube.com/search?q=Song",
  familiar: false,
};

describe("musicRequestSchema", () => {
  test("applies the Python model defaults", () => {
    expect(musicRequestSchema.parse(request)).toEqual({
      conditions: ["calm"], region: "mixed", free_text: null,
      familiar_artists: [], count: 10,
    });
  });

  test.each([5, 10, 15])("accepts count %i", (count) => {
    expect(musicRequestSchema.parse({ ...request, count }).count).toBe(count);
  });

  test("rejects unsupported counts", () => {
    expect(() => musicRequestSchema.parse({ ...request, count: 7 })).toThrow();
  });

  test("rejects an empty request", () => {
    expect(() => musicRequestSchema.parse({ conditions: [], free_text: "   " })).toThrow();
  });
});

describe("playlist schemas", () => {
  test("rejects zero-based track positions", () => {
    expect(() => playlistDraftSchema.parse({
      title: "Focus", request, tracks: [{ ...track, position: 0 }],
    })).toThrow();
  });

  test("parses the complete PlaylistDraft contract", () => {
    expect(playlistDraftSchema.parse({ title: "Focus", request, tracks: [track] })).toEqual({
      title: "Focus", description: "",
      request: {
        conditions: ["calm"], region: "mixed", free_text: null,
        familiar_artists: [], count: 10,
      },
      tracks: [track],
    });
  });

  test("parses the complete SavedPlaylist contract", () => {
    const createdAt = "2026-07-20T12:00:00+00:00";
    expect(savedPlaylistSchema.parse({
      id: 1, created_at: createdAt, title: "Focus", description: "For work",
      request, tracks: [track],
    })).toMatchObject({ id: 1, created_at: createdAt, tracks: [track] });
  });
});
