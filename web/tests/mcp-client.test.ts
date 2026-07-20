import { beforeEach, describe, expect, test, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  clientConstructor: vi.fn(),
  transportConstructor: vi.fn(),
  connect: vi.fn(),
  callTool: vi.fn(),
  close: vi.fn(),
}));

vi.mock("@modelcontextprotocol/sdk/client/index.js", () => ({
  Client: class {
    constructor(...args: unknown[]) { mocks.clientConstructor(...args); }
    connect = mocks.connect;
    callTool = mocks.callTool;
    close = mocks.close;
  },
}));
vi.mock("@modelcontextprotocol/sdk/client/streamableHttp.js", () => ({
  StreamableHTTPClientTransport: class {
    constructor(...args: unknown[]) { mocks.transportConstructor(...args); }
  },
}));

beforeEach(() => {
  vi.resetModules();
  Object.values(mocks).forEach((mock) => mock.mockReset());
  process.env.MCP_SERVER_URL = "http://127.0.0.1:8000/mcp";
});

describe("callTool", () => {
  test("connects lazily once and unwraps structured results", async () => {
    mocks.callTool.mockResolvedValue({
      isError: false,
      content: [],
      structuredContent: { result: { id: 1 } },
    });
    const { callTool } = await import("@/lib/mcp/client");

    expect(mocks.clientConstructor).not.toHaveBeenCalled();
    await expect(callTool("get_playlist", { playlist_id: 1 })).resolves.toEqual({ id: 1 });
    await callTool("list_playlists", {});

    expect(mocks.clientConstructor).toHaveBeenCalledTimes(1);
    expect(mocks.connect).toHaveBeenCalledTimes(1);
  });

  test("reconnects once after a failed call", async () => {
    mocks.callTool
      .mockImplementationOnce(async () => { throw new Error("connection lost"); })
      .mockResolvedValueOnce({ isError: false, content: [{ type: "text", text: "[]" }] });
    const { callTool } = await import("@/lib/mcp/client");

    await expect(callTool("list_playlists", {})).resolves.toEqual([]);
    expect(mocks.clientConstructor).toHaveBeenCalledTimes(2);
    expect(mocks.callTool).toHaveBeenCalledTimes(2);
  });

  test("does not retry a tool-declared error", async () => {
    mocks.callTool.mockResolvedValue({
      isError: true,
      content: [{ type: "text", text: "playlist 99 was not found" }],
    });
    const { callTool, McpToolError } = await import("@/lib/mcp/client");

    await expect(callTool("get_playlist", { playlist_id: 99 })).rejects.toBeInstanceOf(McpToolError);
    expect(mocks.clientConstructor).toHaveBeenCalledTimes(1);
    expect(mocks.callTool).toHaveBeenCalledTimes(1);
  });

  test("does not repeat a successful mutation when its response cannot be decoded", async () => {
    mocks.callTool.mockResolvedValue({
      isError: false,
      content: [{ type: "text", text: "not-json" }],
    });
    const { callTool, McpResponseError } = await import("@/lib/mcp/client");

    await expect(callTool("save_playlist", {})).rejects.toBeInstanceOf(McpResponseError);
    expect(mocks.callTool).toHaveBeenCalledTimes(1);
    expect(mocks.clientConstructor).toHaveBeenCalledTimes(1);
  });

  test("two concurrent failures replace one exact client and close it once", async () => {
    mocks.callTool
      .mockImplementationOnce(async () => { throw new Error("connection lost a"); })
      .mockImplementationOnce(async () => { throw new Error("connection lost b"); })
      .mockResolvedValue({ isError: false, content: [{ type: "text", text: "[]" }] });
    const { callTool } = await import("@/lib/mcp/client");

    await expect(Promise.all([
      callTool("list_playlists", { offset: 0 }),
      callTool("list_playlists", { offset: 1 }),
    ])).resolves.toEqual([[], []]);
    await vi.waitFor(() => expect(mocks.close).toHaveBeenCalledTimes(1));
    expect(mocks.clientConstructor).toHaveBeenCalledTimes(2);
    expect(mocks.callTool).toHaveBeenCalledTimes(4);
  });
});
