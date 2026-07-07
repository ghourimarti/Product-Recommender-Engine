"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/* ── Container ─────────────────────────────────────────────────────────────── */
export function Container({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("max-w-7xl mx-auto px-6", className)}>{children}</div>;
}

/* ── Scroll-reveal section wrapper ─────────────────────────────────────────── */
export function Reveal({
  children, className, delay = 0, y = 24,
}: {
  children: ReactNode; className?: string; delay?: number; y?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ── Section heading ───────────────────────────────────────────────────────── */
export function SectionHeading({
  eyebrow, title, subtitle, center = true,
}: {
  eyebrow?: string; title: ReactNode; subtitle?: ReactNode; center?: boolean;
}) {
  return (
    <div className={cn("max-w-2xl", center && "mx-auto text-center")}>
      {eyebrow && <p className={cn("mkt-eyebrow mb-3", center && "justify-center flex")}>{eyebrow}</p>}
      <h2 className="text-3xl md:text-4xl font-display font-bold tracking-tight text-mkt-ink">
        {title}
      </h2>
      {subtitle && <p className="mt-4 text-mkt-body text-base md:text-lg leading-relaxed">{subtitle}</p>}
    </div>
  );
}

/* ── Eyebrow label ─────────────────────────────────────────────────────────── */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("mkt-eyebrow", className)}>{children}</span>;
}
