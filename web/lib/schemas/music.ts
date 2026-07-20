import { z } from "zod";

export const musicRequestSchema = z.object({
  conditions: z.array(z.string()).min(1),
  region: z.enum(["domestic", "global", "mixed"]).default("mixed"),
  free_text: z.string().nullable().default(null),
  familiar_artists: z.array(z.string()).default([]),
  count: z.union([z.literal(5), z.literal(10), z.literal(15)]).default(10),
});

export type MusicRequest = z.infer<typeof musicRequestSchema>;
