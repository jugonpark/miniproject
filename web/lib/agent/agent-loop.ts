import { callTool, McpTransportError } from "@/lib/mcp/client";
import type { MusicRequest } from "@/lib/schemas/music";
import { playlistDraftSchema, type PlaylistDraft } from "@/lib/schemas/playlist";
import { SYSTEM_PROMPT } from "./system-prompt";

type Message = { role:"system"|"user"|"assistant"|"tool"; content:string|null; tool_call_id?:string; tool_calls?: ToolCall[] };
type ToolCall = { id:string; type:"function"; function:{name:string;arguments:string} };
export type AgentEvent = Record<string, unknown> & { type:string };

const definitions = [
  { name:"discover_music_candidates", description:"조건에 맞는 실제 아티스트 후보 탐색", parameters:{type:"object",properties:{moods:{type:"array",items:{type:"string"}},activities:{type:"array",items:{type:"string"}},vocal_preference:{type:["string","null"]},region:{type:"string"},limit:{type:"integer"}},required:["moods","activities","region"]}},
  { name:"expand_similar_artists", description:"새로운 발견을 위한 유사 아티스트 확장", parameters:{type:"object",properties:{seed_artists:{type:"array",items:{type:"string"}},tags:{type:"array",items:{type:"string"}},limit:{type:"integer"}},required:["seed_artists","tags"]}},
  { name:"verify_music_tracks", description:"아티스트 국가와 실제 곡 검증", parameters:{type:"object",properties:{artist_candidates:{type:"array",items:{type:"string"}},region:{type:"string"},limit_per_artist:{type:"integer"},conditions:{type:"array",items:{type:"string"}},original_request:{type:"string"}},required:["artist_candidates","region"]}},
  { name:"compose_playlist", description:"검증된 곡만 사용해 최종 플레이리스트 구성", parameters:{type:"object",properties:{conditions:{type:"array",items:{type:"string"}},region:{type:"string"},track_count:{type:"integer",enum:[5,10,15]},original_request:{type:"string"},familiar_artists:{type:"array",items:{type:"string"}}},required:["conditions","region","track_count"]}},
];
type ToolDefinition = (typeof definitions)[number];

const label:Record<string,string>={discover_music_candidates:"관련 음악 세계를 살펴보고 있어요.",expand_similar_artists:"새로운 음악의 범위를 넓히고 있어요.",verify_music_tracks:"아티스트 국가와 실제 곡을 확인하고 있어요.",compose_playlist:"감정 흐름에 맞게 순서를 정리하고 있어요."};
const progress:Record<string,number>={discover_music_candidates:20,expand_similar_artists:35,verify_music_tracks:55,compose_playlist:85};

function nextTools(completed:Set<string>,expand:boolean):ToolDefinition[]{
  const name=!completed.has("discover_music_candidates")?"discover_music_candidates":expand&&!completed.has("expand_similar_artists")?"expand_similar_artists":!completed.has("verify_music_tracks")?"verify_music_tracks":!completed.has("compose_playlist")?"compose_playlist":null;
  return name?definitions.filter((tool)=>tool.name===name):[];
}

function normalizeToolCalls(calls:ToolCall[]):ToolCall[]{
  return calls.map((call)=>{if(!call.id?.trim()||!call.function?.name)throw new Error("NVIDIA_TOOL_CALL_INVALID");const args=typeof call.function.arguments==="string"?call.function.arguments:JSON.stringify(call.function.arguments);JSON.parse(args);return{id:call.id,type:"function",function:{name:call.function.name,arguments:args}};});
}

function serializeToolResult(result:unknown):string{
  if(typeof result==="string")return result;
  const serialized=JSON.stringify(result);if(serialized===undefined)throw new Error("NVIDIA_TOOL_RESULT_NOT_SERIALIZABLE");return serialized;
}

