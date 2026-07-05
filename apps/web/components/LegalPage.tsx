import { MarketingShell, PageHeader } from "@/components/MarketingShell";

export type LegalSection = { heading: string; body: string[] };

export function LegalPage({
  title,
  updated,
  intro,
  sections,
}: {
  title: string;
  updated: string;
  intro: string;
  sections: LegalSection[];
}) {
  return (
    <MarketingShell>
      <PageHeader eyebrow="Legal" title={title} subtitle={`Last updated ${updated}`} />

      <div className="max-w-3xl mx-auto px-6 py-16">
        <p className="text-txt-secondary leading-relaxed mb-10">{intro}</p>

        <div className="space-y-10">
          {sections.map((s, i) => (
            <section key={s.heading}>
              <h2 className="text-lg font-display font-bold text-txt-primary mb-3">
                {i + 1}. {s.heading}
              </h2>
              <div className="space-y-3">
                {s.body.map((p, j) => (
                  <p key={j} className="text-sm text-txt-secondary leading-relaxed">{p}</p>
                ))}
              </div>
            </section>
          ))}
        </div>

        <p className="text-xs text-txt-muted mt-12 pt-8 border-t border-bg-border">
          This document is provided for demonstration purposes as part of the ProductIQ portfolio
          project. It is not legal advice. Consult a qualified attorney before relying on any policy
          for a live commercial product.
        </p>
      </div>
    </MarketingShell>
  );
}
