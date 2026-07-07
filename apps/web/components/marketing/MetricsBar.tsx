"use client";

import { useEffect, useRef, useState } from "react";
import { Container, SectionHeading } from "./primitives";

type Metric = { value: number; prefix?: string; suffix?: string; decimals?: number; label: string };

const METRICS: Metric[] = [
  { value: 10000, suffix: "+",  label: "Products indexed" },
  { value: 500,   suffix: "k+", label: "Reviews analyzed" },
  { value: 800,   prefix: "<", suffix: "ms", label: "Median response" },
  { value: 98.9,  suffix: "%",  label: "Uptime SLO", decimals: 1 },
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
  eyebrow = "By the numbers",
  title = "Built to perform at scale",
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
