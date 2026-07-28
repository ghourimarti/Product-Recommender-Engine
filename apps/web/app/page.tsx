import Link from "next/link";
import {
  Search, Star, Sparkles, Shield, MessageSquare, Layers,
  ArrowRight, Check, Brain,
} from "lucide-react";
import { MarketingShell } from "@/components/MarketingShell";
import { DemoNotice } from "@/components/marketing/DemoNotice";
import { HomeHero } from "@/components/marketing/HomeHero";
import { MetricsBar } from "@/components/marketing/MetricsBar";
import { Container, Reveal, SectionHeading } from "@/components/marketing/primitives";
// LogoCloud ("trusted by" + invented brand names) and TestimonialCarousel (invented quotes) are
// deliberately NOT rendered: they are fabricated social proof for a product with zero users.
import { SOLUTIONS } from "@/lib/nav";

/* icon lookup for solutions (nav stores component refs already) */
const PRODUCT_GRID = SOLUTIONS.slice(0, 6);

const CONNECTED = [
  { icon: Search,        title: "Retrieve",  desc: "Hybrid dense + sparse search finds candidates across the whole catalog by meaning." },
  { icon: Star,          title: "Rank",      desc: "A confidence-weighted rating blend orders them by genuine quality, not thin averages." },
  { icon: Sparkles,      title: "Reason",    desc: "A grounded LLM explains why each result fits — citing the reviews it actually read." },
];

export default function LandingPage() {
  return (
    <MarketingShell>
      <DemoNotice />

      <HomeHero />

      {/* ── Product / capability grid ── */}
      <section id="capabilities" className="py-24">
        <Container>
          <SectionHeading
            eyebrow="The platform"
            title="One engine, every part of discovery"
            subtitle="Each capability makes the others smarter — retrieval feeds ranking, ranking feeds reasoning, and feedback improves them all."
          />
          <div className="mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {PRODUCT_GRID.map((s, i) => (
              <Reveal key={s.label} delay={(i % 3) * 0.08}>
                <Link href={s.href} className="mkt-card p-6 block h-full hover:-translate-y-1 hover:shadow-lg
                                               transition-all duration-200 group">
                  {s.icon && (
                    <span className="w-11 h-11 rounded-xl bg-mkt-brand/10 flex items-center justify-center mb-4
                                     group-hover:bg-mkt-brand group-hover:text-white transition-colors">
                      <s.icon className="w-5 h-5 text-mkt-brand group-hover:text-white transition-colors" />
                    </span>
                  )}
                  <h3 className="font-display font-semibold text-mkt-ink mb-1.5 group-hover:text-mkt-brand transition-colors">
                    {s.label}
                  </h3>
                  <p className="text-sm text-mkt-body leading-relaxed">{s.desc}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm text-mkt-brand font-medium">
                    Learn more <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </Link>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

      {/* ── Connected experiences (the "reasoning" story) ── */}
      <section className="py-24 bg-mkt-surface border-y border-mkt-border">
        <Container>
          <SectionHeading
            eyebrow="How it reasons"
            title="Retrieve → Rank → Reason"
            subtitle="Most search stops at matching keywords. ProductIQ runs a reasoning loop that turns a vague request into a confident, explained shortlist."
          />
          <div className="mt-16 grid md:grid-cols-3 gap-6 relative">
            <div className="hidden md:block absolute top-8 left-[16%] right-[16%] h-px
                            bg-gradient-to-r from-mkt-brand/40 via-mkt-teal/40 to-mkt-brand/40" />
            {CONNECTED.map((c, i) => (
              <Reveal key={c.title} delay={i * 0.12}>
                <div className="relative text-center md:text-left">
                  <span className="relative z-10 inline-flex w-16 h-16 rounded-2xl bg-white border border-mkt-border
                                   shadow-sm items-center justify-center mb-5 mx-auto md:mx-0">
                    <c.icon className="w-6 h-6 text-mkt-brand" />
                  </span>
                  <h3 className="font-display font-semibold text-lg text-mkt-ink mb-2">
                    <span className="text-mkt-teal font-mono text-sm mr-2">0{i + 1}</span>{c.title}
                  </h3>
                  <p className="text-sm text-mkt-body leading-relaxed">{c.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

      {/* ── Split value prop ── */}
      <section className="py-24">
        <Container>
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <Reveal>
              <p className="mkt-eyebrow mb-4">Why ProductIQ</p>
              <h2 className="text-3xl md:text-4xl font-display font-bold text-mkt-ink tracking-tight">
                Product discovery is all we do
              </h2>
              <p className="mt-4 text-mkt-body leading-relaxed">
                We&apos;re not a general search tool bolted onto commerce. Every layer — retrieval,
                ranking, reasoning, evaluation — is purpose-built for helping shoppers find the
                right product and understand why.
              </p>
              <ul className="mt-6 space-y-3">
                {[
                  "Grounded explanations — no hallucinated specs",
                  "Transparent relevance scoring on every result",
                  "Rating-aware ranking that resists review gaming",
                  "Streamed results — value in under a second",
                ].map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-mkt-body">
                    <Check className="w-4 h-4 text-mkt-teal mt-0.5 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <Link href="/features" className="mkt-btn-primary mt-8 px-5 py-2.5 text-sm inline-flex">
                Explore the platform <ArrowRight className="w-4 h-4" />
              </Link>
            </Reveal>

            <Reveal delay={0.1}>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { icon: Brain, title: "Semantic", tint: "from-mkt-brand/10" },
                  { icon: Star, title: "Rating-aware", tint: "from-mkt-teal/10" },
                  { icon: MessageSquare, title: "Conversational", tint: "from-indigo-500/10" },
                  { icon: Shield, title: "Secure", tint: "from-emerald-500/10" },
                ].map((c) => (
                  <div key={c.title} className={`mkt-card p-6 bg-gradient-to-br ${c.tint} to-white`}>
                    <c.icon className="w-7 h-7 text-mkt-brand mb-3" />
                    <p className="font-display font-semibold text-mkt-ink">{c.title}</p>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </Container>
      </section>

      <MetricsBar />

      {/* ── Final CTA ── */}
      <section className="py-24">
        <Container>
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-mkt-brand to-mkt-teal
                          px-8 py-16 md:py-20 text-center">
            <div className="absolute inset-0 mkt-dotgrid opacity-10 pointer-events-none" />
            <div className="relative">
              <h2 className="text-3xl md:text-4xl font-display font-bold text-white tracking-tight">
                See what your shoppers have been missing
              </h2>
              <p className="mt-4 text-white/85 text-lg max-w-xl mx-auto">
                Free to start. 100 AI-powered searches every day. No credit card required.
              </p>
              <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link href="/dashboard/discover"
                  className="bg-white text-mkt-brand hover:bg-mkt-elevated rounded-lg font-semibold px-6 py-3 text-base
                             inline-flex items-center gap-2 transition-colors">
                  Try it free <ArrowRight className="w-4 h-4" />
                </Link>
                <Link href="/pricing"
                  className="border border-white/40 text-white hover:bg-white/10 rounded-lg font-semibold px-6 py-3 text-base
                             inline-flex items-center gap-2 transition-colors">
                  View pricing
                </Link>
              </div>
            </div>
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
