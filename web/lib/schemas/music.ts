import { z } from "zod";

export const musicRequestSchema = z.object({
  conditions: z.array(z.string()).default([]),
  region: z.enum(["domestic", "global", "mixed"]).default("mixed"),
  free_text: z.string().nullable().default(null),
  familiar_artists: z.array(z.string()).default([]),
  count: z.union([z.literal(5), z.literal(10), z.literal(15)]).default(10),
  recommendation_session: z.unknown().optional(),
  ui_selections: z.record(z.string(), z.unknown()).optional(),
}).superRefine((request, context) => {
  if (!request.conditions.some((value) => value.trim()) && !request.free_text?.trim()) {
    context.addIssue({ code: "custom", message: "조건이나 추가 요청을 입력해 주세요." });
  }
});

export type MusicRequest = z.infer<typeof musicRequestSchema>;
