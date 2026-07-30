"use client";

import { useEffect, useRef, useState } from "react";
import { Container, SectionHeading } from "./primitives";

type Metric = { value: number; prefix?: string; suffix?: string; decimals?: number; label: string };

/* Every number here must be verifiable by a reader who has only this repository.
   That bar has now cost two rounds of claims:

   1. Fabricated — "10,000+ products", "500k+ reviews", "98.9% uptime". The catalog is 9 seed
      products plus live Google-Shopping offers, and uptime has never been measured (no SLO
      monitor exists). Removed.
   2. Measured but unevidenced — "7.6ms p95 cached" and "66% cache hit rate". Both came from a
      real local k6 run, but no result artifact was ever committed, so a visitor could not check
      either one. Under a heading that promises reproducibility that is the same failure as (1),
      just smaller, so they are removed too rather than quietly kept.

   What replaces them is true by inspection of committed files:
     117  — `uv run pytest --collect-only -q`  (108 offline + 9 integration)
     0    — unignored advisories; pip-audit + npm audit BLOCK every PR (.github/workflows/ci.yml)
     3    — Groq -> OpenAI -> Anthropic fallback chain (packages/core/llm.py)
     6h   — AGGREGATE_TTL_SECONDS (packages/recommender/aggregator.py)

   Keep the test count in sync with the collect command. A stale number here is worse than no
   number, because the repro command sits one line away in the same section. */
const METRICS: Metric[] = [
  { value: 117,   suffix: "",   label: "Automated tests in CI" },
  { value: 0,     suffix: "",   label: "Unignored dependency CVEs (scan blocks every PR)" },
  { value: 3,     suffix: "",   label: "LLM providers, automatic failover" },
  { value: 6,     suffix: "h",  label: "Result cache — a repeat query is free" },
];

function useCountUp(target: number, decimals = 0, run = false) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) return;
    const start = performance.now();
    const dur = 1500;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min((now - start) / dur, 1);
      setV(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run, target]);
  return decimals ? v.toFixed(decimals) : Math.round(v).toLocaleString();
}

function Stat({ m, run }: { m: Metric; run: boolean }) {
  const d = useCountUp(m.value, m.decimals ?? 0, run);
  return (
    <div className="text-center">
      <p className="text-4xl md:text-5xl font-display font-bold text-mkt-ink tabular-nums">
        {m.prefix}{d}<span className="text-mkt-teal">{m.suffix}</span>
      </p>
      <p className="mt-2 text-sm text-mkt-muted">{m.label}</p>
    </div>
  );
}

export function MetricsBar({
  eyebrow = "Measured, not claimed",
  title = "Every number here is reproducible",
}: { eyebrow?: string; title?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [run, setRun] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => e.isIntersecting && setRun(true), { threshold: 0.3 });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div className="py-24" ref={ref}>
      <Container>
        <SectionHeading eyebrow={eyebrow} title={title} />
        <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-10">
          {METRICS.map((m) => <Stat key={m.label} m={m} run={run} />)}
        </div>
      </Container>
    </div>
  );
}
