import { runAgent } from "@/lib/agent/agent-loop";
import { musicRequestSchema } from "@/lib/schemas/music";

const encoder = new TextEncoder();
const line = (value: unknown) => encoder.encode(`${JSON.stringify(value)}\n`);

export async function POST(raw: Request) {
  let request: ReturnType<typeof musicRequestSchema.parse>;
  try { request = musicRequestSchema.parse(await raw.json()); }
  catch { return Response.json({ error:"조건 또는 추가 요청을 입력해 주세요." }, { status:400 }); }

  const stream = new ReadableStream({
    async start(controller) {
      const send = (value: unknown) => controller.enqueue(line(value));
      try {
        for await (const event of runAgent(request)) send(event);
        send({ type:"done" });
      } catch (error) {
        console.error("agent request failed", error instanceof Error ? error.message : "UNKNOWN");
        const missing=error instanceof Error&&error.message==="NVIDIA_API_KEY_MISSING";
        const timeout=error instanceof Error&&(error.message==="MCP_TOOL_TIMEOUT"||error.name==="TimeoutError");
        send({ type:"error", code:missing?"NVIDIA_API_KEY_MISSING":timeout?"UPSTREAM_TIMEOUT":"AGENT_FAILED", message:missing?"NVIDIA API 키가 설정되지 않았습니다.":timeout?"음악 서비스 응답이 늦어 요청을 종료했습니다. 잠시 후 다시 시도해 주세요.":"추천 생성에 실패했습니다. 서버 로그의 오류 코드를 확인해 주세요." });
        send({ type:"done" });
      } finally { controller.close(); }
    },
  });
  return new Response(stream, { headers:{ "Content-Type":"application/x-ndjson; charset=utf-8", "Cache-Control":"no-store" } });
}
