"use client";

import Link from "next/link";
import { useState } from "react";
import { EmotionInterview } from "@/components/EmotionInterview";
import { activityEntry, type ActivityEntry } from "@/lib/agent/activity-log";
import type { MusicRequest } from "@/lib/schemas/music";
import type { PlaylistDraft } from "@/lib/schemas/playlist";

type Insight = { stage: string; message: string };

export default function Home() {
  const [status, setStatus] = useState(""); const [summary, setSummary] = useState("");
  const [playlist, setPlaylist] = useState<PlaylistDraft | null>(null); const [error, setError] = useState("");
  const [loading, setLoading] = useState(false); const [saved, setSaved] = useState(false); const [progress, setProgress] = useState(0);
  const [activityLogs, setActivityLogs] = useState<ActivityEntry[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);

  async function recommend(request: MusicRequest) {
    if (loading) return;
    setLoading(true); setProgress(0); setError(""); setSummary(""); setPlaylist(null); setSaved(false); setActivityLogs([]); setInsights([]);
    try {
      const response = await fetch("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
      if (!response.ok || !response.body) throw new Error("RECOMMENDATION_CONNECTION_FAILED");
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let completionStatus: "SUCCESS" | "PARTIAL" = "SUCCESS";
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true }); const rows = buffer.split("\n"); buffer = rows.pop() ?? "";
        for (const row of rows) {
          if (!row) continue; const event = JSON.parse(row); const entry = activityEntry(event);
          if (entry) setActivityLogs((old) => [...old, entry].slice(-10));
          if (typeof event.progress === "number") setProgress(event.progress);
          if (event.type === "status") setStatus(event.message);
          if (event.type === "tool") setStatus(({ discover_music_candidates: "관련 음악 세계를 살펴보고 있어요.", expand_similar_artists: "음악의 범위를 넓히고 있어요.", verify_music_tracks: "아티스트와 곡 정보를 확인하고 있어요.", compose_playlist: "마음의 흐름에 맞게 곡을 잇고 있어요." } as Record<string, string>)[event.name] ?? "추천을 준비하고 있어요.");
          if (event.type === "text_delta") setSummary((old) => old + event.delta);
          if (event.type === "insight") setInsights((old) => [...old, { stage: event.stage, message: event.message }]);
          if (event.type === "playlist") { completionStatus = event.data?.recommendation_status === "PARTIAL" ? "PARTIAL" : "SUCCESS"; setPlaylist(event.data); setProgress(100); }
          if (event.type === "error") setError(event.message);
          if (event.type === "done") setStatus(event.ok === false ? "추천을 완료하지 못했어요." : completionStatus === "PARTIAL" ? "조건에 맞는 확인된 곡만 담았어요." : "추천이 완성됐어요.");
        }
      }
    } catch { setError("추천 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."); setActivityLogs((old) => [...old, { state: "failed", message: "음악 추천 연결에 실패했어요." }]); }
    finally { setLoading(false); }
  }

  async function save() {
    if (!playlist) return;
    try { const response = await fetch("/api/playlists", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft: playlist, idempotency_key: crypto.randomUUID() }) }); if (!response.ok) throw new Error(); setSaved(true); }
    catch { setError("플레이리스트를 저장하지 못했어요. 다시 시도해 주세요."); }
  }

  return <main className="shell">
    <header className="header"><div><div className="logo">MOODWAVE</div><div className="muted">마음의 흐름을 듣는 AI 음악 큐레이터</div></div><Link className="secondary" href="/library">보관함</Link></header>
    <EmotionInterview loading={loading} onSubmit={recommend} />
    {(loading || status) && <div className="status" aria-live="polite"><div>{loading && "◌ "}{status} <strong>{progress}%</strong></div><div className="progress"><span style={{ width: `${progress}%` }} /></div></div>}
    {activityLogs.length > 0 && <section className="activity-panel" aria-live="polite"><strong>음악을 찾는 과정</strong><ol>{activityLogs.map((entry, index) => <li data-state={entry.state} key={`${index}-${entry.message}`}><span aria-hidden="true" />{entry.message}</li>)}</ol></section>}
    {insights.length > 0 && <section className="activity-panel insight-panel"><strong>추천 데이터 확인</strong><ol>{insights.map((item, index) => <li data-state="completed" key={`${item.stage}-${index}`}><span aria-hidden="true" /><b>{item.stage}</b> {item.message}</li>)}</ol></section>}
    {error && <div className="status error">{error}</div>}
    {summary && <div className="summary"><strong>AI 큐레이터</strong><p>{summary}</p></div>}
    {playlist && <><div className="actions"><h2>{playlist.title}</h2><button className="primary" disabled={saved} onClick={save}>{saved ? "저장 완료" : "플레이리스트 저장"}</button></div><div className="grid">{playlist.tracks.map((track) => <article className="card" key={track.recording_id}><img className="cover" src={track.cover_url ?? "/fallback-cover.svg"} onError={(event) => { event.currentTarget.src = "/fallback-cover.svg"; }} alt={`${track.title} 앨범 표지`} /><h3>{track.title}</h3><div>{track.artist}</div><div className="muted">{track.release_title ?? "앨범 정보 미확인"}</div><span className="badge">{track.role ?? (track.familiar ? "익숙한 선택" : "새로운 발견")}</span>{track.recommendation_reason && <p className="reason">{track.recommendation_reason}</p>}<a className="listen" target="_blank" rel="noreferrer" href={track.youtube_music_url}>YouTube Music에서 듣기</a></article>)}</div></>}
  </main>;
}
