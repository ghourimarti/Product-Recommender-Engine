import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Check, ArrowLeft } from "lucide-react";
import { MarketingShell } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";
import { SOLUTION_CONTENT, getSolution } from "@/lib/solutions-content";

export function generateStaticParams() {
  return SOLUTION_CONTENT.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const s = getSolution(slug);
  return { title: s ? `${s.name} — ProductIQ` : "Solution — ProductIQ" };
}

export default async function SolutionDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const s = getSolution(slug);
  if (!s) notFound();

  const others = SOLUTION_CONTENT.filter((x) => x.slug !== slug).slice(0, 3);

  return (
    <MarketingShell>
      {/* hero */}
      <section className="relative overflow-hidden border-b border-mkt-border bg-mkt-surface">
        <div className="absolute inset-0 mkt-hero-glow pointer-events-none" />
        <Container className="relative py-20 md:py-24">
          <Link href="/solutions" className="inline-flex items-center gap-1.5 text-sm text-mkt-muted hover:text-mkt-brand mb-8 transition-colors">
            <ArrowLeft className="w-4 h-4" /> All solutions
          </Link>
          <div className="max-w-3xl">
            <span className="w-14 h-14 rounded-2xl bg-mkt-brand/10 flex items-center justify-center mb-6">
              <s.icon className="w-7 h-7 text-mkt-brand" />
            </span>
            <p className="mkt-eyebrow mb-3">{s.tagline}</p>
            <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight text-mkt-ink">{s.name}</h1>
            <p className="mt-5 text-lg text-mkt-body leading-relaxed">{s.hero}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/dashboard/discover" className="mkt-btn-primary px-5 py-2.5 text-sm">
                Try it free <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/contact" className="mkt-btn-secondary px-5 py-2.5 text-sm">Talk to us</Link>
            </div>
          </div>
        </Container>
      </section>

      {/* benefits */}
      <section className="py-24">
        <Container>
          <div className="grid md:grid-cols-3 gap-5">
            {s.benefits.map((b, i) => (
              <Reveal key={b.title} delay={i * 0.08}>
                <div className="mkt-card p-6 h-full">
                  <span className="w-8 h-8 rounded-lg bg-mkt-teal/10 flex items-center justify-center mb-4">
                    <Check className="w-4 h-4 text-mkt-teal" />
                  </span>
                  <h3 className="font-display font-semibold text-mkt-ink mb-2">{b.title}</h3>
                  <p className="text-sm text-mkt-body leading-relaxed">{b.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

      {/* how it works + metric */}
      <section className="py-24 bg-mkt-surface border-y border-mkt-border">
        <Container>
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <Reveal>
              <p className="mkt-eyebrow mb-3">How it works</p>
              <h2 className="text-3xl font-display font-bold text-mkt-ink mb-6">Under the hood</h2>
              <ol className="space-y-4">
                {s.how.map((step, i) => (
                  <li key={i} className="flex gap-4">
                    <span className="w-8 h-8 rounded-full bg-mkt-brand text-white text-sm font-semibold
                                     flex items-center justify-center shrink-0">{i + 1}</span>
                    <p className="text-mkt-body leading-relaxed pt-1">{step}</p>
                  </li>
                ))}
              </ol>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="mkt-card p-10 text-center bg-gradient-to-br from-mkt-brand/5 to-mkt-teal/5">
                <p className="text-5xl md:text-6xl font-display font-bold mkt-gradient">{s.metric.value}</p>
                <p className="mt-3 text-mkt-body">{s.metric.label}</p>
              </div>
            </Reveal>
          </div>
        </Container>
      </section>

      {/* related */}
      <section className="py-24">
        <Container>
          <h2 className="text-2xl font-display font-bold text-mkt-ink text-center mb-12">Explore more solutions</h2>
          <div className="grid md:grid-cols-3 gap-5">
            {others.map((o) => (
              <Link key={o.slug} href={`/solutions/${o.slug}`}
                className="mkt-card p-6 block hover:-translate-y-1 hover:shadow-lg transition-all group">
                <o.icon className="w-6 h-6 text-mkt-brand mb-3" />
                <h3 className="font-display font-semibold text-mkt-ink group-hover:text-mkt-brand transition-colors">{o.name}</h3>
                <p className="text-sm text-mkt-body mt-1">{o.tagline}</p>
              </Link>
            ))}
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
