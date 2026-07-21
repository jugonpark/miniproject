import { describe, expect, it } from "vitest";
import { fallbackCandidateSelection, validateCandidateSelection } from "@/lib/agent/candidate-selection";

const candidates = [
  { candidate_id: "candidate:a", recording_id: "a" },
  { candidate_id: "candidate:b", recording_id: "b" },
];

describe("candidate selection", () => {
  it("keeps only known unique IDs and validates roles", () => {
    expect(validateCandidateSelection([
      { candidateId: "candidate:a", role: "EMPATHY", reason: "첫 곡" },
      { candidateId: "candidate:a", role: "TARGET", reason: "중복" },
      { candidateId: "candidate:unknown", role: "TARGET", reason: "환각" },
      { candidateId: "candidate:b", role: "CLOSURE", reason: "마무리" },
    ], candidates, 5)).toEqual([
      { candidateId: "candidate:a", role: "EMPATHY", reason: "첫 곡" },
      { candidateId: "candidate:b", role: "CLOSURE", reason: "마무리" },
    ]);
  });

  it("rejects invalid JSON shape and roles", () => {
    expect(() => validateCandidateSelection("bad", candidates, 5)).toThrow("NVIDIA_SELECTION_INVALID");
    expect(() => validateCandidateSelection([{ candidateId: "candidate:a", role: "MADE_UP", reason: "x" }], candidates, 5)).toThrow("NVIDIA_SELECTION_INVALID");
  });

  it("enforces requested count", () => {
    expect(validateCandidateSelection([
      { candidateId: "candidate:a", role: "EMPATHY", reason: "a" },
      { candidateId: "candidate:b", role: "TARGET", reason: "b" },
    ], candidates, 1)).toHaveLength(1);
  });

  it("falls back to known candidate IDs when NVIDIA only returns unknown IDs", () => {
    expect(fallbackCandidateSelection(candidates, 2)).toEqual([
      { candidateId: "candidate:a", role: "EMPATHY", reason: "검증된 후보 점수 순서를 사용했습니다." },
      { candidateId: "candidate:b", role: "CLOSURE", reason: "검증된 후보 점수 순서를 사용했습니다." },
    ]);
  });
});
