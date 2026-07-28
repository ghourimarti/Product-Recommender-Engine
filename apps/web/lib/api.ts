import { parseSSEBuffer, type SSEEvent } from "./sse";

const API_URL   = process.env.NEXT_PUBLIC_API_URL  ?? "http://localhost:2011";
const DEV_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN ?? "";

export type Recommendation = {
  product_id:    string;
  title:         string;
  avg_rating:    number;
  review_count?: number;   // present if backend sends it
  final_score:   number;
  // Optional live-aggregator fields (present on /aggregate results, absent on /chat):
  price?:        number | null;
  currency?:     string;
  store?:        string;
  product_url?:  string;
  thumbnail?:    string | null;
  reason?:       string;
};

/* ── live aggregator (/aggregate) types ─────────────────────────────────────── */
export type OfferT = {
  product_id: string;
  title: string;
  price: number | null;
  currency: string;
  store: string;
  product_url: string;
  thumbnail: string | null;
  rating: number | null;
  review_count: number;
  snippet: string;
  position: number;
};

export type RankedOfferT = {
  offer: OfferT;
  final_score: number;
  relevance_score: number;
  rating_score: number;
  volume_confidence: number;
  reason: string;
};

export type AggregatorResult = {
  query: string;
  summary: string;
  offers: RankedOfferT[];
  /** We searched successfully and nothing was relevant. */
  no_match: boolean;
  /** The shopping source failed / the search budget is exhausted — an OUTAGE, not an empty result.
   *  These used to be conflated, so a dead SerpApi looked exactly like "no products matched". */
  source_unavailable?: boolean;
  detail?: string;
};

/** Map a ranked live offer into the Recommendation shape ProductCard renders. */
export function offerToRecommendation(r: RankedOfferT): Recommendation {
  return {
    product_id:   r.offer.product_id,
    title:        r.offer.title,
    avg_rating:   r.offer.rating ?? 0,
    review_count: r.offer.review_count,
    final_score:  r.final_score,
    price:        r.offer.price,
    currency:     r.offer.currency,
    store:        r.offer.store,
    product_url:  r.offer.product_url,
    thumbnail:    r.offer.thumbnail,
    reason:       r.reason,
  };
}

/** Live shopping aggregator: POST /aggregate (non-streaming; cached server-side). */
export async function aggregate(
  query: string,
  authToken?: string,
  k = 6,
  signal?: AbortSignal,
): Promise<AggregatorResult> {
  const token = authToken || DEV_TOKEN;
  const response = await fetch(`${API_URL}/aggregate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, k }),
    signal,
  });
  if (!response.ok) throw new Error(`aggregate request failed: ${response.status}`);
  return response.json() as Promise<AggregatorResult>;
}

/**
 * Streaming aggregator: POST /aggregate/stream (SSE).
 *
 * Emits `offers` (ranked cards, no reasons yet) as soon as the shopping search returns, then
 * `final` (same cards + grounded reasons + summary). The blocking `aggregate()` above made the
 * user wait for the search AND the LLM before anything rendered (cold: 2.94s). This paints the
 * cards ~1-1.5s earlier — and it is what makes the SSE path something the UI actually uses.
 */
export async function* streamAggregate(
  query: string,
  authToken?: string,
  k = 6,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const token = authToken || DEV_TOKEN;
  const response = await fetch(`${API_URL}/aggregate/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, k }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`aggregate stream failed: ${response.status}`);
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
