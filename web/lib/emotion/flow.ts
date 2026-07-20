import type { MusicRequest } from "@/lib/schemas/music";

export type EmotionFlowStep = "INTRO" | "BROAD_STATE" | "EMOTION_DETAIL" | "INTENSITY" | "REGULATION_GOAL" | "CONTEXT" | "LYRIC_PREFERENCE" | "REVIVAL_LEVEL" | "FLOW_PREVIEW";
export type BroadEmotionState = "LOW" | "UNSETTLED" | "COMPLEX" | "BLOCKED" | "CALM" | "ENERGETIC" | "UNKNOWN";
export type RegulationGoal = "SOLACE" | "RELAXATION" | "DIVERSION" | "REVIVAL" | "FOCUS" | "MAINTENANCE";
export type EmotionFlowState = { currentStep: EmotionFlowStep; broadState?: BroadEmotionState; emotion?: string; emotionLabel?: string; intensity?: number; regulationGoal?: RegulationGoal; context?: string; lyricPreference?: string; revivalLevel?: string; region?: "domestic" | "global" | "mixed"; extraRequest?: string };
export type Option = { value: string; label: string };

const options = (items: Array<[string, string]>): Option[] => items.map(([value, label]) => ({ value, label }));

export const broadOptions = options([
  ["LOW", "가라앉아 있어요"], ["UNSETTLED", "흔들리고 있어요"], ["COMPLEX", "복잡하게 얽혀 있어요"],
  ["BLOCKED", "무언가 꽉 막힌 느낌이에요"], ["CALM", "가볍고 편안해요"], ["ENERGETIC", "에너지가 넘쳐요"], ["UNKNOWN", "잘 모르겠어요"],
]);

export const detailByBroad: Record<BroadEmotionState, { question: string; options: Option[] }> = {
  LOW: { question: "그 가라앉음은 무엇과 가장 가까운가요?", options: options([["TIRED", "지침"], ["LONELY", "외로움"], ["SAD", "슬픔"], ["LETHARGIC", "무기력"], ["EMPTY", "허전함"], ["PEACEFUL", "조용한 평온"]]) },
  UNSETTLED: { question: "그 흔들림은 무엇과 가장 가까운가요?", options: options([["WORRY", "걱정"], ["TENSION", "긴장"], ["IMPATIENCE", "조급함"], ["EXCITEMENT", "설렘"], ["ANXIETY", "막연한 불안"], ["UNKNOWN", "이유를 잘 모르겠음"]]) },
  COMPLEX: { question: "지금 가장 가까운 느낌을 골라볼까요?", options: options([["OVERTHINKING", "생각이 너무 많음"], ["REGRET", "후회"], ["FRUSTRATION", "답답함"], ["CONFUSION", "혼란"], ["MIXED", "감정이 섞여 있음"], ["UNKNOWN", "정확히 설명하기 어려움"]]) },
  BLOCKED: { question: "막힌 느낌은 어디에 가까운가요?", options: options([["ANGER", "화가 남"], ["STUCK", "진전이 없음"], ["SUPPRESSED", "말로 꺼내기 어려움"], ["PRESSURE", "압박감"], ["RESTLESS", "몸이 답답함"], ["UNKNOWN", "잘 모르겠음"]]) },
  CALM: { question: "그 편안함을 조금 더 표현해 볼까요?", options: options([["CONTENT", "만족스러움"], ["RESTFUL", "느긋함"], ["WARM", "따뜻함"], ["CLEAR", "맑고 가벼움"], ["QUIET", "조용함"], ["UNKNOWN", "그냥 편안함"]]) },
  ENERGETIC: { question: "그 에너지는 무엇에 가까운가요?", options: options([["JOY", "즐거움"], ["MOTIVATED", "의욕"], ["EXCITED", "들뜸"], ["CONFIDENT", "자신감"], ["PLAYFUL", "장난스러움"], ["UNKNOWN", "설명하기 어려움"]]) },
  UNKNOWN: { question: "지금 조금이라도 가까운 표현이 있나요?", options: options([["LOW", "가라앉음"], ["ANXIETY", "흔들림"], ["COMPLEX", "복잡함"], ["BLOCKED", "답답함"], ["CALM", "편안함"], ["UNKNOWN", "아직 설명하기 어려움"]]) },
};

