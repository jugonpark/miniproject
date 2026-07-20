import { afterEach, describe, expect, it, vi } from "vitest";

import { runAgent } from "@/lib/agent/agent-loop";

describe("runAgent", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

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
    expect(body.messages[1].content).toContain("선택한 조건에 맞는 음악을 추천해줘.");
  });

  it("logs a sanitized NVIDIA failure with a request id", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("failed", { status: 503 })));

    const events = runAgent({
      conditions: ["calm"], region: "mixed", free_text: null,
      familiar_artists: [], count: 5,
    });
    await events.next();
    await expect(events.next()).rejects.toThrow("NVIDIA_503");

    expect(error).toHaveBeenCalledWith(expect.stringMatching(/^\[moodwave\] /));
    expect(error.mock.calls[0][0]).toContain('"stage":"nvidia"');
    expect(error.mock.calls[0][0]).not.toContain("test-key");
  });
});
