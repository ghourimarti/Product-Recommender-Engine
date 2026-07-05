import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/* ── Container ─────────────────────────────────────────────────────────────── */
export function Container({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("max-w-7xl mx-auto px-6", className)}>{children}</div>;
}

/* ── Section ───────────────────────────────────────────────────────────────── */
export function Section({
  children,
  className,
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={cn("py-20 md:py-28", className)}>
      {children}
    </section>
  );
}

/* ── Eyebrow (small label above headings) ─────────────────────────────────── */
export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase
                     tracking-[0.2em] text-accent mb-4">
      <span className="w-6 h-px bg-accent/50" />
      {children}
    </span>
  );
}

/* ── Section heading block ─────────────────────────────────────────────────── */
export function SectionHeading({
  eyebrow,
  title,
  subtitle,
  center = true,
}: {
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  center?: boolean;
}) {
  return (
    <div className={cn("max-w-2xl", center && "mx-auto text-center")}>
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="text-3xl md:text-4xl font-display font-bold tracking-tight text-txt-primary">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-4 text-txt-secondary text-base md:text-lg leading-relaxed">
          {subtitle}
        </p>
      )}
    </div>
  );
}

/* ── Button ────────────────────────────────────────────────────────────────── */
type ButtonProps = {
  children: ReactNode;
  href?: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  className?: string;
  onClick?: () => void;
  external?: boolean;
  type?: "button" | "submit";
};

const SIZES = {
  sm: "px-3.5 py-2 text-sm",
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3 text-base",
};

const VARIANTS = {
  primary:   "btn-primary",
  secondary: "btn-secondary",
  ghost:     "btn-ghost",
};

export function Button({
  children,
  href,
  variant = "primary",
  size = "md",
  className,
  onClick,
  external,
  type = "button",
}: ButtonProps) {
  const classes = cn(VARIANTS[variant], SIZES[size], className);

  if (href) {
    if (external) {
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className={classes}>
          {children}
        </a>
      );
    }
    return (
      <Link href={href} className={classes}>
        {children}
      </Link>
    );
  }
  return (
    <button type={type} onClick={onClick} className={classes}>
      {children}
    </button>
  );
}

/* ── Badge / Pill ──────────────────────────────────────────────────────────── */
export function Pill({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-bg-border",
        "bg-bg-surface px-3 py-1 text-xs text-txt-secondary",
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ── Card ──────────────────────────────────────────────────────────────────── */
export function Card({
  children,
  className,
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <div
      className={cn(
        "glass-card p-6",
        hover && "hover:border-accent/30 transition-colors duration-200",
        className,
      )}
    >
      {children}
    </div>
  );
}
