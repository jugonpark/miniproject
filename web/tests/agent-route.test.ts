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
});
