/**
 * Honest framing banner.
 *
 * This site is a portfolio/demo build, not a live commercial service. It previously shipped
 * fabricated social proof — "2,400+ users", "12,000+ active shoppers", "98.9% uptime", invented
 * customer logos and testimonials — none of which the backend could support (zero real users,
 * no uptime monitoring). Presenting that to a client is misrepresentation, so the fake proof was
 * removed and replaced with this notice plus measured numbers only.
 */
import { Info } from "lucide-react";

export function DemoNotice() {
  return (
    <div className="w-full bg-mkt-ink/[0.04] border-b border-mkt-ink/10">
      <div className="mx-auto max-w-6xl px-6 py-2.5 flex items-center justify-center gap-2 text-center">
        <Info className="w-3.5 h-3.5 shrink-0 text-mkt-teal" aria-hidden />
        <p className="text-xs text-mkt-muted">
          <span className="font-semibold text-mkt-ink">Demo build.</span>{" "}
          Product search is live and real. Pricing, customers and testimonials are illustrative —
          this service has no paying users and has not run in production.
        </p>
      </div>
    </div>
  );
}
