export function agentError(error:unknown){
  const message=error instanceof Error?error.message:"UNKNOWN";
  if(message==="NVIDIA_API_KEY_MISSING")return{code:"NVIDIA_API_KEY_MISSING",message:"NVIDIA API 키가 설정되지 않았습니다."};
  if(message==="NVIDIA_TIMEOUT")return{code:"NVIDIA_TIMEOUT",message:"NVIDIA AI 응답이 3분을 초과했습니다. 잠시 후 다시 시도해 주세요."};
  if(message.startsWith("NVIDIA_"))return{code:"NVIDIA_API_ERROR",message:`NVIDIA API 호출에 실패했습니다. (${message.replace("NVIDIA_","")})`};
  if(message==="MCP_TOOL_TIMEOUT")return{code:"MCP_TIMEOUT",message:"음악 검색 Tool 응답이 45초를 초과했습니다. 조건을 줄여 다시 시도해 주세요."};
  if(message==="MCP_CONNECTION_FAILED")return{code:"MCP_CONNECTION_FAILED",message:"FastMCP 서버에 연결할 수 없습니다. MCP URL과 인증 설정을 확인해 주세요."};
  if(message==="AGENT_LOOP_LIMIT")return{code:"AGENT_LOOP_LIMIT",message:"추천 단계를 반복 한도 안에 완료하지 못했습니다. 조건을 단순화해 주세요."};
  return{code:"AGENT_FAILED",message:"추천 생성 중 알 수 없는 오류가 발생했습니다. 서버 로그를 확인해 주세요."};
}
