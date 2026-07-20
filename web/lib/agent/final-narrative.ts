import type { PlaylistDraft } from "@/lib/schemas/playlist";

type VerifiedName = { artist_name?: unknown; track_title?: unknown };

export function safeFinalNarrative(text: string | null | undefined, playlist: PlaylistDraft, verified: VerifiedName[]): string {
  const actual = playlist.tracks.length;
  const selected = new Set(playlist.tracks.flatMap((track) => [track.artist, track.title]).map((value) => value.trim().toLocaleLowerCase()).filter(Boolean));
  const unselectedNames = verified.flatMap((track) => [track.artist_name, track.track_title]).filter((value): value is string => typeof value === "string" && value.trim().length > 2).map((value) => value.trim().toLocaleLowerCase()).filter((value) => !selected.has(value));
  const normalized = (text ?? "").toLocaleLowerCase();
  const counts = [...normalized.matchAll(/(\d+)\s*곡/g)].map((match) => Number(match[1]));
  const unsafe = !text?.trim() || counts.some((count) => count !== actual) || unselectedNames.some((name) => normalized.includes(name));
  if (!unsafe) return text!.trim();
  const names = playlist.tracks.map((track) => `${track.artist}의 ${track.title}`).join(", ");
  return playlist.recommendation_status === "PARTIAL"
    ? `필수 조건을 지키며 확인된 ${actual}곡만 담았어요. ${names}`
    : `요청한 흐름에 맞춰 검증된 ${actual}곡을 담았어요. ${names}`;
}
