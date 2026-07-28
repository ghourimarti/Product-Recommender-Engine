"use client";

import { useRef, useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Search, X, SlidersHorizontal } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import {
  type AggregatorResult,
  type Recommendation,
  offerToRecommendation,
  streamAggregate,
} from "@/lib/api";
import { Topbar }       from "@/components/dashboard/Topbar";
import { ProductCard }  from "@/components/ProductCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import { AIPanel, type AIMeta } from "@/components/AIPanel";
import { Banner }       from "@/components/Banner";

/* ── types ──────────────────────────────────────────────────────────────────── */
type Status = "idle" | "streaming" | "error";

const TRENDING = [
  "best earphones for gym",
  "wireless headphones under ₹5000",
  "noise cancelling for office",
  "budget earphones with bass",
  "premium home speakers",
  "gaming headset with mic",
];

const CATEGORIES = [
  { label: "Earphones",    q: "earphones" },
  { label: "Headphones",   q: "over ear headphones" },
  { label: "TWS Earbuds",  q: "true wireless earbuds" },
  { label: "Speakers",     q: "bluetooth speakers" },
  { label: "Gaming",       q: "gaming headset" },
  { label: "Professional", q: "studio headphones" },
];

/* ── inner component (uses useSearchParams) ──────────────────────────────── */
function DiscoverContent() {
  const searchParams = useSearchParams();
  const { getToken } = useAuth();

  /* ── state (streaming logic — verbatim from the original search page) ── */
  const [query,    setQuery]    = useState("");
  const [products, setProducts] = useState<Recommendation[]>([]);
  const [answer,   setAnswer]   = useState("");
  const [banner,   setBanner]   = useState("");
  const [status,   setStatus]   = useState<Status>("idle");
  const [meta,     setMeta]     = useState<AIMeta>({});
  const abortRef  = useRef<AbortController | null>(null);
  const inputRef  = useRef<HTMLInputElement>(null);
  const startTime = useRef<number>(0);

  /* pre-populate from URL: /dashboard/discover?q=... (hero / quick-search links) */
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      setQuery(q);
      // auto-run when arriving with a query from elsewhere in the app
      void send(q);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── live aggregator: POST /aggregate -> ranked real offers + grounded reasons ── */
  async function send(overrideQuery?: string) {
    const q = (overrideQuery ?? query).trim();
    if (!q || status === "streaming") return;
    if (overrideQuery) setQuery(overrideQuery);

    setProducts([]);
    setAnswer("");
    setBanner("");
    setMeta({});
    setStatus("streaming");
    startTime.current = Date.now();

    const controller = new AbortController();
    abortRef.current  = controller;

    try {
      const token = await getToken();
      // Cards-first streaming: render the ranked offers the moment the search returns, then fill
      // in the grounded reasons when the LLM finishes. Previously this awaited BOTH before
      // painting anything (cold: 2.94s).
      for await (const event of streamAggregate(q, token ?? undefined, 6, controller.signal)) {
        if (event.event === "offers" || event.event === "final") {
          const result = event.data as AggregatorResult;
          setProducts(result.offers.map(offerToRecommendation));
          if (result.summary) setAnswer(result.summary);

          if (event.event === "offers") {
            // First paint — cards are on screen; reasons are still being written.
            setMeta((m) => ({ ...m, cardsMs: Date.now() - startTime.current }));
          }

          // An outage must NOT read as "no good match" — that hid a dead shopping source from
          // both users and operators.
          if (result.source_unavailable) {
            setBanner(result.detail || "Live product search is temporarily unavailable.");
            setMeta((m) => ({ ...m, degraded: true }));
          } else if (result.no_match) {
            setBanner("No good match found for that request.");
          }
        }
      }
      setMeta((m) => ({ ...m, latencyMs: Date.now() - startTime.current }));
      setStatus("idle");
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

  const isStreaming  = status === "streaming";
  const hasResults   = products.length > 0;
  const showSkeleton = isStreaming && !hasResults;
  const showEmpty    = !isStreaming && !hasResults && !answer;

  /* ── render ─────────────────────────────────────────────────────────── */
  return (
    <>
      <Topbar title="Discover" subtitle="AI-powered product search" />

      {/* ── sticky search bar ── */}
      <div className="sticky top-16 z-20 bg-bg-base/90 backdrop-blur-md border-b border-bg-border">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            {/* search input */}
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-txt-muted pointer-events-none" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Describe what you're looking for…"
                disabled={isStreaming}
                className="input-search pl-10 pr-10 disabled:opacity-60 disabled:cursor-not-allowed"
              />
              {query && !isStreaming && (
                <button
                  onClick={() => { setQuery(""); inputRef.current?.focus(); }}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-txt-muted hover:text-txt-primary"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* results count pill */}
            <button className="hidden md:flex items-center gap-2 btn-secondary px-3 py-2.5 text-sm shrink-0">
              <SlidersHorizontal className="w-3.5 h-3.5" />
              3 results
            </button>

            {/* main CTA */}
            {isStreaming ? (
              <button onClick={cancel} className="btn-secondary px-5 py-2.5 text-sm shrink-0">
                Stop
              </button>
            ) : (
              <button
                onClick={() => send()}
                disabled={!query.trim()}
                className="btn-primary px-5 py-2.5 text-sm shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Recommend
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6">

        {/* ── status line ── */}
        {isStreaming && (
          <p className="text-txt-muted text-xs flex items-center gap-2 pt-4">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            {hasResults ? "Generating AI analysis…" : "Searching product catalog…"}
          </p>
        )}

        {/* ── banner ── */}
        {banner && (
          <div className="pt-4">
            <Banner
              message={banner}
              variant={status === "error" ? "error" : "warning"}
              onDismiss={() => setBanner("")}
            />
          </div>
        )}

        {/* ══ EMPTY STATE ══ */}
        {showEmpty && (
          <section className="py-12">
            <div className="text-center mb-10">
              <h2 className="text-2xl font-display font-semibold text-txt-primary mb-2">
                What are you looking for today?
              </h2>
              <p className="text-txt-secondary text-sm">
                Type a natural-language query, or pick a trending search below.
              </p>
            </div>

            <div className="mb-10">
              <p className="text-xs font-semibold text-txt-muted uppercase tracking-widest mb-3">
                Trending
              </p>
              <div className="flex flex-wrap gap-2">
                {TRENDING.map((t) => (
                  <button
                    key={t}
                    onClick={() => send(t)}
                    className="text-sm border border-bg-border hover:border-accent/50
                               text-txt-secondary hover:text-txt-primary
                               px-4 py-2 rounded-full transition-all duration-150"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <p className="text-xs font-semibold text-txt-muted uppercase tracking-widest mb-3">
              Browse by Category
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.label}
                  onClick={() => send(cat.q)}
                  className="glass-card p-4 text-left hover:border-accent/40 transition-colors group"
                >
                  <p className="font-medium text-txt-primary group-hover:text-accent transition-colors text-sm">
                    {cat.label}
                  </p>
                  <p className="text-txt-muted text-xs mt-0.5">Explore →</p>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ══ RESULTS LAYOUT ══ */}
        {(hasResults || showSkeleton || answer) && (
          <section className="py-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

              {/* LEFT — product cards */}
              <div className="lg:col-span-2 space-y-4">
                <p className="text-txt-muted text-sm mb-1">
                  {hasResults
                    ? `${products.length} recommendation${products.length !== 1 ? "s" : ""} for "${query}"`
                    : "Searching…"}
                </p>

                {showSkeleton && (
                  <div className="space-y-4">
                    <SkeletonCard />
                    <SkeletonCard />
                    <SkeletonCard />
                  </div>
                )}

                <AnimatePresence>
                  {products.map((p, i) => (
                    <ProductCard key={p.product_id} product={p} rank={i + 1} delay={i * 0.08} />
                  ))}
                </AnimatePresence>
              </div>

              {/* RIGHT — AI panel + sidebar */}
              <div className="space-y-4">
                <AIPanel answer={answer} isStreaming={isStreaming} meta={meta} />

                {!isStreaming && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-card p-4"
                  >
                    <p className="text-xs font-semibold text-txt-muted uppercase tracking-widest mb-3">
                      Try another search
                    </p>
                    <div className="space-y-1.5">
                      {TRENDING.slice(0, 3).map((t) => (
                        <button
                          key={t}
                          onClick={() => send(t)}
                          className="w-full text-left text-xs text-txt-secondary
                                     hover:text-accent py-1 transition-colors"
                        >
                          → {t}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}
              </div>
            </div>
          </section>
        )}
      </div>
    </>
  );
}

/* ── page shell with Suspense (required for useSearchParams in Next.js 15) ── */
export default function DiscoverPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-bg-base flex items-center justify-center">
          <span className="text-txt-muted text-sm">Loading…</span>
        </div>
      }
    >
      <DiscoverContent />
    </Suspense>
  );
}
