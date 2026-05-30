// SSE streaming client for the chat API (Decision 8).
// EventSource can't POST, so we POST and read the response stream manually, parsing the
// `event:`/`data:` SSE frames. Supports cancellation via AbortSignal.

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface Citation {
  product_name: string;
  snippet?: string;
}

export type StreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "citations"; data: { items: Citation[] } }
  | { event: "done"; data: { session_id: string } }
  | { event: "error"; data: { detail: string } };

function parseFrame(frame: string): StreamEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) } as StreamEvent;
  } catch {
    return null;
  }
}

export async function* streamChat(
  message: string,
  sessionId: string | null,
  token: string | null,
  signal: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  });

  if (!res.ok || !res.body) {
    yield { event: "error", data: { detail: `HTTP ${res.status}` } };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const parsed = parseFrame(frame);
      if (parsed) yield parsed;
    }
  }
}
