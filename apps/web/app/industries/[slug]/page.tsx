import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, ArrowLeft, AlertCircle } from "lucide-react";
import { MarketingShell } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";
import { INDUSTRY_CONTENT, getIndustry } from "@/lib/industries-content";

export function generateStaticParams() {
  return INDUSTRY_CONTENT.map((i) => ({ slug: i.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const ind = getIndustry(slug);
  return { title: ind ? `${ind.name} — ProductIQ` : "Industry — ProductIQ" };
}

export default async function IndustryDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const ind = getIndustry(slug);
  if (!ind) notFound();

  return (
    <MarketingShell>
      {/* hero */}
      <section className="relative overflow-hidden border-b border-mkt-border bg-mkt-surface">
        <div className="absolute inset-0 mkt-hero-glow pointer-events-none" />
        <Container className="relative py-20 md:py-24">
          <Link href="/industries" className="inline-flex items-center gap-1.5 text-sm text-mkt-muted hover:text-mkt-brand mb-8 transition-colors">
            <ArrowLeft className="w-4 h-4" /> All industries
          </Link>
          <div className="max-w-3xl">
            <span className="w-14 h-14 rounded-2xl bg-mkt-teal/10 flex items-center justify-center mb-6">
              <ind.icon className="w-7 h-7 text-mkt-teal" />
            </span>
            <p className="mkt-eyebrow mb-3">{ind.tagline}</p>
            <h1 className="text-4xl md:text-5xl font-display font-bold tracking-tight text-mkt-ink">{ind.name}</h1>
            <p className="mt-5 text-lg text-mkt-body leading-relaxed">{ind.hero}</p>
            <Link href="/dashboard/discover" className="mkt-btn-primary mt-8 px-5 py-2.5 text-sm inline-flex">
              Try it free <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Container>
      </section>

      {/* wins */}
      <section className="py-20 border-b border-mkt-border">
        <Container>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {ind.wins.map((w) => (
              <div key={w.label} className="text-center">
                <p className="text-4xl md:text-5xl font-display font-bold mkt-gradient">{w.stat}</p>
                <p className="mt-2 text-sm text-mkt-muted">{w.label}</p>
              </div>
            ))}
          </div>
          <p className="text-center text-xs text-mkt-muted mt-8">
            Illustrative outcomes based on the ProductIQ discovery pattern. Your results depend on catalog and traffic.
          </p>
        </Container>
      </section>

      {/* challenges + example */}
      <section className="py-24">
        <Container>
          <div className="grid lg:grid-cols-2 gap-12">
            <Reveal>
              <p className="mkt-eyebrow mb-3">The challenge</p>
              <h2 className="text-3xl font-display font-bold text-mkt-ink mb-6">What makes this category hard</h2>
              <ul className="space-y-4">
                {ind.challenges.map((c, i) => (
                  <li key={i} className="flex gap-3">
                    <AlertCircle className="w-5 h-5 text-mkt-teal shrink-0 mt-0.5" />
                    <p className="text-mkt-body leading-relaxed">{c}</p>
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="mkt-card p-8 bg-gradient-to-br from-mkt-brand/5 to-mkt-teal/5 h-full flex flex-col justify-center">
                <p className="mkt-eyebrow mb-3">In practice</p>
                <p className="text-lg text-mkt-ink font-display leading-relaxed">{ind.example}</p>
                <Link href="/dashboard/discover" className="mkt-btn-primary mt-6 px-5 py-2.5 text-sm w-fit">
                  See it live <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </Reveal>
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
