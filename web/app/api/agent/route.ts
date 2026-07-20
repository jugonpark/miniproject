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
        const missing=error instanceof Error&&error.message==="NVIDIA_API_KEY_MISSING";
        send({ type:"error", code:missing?"NVIDIA_API_KEY_MISSING":"AGENT_FAILED", message:missing?"NVIDIA API 키가 설정되지 않았습니다.":"추천을 만드는 중 문제가 발생했습니다. NVIDIA와 MCP 설정을 확인해 주세요." });
        send({ type:"done" });
      } finally { controller.close(); }
    },
  });
  return new Response(stream, { headers:{ "Content-Type":"application/x-ndjson; charset=utf-8", "Cache-Control":"no-store" } });
}
