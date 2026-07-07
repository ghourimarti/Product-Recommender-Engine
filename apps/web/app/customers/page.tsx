import Link from "next/link";
import { ArrowRight, Star, Quote } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";
import { LogoCloud } from "@/components/marketing/LogoCloud";

export const metadata = { title: "Customers — ProductIQ" };

const CASE_STUDIES = [
  {
    company: "SoundWave",
    industry: "Consumer Electronics",
    headline: "How SoundWave lifted search conversion 18% with reasoning-led discovery",
    stat: "+18%", statLabel: "search conversion",
    quote: "ProductIQ turned our search bar into an actual assistant.",
    person: "Meera Kapoor, Head of Ecommerce",
  },
  {
    company: "PulseGear",
    industry: "Gaming & Hobbies",
    headline: "PulseGear cut returns 12% by ranking on real review quality",
    stat: "-12%", statLabel: "return rate",
    quote: "The rating-aware ranking was the unlock.",
    person: "David Lin, Director of Product",
  },
  {
    company: "EchoStore",
    industry: "Home & Furniture",
    headline: "EchoStore built customer trust with transparent, explained results",
    stat: "4.8/5", statLabel: "post-launch CSAT",
    quote: "Transparent scoring built instant trust with our customers.",
    person: "Ana Torres, VP Digital",
  },
];

const LOVE = [
  { text: "Finally, a search that understands what I actually mean. Found my headphones in 30 seconds.", name: "Arjun S.", role: "Music producer" },
  { text: "The explanations are the best part — I understand WHY it's recommending something.", name: "Priya M.", role: "UX designer" },
  { text: "We embedded it into our storefront and never looked back. Conversion is up across the board.", name: "David L.", role: "PM, PulseGear" },
  { text: "The relevance score makes me trust it more than any influencer pick.", name: "Vikram R.", role: "Audio engineer" },
  { text: "Rating intelligence caught products our old star-sort was burying. Game changer.", name: "Sara K.", role: "Merchandiser" },
  { text: "Sub-second, streamed, and grounded. It feels like a premium product because it is.", name: "Tom H.", role: "Frontend lead" },
];

export default function CustomersPage() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Customers"
        title="Teams that ship discovery shoppers trust"
        subtitle="From electronics to home goods, product teams use ProductIQ to turn search into an assistant."
      />

      <LogoCloud label="Powering discovery for" />

      {/* case studies */}
      <section className="py-24">
        <Container>
          <div className="space-y-6">
            {CASE_STUDIES.map((c, i) => (
              <Reveal key={c.company} delay={i * 0.06}>
                <div className="mkt-card p-8 grid md:grid-cols-3 gap-8 items-center hover:shadow-lg transition-shadow">
                  <div className="md:col-span-2">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="font-display font-bold text-mkt-ink">{c.company}</span>
                      <span className="text-xs text-mkt-muted">·</span>
                      <span className="text-xs text-mkt-teal">{c.industry}</span>
                    </div>
                    <h3 className="text-xl font-display font-semibold text-mkt-ink leading-snug mb-3">{c.headline}</h3>
                    <p className="text-mkt-body italic flex items-start gap-2">
                      <Quote className="w-4 h-4 text-mkt-brand/40 shrink-0 mt-1" />
                      &ldquo;{c.quote}&rdquo;
                    </p>
                    <p className="text-xs text-mkt-muted mt-2 ml-6">— {c.person}</p>
                  </div>
                  <div className="text-center md:border-l md:border-mkt-border">
                    <p className="text-5xl font-display font-bold mkt-gradient">{c.stat}</p>
                    <p className="text-sm text-mkt-muted mt-1">{c.statLabel}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

      {/* wall of love */}
      <section id="love" className="py-24 bg-mkt-surface border-y border-mkt-border scroll-mt-20">
        <Container>
          <div className="text-center mb-14">
            <p className="mkt-eyebrow justify-center flex mb-3">Wall of love</p>
            <h2 className="text-3xl md:text-4xl font-display font-bold text-mkt-ink">Don&apos;t take our word for it</h2>
          </div>
          <div className="columns-1 md:columns-2 lg:columns-3 gap-5 space-y-5">
            {LOVE.map((l, i) => (
              <div key={i} className="mkt-card p-5 break-inside-avoid">
                <div className="flex gap-0.5 mb-3">
                  {[1,2,3,4,5].map((s) => <Star key={s} className="w-3.5 h-3.5 text-rank-gold fill-rank-gold" />)}
                </div>
                <p className="text-sm text-mkt-body leading-relaxed mb-4">&ldquo;{l.text}&rdquo;</p>
                <div className="flex items-center gap-2.5">
                  <span className="w-8 h-8 rounded-full bg-gradient-to-br from-mkt-brand to-mkt-teal
                                   flex items-center justify-center text-white text-xs font-semibold">{l.name[0]}</span>
                  <div>
                    <p className="text-sm font-medium text-mkt-ink">{l.name}</p>
                    <p className="text-xs text-mkt-muted">{l.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Container>
      </section>

      {/* CTA */}
      <section className="py-20">
        <Container>
          <div className="text-center">
            <h2 className="text-2xl font-display font-bold text-mkt-ink mb-4">Ready to join them?</h2>
            <Link href="/dashboard/discover" className="mkt-btn-primary px-6 py-3 text-base inline-flex">
              Start free <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
