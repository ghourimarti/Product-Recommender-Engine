import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";
import { SOLUTION_CONTENT } from "@/lib/solutions-content";

export const metadata = { title: "Solutions — ProductIQ" };

export default function SolutionsHub() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Solutions"
        title="Everything discovery needs, in one engine"
        subtitle="Six capabilities that make each other smarter — from retrieval to reasoning to security."
      />
      <section className="py-20">
        <Container>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {SOLUTION_CONTENT.map((s, i) => (
              <Reveal key={s.slug} delay={(i % 3) * 0.08}>
                <Link href={`/solutions/${s.slug}`}
                  className="mkt-card p-6 block h-full hover:-translate-y-1 hover:shadow-lg transition-all group">
                  <span className="w-11 h-11 rounded-xl bg-mkt-brand/10 flex items-center justify-center mb-4
                                   group-hover:bg-mkt-brand transition-colors">
                    <s.icon className="w-5 h-5 text-mkt-brand group-hover:text-white transition-colors" />
                  </span>
                  <h3 className="font-display font-semibold text-mkt-ink group-hover:text-mkt-brand transition-colors">
                    {s.name}
                  </h3>
                  <p className="text-sm text-mkt-teal font-medium mt-1">{s.tagline}</p>
                  <p className="text-sm text-mkt-body leading-relaxed mt-3">{s.hero}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm text-mkt-brand font-medium">
                    Explore <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </Link>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>
    </MarketingShell>
  );
}
