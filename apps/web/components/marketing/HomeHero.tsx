"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Search, ArrowRight, Award, Star, Sparkles } from "lucide-react";
import { Container } from "./primitives";

const EXAMPLES = ["wireless earbuds under ₹2000", "ANC for the office", "bass speakers for home"];

export function HomeHero() {
  const router = useRouter();
  const [q, setQ] = useState("");

  const go = () =>
    router.push(q.trim() ? `/dashboard/discover?q=${encodeURIComponent(q)}` : "/dashboard/discover");

  return (
    <div className="relative overflow-hidden pt-28 pb-20 md:pt-36">
      {/* backgrounds */}
      <div className="absolute inset-0 mkt-hero-glow pointer-events-none" />
      <div className="absolute inset-x-0 top-0 h-[520px] mkt-dotgrid opacity-[0.55]
                      [mask-image:radial-gradient(ellipse_60%_60%_at_50%_0%,black,transparent)] pointer-events-none" />

      <Container className="relative">
        <div className="grid lg:grid-cols-2 gap-14 items-center">

          {/* ── left: copy ── */}
          <div>
            {/* award badge */}
            <motion.div
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
              className="inline-flex items-center gap-2 rounded-full border border-mkt-border bg-white
                         px-3 py-1.5 text-xs font-medium text-mkt-body shadow-sm mb-6"
            >
              <Award className="w-3.5 h-3.5 text-mkt-teal" />
              Rated 4.8/5 by 2,400+ users
              <span className="text-mkt-brand font-semibold">Read reviews →</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.05 }}
              className="text-4xl md:text-[3.4rem] font-display font-bold tracking-tight leading-[1.05] text-mkt-ink"
            >
              The AI discovery engine <span className="mkt-gradient">powering commerce</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.12 }}
              className="mt-5 text-lg text-mkt-body leading-relaxed max-w-xl"
            >
              ProductIQ doesn&apos;t just search — it reasons. Semantic retrieval, rating-aware
              ranking, and grounded explanations that tell shoppers exactly why a product fits.
            </motion.p>

            {/* search */}
            <motion.div
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}
              className="mt-8 max-w-xl"
            >
              <div className="relative flex items-center">
                <Search className="absolute left-4 w-5 h-5 text-mkt-muted pointer-events-none" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && go()}
                  placeholder="Describe what you're looking for…"
                  className="w-full bg-white border border-mkt-border rounded-xl pl-12 pr-32 py-3.5
                             text-mkt-ink placeholder:text-mkt-muted shadow-sm
                             focus:outline-none focus:ring-2 focus:ring-mkt-brand/25 focus:border-mkt-brand/50 transition-all"
                />
                <button onClick={go} className="mkt-btn-primary absolute right-2 px-4 py-2 text-sm">
                  Try it <ArrowRight className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-mkt-muted">Try:</span>
                {EXAMPLES.map((e) => (
                  <button key={e} onClick={() => router.push(`/dashboard/discover?q=${encodeURIComponent(e)}`)}
                    className="text-mkt-body hover:text-mkt-brand underline-offset-4 hover:underline transition-colors">
                    &ldquo;{e}&rdquo;
                  </button>
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, delay: 0.3 }}
              className="mt-8 flex items-center gap-6 text-sm text-mkt-muted"
            >
              <Link href="/pricing" className="mkt-btn-ghost">See pricing</Link>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-mkt-teal" /> No credit card required
              </span>
            </motion.div>
          </div>

          {/* ── right: animated result mockup ── */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.15 }}
            className="relative"
          >
            <div className="mkt-card p-5 shadow-2xl shadow-slate-300/50">
              {/* browser chrome */}
              <div className="flex items-center gap-1.5 mb-4">
                <span className="w-3 h-3 rounded-full bg-red-400/70" />
                <span className="w-3 h-3 rounded-full bg-amber-400/70" />
                <span className="w-3 h-3 rounded-full bg-green-400/70" />
                <span className="ml-3 text-xs text-mkt-muted font-mono">productiq.app/discover</span>
              </div>

              <div className="flex items-center gap-2 bg-mkt-surface border border-mkt-border rounded-lg px-3 py-2 mb-4">
                <Search className="w-4 h-4 text-mkt-muted" />
                <span className="text-sm text-mkt-body font-mono">wireless earbuds for gym, good bass</span>
              </div>

              {/* result cards */}
              <div className="space-y-2.5">
                {[
                  { rank: "🥇", name: "SoundWave Pulse Pro", rating: 4.5, score: 92 },
                  { rank: "🥈", name: "PulseGear Active TWS", rating: 4.3, score: 84 },
                  { rank: "🥉", name: "EchoStore FitBuds",   rating: 4.1, score: 76 },
                ].map((r, idx) => (
                  <motion.div
                    key={r.name}
                    initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + idx * 0.15 }}
                    className="flex items-center gap-3 border border-mkt-border rounded-lg p-3 bg-white"
                  >
                    <span className="text-lg">{r.rank}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-mkt-ink truncate">{r.name}</p>
                      <p className="text-xs text-mkt-muted flex items-center gap-1">
                        <Star className="w-3 h-3 text-rank-gold fill-rank-gold" /> {r.rating}
                        <span className="mx-1">·</span> {r.score}% match
                      </p>
                    </div>
                    <div className="w-16 h-1.5 rounded-full bg-mkt-elevated overflow-hidden">
                      <motion.div className="h-full bg-mkt-teal rounded-full"
                        initial={{ width: 0 }} animate={{ width: `${r.score}%` }}
                        transition={{ delay: 0.7 + idx * 0.15, duration: 0.5 }} />
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* AI reason */}
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.1 }}
                className="mt-4 flex items-start gap-2 bg-mkt-brand/5 border border-mkt-brand/15 rounded-lg p-3"
              >
                <Sparkles className="w-4 h-4 text-mkt-brand shrink-0 mt-0.5" />
                <p className="text-xs text-mkt-body leading-relaxed">
                  The Pulse Pro leads for gym use — reviewers highlight secure fit and deep bass across 47 reviews.
                </p>
              </motion.div>
            </div>

            {/* floating badge */}
            <motion.div
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.3 }}
              className="absolute -bottom-4 -left-4 bg-white rounded-xl border border-mkt-border shadow-lg px-4 py-2.5
                         hidden sm:flex items-center gap-2"
            >
              <span className="text-2xl font-display font-bold text-mkt-teal">&lt;800ms</span>
              <span className="text-xs text-mkt-muted leading-tight">median<br />response</span>
            </motion.div>
          </motion.div>
        </div>
      </Container>
    </div>
  );
}