async function chat(messages:Message[], tools:ToolDefinition[], requestId:string, iteration:number) {
  const key=process.env.NVIDIA_API_KEY; if(!key) throw new Error("NVIDIA_API_KEY_MISSING");
  const started=Date.now();
  const toolCalls=messages.flatMap((message)=>message.tool_calls??[]);const toolMessages=messages.filter((message)=>message.role==="tool");
  console.info(`[moodwave] ${JSON.stringify({requestId,stage:"nvidia_request",iteration,messageRoles:messages.map((message)=>message.role),messageCount:messages.length,toolCount:tools.length,toolChoice:tools.length?"required":"none",maxTokens:512,assistantToolCallCount:toolCalls.length,toolMessageCount:toolMessages.length,toolCallIds:toolCalls.map((call)=>call.id),toolMessageCallIds:toolMessages.map((message)=>message.tool_call_id)})}`);
  let response:Response;
  const toolConfig=tools.length?{tools:tools.map((fn)=>({type:"function",function:fn})),tool_choice:"required"}:{};
  try{response=await fetch(`${process.env.NVIDIA_BASE_URL??"https://integrate.api.nvidia.com/v1"}/chat/completions`,{method:"POST",headers:{Authorization:`Bearer ${key}`,"Content-Type":"application/json"},signal:AbortSignal.timeout(180_000),body:JSON.stringify({model:process.env.NVIDIA_MODEL??"qwen/qwen3-235b-a22b",messages,...toolConfig,temperature:.2,max_tokens:512})});}
  catch(error){if(error instanceof Error&&error.name==="TimeoutError")throw new Error("NVIDIA_TIMEOUT");throw error;}
  if(!response.ok){const errorBody=(await response.text()).slice(0,3000);let body:{detail?:unknown;message?:unknown;error?:{message?:unknown;type?:unknown;code?:unknown;param?:unknown}}|null=null;try{body=JSON.parse(errorBody)}catch{}const detail=[body?.detail,body?.message,body?.error?.message].find((value)=>typeof value==="string") as string|undefined;console.error(`[moodwave] ${JSON.stringify({requestId,stage:"nvidia",state:"failed",status:response.status,durationMs:Date.now()-started,errorBody,...(detail?{detail:detail.slice(0,3000)}:{}),error:body?.error})}`);throw new Error(`NVIDIA_${response.status}`);}
  const data=await response.json() as {choices:Array<{message:{content:string|null;tool_calls?:ToolCall[]}}>};
  console.info(`[moodwave] ${JSON.stringify({requestId,stage:"nvidia",state:"completed",durationMs:Date.now()-started,toolCalls:data.choices[0]?.message.tool_calls?.map((call)=>call.function.name)??[]})}`);
  return data.choices[0]?.message;
}

