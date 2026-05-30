import { parseSSEBuffer, type SSEEvent } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
const DEV_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";

export type Recommendation = {
  product_id: string;
  title: string;
  avg_rating: number;
  final_score: number;
};

export type RecommendationsPayload = { products: Recommendation[]; no_match: boolean };

/** Stream the /chat SSE response as parsed events (recommendations -> token -> done). */
export async function* streamChat(
  query: string,
  sessionId: string,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(DEV_TOKEN ? { Authorization: `Bearer ${DEV_TOKEN}` } : {}),
    },
    body: JSON.stringify({ query, session_id: sessionId, k: 3 }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSSEBuffer(buffer);
    buffer = rest;
    for (const event of events) yield event;
  }
}
