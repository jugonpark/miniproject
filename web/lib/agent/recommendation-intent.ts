import { z } from "zod";
import type { MusicRequest } from "@/lib/schemas/music";

const strings = z.array(z.string()).default([]);
export const recommendationIntentSchema = z.object({
  rawRequest: z.string().default(""),
  rawRequests: strings,
  currentState: z.object({ broadState: z.string().optional(), emotionDetail: z.string().optional(), energy: z.enum(["low", "medium", "high", "unknown"]).optional(), valence: z.enum(["negative", "neutral", "positive", "mixed"]).optional() }).default({}),
  targetState: z.object({ goal: z.string().optional(), energy: z.enum(["low", "medium", "high", "unknown"]).optional(), changeIntensity: z.number().min(1).max(5).optional() }).default({}),
  activity: z.string().optional(),
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
    genreDiversity: z.enum(["low", "balanced", "high"]).default("balanced"),
    mainstreamRatio: z.number().min(0).max(1).optional(),
    lyricPreference: z.enum(["lyrics", "low_lyrics", "instrumental", "any"]).optional(),
    era: z.object({ from: z.number().int().optional(), to: z.number().int().optional() }).optional(),
  }),
  emotionalArc: z.object({ start: z.string(), middle: z.string(), end: z.string() }),
  priorityOrder: strings,
  updatedAt: z.string().default(""),
});

export type RecommendationIntent = z.infer<typeof recommendationIntentSchema>;

export const recommendationIntentPatchSchema = z.object({
  operation: z.enum(["MERGE", "REPLACE", "RESET"]).default("MERGE"),
  add: z.record(z.string(), strings).optional(), remove: z.record(z.string(), strings).optional(),
  set: z.object({ region: z.enum(["domestic", "global", "mixed"]).optional(), goal: z.string().optional(), activity: z.string().optional(), intensity: z.number().min(1).max(5).optional(), vocalAmount: z.enum(["none", "low", "normal", "prominent"]).optional(), popularity: z.enum(["popular", "balanced", "hidden_gems"]).optional(), familiarity: z.enum(["familiar", "balanced", "discovery"]).optional(), genreDiversity: z.enum(["low", "balanced", "high"]).optional(), mainstreamRatio: z.number().min(0).max(1).optional() }).optional(),
  userMeaningSummary: z.string().default("요청을 반영했어요."),
});
export type RecommendationIntentPatch = z.infer<typeof recommendationIntentPatchSchema>;
export type RevisionScope = "ARRANGEMENT_ONLY" | "RESCORE" | "REDISCOVER";
export type RecommendationChatMessage = { id: string; role: "user" | "assistant"; content: string; createdAt: string };
export type AppliedIntentChange = { messageId: string; summary: string; addedConstraints: string[]; removedConstraints: string[]; changedPreferences: string[]; createdAt: string };
export type RecommendationSession = { sessionId: string; messages: RecommendationChatMessage[]; uiSelections: Record<string, unknown>; currentIntent: RecommendationIntent; previousIntent?: RecommendationIntent; currentPlaylistCandidateIds: string[]; revisionCount: number; appliedIntentChanges: AppliedIntentChange[] };

const constraintKeys = ["allowedCountries", "excludedCountries", "includedArtists", "excludedArtists", "includedGenres", "excludedGenres", "requiredScenes", "excludedScenes"] as const;
export function applyIntentPatch(current: RecommendationIntent, patch: RecommendationIntentPatch, message: string): RecommendationIntent {
  if (patch.operation === "RESET") return recommendationIntentSchema.parse({ ...fallbackIntent({ conditions: [], region: current.hardConstraints.region ?? "mixed", free_text: message, familiar_artists: [], count: 10 }), rawRequests: [message], updatedAt: new Date().toISOString() });
  const base = patch.operation === "REPLACE" ? fallbackIntent({ conditions: [], region: patch.set?.region ?? "mixed", free_text: message, familiar_artists: [], count: 10 }) : current;
  const hard = { ...base.hardConstraints } as RecommendationIntent["hardConstraints"];
  for (const key of constraintKeys) { const values = new Set(hard[key]); for (const value of patch.remove?.[key] ?? []) values.delete(value); for (const value of patch.add?.[key] ?? []) values.add(value); hard[key] = [...values]; }
  if (patch.set?.region) { hard.region = patch.set.region; hard.allowedCountries = patch.set.region === "domestic" ? ["KR"] : []; }
  const preferences = { ...base.preferences, ...(patch.set?.vocalAmount ? { vocalAmount: patch.set.vocalAmount } : {}), ...(patch.set?.popularity ? { popularity: patch.set.popularity } : {}), ...(patch.set?.familiarity ? { familiarity: patch.set.familiarity } : {}), ...(patch.set?.genreDiversity ? { genreDiversity: patch.set.genreDiversity } : {}), ...(patch.set?.mainstreamRatio !== undefined ? { mainstreamRatio: patch.set.mainstreamRatio } : {}) };
  return recommendationIntentSchema.parse({ ...base, rawRequest: message, rawRequests: [...base.rawRequests, message], hardConstraints: hard, preferences, targetState: { ...base.targetState, ...(patch.set?.goal ? { goal: patch.set.goal } : {}), ...(patch.set?.intensity ? { changeIntensity: patch.set.intensity } : {}) }, activity: patch.set?.activity ?? base.activity, updatedAt: new Date().toISOString() });
}

