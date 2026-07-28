import { Check, Minus } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { DemoNotice } from "@/components/marketing/DemoNotice";
import { PricingPlans } from "@/components/PricingPlans";

export const metadata = { title: "Pricing — ProductIQ" };

const COMPARISON = [
  { feature: "AI searches per day",       free: "100",   pro: "Unlimited", ent: "Unlimited" },
  { feature: "Results per search",        free: "3",     pro: "10",        ent: "Custom" },
  { feature: "Streamed AI explanations",  free: true,    pro: true,        ent: true },
  { feature: "Semantic caching",          free: false,   pro: true,        ent: true },
  { feature: "Cross-encoder reranking",   free: false,   pro: true,        ent: true },
  { feature: "Search history & saved",    free: false,   pro: true,        ent: true },
  { feature: "API access",                free: false,   pro: true,        ent: true },
  { feature: "White-label",               free: false,   pro: false,       ent: true },
  { feature: "SSO / SAML",                free: false,   pro: false,       ent: true },
  { feature: "SLA + dedicated support",   free: false,   pro: false,       ent: true },
];

const FAQ = [
  { q: "Is there really a free plan?", a: "Yes. 100 AI-powered searches every day, forever, no credit card required. It's the same core engine as the paid plans — just with daily limits and fewer results per search." },
  { q: "Can I change plans anytime?", a: "Absolutely. Upgrade, downgrade, or cancel at any time. Changes take effect immediately, and we prorate any difference." },
  { q: "What models power the recommendations?", a: "The Free plan uses Llama 3.1. Pro and Enterprise unlock cross-encoder reranking for sharper ordering, plus optional custom models on Enterprise." },
  { q: "Do you offer refunds?", a: "Pro comes with a 14-day free trial so you can evaluate risk-free. If you're unhappy within the first 30 days of a paid plan, contact us for a full refund." },
  { q: "How does billing work for teams?", a: "Enterprise plans are billed annually with custom seat counts and volume pricing. Contact sales for a quote tailored to your usage." },
];

function Cell({ value }: { value: string | boolean }) {
  if (typeof value === "boolean") {
    return value
      ? <Check className="w-4 h-4 text-status-success mx-auto" />
      : <Minus className="w-4 h-4 text-txt-muted mx-auto" />;
  }
  return <span className="text-sm text-txt-secondary">{value}</span>;
}

export default function PricingPage() {
  return (
    <MarketingShell>
      {/* Pricing tiers (and the SLA line in the comparison table) are illustrative — nothing is
          actually for sale and no SLA is offered. Say so plainly. */}
      <DemoNotice />
      <PageHeader
        eyebrow="Pricing"
        title="Plans that scale with you"
        subtitle="Start free. Upgrade when you need unlimited searches, reranking, and API access."
      />

      <div className="max-w-6xl mx-auto px-6 py-16">
        <PricingPlans />
      </div>

      {/* comparison table */}
      <div className="max-w-5xl mx-auto px-6 pb-16">
        <h2 className="text-2xl font-display font-bold text-txt-primary text-center mb-10">
          Compare plans in detail
        </h2>
        <div className="glass-card overflow-x-auto">
          <table className="w-full min-w-[600px]">
            <thead>
              <tr className="border-b border-bg-border">
                <th className="text-left text-sm font-medium text-txt-secondary p-4">Feature</th>
                <th className="text-center text-sm font-medium text-txt-secondary p-4">Free</th>
                <th className="text-center text-sm font-medium text-accent p-4">Pro</th>
                <th className="text-center text-sm font-medium text-txt-secondary p-4">Enterprise</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row) => (
                <tr key={row.feature} className="border-b border-bg-border last:border-0">
                  <td className="text-sm text-txt-primary p-4">{row.feature}</td>
                  <td className="text-center p-4"><Cell value={row.free} /></td>
                  <td className="text-center p-4 bg-accent-muted/30"><Cell value={row.pro} /></td>
                  <td className="text-center p-4"><Cell value={row.ent} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* FAQ */}
      <div className="max-w-3xl mx-auto px-6 pb-24">
        <h2 className="text-2xl font-display font-bold text-txt-primary text-center mb-10">
          Frequently asked questions
        </h2>
        <div className="space-y-3">
          {FAQ.map((item) => (
            <details key={item.q} className="glass-card p-5 group">
              <summary className="flex items-center justify-between cursor-pointer list-none">
                <span className="text-sm font-medium text-txt-primary">{item.q}</span>
                <span className="text-txt-muted group-open:rotate-45 transition-transform text-xl leading-none">+</span>
              </summary>
              <p className="text-sm text-txt-secondary leading-relaxed mt-3">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </MarketingShell>
  );
}
