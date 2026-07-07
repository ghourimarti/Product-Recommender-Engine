"use client";

import { useState, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Quote } from "lucide-react";
import { cn } from "@/lib/utils";
import { Container } from "./primitives";

type Slide = {
  quote: string;
  name: string;
  role: string;
  company: string;
  metric?: { value: string; label: string };
};

const SLIDES: Slide[] = [
  {
    quote:
      "ProductIQ turned our search bar from a keyword box into an actual assistant. Shoppers describe what they want and land on the right product — with a reason they trust.",
    name: "Meera Kapoor",
    role: "Head of Ecommerce",
    company: "SoundWave",
    metric: { value: "+18%", label: "search conversion" },
  },
  {
    quote:
      "The rating-aware ranking was the unlock. We stopped surfacing thinly-reviewed products that gamed our old star sort. Returns dropped noticeably.",
    name: "David Lin",
    role: "Director of Product",
    company: "PulseGear",
    metric: { value: "-12%", label: "return rate" },
  },
  {
    quote:
      "Transparent scoring built instant trust with our customers. Being able to see why something ranked where it did is a feature our competitors simply don't have.",
    name: "Ana Torres",
    role: "VP Digital",
    company: "EchoStore",
    metric: { value: "4.8/5", label: "CSAT after launch" },
  },
];

export function TestimonialCarousel() {
  const [i, setI] = useState(0);
  const [dir, setDir] = useState(1);

  const go = useCallback((next: number) => {
    setDir(next > i ? 1 : -1);
    setI((next + SLIDES.length) % SLIDES.length);
  }, [i]);

  // auto-advance
  useEffect(() => {
    const t = setInterval(() => { setDir(1); setI((p) => (p + 1) % SLIDES.length); }, 6500);
    return () => clearInterval(t);
  }, []);

  const s = SLIDES[i];

  return (
    <div className="py-24 bg-mkt-surface border-y border-mkt-border overflow-hidden">
      <Container>
        <div className="max-w-4xl mx-auto">
          <div className="relative min-h-[280px]">
            <AnimatePresence mode="wait" custom={dir}>
              <motion.figure
                key={i}
                custom={dir}
                initial={{ opacity: 0, x: dir * 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: dir * -40 }}
                transition={{ duration: 0.4 }}
                className="text-center"
              >
                <Quote className="w-10 h-10 text-mkt-brand/30 mx-auto mb-6" />
                <blockquote className="text-xl md:text-2xl font-display text-mkt-ink leading-relaxed">
                  &ldquo;{s.quote}&rdquo;
                </blockquote>

                <figcaption className="mt-8 flex items-center justify-center gap-4">
                  <span className="w-12 h-12 rounded-full bg-gradient-to-br from-mkt-brand to-mkt-teal
                                   flex items-center justify-center text-white font-semibold">
                    {s.name[0]}
                  </span>
                  <div className="text-left">
                    <p className="font-semibold text-mkt-ink text-sm">{s.name}</p>
                    <p className="text-xs text-mkt-muted">{s.role}, {s.company}</p>
                  </div>
                  {s.metric && (
                    <div className="hidden sm:block pl-6 ml-2 border-l border-mkt-border text-left">
                      <p className="text-2xl font-display font-bold text-mkt-teal">{s.metric.value}</p>
                      <p className="text-xs text-mkt-muted">{s.metric.label}</p>
                    </div>
                  )}
                </figcaption>
              </motion.figure>
            </AnimatePresence>
          </div>

          {/* controls */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <button onClick={() => go(i - 1)}
              className="w-9 h-9 rounded-full border border-mkt-border bg-white flex items-center justify-center
                         text-mkt-body hover:text-mkt-brand hover:border-mkt-brand/40 transition-colors"
              aria-label="Previous">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2">
              {SLIDES.map((_, idx) => (
                <button key={idx} onClick={() => go(idx)}
                  className={cn("h-1.5 rounded-full transition-all",
                    idx === i ? "w-6 bg-mkt-brand" : "w-1.5 bg-mkt-border hover:bg-mkt-muted")}
                  aria-label={`Slide ${idx + 1}`} />
              ))}
            </div>
            <button onClick={() => go(i + 1)}
              className="w-9 h-9 rounded-full border border-mkt-border bg-white flex items-center justify-center
                         text-mkt-body hover:text-mkt-brand hover:border-mkt-brand/40 transition-colors"
              aria-label="Next">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </Container>
    </div>
  );
}
