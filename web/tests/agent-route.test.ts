import { describe, expect, it } from "vitest";

import { agentError } from "@/lib/agent/error";

describe("agentError", () => {
  it.each([
    ["NVIDIA_API_KEY_MISSING", "NVIDIA_API_KEY_MISSING"],
    ["NVIDIA_TIMEOUT", "NVIDIA_TIMEOUT"],
    ["NVIDIA_429", "NVIDIA_API_ERROR"],
    ["MCP_TOOL_TIMEOUT", "MCP_TIMEOUT"],
    ["MCP_CONNECTION_FAILED", "MCP_CONNECTION_FAILED"],
    ["AGENT_LOOP_LIMIT", "AGENT_LOOP_LIMIT"],
  ])("classifies %s", (message, code) => {
    expect(agentError(new Error(message)).code).toBe(code);
  });

  it("explains a tool-result follow-up format failure without exposing internals", () => {
    expect(agentError(new Error("NVIDIA_400")).message).toBe("음악 검색은 완료됐지만 결과를 처리하는 AI 요청 형식에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.");
  });
});
