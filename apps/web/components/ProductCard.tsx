"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { Recommendation } from "@/lib/api";

/* ── rank badge config ────────────────────────────────────────────────────── */
const RANK: Record<number, { label: string; cls: string }> = {
  1: {
    label: "🥇 Top Pick",
    cls:   "text-rank-gold  border-rank-gold/30  bg-rank-gold/10",
  },
  2: {
    label: "🥈 Runner Up",
    cls:   "text-rank-silver border-rank-silver/30 bg-rank-silver/10",
  },
  3: {
    label: "🥉 Great Choice",
    cls:   "text-rank-bronze border-rank-bronze/30 bg-rank-bronze/10",
  },
};

/* ── star rating ──────────────────────────────────────────────────────────── */
function Stars({ rating }: { rating: number }) {
  const filled = Math.round(rating);
  return (
    <span className="flex gap-0.5" aria-label={`${rating.toFixed(1)} stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={cn("text-sm", i <= filled ? "text-rank-gold" : "text-bg-border")}
        >
          ★
        </span>
      ))}
    </span>
  );
}

/* ── relevance progress bar ───────────────────────────────────────────────── */
function RelevanceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "bg-status-success" :
    pct >= 60 ? "bg-rank-gold"      : "bg-status-warning";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-txt-muted text-xs">Relevance</span>
        <span className="font-mono text-xs text-txt-secondary">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-bg-border overflow-hidden">
        <motion.div
          className={cn("h-full rounded-full", color)}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

/* ── product initial avatar ───────────────────────────────────────────────── */
function Avatar({ title }: { title: string }) {
  return (
    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent/20 to-purple-500/20
                    border border-accent/20 flex items-center justify-center
                    text-accent font-bold font-display text-base shrink-0">
      {title[0]?.toUpperCase() ?? "P"}
    </div>
  );
}

/* ── main component ───────────────────────────────────────────────────────── */
export function ProductCard({
  product,
  rank,
  delay = 0,
}: {
  product: Recommendation;
  rank: number;
  delay?: number;
}) {
  const badge = RANK[rank];

  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: "easeOut" }}
      className="glass-card p-5 hover:border-accent/30 transition-colors duration-200 group"
    >
      {/* rank badge */}
      {badge ? (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1",
            "rounded-full border mb-3",
            badge.cls,
          )}
        >
          {badge.label}
        </span>
      ) : (
        <span className="inline-flex items-center text-xs font-medium px-2.5 py-1 mb-3
                         rounded-full border border-bg-border text-txt-muted bg-bg-elevated">
          #{rank}
        </span>
      )}

      {/* title row */}
      <div className="flex items-start gap-3 mb-3">
        <Avatar title={product.title} />
        <h3 className="font-semibold text-txt-primary leading-snug line-clamp-2
                       group-hover:text-accent transition-colors">
          {product.title}
        </h3>
      </div>

      {/* rating row */}
      <div className="flex items-center gap-2 mb-4">
        <Stars rating={product.avg_rating} />
        <span className="font-mono text-sm text-txt-secondary">
          {product.avg_rating.toFixed(1)}
        </span>
        {product.review_count != null && (
          <>
            <span className="text-txt-muted text-xs">·</span>
            <span className="text-txt-muted text-xs">{product.review_count} reviews</span>
          </>
        )}
      </div>

      {/* relevance bar */}
      <RelevanceBar score={product.final_score} />

      {/* footer */}
      <div className="mt-3 pt-3 border-t border-bg-border flex items-center justify-between">
        <span className="font-mono text-xs text-txt-muted">
          {product.product_id.slice(0, 10)}…
        </span>
        <span className="text-xs text-accent cursor-default select-none">
          See analysis →
        </span>
      </div>
    </motion.article>
  );
}
