import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { CallToolResultSchema } from "@modelcontextprotocol/sdk/types.js";

let clientPromise: Promise<Client> | undefined;

export class McpToolError extends Error {
  readonly notFound: boolean;

  constructor(message: string) {
    super(message);
    this.notFound = /\bnot found\b/i.test(message);
  }
}

export class McpResponseError extends Error {}
export class McpTransportError extends Error {}

async function connect(): Promise<Client> {
  const url = process.env.MCP_SERVER_URL;
  if (!url) throw new Error("MCP_SERVER_URL is not configured");
  const apiKey = process.env.FASTMCP_API_KEY;

  const client = new Client({ name: "moodwave-web", version: "1.0.0" });
  await client.connect(new StreamableHTTPClientTransport(new URL(url), apiKey ? {
    requestInit: { headers: { Authorization: `Bearer ${apiKey}` } },
  } : undefined));
  return client;
}

function getClient(): Promise<Client> {
  return (clientPromise ??= connect());
}

function outputOf(raw: unknown): unknown {
  const parsed = CallToolResultSchema.safeParse(raw);
  if (!parsed.success) throw new McpResponseError("MCP returned an invalid result");
  const result = parsed.data;
  if (result.isError) {
    const message = result.content.find((item) => item.type === "text");
    throw new McpToolError(message?.type === "text" ? message.text : "MCP tool failed");
  }
  if (result.structuredContent) {
    return "result" in result.structuredContent
      ? result.structuredContent.result
      : result.structuredContent;
  }
  const text = result.content.find((item) => item.type === "text");
  if (text?.type !== "text") return null;
  try {
    return JSON.parse(text.text) as unknown;
  } catch {
    throw new McpResponseError("MCP returned invalid JSON");
  }
}

async function discardClient(used: Promise<Client>): Promise<void> {
  if (clientPromise !== used) return;
  clientPromise = undefined;
  try {
    await (await used).close();
  } catch {
    // A failed connection has nothing usable to close.
  }
}

export async function callTool<T>(name: string, args: Record<string, unknown>): Promise<T> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const used = getClient();
    try {
      const result = await (await used).callTool({ name, arguments: args });
      return outputOf(result) as T;
    } catch (error) {
      if (error instanceof McpToolError || error instanceof McpResponseError) throw error;
      if (attempt === 1) throw new McpTransportError("MCP request failed", { cause: error });
      await discardClient(used);
    }
  }
  throw new Error("MCP tool failed");
}
