import Link from "next/link";
import { ArrowRight, BookOpen, FileText, Calendar, Newspaper, Play, Download } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";
import { POSTS } from "@/lib/posts";

export const metadata = { title: "Resources — ProductIQ" };

const GUIDES = [
  { icon: FileText, title: "The Journey of a Query", type: "Whitepaper", desc: "How a natural-language request becomes a ranked, explained shortlist." },
  { icon: Download, title: "Retrieval → Rank → Reason", type: "Guide", desc: "A practical playbook for building reasoning-led product discovery." },
  { icon: Play,     title: "Live product walkthrough", type: "Webinar", desc: "See ProductIQ handle real shopper queries end to end." },
];

const NEWS = [
  { date: "Jun 24, 2026", title: "ProductIQ adds cross-encoder reranking to the Pro plan" },
  { date: "May 30, 2026", title: "Rating-intelligence v2: confidence-weighted scoring goes GA" },
  { date: "Apr 18, 2026", title: "Streamed explanations now ground to matched-review counts" },
];

export default function ResourcesPage() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Resources"
        title="Learn how modern discovery works"
        subtitle="Guides, deep-dives, and product news on semantic search, rating intelligence, and reasoning."
      />

      {/* featured guides */}
      <section id="docs" className="py-20 scroll-mt-20">
        <Container>
          <h2 className="text-2xl font-display font-bold text-mkt-ink mb-8">Guides & reports</h2>
          <div className="grid md:grid-cols-3 gap-5">
            {GUIDES.map((g, i) => (
              <Reveal key={g.title} delay={i * 0.08}>
                <div className="mkt-card p-6 h-full flex flex-col hover:shadow-lg transition-shadow">
                  <span className="w-11 h-11 rounded-xl bg-mkt-brand/10 flex items-center justify-center mb-4">
                    <g.icon className="w-5 h-5 text-mkt-brand" />
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-widest text-mkt-teal mb-2">{g.type}</span>
                  <h3 className="font-display font-semibold text-mkt-ink mb-2">{g.title}</h3>
                  <p className="text-sm text-mkt-body leading-relaxed flex-1">{g.desc}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm text-mkt-brand font-medium">
                    Read <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>

      {/* from the blog */}
      <section className="py-20 bg-mkt-surface border-y border-mkt-border">
        <Container>
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-display font-bold text-mkt-ink flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-mkt-brand" /> From the blog
            </h2>
            <Link href="/blog" className="text-sm text-mkt-brand font-medium inline-flex items-center gap-1">
              All posts <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {POSTS.map((p) => (
              <Link key={p.slug} href={`/blog/${p.slug}`}
                className="mkt-card p-6 block hover:shadow-lg transition-shadow group">
                <span className="text-xs font-medium text-mkt-teal">{p.category}</span>
                <h3 className="font-display font-semibold text-mkt-ink mt-2 mb-2 leading-snug group-hover:text-mkt-brand transition-colors">
                  {p.title}
                </h3>
                <p className="text-sm text-mkt-body leading-relaxed line-clamp-2">{p.excerpt}</p>
                <p className="text-xs text-mkt-muted mt-3">{p.date} · {p.readTime}</p>
              </Link>
            ))}
          </div>
        </Container>
      </section>

      {/* news + events */}
      <section id="news" className="py-20 scroll-mt-20">
        <Container>
          <div className="grid lg:grid-cols-2 gap-12">
            <div>
              <h2 className="text-2xl font-display font-bold text-mkt-ink flex items-center gap-2 mb-6">
                <Newspaper className="w-5 h-5 text-mkt-brand" /> Latest news
              </h2>
              <div className="space-y-3">
                {NEWS.map((n) => (
                  <div key={n.title} className="mkt-card p-4 flex items-start gap-4">
                    <span className="text-xs text-mkt-muted font-mono shrink-0 pt-0.5 w-24">{n.date}</span>
                    <p className="text-sm text-mkt-ink font-medium">{n.title}</p>
                  </div>
                ))}
              </div>
            </div>
            <div id="events" className="scroll-mt-20">
              <h2 className="text-2xl font-display font-bold text-mkt-ink flex items-center gap-2 mb-6">
                <Calendar className="w-5 h-5 text-mkt-brand" /> Upcoming events
              </h2>
              <div className="mkt-card p-8 bg-gradient-to-br from-mkt-brand/5 to-mkt-teal/5">
                <p className="text-xs font-semibold uppercase tracking-widest text-mkt-teal mb-2">Webinar</p>
                <h3 className="text-xl font-display font-semibold text-mkt-ink mb-3">
                  Building reasoning-led discovery
                </h3>
                <p className="text-sm text-mkt-body leading-relaxed mb-5">
                  A live walkthrough of the retrieve → rank → reason loop, with Q&A.
                </p>
                <Link href="/contact" className="mkt-btn-primary px-5 py-2.5 text-sm w-fit">
                  Register interest <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
