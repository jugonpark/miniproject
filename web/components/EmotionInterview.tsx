"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { MusicRequest } from "@/lib/schemas/music";
import { broadOptions, clearDependentAnswers, conditionalOptions, detailByBroad, goalOptions, intensityOptions, pathFor, previewArc, toMusicRequest, type BroadEmotionState, type EmotionFlowState, type EmotionFlowStep, type Option, type RegulationGoal } from "@/lib/emotion/flow";

const initial: EmotionFlowState = { currentStep: "INTRO" };

export function EmotionInterview({ loading, onSubmit, onReset }: { loading: boolean; onSubmit: (request: MusicRequest) => void; onReset?: () => void }) {
  const [state, setState] = useState<EmotionFlowState>(initial);
  const [history, setHistory] = useState<EmotionFlowState[]>([]);
  const [locked, setLocked] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    try { const saved = localStorage.getItem("moodwave-emotion-flow"); if (saved) { const parsed = JSON.parse(saved); if (parsed.state) { setState(parsed.state); setHistory(parsed.history ?? []); } else setState(parsed); } } catch { /* 손상된 임시 상태는 무시합니다. */ }
    setHydrated(true);
  }, []);
  useEffect(() => { if (hydrated) localStorage.setItem("moodwave-emotion-flow", JSON.stringify({ state, history })); }, [history, hydrated, state]);
  useEffect(() => { heading.current?.focus(); }, [state.currentStep]);

  const move = (next: EmotionFlowState) => {
    if (locked) return;
    setLocked(true); setHistory((old) => [...old, state]);
    window.setTimeout(() => { setState(next); setLocked(false); }, 300);
  };
  const back = () => {
    if (loading || locked) return;
    const previous = history.at(-1);
    if (previous) { setHistory((old) => old.slice(0, -1)); setState(previous); }
  };
  const reset = () => { setState(initial); setHistory([]); setLocked(false); localStorage.removeItem("moodwave-emotion-flow"); onReset?.(); };
  const nextAfter = (updated: EmotionFlowState, step: EmotionFlowStep) => {
    const path = pathFor(updated); return { ...updated, currentStep: path[path.indexOf(step) + 1] ?? "FLOW_PREVIEW" };
  };
  const select = (option: Option) => {
    let updated = { ...state };
    if (state.currentStep === "BROAD_STATE") { updated.broadState = option.value as BroadEmotionState; updated.emotion = undefined; updated.emotionLabel = undefined; move({ ...updated, currentStep: "EMOTION_DETAIL" }); return; }
    if (state.currentStep === "EMOTION_DETAIL") { updated.emotion = option.value; updated.emotionLabel = option.label; move({ ...updated, currentStep: "INTENSITY" }); return; }
    if (state.currentStep === "INTENSITY") { updated.intensity = Number(option.value); move({ ...updated, currentStep: "REGULATION_GOAL" }); return; }
    if (state.currentStep === "REGULATION_GOAL") { updated = clearDependentAnswers(updated, option.value as RegulationGoal); move(nextAfter(updated, "REGULATION_GOAL")); return; }
    const config = state.regulationGoal && conditionalOptions[state.regulationGoal];
    if (config) { updated = { ...updated, [config.field]: option.value }; move({ ...updated, currentStep: "FLOW_PREVIEW" }); }
  };

  const question = questionFor(state); const choices = optionsFor(state);
  const steps: EmotionFlowStep[] = pathFor(state).filter((step) => step !== "INTRO"); const active = Math.max(0, steps.indexOf(state.currentStep));
  return <section className={`emotion-interview mood-${state.broadState?.toLowerCase() ?? "intro"}`} aria-labelledby="emotion-question">
    <div className="flow-dots" aria-hidden="true">{steps.map((step, index) => <span className={index <= active ? "active" : ""} key={step} />)}</div>
    <span className="sr-only" aria-live="polite">감정 인터뷰 {active + 1}단계</span>
    {state.currentStep === "INTRO" ? <div className="question-stage">
      <p className="eyebrow">MOODWAVE EMOTION INTERVIEW</p><h1 id="emotion-question" ref={heading} tabIndex={-1}>오늘 마음은 어떤 파도에 가까운가요?</h1>
      <p>천천히 골라도 괜찮아요.<br />지금의 마음을 음악으로 이어볼게요.</p>
      <button className="primary interview-start" onClick={() => move({ ...state, currentStep: "BROAD_STATE" })}>지금의 마음 들여다보기</button>
    </div> : state.currentStep === "FLOW_PREVIEW" ? <div className="question-stage">
      <p className="eyebrow">마음의 흐름</p><h1 id="emotion-question" ref={heading} tabIndex={-1}>지금의 마음에서<br />원하는 상태까지 천천히 이어볼게요.</h1>
      <div className="arc">{previewArc(state).map((item, index) => <span key={item}>{index > 0 && <b aria-hidden="true">→</b>}{item}</span>)}</div>
      <div className="region-options" aria-label="추천 범위"><button aria-pressed={!state.region || state.region === "mixed"} onClick={() => setState((old) => ({ ...old, region: "mixed" }))}>국내+해외</button><button aria-pressed={state.region === "domestic"} onClick={() => setState((old) => ({ ...old, region: "domestic" }))}>국내</button><button aria-pressed={state.region === "global"} onClick={() => setState((old) => ({ ...old, region: "global" }))}>해외</button></div>
      <label className="extra-request"><span>추가 요청 <small>선택</small></span><textarea value={state.extraRequest ?? ""} onChange={(event) => setState((old) => ({ ...old, extraRequest: event.target.value }))} placeholder="예: 너무 유명한 곡만 나오지 않았으면 좋겠어" maxLength={500} /></label>
      <button className="primary interview-start" disabled={loading} onClick={() => onSubmit(toMusicRequest(state))}>{loading ? "음악을 찾고 있어요…" : "이 흐름으로 음악 만나기"}</button>
    </div> : <div className={`question-stage ${locked ? "leaving" : ""}`}>
      <p className="eyebrow">지금의 마음을 천천히 들여다봐요</p><h1 id="emotion-question" ref={heading} tabIndex={-1}>{question}</h1>
      <div className={`interview-options ${state.currentStep === "INTENSITY" ? "intensity-options" : ""}`}>{choices.map((option) => <button key={option.value} className="emotion-option" disabled={locked} aria-pressed={selected(state, option.value)} onClick={() => select(option)}>{state.currentStep === "INTENSITY" && <i style={{ "--size": `${18 + Number(option.value) * 5}px` } as CSSProperties} />}<span>{option.label}</span></button>)}</div>
    </div>}
    {state.currentStep !== "INTRO" && <div className="interview-nav"><button className="back-button" disabled={loading || locked || history.length === 0} onClick={back}>← 이전으로</button><button className="reset-button" onClick={reset}>처음부터</button></div>}
  </section>;
}

