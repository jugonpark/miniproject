import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/mcp/client", () => ({
  callTool: mocks.callTool,
  McpTransportError: class McpTransportError extends Error {},
}));

import { runAgent } from "@/lib/agent/agent-loop";

describe("runAgent", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    mocks.callTool.mockReset();
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
    const connecting = await events.next();
    await events.next();

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(connecting.value).toMatchObject({ type: "activity", state: "started", message: "NVIDIA AI 연결 중" });
    expect(body.tool_choice).toBe("required");
    expect(body.messages[1].content).toContain("선택한 조건에 맞는 음악을 추천해줘.");
  });

  it("logs a sanitized NVIDIA failure with a request id", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "tool message is invalid" }), { status: 503 })));

    const events = runAgent({
      conditions: ["calm"], region: "mixed", free_text: null,
      familiar_artists: [], count: 5,
    });
    await events.next();
    await events.next();
    await expect(events.next()).rejects.toThrow("NVIDIA_503");

    expect(error).toHaveBeenCalledWith(expect.stringMatching(/^\[moodwave\] /));
    expect(error.mock.calls[0][0]).toContain('"stage":"nvidia"');
    expect(error.mock.calls[0][0]).toContain('"detail":"tool message is invalid"');
    expect(error.mock.calls[0][0]).toContain('"errorBody":');
    expect(error.mock.calls[0][0]).not.toContain("test-key");
  });

  it("normalizes the tool exchange and only offers the next stage tool", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    const replies = [
      { content: null, tool_calls: [{ id: "call_discover", type: "function", function: { name: "discover_music_candidates", arguments: "{\"moods\":[\"calm\"],\"activities\":[\"study\"],\"region\":\"mixed\"}" } }] },
      { content: null, tool_calls: [{ id: "call_compose", type: "function", function: { name: "compose_playlist", arguments: "{\"conditions\":[\"study\"],\"region\":\"mixed\",\"track_count\":5}" } }] },
      { content: "추천이 완료되었습니다." },
    ];
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ choices: [{ message: replies.shift() }] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const verified = [{ recording_id:"recording-1", track_title:"Song", artist_name:"Artist" }];
    mocks.callTool
      .mockResolvedValueOnce([{ artist_name:"Artist" }])
      .mockResolvedValueOnce(verified)
      .mockResolvedValueOnce({
        title:"Playlist", description:"", request:{conditions:["study"],region:"mixed",free_text:null,familiar_artists:[],count:5},
        tracks:[{position:1,recording_id:"recording-1",title:"Song",artist:"Artist",artist_id:null,release_id:null,release_title:null,cover_url:null,youtube_music_url:"https://music.youtube.com/search?q=Artist%20Song",familiar:true}],
      });

    const events = [];
    for await (const event of runAgent({ conditions:["study"],region:"mixed",free_text:null,familiar_artists:[],count:5 })) events.push(event);

    const requests = fetchMock.mock.calls.map((call) => JSON.parse(call[1].body as string));
    expect(requests.map((request) => (request.tools??[]).map((tool: {function:{name:string}}) => tool.function.name))).toEqual([
      ["discover_music_candidates"], ["compose_playlist"], [],
    ]);
    expect(requests[1].messages.slice(-2)).toMatchObject([
      { role:"assistant", content:"", tool_calls:[{id:"call_discover"}] },
      { role:"tool", tool_call_id:"call_discover" },
    ]);
    expect(typeof requests[1].messages.at(-1).content).toBe("string");
    expect(mocks.callTool.mock.calls[2][1].verified_tracks).toEqual(verified);
    expect(mocks.callTool.mock.calls[1][1].artist_candidates).toEqual(["Artist"]);
    expect(events.some((event) => event.type === "playlist")).toBe(true);
    expect(events.some((event) => event.type === "insight" && event.stage === "AI 검색 조건")).toBe(true);
    expect(events.some((event) => event.type === "insight" && event.stage === "검증된 곡")).toBe(true);
  });

  it("stops before compose when no tracks were verified", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    const replies = [
      { content:null, tool_calls:[{id:"discover",type:"function",function:{name:"discover_music_candidates",arguments:'{"moods":["calm"],"activities":[],"region":"mixed"}'}}] },
    ];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify({choices:[{message:replies.shift()}]}), {status:200})));
    mocks.callTool.mockResolvedValueOnce([{artist_name:"Artist"}]).mockResolvedValueOnce([]);

    const events = runAgent({conditions:["calm"],region:"mixed",free_text:null,familiar_artists:[],count:5});
    await expect(async () => { for await (const _ of events) void _; }).rejects.toThrow("NO_VERIFIED_TRACKS");
    expect(mocks.callTool).toHaveBeenCalledTimes(2);
    expect(mocks.callTool).not.toHaveBeenCalledWith("compose_playlist", expect.anything());
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("reports empty discovery without starting verification", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({choices:[{message:{content:null,tool_calls:[{id:"discover",type:"function",function:{name:"discover_music_candidates",arguments:'{"moods":["blocked"],"activities":["study"],"region":"domestic"}'}}]}}]}), {status:200})));
    mocks.callTool.mockResolvedValueOnce([]);

    const events = runAgent({conditions:["답답함","공부"],region:"domestic",free_text:null,familiar_artists:[],count:5});
    await expect(async () => { for await (const _ of events) void _; }).rejects.toThrow("NO_DISCOVERY_CANDIDATES");
    expect(mocks.callTool).toHaveBeenCalledTimes(1);
    expect(mocks.callTool).not.toHaveBeenCalledWith("verify_music_tracks", expect.anything());
  });

  it("stops immediately when NVIDIA repeats the same tool call", async () => {
    process.env.NVIDIA_API_KEY = "test-key";
    const repeated = {content:null,tool_calls:[{id:"call",type:"function",function:{name:"discover_music_candidates",arguments:'{"moods":["calm"],"activities":[],"region":"mixed"}'}}]};
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify({choices:[{message:repeated}]}), {status:200})));
    mocks.callTool.mockResolvedValue([{artist_name:"Artist"}]);
    const events = runAgent({conditions:["calm"],region:"mixed",free_text:null,familiar_artists:[],count:5});
    await expect(async () => { for await (const _ of events) void _; }).rejects.toThrow("DUPLICATE_TOOL_CALL_BLOCKED");
    expect(mocks.callTool).toHaveBeenCalledTimes(2);
  });
});
