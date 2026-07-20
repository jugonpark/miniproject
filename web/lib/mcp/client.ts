import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";

let clientPromise: Promise<Client> | undefined;

class ToolCallError extends Error {}

async function connect(): Promise<Client> {
  const url = process.env.MCP_SERVER_URL;
  if (!url) throw new Error("MCP_SERVER_URL is not configured");

  const client = new Client({ name: "moodwave-web", version: "1.0.0" });
  await client.connect(new StreamableHTTPClientTransport(new URL(url)));
  return client;
}

function getClient(): Promise<Client> {
  return (clientPromise ??= connect());
}

function outputOf(result: CallToolResult): unknown {
  if (result.isError) {
    const message = result.content.find((item) => item.type === "text");
    throw new ToolCallError(message?.type === "text" ? message.text : "MCP tool failed");
  }
  if (result.structuredContent) {
    return "result" in result.structuredContent
      ? result.structuredContent.result
      : result.structuredContent;
  }
  const text = result.content.find((item) => item.type === "text");
  if (text?.type !== "text") return null;
  return JSON.parse(text.text) as unknown;
}

export async function callTool<T>(name: string, args: Record<string, unknown>): Promise<T> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const result = await (await getClient()).callTool({ name, arguments: args });
      return outputOf(result as CallToolResult) as T;
    } catch (error) {
      if (error instanceof ToolCallError) throw error;
      if (attempt === 1) throw error;
      const stale = clientPromise;
      clientPromise = undefined;
      void stale?.then((client) => client.close()).catch(() => undefined);
    }
  }
  throw new Error("MCP tool failed");
}
