import { NextResponse } from "next/server";
import { z } from "zod";
import { callTool, McpResponseError, McpToolError } from "@/lib/mcp/client";
import { playlistDraftSchema, savedPlaylistSchema } from "@/lib/schemas/playlist";

const saveSchema=z.object({draft:playlistDraftSchema,idempotency_key:z.string().min(1)});
const pagingSchema=z.object({limit:z.coerce.number().int().min(1).max(100).default(20),offset:z.coerce.number().int().min(0).default(0)});
const upstream=(error:unknown)=>error instanceof z.ZodError||error instanceof McpResponseError||error instanceof McpToolError;

export async function POST(request:Request){
  let input:z.infer<typeof saveSchema>;try{input=saveSchema.parse(await request.json())}catch{return NextResponse.json({error:"요청 형식이 올바르지 않습니다."},{status:400})}
  try{return NextResponse.json(savedPlaylistSchema.parse(await callTool("save_playlist",input)),{status:201})}catch(error){return NextResponse.json({error:upstream(error)?"MCP 서버 응답이 올바르지 않습니다.":"플레이리스트를 저장하지 못했습니다."},{status:upstream(error)?502:500})}
}
export async function GET(request:Request){
  let paging:z.infer<typeof pagingSchema>;try{paging=pagingSchema.parse(Object.fromEntries(new URL(request.url).searchParams))}catch{return NextResponse.json({error:"조회 조건이 올바르지 않습니다."},{status:400})}
  try{return NextResponse.json(z.array(savedPlaylistSchema).parse(await callTool("list_playlists",paging)))}catch(error){return NextResponse.json({error:upstream(error)?"MCP 서버 응답이 올바르지 않습니다.":"재생목록을 불러오지 못했습니다."},{status:upstream(error)?502:500})}
}
