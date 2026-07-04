import Link from "next/link";
import { Zap } from "lucide-react";

const COLS = [
  {
    heading: "Product",
    links: ["Features", "Pricing", "API Docs", "Status", "Changelog"],
  },
  {
    heading: "Company",
    links: ["About", "Blog", "Careers", "Contact", "Press Kit"],
  },
  {
    heading: "Legal",
    links: ["Privacy Policy", "Terms of Service", "Cookie Policy", "Security", "GDPR"],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-bg-border bg-bg-surface/40 mt-24">
      <div className="max-w-7xl mx-auto px-6 py-14">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10">

          {/* Brand column */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="w-6 h-6 rounded-md bg-accent flex items-center justify-center">
                <Zap className="w-3.5 h-3.5 text-white" />
              </span>
              <span className="font-display font-bold text-txt-primary">ProductIQ</span>
            </div>
            <p className="text-txt-muted text-sm leading-relaxed mb-4">
              AI-powered product discovery. Find exactly what you need — with
              explanations you can trust.
            </p>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((i) => (
                <span key={i} className="text-rank-gold text-xs">★</span>
              ))}
              <span className="text-txt-muted text-xs ml-1.5">4.8 / 5 · 2,400+ users</span>
            </div>
          </div>

          {/* Link columns */}
          {COLS.map(({ heading, links }) => (
            <div key={heading}>
              <h4 className="text-txt-secondary text-xs font-semibold uppercase tracking-widest mb-4">
                {heading}
              </h4>
              <ul className="space-y-2.5">
                {links.map((link) => (
                  <li key={link}>
                    <Link
                      href="#"
                      className="text-txt-muted hover:text-txt-primary text-sm transition-colors"
                    >
                      {link}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="border-t border-bg-border mt-10 pt-6 flex flex-col md:flex-row items-center justify-between gap-3">
          <p className="text-txt-muted text-sm">© 2025 ProductIQ. All rights reserved.</p>
          <p className="text-txt-muted text-xs">
            Semantic AI · Llama 3.1 · Qdrant · FastAPI · Next.js
          </p>
        </div>
      </div>
    </footer>
  );
}
