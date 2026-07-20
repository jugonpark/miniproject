import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/lib/mcp/client", () => ({ callTool: vi.fn() }));

import { DELETE, GET as getOne } from "@/app/api/playlists/[id]/route";
import { GET as list, POST as save } from "@/app/api/playlists/route";
import { callTool } from "@/lib/mcp/client";

const mockedCallTool = vi.mocked(callTool);
const draft = {
  title: "Focus",
  description: "",
  request: {
    conditions: ["calm"], region: "mixed" as const, free_text: null,
    familiar_artists: [], count: 10 as const,
  },
  tracks: [{
    position: 1, recording_id: "recording-1", title: "Song", artist: "Artist",
    artist_id: null, release_id: null, release_title: null, cover_url: null,
    youtube_music_url: "https://music.youtube.com/search?q=Song", familiar: false,
  }],
};
const saved = { ...draft, id: 1, created_at: "2026-07-20T12:00:00+00:00" };
const context = (id: string) => ({ params: Promise.resolve({ id }) });

beforeEach(() => mockedCallTool.mockReset());

describe("playlist collection route", () => {
  test("saves a validated draft with its idempotency key", async () => {
    mockedCallTool.mockResolvedValue(saved);
    const response = await save(new Request("http://localhost/api/playlists", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ draft, idempotency_key: "save-1" }),
    }));

    expect(mockedCallTool).toHaveBeenCalledWith("save_playlist", {
      draft, idempotency_key: "save-1",
    });
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual(saved);
  });

  test("lists playlists with validated paging", async () => {
    mockedCallTool.mockResolvedValue([saved]);
    const response = await list(new Request("http://localhost/api/playlists?limit=5&offset=2"));

    expect(mockedCallTool).toHaveBeenCalledWith("list_playlists", { limit: 5, offset: 2 });
    expect(await response.json()).toEqual([saved]);
  });

  test("maps malformed save responses to 502", async () => {
    mockedCallTool.mockResolvedValue({ id: 1 });
    const response = await save(new Request("http://localhost/api/playlists", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ draft, idempotency_key: "save-1" }),
    }));

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "MCP 서버 응답이 올바르지 않습니다." });
  });

  test("rejects malformed MCP responses without leaking configuration", async () => {
    process.env.MCP_SERVER_URL = "http://secret.invalid/mcp";
    mockedCallTool.mockResolvedValue({ secret: process.env.MCP_SERVER_URL });
    const response = await list(new Request("http://localhost/api/playlists"));
    const body = JSON.stringify(await response.json());

    expect(response.status).toBe(502);
    expect(body).toContain("MCP 서버 응답이 올바르지 않습니다");
    expect(body).not.toContain(process.env.MCP_SERVER_URL);
  });

  test("maps MCP failures to a safe Korean 500 response", async () => {
    process.env.MCP_SERVER_URL = "http://secret.invalid/mcp";
    mockedCallTool.mockImplementationOnce(async () => {
      throw new Error(process.env.MCP_SERVER_URL);
    });
    const response = await list(new Request("http://localhost/api/playlists"));
    const body = JSON.stringify(await response.json());

    expect(response.status).toBe(500);
    expect(body).toContain("재생목록을 불러오지 못했습니다");
    expect(body).not.toContain(process.env.MCP_SERVER_URL);
  });
});

describe("single playlist route", () => {
  test("gets a playlist by numeric id", async () => {
    mockedCallTool.mockResolvedValue(saved);
    const response = await getOne(new Request("http://localhost/api/playlists/1"), context("1"));

    expect(mockedCallTool).toHaveBeenCalledWith("get_playlist", { playlist_id: 1 });
    expect(await response.json()).toEqual(saved);
  });

  test("deletes a playlist by numeric id", async () => {
    mockedCallTool.mockResolvedValue(null);
    const response = await DELETE(
      new Request("http://localhost/api/playlists/1", { method: "DELETE" }), context("1"),
    );

    expect(mockedCallTool).toHaveBeenCalledWith("delete_playlist", { playlist_id: 1 });
    expect(response.status).toBe(204);
  });

  test.each(["abc", "0", "1.5"])("rejects invalid id %s", async (id) => {
    const response = await getOne(new Request(`http://localhost/api/playlists/${id}`), context(id));
    expect(response.status).toBe(400);
    expect(mockedCallTool).not.toHaveBeenCalled();
  });

  test("maps missing playlists to 404", async () => {
    mockedCallTool.mockImplementationOnce(async () => {
      throw new Error("playlist 99 was not found");
    });
    const response = await getOne(new Request("http://localhost/api/playlists/99"), context("99"));
    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: "재생목록을 찾을 수 없습니다." });
  });

  test("rejects a malformed single-playlist response", async () => {
    mockedCallTool.mockResolvedValue({ id: 1 });
    const response = await getOne(new Request("http://localhost/api/playlists/1"), context("1"));
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "MCP 서버 응답이 올바르지 않습니다." });
  });
});