function questionFor(state: EmotionFlowState) {
  if (state.currentStep === "BROAD_STATE") return "지금 마음의 움직임은 어떤가요?";
  if (state.currentStep === "EMOTION_DETAIL" && state.broadState) return detailByBroad[state.broadState].question;
  if (state.currentStep === "INTENSITY") return "그 감정은 지금 마음에서 얼마나 크게 느껴지나요?";
  if (state.currentStep === "REGULATION_GOAL") return "음악이 지금의 마음을 어떻게 도와주면 좋을까요?";
  return state.regulationGoal ? conditionalOptions[state.regulationGoal]?.question ?? "지금의 마음을 확인해 볼까요?" : "";
}
function optionsFor(state: EmotionFlowState): Option[] {
  if (state.currentStep === "BROAD_STATE") return broadOptions;
  if (state.currentStep === "EMOTION_DETAIL" && state.broadState) return detailByBroad[state.broadState].options;
  if (state.currentStep === "INTENSITY") return intensityOptions;
  if (state.currentStep === "REGULATION_GOAL") return goalOptions;
  return state.regulationGoal ? conditionalOptions[state.regulationGoal]?.options ?? [] : [];
}
function selected(state: EmotionFlowState, value: string) { return value === state.broadState || value === state.emotion || Number(value) === state.intensity || value === state.regulationGoal || value === state.context || value === state.lyricPreference || value === state.revivalLevel; }
