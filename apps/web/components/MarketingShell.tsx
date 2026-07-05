import type { ReactNode } from "react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";

/** Wraps every marketing page with the nav + footer + top offset for the fixed navbar. */
export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-bg-base">
      <Navbar />
      <main className="flex-1 pt-16">{children}</main>
      <Footer />
    </div>
  );
}

/** Simple centered page header for interior marketing pages. */
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
    <div className="relative overflow-hidden border-b border-bg-border">
      <div className="absolute inset-0 bg-grid-glow pointer-events-none" />
      <div className="relative max-w-3xl mx-auto px-6 py-20 md:py-24 text-center">
        {eyebrow && (
          <p className="text-accent text-sm font-semibold uppercase tracking-widest mb-3">
            {eyebrow}
          </p>
        )}
        <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight text-txt-primary">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-4 text-lg text-txt-secondary leading-relaxed">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
