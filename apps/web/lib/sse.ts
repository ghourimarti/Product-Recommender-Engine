// Minimal SSE buffer parser. Pure + framework-free so it is easy to reason about/test.

export type SSEEvent = { event: string; data: unknown };

/**
 * Parse complete `event:/data:` blocks out of an accumulating buffer.
 * Returns the parsed events plus any trailing partial block to carry forward.
 */
export function parseSSEBuffer(buffer: string): { events: SSEEvent[]; rest: string } {
  const events: SSEEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";

  for (const block of blocks) {
    let event = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice("event:".length).trim();
      else if (line.startsWith("data:")) data += line.slice("data:".length).trim();
    }
    if (!data) continue;
    try {
      events.push({ event, data: JSON.parse(data) });
    } catch {
      events.push({ event, data });
    }
  }
  return { events, rest };
}