export function inferIntentPatch(message: string): RecommendationIntentPatch {
  const text = message.trim(); const reset = /처음부터|초기화|reset/i.test(text);
  const excludedArtists = [...text.matchAll(/([가-힣A-Za-z0-9 .!]+?)(?:은|는)?\s*(?:빼|제외)/g)].map((match) => match[1].trim()).filter(Boolean);
  return recommendationIntentPatchSchema.parse({ operation: reset ? "RESET" : "MERGE", add: { excludedArtists, includedGenres: /힙합|hip-hop/i.test(text) ? ["hip-hop"] : /록|rock/i.test(text) ? ["rock"] : [] }, remove: { excludedCountries: /일본.{0,8}(괜찮|허용|포함)/.test(text) ? ["JP"] : [] }, set: { ...( /여러 장르|다양한 장르/.test(text) ? { genreDiversity: "high" } : {}), ...( /아이돌.{0,8}조금/.test(text) ? { mainstreamRatio: .3 } : {}), ...( /유명.{0,8}(말고|줄)/.test(text) ? { popularity: "hidden_gems" } : {}), ...( /조금 더 신나/.test(text) ? { intensity: 4 } : {}) }, userMeaningSummary: text });
}

export function revisionScope(message: string): RevisionScope { if (/순서|첫 곡|마지막 곡/.test(message)) return "ARRANGEMENT_ONLY"; if (/비중|더 위로|유명한 곡/.test(message)) return "RESCORE"; return "REDISCOVER"; }

export function mergeIntent(ai: RecommendationIntent, fallback: RecommendationIntent): RecommendationIntent {
  const explicit = fallback.hardConstraints;
  return recommendationIntentSchema.parse({
    ...ai,
    rawRequest: fallback.rawRequest,
    currentState: fallback.currentState,
    targetState: fallback.targetState,
    activity: fallback.activity,
    hardConstraints: { ...ai.hardConstraints, region: explicit.region, allowedCountries: explicit.allowedCountries.length ? explicit.allowedCountries : ai.hardConstraints.allowedCountries, excludedCountries: explicit.excludedCountries.length ? explicit.excludedCountries : ai.hardConstraints.excludedCountries, requiredScenes: explicit.requiredScenes },
    preferences: { ...ai.preferences, moods: [...new Set([...fallback.preferences.moods, ...ai.preferences.moods])], activities: fallback.preferences.activities.length ? fallback.preferences.activities : ai.preferences.activities, genres: fallback.preferences.genres, ...(fallback.preferences.energy !== undefined ? { energy: fallback.preferences.energy } : {}), ...(fallback.preferences.vocalAmount ? { vocalAmount: fallback.preferences.vocalAmount } : {}), ...(fallback.preferences.popularity === "hidden_gems" ? { popularity: "hidden_gems", familiarity: "discovery" } : {}) },
  });
}

export function fallbackIntent(request: MusicRequest): RecommendationIntent {
  const ui = request.ui_selections ?? {};
  const broadState = typeof ui.broadState === "string" ? ui.broadState : undefined;
  const emotionDetail = typeof ui.emotionDetail === "string" ? ui.emotionDetail : undefined;
  const regulationGoal = typeof ui.regulationGoal === "string" ? ui.regulationGoal : undefined;
  const uiActivity = typeof ui.activity === "string" ? ui.activity : undefined;
  const uiIntensity = typeof ui.intensity === "number" ? ui.intensity : undefined;
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
    rawRequests: request.free_text ? [request.free_text] : [],
    currentState: { broadState, emotionDetail, energy: highEnergy ? "high" : "unknown" },
    targetState: { goal: regulationGoal ?? (revival ? "REVIVAL" : study ? "FOCUS" : undefined), energy: highEnergy ? "high" : "unknown", changeIntensity: uiIntensity },
    activity: uiActivity ?? (explicitWorkout ? "WORKOUT" : study ? "STUDY" : undefined),
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
    updatedAt: new Date().toISOString(),
  });
}
