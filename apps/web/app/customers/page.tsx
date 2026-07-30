import Link from "next/link";
import { ArrowRight, Gauge, ShieldCheck, Target, Wallet } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";

export const metadata = { title: "Evidence — ProductIQ" };

/**
 * This page used to be "Customers": three case studies with named people
 * ("Meera Kapoor, Head of Ecommerce"), asserted business outcomes ("+18% search
 * conversion", "-12% return rate"), and a six-quote "wall of love" — all invented,
 * for a product with zero users, under the headline "Teams that ship discovery
 * shoppers trust" and a "Ready to join them?" call to action.
 *
 * None of it was real, and unlike the landing page it carried no demo disclaimer.
 * Inventing named customers and the results they got is misrepresentation, not
 * placeholder copy, so it is gone.
 *
 * What replaces it is the only honest version of this page: the measurements the
 * repo can actually reproduce, each one traceable to a command you can run.
 */

const EVIDENCE = [
  {
    icon: Target,
    stat: "0.941",
    statLabel: "NDCG@3, live-aggregator ranking",
    headline: "Our ranking beats Google Shopping's own ordering",
    detail:
      "Scored over recorded Google Shopping fixtures: ours NDCG@3 0.9413 / MRR 1.0000 against " +
      "Google's own result order at 0.8240 / 0.8750. CI fails the build if that stops being true — " +
      "if the re-ranker no longer beats the source, it has no reason to exist.",
    repro: "uv run python -m evaluation.aggregator.gate",
  },
  {
    icon: Gauge,
    stat: "6h",
    statLabel: "result cache window",
    headline: "A repeat question costs nothing",
    detail:
      "Results are cached for six hours, so a repeated query spends zero paid searches and zero " +
      "LLM calls. The window itself is the cost control: every expiry costs a real metered " +
      "search, which is why it is six hours and not ten minutes.",
    repro: "packages/recommender/aggregator.py",
  },
  {
    icon: Wallet,
    stat: "250",
    statLabel: "searches/month — the real constraint",
    headline: "Spend is capped globally, not per user",
    detail:
      "The live shopping source is metered. Per-user rate limits do not protect a shared budget: " +
      "one user inside their own quota can drain everyone's month. Spend is counted globally in " +
      "Redis per day and per month, and refused past the cap.",
    repro: "packages/recommender/aggregator.py",
  },
  {
    icon: ShieldCheck,
    stat: "117",
    statLabel: "automated tests, green in CI",
    headline: "An outage is never dressed up as an empty result",
    detail:
      "Quota exhausted, bad key, or a network failure returns a distinct, alertable " +
      "source_unavailable state — not 'no match'. An outage that looks like a legitimate empty " +
      "result is an outage nobody notices.",
    repro: "uv run pytest -q",
  },
];

const LIMITS = [
  "No paying users, and this has never run in production. Every number above is a local or CI measurement, not a production SLO.",
  "The bring-your-own-catalog mode ships with a 9-product demo catalog — enough to prove ranking behaviour, far too small to be a relevance benchmark.",
  "Answer faithfulness on the catalog path scores 0.56, which is weak. It is a documented improvement target, not a solved problem.",
  "Infrastructure (Helm, Terraform) is validated but has never been applied to a live cluster.",
];

export default function EvidencePage() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Evidence"
        title="No customers yet — so here are the measurements instead"
        subtitle="This is a working demo, not a commercial service. Rather than invent case studies, every claim below is something you can reproduce from the repository."
      />

      <section className="py-24">
        <Container>
          <div className="space-y-6">
            {EVIDENCE.map((e, i) => (
              <Reveal key={e.headline} delay={i * 0.06}>
                <div className="mkt-card p-8 grid md:grid-cols-3 gap-8 items-center hover:shadow-lg transition-shadow">
                  <div className="md:col-span-2">
                    <div className="flex items-center gap-2 mb-3">
                      <e.icon className="w-4 h-4 text-mkt-teal" aria-hidden />
                      <span className="text-xs text-mkt-teal uppercase tracking-wide">Measured</span>
                    </div>
                    <h3 className="text-xl font-display font-semibold text-mkt-ink leading-snug mb-3">
                      {e.headline}
                    </h3>
                    <p className="text-mkt-body leading-relaxed">{e.detail}</p>
                    <p className="mt-4 text-xs text-mkt-muted font-mono break-all">
                      reproduce: {e.repro}
                    </p>
                  </div>
                  <div className="text-center md:border-l md:border-mkt-border">
                    <p className="text-5xl font-display font-bold mkt-gradient">{e.stat}</p>
                    <p className="text-sm text-mkt-muted mt-1">{e.statLabel}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

      <section className="py-24 bg-mkt-surface border-y border-mkt-border">
        <Container>
          <div className="max-w-3xl mx-auto">
            <p className="mkt-eyebrow mb-3">What this is not</p>
            <h2 className="text-3xl font-display font-bold text-mkt-ink mb-8">
              The limits, stated up front
            </h2>
            <ul className="space-y-4">
              {LIMITS.map((l) => (
                <li key={l} className="flex gap-3 text-mkt-body leading-relaxed">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full bg-mkt-muted shrink-0" />
                  {l}
                </li>
              ))}
            </ul>
          </div>
        </Container>
      </section>

      <section className="py-20">
        <Container>
          <div className="text-center">
            <h2 className="text-2xl font-display font-bold text-mkt-ink mb-4">
              Try it against a live query
            </h2>
            <Link
              href="/dashboard/discover"
              className="mkt-btn-primary px-6 py-3 text-base inline-flex"
            >
              Open Discover <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
