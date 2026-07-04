"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Copy, Check, BarChart3, Zap, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

export type AIMeta = {
  matchedReviews?: number;
  cached?: boolean;
  latencyMs?: number;
  model?: string;
  degraded?: boolean;
};

export function AIPanel({
  answer,
  isStreaming,
  meta,
  className,
}: {
  answer: string;
  isStreaming: boolean;
  meta?: AIMeta;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!answer) return;
    await navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const visible = !!answer || isStreaming;
  if (!visible) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: 14 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 14 }}
        transition={{ duration: 0.3 }}
        className={cn("glass-card overflow-hidden", className)}
      >
        {/* ── header ── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-bg-border">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            <span className="text-sm font-semibold text-txt-primary">AI Analysis</span>
            {isStreaming && (
              <span className="flex gap-0.5 ml-1" aria-label="streaming">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="w-1 h-1 rounded-full bg-accent"
                    animate={{ opacity: [0.25, 1, 0.25] }}
                    transition={{ duration: 1.1, delay: i * 0.18, repeat: Infinity }}
                  />
                ))}
              </span>
            )}
          </div>

          {answer && (
            <button
              onClick={copy}
              className="text-txt-muted hover:text-txt-primary transition-colors"
              aria-label="Copy analysis"
            >
              {copied ? (
                <Check className="w-4 h-4 text-status-success" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          )}
        </div>

        {/* ── body ── */}
        <div className="p-4">
          {/* skeleton while streaming before first token */}
          {!answer && isStreaming && (
            <div className="space-y-2.5">
              {[100, 80, 90, 70].map((w, i) => (
                <div
                  key={i}
                  className="skeleton-base h-3.5 rounded"
                  style={{ width: `${w}%` }}
                />
              ))}
            </div>
          )}

          {/* answer text */}
          {answer && (
            <p className="text-sm text-txt-secondary leading-relaxed whitespace-pre-wrap">
              {answer}
              {isStreaming && <span className="cursor-blink" />}
            </p>
          )}
        </div>

        {/* ── metadata footer ── */}
        {!isStreaming && answer && meta && (
          <div className="px-4 py-3 border-t border-bg-border bg-bg-elevated/40
                          flex flex-wrap gap-x-4 gap-y-1.5">
            {meta.matchedReviews != null && (
              <MetaChip icon={BarChart3} label={`${meta.matchedReviews} reviews matched`} />
            )}
            {meta.cached && <MetaChip icon={Zap} label="Semantic cache hit" />}
            {meta.latencyMs != null && (
              <MetaChip icon={Clock} label={`${(meta.latencyMs / 1000).toFixed(1)}s`} />
            )}
            {meta.model && (
              <span className="font-mono text-xs text-txt-muted">{meta.model}</span>
            )}
          </div>
        )}

        {/* degraded notice */}
        {meta?.degraded && (
          <p className="px-4 py-2.5 text-xs text-status-warning border-t border-bg-border bg-status-warning/5">
            ⚠ Explanations temporarily unavailable — showing products only.
          </p>
        )}
      </motion.div>
    </AnimatePresence>
  );
}

function MetaChip({
  icon: Icon,
  label,
}: {
  icon: typeof BarChart3;
  label: string;
}) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-txt-muted">
      <Icon className="w-3 h-3 text-accent/70 shrink-0" />
      <span>{label}</span>
    </div>
  );
}
