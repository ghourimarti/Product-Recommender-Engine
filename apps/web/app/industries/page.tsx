import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { Container, Reveal } from "@/components/marketing/primitives";
import { INDUSTRY_CONTENT } from "@/lib/industries-content";

export const metadata = { title: "Industries — ProductIQ" };

export default function IndustriesHub() {
  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Industries"
        title="Tuned for how your category is shopped"
        subtitle="The same engine, adapted to the discovery patterns, review dynamics, and data quirks of each vertical."
      />
      <section className="py-20">
        <Container>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {INDUSTRY_CONTENT.map((ind, i) => (
              <Reveal key={ind.slug} delay={(i % 3) * 0.08}>
                <Link href={`/industries/${ind.slug}`}
                  className="mkt-card p-6 block h-full hover:-translate-y-1 hover:shadow-lg transition-all group">
                  <span className="w-11 h-11 rounded-xl bg-mkt-teal/10 flex items-center justify-center mb-4
                                   group-hover:bg-mkt-teal transition-colors">
                    <ind.icon className="w-5 h-5 text-mkt-teal group-hover:text-white transition-colors" />
                  </span>
                  <h3 className="font-display font-semibold text-mkt-ink group-hover:text-mkt-brand transition-colors">
                    {ind.name}
                  </h3>
                  <p className="text-sm text-mkt-teal font-medium mt-1">{ind.tagline}</p>
                  <p className="text-sm text-mkt-body leading-relaxed mt-3">{ind.hero}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm text-mkt-brand font-medium">
                    Learn more <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
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