export const goalOptions = options([["SOLACE", "지금 마음을 이해해 줬으면 해요"], ["RELAXATION", "조금 편안해지고 싶어요"], ["DIVERSION", "생각에서 잠시 벗어나고 싶어요"], ["REVIVAL", "다시 힘을 얻고 싶어요"], ["FOCUS", "차분하게 집중하고 싶어요"], ["MAINTENANCE", "지금 감정을 그대로 이어가고 싶어요"]]);
export const intensityOptions = options([["1", "아주 약하게 느껴져요"], ["2", "조금 느껴져요"], ["3", "분명하게 느껴져요"], ["4", "마음을 크게 차지하고 있어요"], ["5", "거의 가득 차 있어요"]]);
export const conditionalOptions: Record<string, { question: string; field: "context" | "lyricPreference" | "revivalLevel"; options: Option[] }> = {
  FOCUS: { question: "지금 무엇에 집중하고 있나요?", field: "context", options: options([["STUDY", "공부"], ["CODING", "코딩·작업"], ["READING", "독서"], ["MOVING", "이동"], ["ORGANIZING", "정리"], ["OTHER", "기타"]]) },
  DIVERSION: { question: "어떤 방식으로 잠시 벗어나고 싶나요?", field: "context", options: options([["WALK", "산책"], ["DRIVE", "드라이브"], ["REST", "휴식"], ["CHORES", "가벼운 정리"], ["OTHER", "상관없어요"]]) },
  RELAXATION: { question: "어떤 음악이 지금 더 편할까요?", field: "lyricPreference", options: options([["LYRICS", "가사가 있는 음악"], ["LOW", "가사가 적은 음악"], ["INSTRUMENTAL", "연주곡"], ["ANY", "상관없어요"]]) },
  REVIVAL: { question: "어느 정도의 활력을 원하시나요?", field: "revivalLevel", options: options([["SLOW", "아주 천천히"], ["GRADUAL", "조금씩"], ["STRONG", "확실하게 기분 전환"]]) },
};

const broadLabel = (value?: string) => broadOptions.find((option) => option.value === value)?.label;
const goalLabel = (value?: string) => goalOptions.find((option) => option.value === value)?.label;
const conditionalLabel = (state: EmotionFlowState) => state.regulationGoal
  ? conditionalOptions[state.regulationGoal]?.options.find((option) => [state.context, state.lyricPreference, state.revivalLevel].includes(option.value))?.label
  : undefined;

export function pathFor(state: EmotionFlowState): EmotionFlowStep[] {
  const path: EmotionFlowStep[] = ["INTRO", "BROAD_STATE", "EMOTION_DETAIL", "INTENSITY", "REGULATION_GOAL"];
  const extra = state.regulationGoal && conditionalOptions[state.regulationGoal];
  if (extra) path.push(extra.field === "context" ? "CONTEXT" : extra.field === "lyricPreference" ? "LYRIC_PREFERENCE" : "REVIVAL_LEVEL");
  return [...path, "FLOW_PREVIEW"];
}

export function clearDependentAnswers(state: EmotionFlowState, goal: RegulationGoal): EmotionFlowState {
  return { ...state, regulationGoal: goal, context: undefined, lyricPreference: undefined, revivalLevel: undefined };
}

export function toMusicRequest(state: EmotionFlowState): MusicRequest {
  const labels = [broadLabel(state.broadState), state.emotionLabel, goalLabel(state.regulationGoal), conditionalLabel(state), state.intensity ? `감정 강도 ${state.intensity}` : undefined].filter((value): value is string => Boolean(value));
  const base = `현재 마음은 ${labels.join(", ")}에 가깝습니다. 이 감정의 흐름을 존중하며 실제로 검증된 음악을 추천해 주세요.`;
  return { conditions: labels, region: state.region ?? "mixed", free_text: state.extraRequest?.trim() ? `${base} 추가 요청: ${state.extraRequest.trim()}` : base, familiar_artists: [], count: 10, ui_selections: { broadState: state.broadState, emotionDetail: state.emotion, regulationGoal: state.regulationGoal, intensity: state.intensity, activity: state.context, region: state.region ?? "mixed" } };
}

export function previewArc(state: EmotionFlowState): string[] {
  const start = state.emotionLabel ?? broadLabel(state.broadState) ?? "지금의 마음";
  const end: Record<string, string> = { SOLACE: "부드러운 위로", RELAXATION: "편안한 안정", DIVERSION: "가벼운 환기", REVIVAL: "천천히 활력", FOCUS: "차분한 집중", MAINTENANCE: "감정의 여운" };
  return [start, "감정을 머무르기", end[state.regulationGoal ?? ""] ?? "자연스러운 마무리"];
}
