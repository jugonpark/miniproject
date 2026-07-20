import { NextResponse } from "next/server";
import { z } from "zod";
import { callTool, McpResponseError, McpToolError } from "@/lib/mcp/client";
import { savedPlaylistSchema } from "@/lib/schemas/playlist";

type RouteContext={params:Promise<{id:string}>};
const idSchema=z.string().regex(/^[1-9]\d*$/).transform(Number).refine(Number.isSafeInteger);
async function idOf(context:RouteContext){return idSchema.parse((await context.params).id)}
function failure(error:unknown,action:string){if(error instanceof McpToolError&&error.notFound)return NextResponse.json({error:"재생목록을 찾을 수 없습니다."},{status:404});if(error instanceof z.ZodError||error instanceof McpResponseError||error instanceof McpToolError)return NextResponse.json({error:"MCP 서버 응답이 올바르지 않습니다."},{status:502});return NextResponse.json({error:`재생목록을 ${action} 못했습니다.`},{status:500})}
export async function GET(_request:Request,context:RouteContext){let id:number;try{id=await idOf(context)}catch{return NextResponse.json({error:"플레이리스트 ID가 올바르지 않습니다."},{status:400})}try{return NextResponse.json(savedPlaylistSchema.parse(await callTool("get_playlist",{playlist_id:id})))}catch(error){return failure(error,"불러오지")}}
export async function DELETE(_request:Request,context:RouteContext){let id:number;try{id=await idOf(context)}catch{return NextResponse.json({error:"플레이리스트 ID가 올바르지 않습니다."},{status:400})}try{const result=await callTool("delete_playlist",{playlist_id:id});z.union([z.null(),z.object({deleted:z.literal(true),playlist_id:z.number().int()})]).parse(result);return new Response(null,{status:204})}catch(error){return failure(error,"삭제하지")}}
