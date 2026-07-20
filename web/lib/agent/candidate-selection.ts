import { z } from "zod";

const selectionSchema = z.array(z.object({
  candidateId: z.string().min(1),
  role: z.enum(["EMPATHY", "GROUNDING", "TRANSITION", "TARGET", "CLOSURE"]),
  reason: z.string().min(1).max(240),
}));

export type CandidateSelection = z.infer<typeof selectionSchema>;

export function validateCandidateSelection(value: unknown, candidates: Array<{ candidate_id?: unknown; recording_id?: unknown }>, count: number): CandidateSelection {
  const parsed = selectionSchema.safeParse(value);
  if (!parsed.success) throw new Error("NVIDIA_SELECTION_INVALID");
  const allowed = new Set(candidates.map((item) => String(item.candidate_id ?? item.recording_id ?? "")).filter(Boolean));
  const seen = new Set<string>();
  return parsed.data.filter((item) => allowed.has(item.candidateId) && !seen.has(item.candidateId) && seen.add(item.candidateId)).slice(0, count);
}

export function fallbackCandidateSelection(candidates: Array<{ candidate_id?: unknown; recording_id?: unknown }>, count: number): CandidateSelection {
  const ids = [...new Set(candidates.map((item) => String(item.candidate_id ?? item.recording_id ?? "")).filter(Boolean))].slice(0, count);
  const roles = ["EMPATHY", "GROUNDING", "TRANSITION", "TARGET", "CLOSURE"] as const;
  return ids.map((candidateId, index) => ({
    candidateId,
    role: roles[Math.round(index * (roles.length - 1) / Math.max(1, ids.length - 1))],
    reason: "검증된 후보 점수 순서를 사용했습니다.",
  }));
}
