import Link from "next/link";
import { Target, Users, Zap, Globe, ArrowRight } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";

export const metadata = { title: "About — ProductIQ" };

const VALUES = [
  { icon: Target,  title: "Relevance over noise", desc: "We rank by what genuinely fits your need — not by who paid for placement." },
  { icon: Users,   title: "Trust through transparency", desc: "Every recommendation shows its score and the reviews behind it. No black boxes." },
  { icon: Zap,     title: "Fast by default", desc: "Sub-second responses, streamed results, and aggressive caching so you never wait." },
  { icon: Globe,   title: "Built to scale", desc: "The same architecture serving a demo scales to millions of queries — statelessly." },
];

/* Only numbers verifiable from the repository itself. Two earlier rounds of cuts:
   1. Invented ("10,000+ products", "500k+ reviews", "12,000+ active shoppers", "98.9% uptime") —
      zero real users, and uptime has never been measured.
   2. Measured locally but never evidenced ("7.6ms p95", "66% cache hit rate") — real numbers from
      a k6 run, but no artifact was committed, so no reader could confirm them. Also gone.
   What remains is true by inspection: the test count from `pytest --collect-only`, the blocking
   CVE scan in .github/workflows/ci.yml, the fallback chain in packages/core/llm.py, and
   AGGREGATE_TTL_SECONDS in packages/recommender/aggregator.py. */
const STATS = [
  { value: "117",  label: "Automated tests in CI" },
  { value: "0",    label: "Unignored dependency CVEs" },
  { value: "3",    label: "LLM providers, auto-failover" },
  { value: "6h",   label: "Result cache — repeats are free" },
];

export default function AboutPage() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Our story"
        title="We're rebuilding product discovery"
        subtitle="Shopping shouldn't mean wading through fake reviews and keyword-stuffed listings. We built the search we always wanted."
      />

      {/* mission */}
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="prose-invert space-y-5 text-txt-secondary leading-relaxed">
          <p>
            ProductIQ started with a simple frustration: finding the right product means reading
            dozens of reviews, comparing specs you don't understand, and second-guessing star
            ratings that a handful of reviews can distort.
          </p>
          <p>
            So we built a discovery engine that does the reading for you. It understands your
            request in plain language, retrieves the most relevant products across thousands of
            listings, weighs their reviews intelligently, and explains — in a sentence — why each
            one fits. No sponsored placements. No keyword games. Just relevance you can see and trust.
          </p>
          <p className="text-txt-primary font-medium">
            Our mission is to make every purchase a confident one.
          </p>
        </div>
      </div>

      {/* stats */}
      <div className="border-y border-bg-border bg-bg-surface/30">
        <div className="max-w-5xl mx-auto px-6 py-14">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {STATS.map((s) => (
              <div key={s.label}>
                <p className="text-3xl font-display font-bold text-txt-primary">{s.value}</p>
                <p className="text-sm text-txt-muted mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* values */}
      <div className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-display font-bold text-txt-primary text-center mb-12">
          What we believe
        </h2>
        <div className="grid md:grid-cols-2 gap-5">
          {VALUES.map((v) => (
            <div key={v.title} className="glass-card p-6 flex gap-4">
              <span className="w-11 h-11 rounded-xl bg-accent-muted flex items-center justify-center shrink-0">
                <v.icon className="w-5 h-5 text-accent" />
              </span>
              <div>
                <h3 className="font-display font-semibold text-txt-primary mb-1.5">{v.title}</h3>
                <p className="text-sm text-txt-secondary leading-relaxed">{v.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center mt-14">
          <Link href="/contact" className="btn-primary px-6 py-3 text-base inline-flex">
            Get in touch <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </MarketingShell>
  );
}
