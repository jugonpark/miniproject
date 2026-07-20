import type { PlaylistDraft } from "@/lib/schemas/playlist";

type VerifiedName = { artist_name?: unknown; track_title?: unknown; artist_country?: unknown; origin_status?: unknown; tags?: unknown };

export function safeFinalNarrative(_text: string | null | undefined, playlist: PlaylistDraft, verified: VerifiedName[]): string {
  const actual = playlist.tracks.length;
  const selectedKeys = new Set(playlist.tracks.map((track) => `${track.artist}::${track.title}`.toLocaleLowerCase()));
  const evidence = verified.filter((track) => selectedKeys.has(`${String(track.artist_name ?? "")}::${String(track.track_title ?? "")}`.toLocaleLowerCase()));
  const allKorean = evidence.length === actual && evidence.every((track) => track.origin_status === "VERIFIED_KR" || track.artist_country === "KR");
  const tagSets = evidence.map((track) => new Set(Array.isArray(track.tags) ? track.tags.map(String).map((tag) => tag.toLocaleLowerCase()) : []));
  const supported = (tags: string[]) => tagSets.length > 0 && tagSets.filter((set) => tags.some((tag) => set.has(tag))).length >= Math.ceil(tagSets.length * 0.6);
  const claims = [
    allKorean ? "아티스트 국가가 대한민국으로 확인된 곡만 포함했어요." : "",
    supported(["mellow", "ambient", "downtempo"]) ? "차분한 분위기 태그가 확인된 곡을 중심으로 골랐어요." : "",
    supported(["energetic", "high energy", "dance"]) ? "활력 있는 분위기 태그가 확인된 곡을 중심으로 골랐어요." : "",
    supported(["instrumental"]) ? "연주곡 태그가 확인된 곡을 중심으로 골랐어요." : "",
  ].filter(Boolean).join(" ");
  const names = playlist.tracks.map((track) => `${track.artist}의 ${track.title}`).join(", ");
  const prefix = playlist.recommendation_status === "PARTIAL"
    ? `필수 조건을 지키며 확인된 ${actual}곡만 담았어요.`
    : `현재 감정과 요청을 고려해 실제로 확인된 ${actual}곡을 골랐어요.`;
  return `${prefix}${claims ? ` ${claims}` : ""} ${names}`;
}
