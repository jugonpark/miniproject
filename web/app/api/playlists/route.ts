import { NextResponse } from "next/server";
import { z } from "zod";

import { callTool, McpResponseError, McpToolError } from "@/lib/mcp/client";
import { playlistDraftSchema, savedPlaylistSchema } from "@/lib/schemas/playlist";

const saveSchema = z.object({
  draft: playlistDraftSchema,
  idempotency_key: z.string().min(1),
});
const pagingSchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
  offset: z.coerce.number().int().min(0).default(0),
});

export async function POST(request: Request) {
  let input: z.infer<typeof saveSchema>;
  try {
    input = saveSchema.parse(await request.json());
  } catch {
    return NextResponse.json({ error: "요청 형식이 올바르지 않습니다." }, { status: 400 });
  }
  try {
    const result = savedPlaylistSchema.parse(await callTool("save_playlist", input));
    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    if (
      error instanceof z.ZodError ||
      error instanceof McpResponseError ||
      error instanceof McpToolError
    ) {
      return NextResponse.json({ error: "MCP 서버 응답이 올바르지 않습니다." }, { status: 502 });
    }
    return NextResponse.json({ error: "재생목록을 저장하지 못했습니다." }, { status: 500 });
  }
}

export async function GET(request: Request) {
  let paging: z.infer<typeof pagingSchema>;
  try {
    const url = new URL(request.url);
    paging = pagingSchema.parse(Object.fromEntries(url.searchParams));
  } catch {
    return NextResponse.json({ error: "조회 조건이 올바르지 않습니다." }, { status: 400 });
  }
  try {
    const result = z.array(savedPlaylistSchema).parse(await callTool("list_playlists", paging));
    return NextResponse.json(result);
  } catch (error) {
    if (
      error instanceof z.ZodError ||
      error instanceof McpResponseError ||
      error instanceof McpToolError
    ) {
      return NextResponse.json({ error: "MCP 서버 응답이 올바르지 않습니다." }, { status: 502 });
    }
    return NextResponse.json({ error: "재생목록을 불러오지 못했습니다." }, { status: 500 });
  }
}