export async function* runAgent(request:MusicRequest):AsyncGenerator<AgentEvent>{
  const requestId=crypto.randomUUID();
  const messages:Message[]=[{role:"system",content:SYSTEM_PROMPT},{role:"user",content:JSON.stringify({...request,free_text:request.free_text?.trim()||"선택한 조건에 맞는 음악을 추천해줘."})}];
  const seen=new Set<string>();const completed=new Set<string>();const expand=/(새로운|발견|유명한 곡만|new|discover)/i.test(request.free_text??"");let playlist:PlaylistDraft|undefined;let verifiedTracks:unknown;let discoveredArtists:string[]=[];
  yield {type:"status",step:"analyze",message:"요청 조건을 분석하고 있습니다.",progress:5};
  for(let turn=0;turn<8;turn++){
    if(completed.has("discover_music_candidates")&&(!expand||completed.has("expand_similar_artists"))&&!completed.has("verify_music_tracks")){
      yield {type:"insight",stage:"발견 후보",message:`${discoveredArtists.length}명 · ${discoveredArtists.slice(0,6).join(", ")}`};
      yield {type:"tool",name:"verify_music_tracks",state:"started",message:label.verify_music_tracks,progress:progress.verify_music_tracks};
      const started=Date.now();console.info(`[moodwave] ${JSON.stringify({requestId,stage:"mcp",tool:"verify_music_tracks",state:"started",artistCount:discoveredArtists.length})}`);
      const result=await Promise.race([callTool<unknown>("verify_music_tracks",{artist_candidates:discoveredArtists,conditions:request.conditions,original_request:request.free_text??"",region:request.region,limit_per_artist:2}),new Promise<never>((_,reject)=>setTimeout(()=>reject(new Error("MCP_TOOL_TIMEOUT")),90_000))]);
      console.info(`[moodwave] ${JSON.stringify({requestId,stage:"mcp",tool:"verify_music_tracks",state:"completed",durationMs:Date.now()-started,resultCount:Array.isArray(result)?result.length:null})}`);
      if(!Array.isArray(result)||result.length===0)throw new Error("NO_VERIFIED_TRACKS");
      const verifiedNames=result.slice(0,6).map((item)=>typeof item==="object"&&item!==null?`${String((item as {artist_name?:unknown}).artist_name??"")} - ${String((item as {track_title?:unknown}).track_title??"")}`:"").filter(Boolean);
      verifiedTracks=result;completed.add("verify_music_tracks");yield {type:"insight",stage:"검증된 곡",message:`${result.length}곡 · ${verifiedNames.join(", ")}`};yield {type:"tool_result",name:"verify_music_tracks",state:"completed",summary:`${result.length}곡을 확인했습니다.`,progress:65};continue;
    }
    const tools=nextTools(completed,expand);
    yield {type:"activity",service:"nvidia",state:"started",message:"NVIDIA AI 연결 중"};
    const answer=await chat(messages,tools,requestId,turn+1); if(!answer) throw new Error("EMPTY_LLM_RESPONSE");
    yield {type:"activity",service:"nvidia",state:"completed",message:"NVIDIA AI 응답 완료"};
    if(!answer.tool_calls?.length){
      if(tools.length)throw new Error("NVIDIA_TOOL_CALL_MISSING");
      const content=answer.content?.trim()||`검증된 곡 ${playlist?.tracks.length??0}곡을 찾았습니다.`;
      for(const delta of content.match(/.{1,16}/gs)??[]) yield {type:"text_delta",delta,progress:95};
      if(playlist) yield {type:"playlist",data:playlist};
      return;
    }
    const normalizedToolCalls=normalizeToolCalls(answer.tool_calls);messages.push({role:"assistant",content:answer.content??"",tool_calls:normalizedToolCalls});
    for(const call of normalizedToolCalls){
      let args:Record<string,unknown>; try{args=JSON.parse(call.function.arguments)}catch{messages.push({role:"tool",tool_call_id:call.id,content:JSON.stringify({error:"도구 인자 JSON 오류"})});continue;}
      if(call.function.name==="discover_music_candidates"){const terms=[...(Array.isArray(args.moods)?args.moods:[]),...(Array.isArray(args.activities)?args.activities:[])].map(String);yield {type:"insight",stage:"AI 검색 조건",message:`${terms.join(", ")||"조건 없음"} · 범위 ${String(args.region??request.region)}`};}
      const signature=`${call.function.name}:${JSON.stringify(args)}`; if(seen.has(signature))throw new Error("DUPLICATE_TOOL_CALL_BLOCKED"); seen.add(signature);
      yield {type:"tool",name:call.function.name,state:"started",message:label[call.function.name]??"도구를 실행하고 있습니다.",progress:progress[call.function.name]??15};
      const toolStarted=Date.now(); console.info(`[moodwave] ${JSON.stringify({requestId,stage:"mcp",tool:call.function.name,state:"started"})}`);
      if(call.function.name==="verify_music_tracks")args={...args,...(discoveredArtists.length?{artist_candidates:discoveredArtists}:{}),conditions:request.conditions,original_request:request.free_text??"",region:request.region};
      if(call.function.name==="compose_playlist")args={...args,conditions:request.conditions,original_request:request.free_text??"",region:request.region,track_count:request.count,familiar_artists:request.familiar_artists};
      try{if(call.function.name==="compose_playlist"){if(!Array.isArray(verifiedTracks)||verifiedTracks.length===0)throw new Error("NO_VERIFIED_TRACKS");args={...args,verified_tracks:verifiedTracks};}const result=await Promise.race([callTool<unknown>(call.function.name,args),new Promise<never>((_,reject)=>setTimeout(()=>reject(new Error("MCP_TOOL_TIMEOUT")),90_000))]);console.info(`[moodwave] ${JSON.stringify({requestId,stage:"mcp",tool:call.function.name,state:"completed",durationMs:Date.now()-toolStarted})}`);if(["discover_music_candidates","expand_similar_artists"].includes(call.function.name)&&Array.isArray(result)){const names=result.map((item)=>typeof item==="object"&&item!==null?String((item as {name?:unknown;artist_name?:unknown}).name??(item as {artist_name?:unknown}).artist_name??""):"").filter(Boolean);discoveredArtists=[...new Set([...discoveredArtists,...names])];if(call.function.name==="discover_music_candidates"&&discoveredArtists.length===0)throw new Error("NO_DISCOVERY_CANDIDATES");}if(call.function.name==="verify_music_tracks"){if(!Array.isArray(result)||result.length===0)throw new Error("NO_VERIFIED_TRACKS");verifiedTracks=result;}if(call.function.name==="compose_playlist")playlist=playlistDraftSchema.parse(result);completed.add(call.function.name);messages.push({role:"tool",tool_call_id:call.id,content:serializeToolResult(result)});yield {type:"tool_result",name:call.function.name,state:"completed",summary:call.function.name==="compose_playlist"?`${playlist?.tracks.length??0}곡을 구성했습니다.`:"완료했습니다.",progress:Math.min(95,(progress[call.function.name]??15)+10)};}
      catch(error){console.error(`[moodwave] ${JSON.stringify({requestId,stage:"mcp",tool:call.function.name,state:"failed",durationMs:Date.now()-toolStarted,error:error instanceof Error?error.message:"UNKNOWN"})}`);if(error instanceof Error&&["MCP_TOOL_TIMEOUT","NO_VERIFIED_TRACKS","NO_DISCOVERY_CANDIDATES"].includes(error.message))throw error;if(error instanceof McpTransportError)throw new Error("MCP_CONNECTION_FAILED");messages.push({role:"tool",tool_call_id:call.id,content:JSON.stringify({error:"도구 실행 실패. 인자를 수정하거나 가능한 결과로 계속하세요."})});yield {type:"tool_result",name:call.function.name,state:"failed",summary:"도구 실행에 실패했습니다.",progress:progress[call.function.name]??15};}
    }
  }
  throw new Error("AGENT_LOOP_LIMIT");
}
