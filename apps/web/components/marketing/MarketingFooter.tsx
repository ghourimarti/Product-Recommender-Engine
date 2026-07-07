import Link from "next/link";
import { Zap, Twitter, Linkedin, Github } from "lucide-react";
import { SOLUTIONS, INDUSTRIES, RESOURCES } from "@/lib/nav";

const COMPANY = [
  { label: "About",   href: "/about" },
  { label: "Customers", href: "/customers" },
  { label: "Pricing", href: "/pricing" },
  { label: "Contact", href: "/contact" },
  { label: "Careers", href: "#" },
];

const LEGAL = [
  { label: "Privacy Policy",   href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
  { label: "Security",         href: "#" },
  { label: "GDPR",             href: "#" },
];

function Col({ heading, links }: { heading: string; links: { label: string; href: string }[] }) {
  return (
    <div>
      <h4 className="text-xs font-bold uppercase tracking-widest text-mkt-muted mb-4">{heading}</h4>
      <ul className="space-y-2.5">
        {links.map((l) => (
          <li key={l.label}>
            <Link href={l.href} className="text-sm text-mkt-body hover:text-mkt-brand transition-colors">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MarketingFooter() {
  return (
    <footer className="bg-mkt-surface border-t border-mkt-border">
      <div className="max-w-7xl mx-auto px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">

          {/* brand */}
          <div className="col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-mkt-brand to-mkt-teal
                               flex items-center justify-center">
                <Zap className="w-4 h-4 text-white" />
              </span>
              <span className="font-display font-bold text-lg text-mkt-ink">ProductIQ</span>
            </div>
            <p className="text-sm text-mkt-body leading-relaxed max-w-xs mb-5">
              The AI product-discovery engine. Semantic search, rating intelligence,
              and reasoning you can trust.
            </p>
            <div className="flex items-center gap-3">
              {[Twitter, Linkedin, Github].map((Icon, i) => (
                <a key={i} href="#" className="w-9 h-9 rounded-lg border border-mkt-border bg-white
                                               flex items-center justify-center text-mkt-muted
                                               hover:text-mkt-brand hover:border-mkt-brand/40 transition-colors">
                  <Icon className="w-4 h-4" />
                </a>
              ))}
            </div>
          </div>

          <Col heading="Solutions" links={SOLUTIONS.slice(0, 5).map((s) => ({ label: s.label, href: s.href }))} />
          <Col heading="Industries" links={INDUSTRIES.slice(0, 5).map((s) => ({ label: s.label, href: s.href }))} />
          <Col heading="Resources" links={RESOURCES.slice(0, 5).map((s) => ({ label: s.label, href: s.href }))} />
          <Col heading="Company" links={COMPANY} />
        </div>

        <div className="mt-12 pt-8 border-t border-mkt-border flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-mkt-muted">© 2026 ProductIQ. All rights reserved.</p>
          <div className="flex items-center gap-5">
            {LEGAL.map((l) => (
              <Link key={l.label} href={l.href} className="text-xs text-mkt-muted hover:text-mkt-brand transition-colors">
                {l.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
