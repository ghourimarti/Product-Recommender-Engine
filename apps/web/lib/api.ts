import { parseSSEBuffer, type SSEEvent } from "./sse";

const API_URL   = process.env.NEXT_PUBLIC_API_URL  ?? "http://localhost:2011";
const DEV_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";

export type Recommendation = {
  product_id:    string;
  title:         string;
  avg_rating:    number;
  review_count?: number;   // present if backend sends it
  final_score:   number;
};

export type RecommendationsPayload = {
  products:  Recommendation[];
  no_match:  boolean;
};

/**
 * Stream the /chat SSE response as parsed events (recommendations → token → done).
 * authToken is optional — falls back to DEV_TOKEN for local dev without Clerk.
 */
export async function* streamChat(
  query:     string,
  sessionId: string,
  signal:    AbortSignal,
  authToken?: string,
): AsyncGenerator<SSEEvent> {
  // Prefer the real Clerk session token when the user is signed in — that's what
  // an RS256 backend (CLERK_JWKS_URL set) accepts. Fall back to DEV_TOKEN only
  // when Clerk hasn't issued one AND a dev token was explicitly baked in
  // (NEXT_PUBLIC_DEV_TOKEN in .env). Priority order matters: without this flip,
  // an empty-but-truthy build-time default would beat a real Clerk token → 401.
  const token = authToken || DEV_TOKEN;

  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, session_id: sessionId, k: 3 }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`chat request failed: ${response.status}`);
  }

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer    = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSSEBuffer(buffer);
    buffer = rest;
    for (const event of events) yield event;
  }
}
