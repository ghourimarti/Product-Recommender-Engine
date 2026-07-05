"use client";

import { useState } from "react";
import { Check, Download, CreditCard, Zap, TrendingUp } from "lucide-react";
import { Topbar } from "@/components/dashboard/Topbar";
import { cn } from "@/lib/utils";

/* mock billing state — UI only; no real Stripe. In production this reads from
   the subscription service + Stripe customer portal. */
const CURRENT_PLAN = "Free";
const USAGE = { searches: 27, limit: 100, cost: 0 };

const PLANS = [
  { name: "Free",  price: "$0",   period: "/mo", features: ["100 searches/day", "Top 3 results", "Community support"] },
  { name: "Pro",   price: "$23",  period: "/mo", features: ["Unlimited searches", "Top 10 results", "Reranking", "Priority support"], featured: true },
  { name: "Enterprise", price: "Custom", period: "", features: ["White-label + API", "SSO/SAML", "SLA + support"] },
];

const INVOICES = [
  { id: "INV-2026-006", date: "Jun 1, 2026", amount: "$0.00", status: "Paid" },
  { id: "INV-2026-005", date: "May 1, 2026", amount: "$0.00", status: "Paid" },
  { id: "INV-2026-004", date: "Apr 1, 2026", amount: "$0.00", status: "Paid" },
];

export default function BillingPage() {
  const [showModal, setShowModal] = useState<string | null>(null);
  const pct = Math.round((USAGE.searches / USAGE.limit) * 100);

  return (
    <>
      <Topbar title="Billing" subtitle="Manage your plan, usage, and invoices" />

      <div className="p-6 max-w-5xl mx-auto space-y-6">

        {/* current plan + usage */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-6 md:col-span-2">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-txt-muted uppercase tracking-widest mb-1">Current plan</p>
                <p className="text-2xl font-display font-bold text-txt-primary flex items-center gap-2">
                  {CURRENT_PLAN}
                  <span className="text-xs font-normal bg-accent-muted text-accent px-2 py-0.5 rounded-full">
                    Active
                  </span>
                </p>
              </div>
              <button
                onClick={() => setShowModal("Pro")}
                className="btn-primary px-4 py-2 text-sm"
              >
                <Zap className="w-4 h-4" /> Upgrade
              </button>
            </div>

            {/* usage bar */}
            <div className="mt-6">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-txt-secondary">Searches this period</span>
                <span className="font-mono text-txt-primary">{USAGE.searches} / {USAGE.limit}</span>
              </div>
              <div className="h-2.5 rounded-full bg-bg-border overflow-hidden">
                <div
                  className={cn("h-full rounded-full",
                    pct > 80 ? "bg-status-warning" : "bg-gradient-to-r from-accent to-purple-500")}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-xs text-txt-muted mt-2">Resets daily at midnight UTC</p>
            </div>
          </div>

          {/* spend card */}
          <div className="glass-card p-6 flex flex-col justify-center">
            <div className="flex items-center gap-2 text-txt-muted mb-1">
              <TrendingUp className="w-4 h-4" />
              <span className="text-xs uppercase tracking-widest">This month</span>
            </div>
            <p className="text-3xl font-display font-bold text-txt-primary">${USAGE.cost.toFixed(2)}</p>
            <p className="text-xs text-txt-muted mt-1">Free tier — no charges</p>
          </div>
        </div>

        {/* plan comparison */}
        <div>
          <h3 className="font-display font-semibold text-txt-primary mb-4">Available plans</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PLANS.map((plan) => {
              const isCurrent = plan.name === CURRENT_PLAN;
              return (
                <div
                  key={plan.name}
                  className={cn(
                    "glass-card p-5 flex flex-col relative",
                    plan.featured && "border-accent/50 ring-1 ring-accent/20",
                  )}
                >
                  {plan.featured && (
                    <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 bg-accent text-white
                                     text-xs font-medium px-2.5 py-0.5 rounded-full">
                      Popular
                    </span>
                  )}
                  <p className="font-display font-semibold text-txt-primary">{plan.name}</p>
                  <p className="mt-1 mb-4">
                    <span className="text-2xl font-display font-bold text-txt-primary">{plan.price}</span>
                    <span className="text-sm text-txt-muted">{plan.period}</span>
                  </p>
                  <ul className="space-y-2 flex-1 mb-4">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-xs text-txt-secondary">
                        <Check className="w-3.5 h-3.5 text-status-success mt-0.5 shrink-0" /> {f}
                      </li>
                    ))}
                  </ul>
                  {isCurrent ? (
                    <button disabled className="btn-secondary py-2 text-sm opacity-50 cursor-default">
                      Current plan
                    </button>
                  ) : (
                    <button
                      onClick={() => setShowModal(plan.name)}
                      className={cn("py-2 text-sm", plan.featured ? "btn-primary" : "btn-secondary")}
                    >
                      {plan.name === "Enterprise" ? "Contact sales" : `Switch to ${plan.name}`}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* payment method */}
        <div className="glass-card p-6">
          <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2 mb-4">
            <CreditCard className="w-4 h-4 text-txt-muted" /> Payment method
          </h3>
          <div className="flex items-center justify-between">
            <p className="text-sm text-txt-secondary">No payment method on file.</p>
            <button onClick={() => setShowModal("Pro")} className="btn-secondary px-4 py-2 text-sm">
              Add card
            </button>
          </div>
        </div>

        {/* invoices */}
        <div className="glass-card p-6">
          <h3 className="font-display font-semibold text-txt-primary mb-4">Invoice history</h3>
          <div className="space-y-1">
            {INVOICES.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between py-3 border-b border-bg-border last:border-0">
                <div className="flex items-center gap-4">
                  <span className="font-mono text-xs text-txt-muted">{inv.id}</span>
                  <span className="text-sm text-txt-secondary">{inv.date}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-txt-primary">{inv.amount}</span>
                  <span className="text-xs bg-status-success/10 text-status-success px-2 py-0.5 rounded-full">
                    {inv.status}
                  </span>
                  <button className="text-txt-muted hover:text-txt-primary" aria-label="Download">
                    <Download className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* upgrade modal (mock) */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowModal(null)}
        >
          <div
            className="glass-card p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-display font-semibold text-lg text-txt-primary mb-2">
              {showModal === "Enterprise" ? "Contact our sales team" : `Upgrade to ${showModal}`}
            </h3>
            <p className="text-sm text-txt-secondary mb-5">
              {showModal === "Enterprise"
                ? "Tell us about your use case and we'll put together a custom plan with SLA and dedicated support."
                : "This is a demo checkout. In production this opens Stripe Checkout and provisions your plan on payment."}
            </p>
            <div className="bg-bg-elevated border border-bg-border rounded-lg p-4 mb-5 text-sm text-txt-muted">
              💳 Stripe integration is stubbed in this build — no real charge occurs.
            </div>
            <div className="flex gap-3">
              <button onClick={() => setShowModal(null)} className="btn-secondary flex-1 py-2.5 text-sm">
                Cancel
              </button>
              <button onClick={() => setShowModal(null)} className="btn-primary flex-1 py-2.5 text-sm">
                {showModal === "Enterprise" ? "Request demo" : "Continue to checkout"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
