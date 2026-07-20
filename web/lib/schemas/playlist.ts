import { z } from "zod";

import { musicRequestSchema } from "./music";

const httpUrlSchema = z.url().refine((value) => {
  const protocol = new URL(value).protocol;
  return protocol === "http:" || protocol === "https:";
});

export const recommendedTrackSchema = z.object({
  position: z.number().int().min(1),
  recording_id: z.string().min(1),
  title: z.string().min(1),
  artist: z.string().min(1),
  artist_id: z.string().nullable().default(null),
  release_id: z.string().nullable().default(null),
  release_title: z.string().nullable().default(null),
  release_year: z.number().int().nullable().optional(),
  cover_url: httpUrlSchema.nullable().default(null),
  tags: z.array(z.string()).optional(),
  discovery_type: z.enum(["familiar", "discovery"]).optional(),
  recommendation_reason: z.string().optional(),
  youtube_music_url: httpUrlSchema,
  familiar: z.boolean(),
});

export const playlistDraftSchema = z.object({
  title: z.string().min(1),
  description: z.string().default(""),
  request: musicRequestSchema,
  tracks: z.array(recommendedTrackSchema).min(1),
});

export const savedPlaylistSchema = playlistDraftSchema.extend({
  id: z.number().int().positive(),
  created_at: z.iso.datetime({ offset: true }),
});

export type RecommendedTrack = z.infer<typeof recommendedTrackSchema>;
export type PlaylistDraft = z.infer<typeof playlistDraftSchema>;
export type SavedPlaylist = z.infer<typeof savedPlaylistSchema>;
