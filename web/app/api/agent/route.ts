import { runAgent } from "@/lib/agent/agent-loop";
import { agentError } from "@/lib/agent/error";
import { musicRequestSchema } from "@/lib/schemas/music";

const encoder = new TextEncoder();
const line = (value: unknown) => encoder.encode(`${JSON.stringify(value)}\n`);

export async function POST(raw: Request) {
  let request: ReturnType<typeof musicRequestSchema.parse>;
  try { request = musicRequestSchema.parse(await raw.json()); }
  catch { return Response.json({ error:"감정 또는 추천 조건을 입력해 주세요." }, { status:400 }); }

  const stream = new ReadableStream({
    async start(controller) {
      const send = (value: unknown) => controller.enqueue(line(value));
      try {
        for await (const event of runAgent(request)) send(event);
        send({ type:"done", ok:true });
      } catch (error) {
        console.error("agent request failed", error instanceof Error ? error.message : "UNKNOWN");
        send({ type:"error", ...agentError(error) });
        send({ type:"done", ok:false });
      } finally { controller.close(); }
    },
  });
  return new Response(stream, { headers:{ "Content-Type":"application/x-ndjson; charset=utf-8", "Cache-Control":"no-store" } });
}
