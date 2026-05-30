"use client";

import { useRef, useState } from "react";

import { type Recommendation, type RecommendationsPayload, streamChat } from "@/lib/api";

type Status = "idle" | "streaming" | "error";

export default function Home() {
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<Recommendation[]>([]);
  const [answer, setAnswer] = useState("");
  const [banner, setBanner] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = "web-session";

  async function send() {
    if (!query.trim() || status === "streaming") return;
    setProducts([]);
    setAnswer("");
    setBanner("");
    setStatus("streaming");

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      for await (const event of streamChat(query, sessionId, controller.signal)) {
        if (event.event === "recommendations") {
          // Cards render first (Decision 8) — before any explanation tokens arrive.
          const payload = event.data as RecommendationsPayload;
          setProducts(payload.products ?? []);
          if (payload.no_match) setBanner("No good match found for that request.");
        } else if (event.event === "token") {
          const { text } = event.data as { text: string };
          setAnswer((prev) => prev + text);
        } else if (event.event === "done") {
          const { degraded } = event.data as { degraded?: boolean };
          if (degraded) setBanner("Explanations are temporarily unavailable.");
          setStatus("idle");
        }
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") setStatus("idle");
      else {
        setStatus("error");
        setBanner("Something went wrong. Is the API running?");
      }
    }
  }

  function cancel() {
    abortRef.current?.abort();
    setStatus("idle");
  }

  return (
    <main className="container">
      <h1>Audio Product Recommender</h1>
      <div className="input-row">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && send()}
          placeholder="e.g. good bass earphones for the gym"
        />
        {status === "streaming" ? (
          <button onClick={cancel}>Stop</button>
        ) : (
          <button onClick={send}>Recommend</button>
        )}
      </div>

      {banner && <p className="banner">{banner}</p>}

      <section className="cards">
        {products.map((product) => (
          <article key={product.product_id} className="card">
            <h3>{product.title}</h3>
            <p>
              ★ {product.avg_rating.toFixed(2)} · score {product.final_score.toFixed(3)}
            </p>
          </article>
        ))}
      </section>

      {answer && (
        <section className="answer">
          <p>{answer}</p>
        </section>
      )}
    </main>
  );
}
