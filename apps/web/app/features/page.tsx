import Link from "next/link";
import {
  Brain, Star, Sparkles, Shield, Zap, BarChart3, ArrowRight, Check,
} from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";

export const metadata = { title: "Features — ProductIQ" };

const SECTIONS = [
  {
    id: "semantic",
    icon: Brain,
    title: "Semantic Search",
    lead: "Understands what you mean, not just what you type.",
    body: "Traditional search matches keywords. ProductIQ embeds your query and the entire catalog into the same vector space, so 'earphones that survive a sweaty gym session' finds sweat-resistant, secure-fit products even if none of those exact words appear in the listing.",
    points: ["Dense vector retrieval over 10,000+ products", "Hybrid dense + sparse (BM25) matching", "Understands synonyms, intent, and context"],
  },
  {
    id: "rating",
    icon: Star,
    title: "Rating Intelligence",
    lead: "Weighs real reviews — not a naive star average.",
    body: "A 5.0 from two reviews is not better than a 4.6 from four hundred. Our rating-aware blend combines semantic relevance with a confidence-weighted rating score, so popular, genuinely-loved products rise and thinly-reviewed outliers don't game the ranking.",
    points: ["Confidence-weighted rating blend", "Review-volume aware scoring", "Transparent per-product relevance %"],
  },
  {
    id: "explain",
    icon: Sparkles,
    title: "AI Explanations",
    lead: "Every recommendation comes with grounded reasoning.",
    body: "The assistant streams a plain-language explanation of why each product fits your request — grounded in the actual reviews it retrieved, with the number of matched reviews shown. No hallucinated specs, no marketing fluff.",
    points: ["Grounded in retrieved reviews", "Token-by-token streaming", "Matched-review attribution"],
  },
  {
    id: "security",
    icon: Shield,
    title: "Enterprise Security",
    lead: "Auth, quotas, and rate limits built in from day one.",
    body: "Every request is authenticated (JWT), rate-limited per user, and metered against a quota. Circuit breakers keep the app responsive when an upstream provider degrades, and no user's data or session bleeds into another's.",
    points: ["JWT auth + per-user isolation", "Rate limiting + daily quotas", "Circuit-breaker fallbacks"],
  },
];

const GRID = [
  { icon: Zap, title: "Real-time streaming", desc: "Cards render before the explanation streams — no spinner-then-dump." },
  { icon: BarChart3, title: "Transparent scoring", desc: "See the relevance % and rating breakdown behind every rank." },
  { icon: Shield, title: "Graceful degradation", desc: "If the LLM is down, you still get ranked products." },
];

export default function FeaturesPage() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Features"
        title="Built like a production search platform"
        subtitle="The same retrieval, ranking, and generation stack that powers enterprise product discovery — in a product you can use today."
      />

      {/* alternating feature sections */}
      <div className="max-w-5xl mx-auto px-6 py-16 space-y-20">
        {SECTIONS.map((s, i) => (
          <section key={s.id} id={s.id} className="scroll-mt-24 grid md:grid-cols-2 gap-10 items-center">
            <div className={i % 2 === 1 ? "md:order-2" : ""}>
              <span className="w-12 h-12 rounded-xl bg-accent-muted flex items-center justify-center mb-5">
                <s.icon className="w-6 h-6 text-accent" />
              </span>
              <h2 className="text-2xl md:text-3xl font-display font-bold text-txt-primary mb-2">{s.title}</h2>
              <p className="text-accent text-sm font-medium mb-4">{s.lead}</p>
              <p className="text-txt-secondary leading-relaxed mb-5">{s.body}</p>
              <ul className="space-y-2">
                {s.points.map((p) => (
                  <li key={p} className="flex items-start gap-2.5 text-sm text-txt-secondary">
                    <Check className="w-4 h-4 text-status-success mt-0.5 shrink-0" /> {p}
                  </li>
                ))}
              </ul>
            </div>

            {/* visual placeholder */}
            <div className={i % 2 === 1 ? "md:order-1" : ""}>
              <div className="glass-card p-8 aspect-[4/3] flex items-center justify-center bg-grid-glow">
                <s.icon className="w-16 h-16 text-accent/30" />
              </div>
            </div>
          </section>
        ))}
      </div>

      {/* small grid */}
      <div className="border-t border-bg-border bg-bg-surface/30">
        <div className="max-w-5xl mx-auto px-6 py-16">
          <div className="grid md:grid-cols-3 gap-5">
            {GRID.map((g) => (
              <div key={g.title} className="glass-card p-6">
                <g.icon className="w-5 h-5 text-accent mb-3" />
                <h3 className="font-display font-semibold text-txt-primary mb-1.5">{g.title}</h3>
                <p className="text-sm text-txt-secondary leading-relaxed">{g.desc}</p>
              </div>
            ))}
          </div>

          <div className="text-center mt-14">
            <Link href="/dashboard/discover" className="btn-primary px-6 py-3 text-base inline-flex">
              Try it free <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </MarketingShell>
  );
}
