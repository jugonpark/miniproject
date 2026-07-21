export function agentError(error: unknown) {
  const message = error instanceof Error ? error.message : "UNKNOWN";
  if (message === "NO_DISCOVERY_CANDIDATES") return { code: message, message: "조건과 가까운 음악 후보를 충분히 찾지 못했어요. 다른 검색 방향으로 다시 살펴볼 수 있어요." };
  if (message === "NVIDIA_SELECTION_INVALID") return { code: message, message: "검증된 음악 후보의 구성 결과를 확인하지 못했어요. 잠시 후 다시 시도해 주세요." };
  if (message === "NO_VERIFIED_TRACKS") return { code: message, message: "조건에 맞으며 실제로 확인된 곡을 찾지 못했어요. 추천 범위나 추가 요청을 바꿔 다시 시도해 주세요." };
  if (message === "DUPLICATE_TOOL_CALL_BLOCKED") return { code: message, message: "같은 검색이 반복되어 추천 요청을 안전하게 중단했어요." };
  if (message === "NVIDIA_API_KEY_MISSING") return { code: message, message: "NVIDIA API 키가 설정되지 않았어요." };
  if (message === "NVIDIA_TIMEOUT") return { code: message, message: "NVIDIA AI 응답이 3분을 초과했어요. 잠시 후 다시 시도해 주세요." };
  if (message === "NVIDIA_400") return { code: "NVIDIA_API_ERROR", message: "음악 검색은 완료됐지만 결과를 처리하는 AI 요청 형식에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요." };
  if (message.startsWith("NVIDIA_")) return { code: "NVIDIA_API_ERROR", message: `NVIDIA API 호출에 실패했어요. (${message.replace("NVIDIA_", "")})` };
  if (message === "MCP_TOOL_TIMEOUT") return { code: "MCP_TIMEOUT", message: "음악 서비스 응답이 90초를 넘어 요청을 종료했어요. 잠시 후 다시 시도해 주세요." };
  if (message === "MCP_CONNECTION_FAILED") return { code: message, message: "음악 검색 서버에 연결할 수 없어요. MCP 설정을 확인해 주세요." };
  if (message === "AGENT_LOOP_LIMIT") return { code: message, message: "추천 단계를 반복 제한 안에 마치지 못했어요. 조건을 조금 단순하게 바꿔 주세요." };
  return { code: "AGENT_FAILED", message: "추천을 만드는 중 문제가 발생했어요. 서버 로그를 확인해 주세요." };
}
