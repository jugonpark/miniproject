import { afterEach, describe, expect, it, vi } from "vitest";

import { runAgent } from "@/lib/agent/agent-loop";

describe("runAgent", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requires a tool call before a playlist exists", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ choices: [{ message: { content: "정보 미확인" } }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const events = runAgent({
      conditions: ["차분함"], region: "mixed", free_text: null,
      familiar_artists: [], count: 5,
    });
    await events.next();
    await events.next();

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.tool_choice).toBe("required");
  });
});
