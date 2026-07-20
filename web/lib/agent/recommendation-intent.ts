import { z } from "zod";
import type { MusicRequest } from "@/lib/schemas/music";

const strings = z.array(z.string()).default([]);
export const recommendationIntentSchema = z.object({
  rawRequest: z.string().default(""),
  hardConstraints: z.object({
    region: z.enum(["domestic", "global", "mixed"]).optional(),
    allowedCountries: strings,
    excludedCountries: strings,
    requiredScenes: strings,
    excludedScenes: strings,
    includedGenres: strings,
    excludedGenres: strings,
    includedArtists: strings,
    excludedArtists: strings,
    allowedLanguages: strings,
    excludedLanguages: strings,
    instrumentalOnly: z.boolean().default(false),
    vocalRequired: z.boolean().default(false),
    excludeLiveRemix: z.boolean().default(true),
  }),
  preferences: z.object({
    moods: strings,
    activities: strings,
    genres: strings,
    vocalAmount: z.enum(["none", "low", "normal", "prominent"]).optional(),
    energy: z.number().min(0).max(1).optional(),
    tempo: z.enum(["slow", "medium", "fast"]).optional(),
    familiarity: z.enum(["familiar", "balanced", "discovery"]).default("balanced"),
    popularity: z.enum(["popular", "balanced", "hidden_gems"]).default("balanced"),
    lyricPreference: z.enum(["lyrics", "low_lyrics", "instrumental", "any"]).optional(),
    era: z.object({ from: z.number().int().optional(), to: z.number().int().optional() }).optional(),
  }),
  emotionalArc: z.object({ start: z.string(), middle: z.string(), end: z.string() }),
  priorityOrder: strings,
});

export type RecommendationIntent = z.infer<typeof recommendationIntentSchema>;

export function mergeIntent(ai: RecommendationIntent, fallback: RecommendationIntent): RecommendationIntent {
  const explicit = fallback.hardConstraints;
  return recommendationIntentSchema.parse({
    ...ai,
    rawRequest: fallback.rawRequest,
    hardConstraints: { ...ai.hardConstraints, region: explicit.region, allowedCountries: explicit.allowedCountries.length ? explicit.allowedCountries : ai.hardConstraints.allowedCountries, excludedCountries: explicit.excludedCountries.length ? explicit.excludedCountries : ai.hardConstraints.excludedCountries, requiredScenes: explicit.requiredScenes },
    preferences: { ...ai.preferences, moods: [...new Set([...fallback.preferences.moods, ...ai.preferences.moods])], activities: fallback.preferences.activities.length ? fallback.preferences.activities : ai.preferences.activities, genres: fallback.preferences.genres, ...(fallback.preferences.energy !== undefined ? { energy: fallback.preferences.energy } : {}), ...(fallback.preferences.vocalAmount ? { vocalAmount: fallback.preferences.vocalAmount } : {}), ...(fallback.preferences.popularity === "hidden_gems" ? { popularity: "hidden_gems", familiarity: "discovery" } : {}) },
  });
}

export function fallbackIntent(request: MusicRequest): RecommendationIntent {
  const text = `${request.conditions.join(" ")} ${request.free_text ?? ""}`.toLowerCase();
  const allowJapan = /일본.{0,8}(괜찮|포함|좋아)|japan.{0,8}(ok|include)/i.test(text);
  const domestic = !allowJapan && (request.region === "domestic" || /국내|한국|korean|k-indie/.test(text));
  const indie = /인디|indie/.test(text);
  const koreanIndie = domestic && indie;
  const hipHop = /힙합|hip[ -]?hop/.test(text);
  const study = /공부|집중|study|focus/.test(text);
  const explicitWorkout = /운동|workout|strong rhythm|강한\s*리듬/.test((request.free_text ?? "").toLowerCase());
  const revival = /다시 힘|기분 전환|활력|revival/.test(text);
  const highEnergy = /에너지가 넘쳐|들뜸|확실하게 기분 전환|신나는|energetic|upbeat/.test(text);
  const lowVocal = /보컬.{0,8}(적|튀지|낮)|가사.{0,8}(적|많.{0,4}싫)|low vocal/.test(text);
  const hidden = /유명.{0,8}(말고|않|빼)|숨은|새로운 곡|hidden/.test(text);
  return recommendationIntentSchema.parse({
    rawRequest: request.free_text ?? "",
    hardConstraints: {
      region: allowJapan ? "mixed" : request.region,
      allowedCountries: domestic ? ["KR"] : [],
      excludedCountries: !allowJapan && /일본.{0,8}(제외|빼|싫)|일본 노래는 빼|exclude.{0,5}japan/i.test(text) ? ["JP"] : [],
      requiredScenes: koreanIndie ? ["KOREAN_INDIE"] : [],
    },
    preferences: {
      moods: [...request.conditions, ...(highEnergy ? ["energetic", "upbeat", "exciting"] : [])],
      activities: explicitWorkout ? ["WORKOUT"] : revival ? ["REVIVAL"] : study ? ["STUDY"] : [],
      genres: hipHop ? ["hip-hop"] : indie ? ["indie"] : [],
      ...(highEnergy ? { energy: 0.85 } : {}),
      ...(lowVocal ? { vocalAmount: "low", lyricPreference: "low_lyrics" } : {}),
      familiarity: hidden ? "discovery" : "balanced",
      popularity: hidden ? "hidden_gems" : "balanced",
    },
    emotionalArc: {
      start: request.conditions[1] ?? request.conditions[0] ?? "current",
      middle: "grounding",
      end: explicitWorkout ? "energized" : study ? "focus" : request.conditions[2] ?? "balanced",
    },
    priorityOrder: ["explicit_chat", "hard_constraints", "emotion", "preferences", "defaults"],
  });
}
