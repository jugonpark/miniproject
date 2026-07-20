import { callTool } from "@/lib/mcp/client";
import type { MusicRequest } from "@/lib/schemas/music";
import { playlistDraftSchema, type PlaylistDraft } from "@/lib/schemas/playlist";
import { SYSTEM_PROMPT } from "./system-prompt";

type Message = { role:"system"|"user"|"assistant"|"tool"; content:string|null; tool_call_id?:string; tool_calls?: ToolCall[] };
type ToolCall = { id:string; type:"function"; function:{name:string;arguments:string} };
export type AgentEvent = Record<string, unknown> & { type:string };

const definitions = [
  { name:"discover_music_candidates", description:"조건에 맞는 실제 아티스트 후보 탐색", parameters:{type:"object",properties:{moods:{type:"array",items:{type:"string"}},activities:{type:"array",items:{type:"string"}},vocal_preference:{type:["string","null"]},region:{type:"string"},limit:{type:"integer"}},required:["moods","activities","region"]}},
  { name:"expand_similar_artists", description:"새로운 발견을 위한 유사 아티스트 확장", parameters:{type:"object",properties:{seed_artists:{type:"array",items:{type:"string"}},tags:{type:"array",items:{type:"string"}},limit:{type:"integer"}},required:["seed_artists","tags"]}},
  { name:"verify_music_tracks", description:"MusicBrainz에서 실제 곡 검증", parameters:{type:"object",properties:{artist_candidates:{type:"array",items:{type:"string"}},region:{type:"string"},limit_per_artist:{type:"integer"}},required:["artist_candidates","region"]}},
  { name:"compose_playlist", description:"검증된 곡만 사용해 최종 플레이리스트 구성", parameters:{type:"object",properties:{verified_tracks:{type:"array",items:{type:"object"}},conditions:{type:"array",items:{type:"string"}},region:{type:"string"},track_count:{type:"integer",enum:[5,10,15]},original_request:{type:"string"},familiar_artists:{type:"array",items:{type:"string"}}},required:["verified_tracks","conditions","region","track_count"]}},
];

const label:Record<string,string>={discover_music_candidates:"관련 아티스트를 찾고 있습니다.",expand_similar_artists:"새로운 음악을 더 찾고 있습니다.",verify_music_tracks:"실제로 발매된 곡을 검증하고 있습니다.",compose_playlist:"플레이리스트를 구성하고 있습니다."};

async function chat(messages:Message[], requireTool:boolean) {
  const key=process.env.NVIDIA_API_KEY; if(!key) throw new Error("NVIDIA_API_KEY_MISSING");
  const response=await fetch(`${process.env.NVIDIA_BASE_URL??"https://integrate.api.nvidia.com/v1"}/chat/completions`,{method:"POST",headers:{Authorization:`Bearer ${key}`,"Content-Type":"application/json"},body:JSON.stringify({model:process.env.NVIDIA_MODEL??"qwen/qwen3-235b-a22b",messages,tools:definitions.map((fn)=>({type:"function",function:fn})),tool_choice:requireTool?"required":"auto",temperature:.2})});
  if(!response.ok) throw new Error(`NVIDIA_${response.status}`);
  const data=await response.json() as {choices:Array<{message:{content:string|null;tool_calls?:ToolCall[]}}>};
  return data.choices[0]?.message;
}

export async function* runAgent(request:MusicRequest):AsyncGenerator<AgentEvent>{
  const messages:Message[]=[{role:"system",content:SYSTEM_PROMPT},{role:"user",content:JSON.stringify(request)}];
  const seen=new Set<string>(); let playlist:PlaylistDraft|undefined;
  yield {type:"status",step:"analyze",message:"요청 조건을 분석하고 있습니다."};
  for(let turn=0;turn<8;turn++){
    const answer=await chat(messages,!playlist); if(!answer) throw new Error("EMPTY_LLM_RESPONSE");
    if(!answer.tool_calls?.length){
      const content=answer.content?.trim()||`검증된 곡 ${playlist?.tracks.length??0}곡을 찾았습니다.`;
      for(const delta of content.match(/.{1,16}/gs)??[]) yield {type:"text_delta",delta};
      if(playlist) yield {type:"playlist",data:playlist};
      return;
    }
    messages.push({role:"assistant",content:answer.content,tool_calls:answer.tool_calls});
    for(const call of answer.tool_calls){
      let args:Record<string,unknown>; try{args=JSON.parse(call.function.arguments)}catch{messages.push({role:"tool",tool_call_id:call.id,content:JSON.stringify({error:"도구 인자 JSON 오류"})});continue;}
      const signature=`${call.function.name}:${JSON.stringify(args)}`; if(seen.has(signature)){messages.push({role:"tool",tool_call_id:call.id,content:JSON.stringify({error:"동일 도구 호출 반복 차단"})});continue;} seen.add(signature);
      yield {type:"tool",name:call.function.name,state:"started",message:label[call.function.name]??"도구를 실행하고 있습니다."};
      try{const result=await callTool<unknown>(call.function.name,args);if(call.function.name==="compose_playlist")playlist=playlistDraftSchema.parse(result);messages.push({role:"tool",tool_call_id:call.id,content:JSON.stringify(result)});yield {type:"tool_result",name:call.function.name,state:"completed",summary:call.function.name==="compose_playlist"?`${playlist?.tracks.length??0}곡을 구성했습니다.`:"완료했습니다."};}
      catch{messages.push({role:"tool",tool_call_id:call.id,content:JSON.stringify({error:"도구 실행 실패. 인자를 수정하거나 가능한 결과로 계속하세요."})});yield {type:"tool_result",name:call.function.name,state:"failed",summary:"도구 실행에 실패했습니다."};}
    }
  }
  throw new Error("AGENT_LOOP_LIMIT");
}
