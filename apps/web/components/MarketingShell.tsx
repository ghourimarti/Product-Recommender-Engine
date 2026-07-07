import type { ReactNode } from "react";
import { MarketingNavbar } from "@/components/marketing/MarketingNavbar";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";

/**
 * Wraps every marketing page with the light theme, mega-menu nav, and footer.
 * The `.theme-light` class scopes the light palette so the dark dashboard is
 * completely unaffected.
 */
export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="theme-light min-h-screen flex flex-col bg-mkt-bg">
      <MarketingNavbar />
      <main className="flex-1 pt-16">{children}</main>
      <MarketingFooter />
    </div>
  );
}

/** Centered page header for interior marketing pages (light theme). */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="relative overflow-hidden border-b border-mkt-border bg-mkt-surface">
      <div className="absolute inset-0 mkt-hero-glow pointer-events-none" />
      <div className="relative max-w-3xl mx-auto px-6 py-20 md:py-24 text-center">
        {eyebrow && <p className="mkt-eyebrow mb-3 justify-center flex">{eyebrow}</p>}
        <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight text-mkt-ink">
          {title}
        </h1>
        {subtitle && <p className="mt-4 text-lg text-mkt-body leading-relaxed">{subtitle}</p>}
      </div>
    </div>
  );
}
