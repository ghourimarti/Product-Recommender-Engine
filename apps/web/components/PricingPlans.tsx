"use client";

import { useState } from "react";
import Link from "next/link";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type Plan = {
  name: string;
  tagline: string;
  monthly: number;
  annual: number;   // per-month price when billed annually
  cta: string;
  href: string;
  featured?: boolean;
  features: string[];
};

export const PLANS: Plan[] = [
  {
    name: "Free",
    tagline: "For trying it out",
    monthly: 0,
    annual: 0,
    cta: "Get started",
    href: "/sign-up",
    features: [
      "100 AI searches / day",
      "Top 3 ranked results",
      "Streamed AI explanations",
      "Community support",
      "Standard models (Llama 3.1)",
    ],
  },
  {
    name: "Pro",
    tagline: "For power shoppers & small teams",
    monthly: 29,
    annual: 23,
    cta: "Start 14-day trial",
    href: "/sign-up",
    featured: true,
    features: [
      "Unlimited AI searches",
      "Top 10 ranked results",
      "Semantic caching (faster)",
      "Search history & saved lists",
      "Priority support",
      "Cross-encoder reranking",
    ],
  },
  {
    name: "Enterprise",
    tagline: "For platforms & high volume",
    monthly: -1,      // "Custom"
    annual: -1,
    cta: "Contact sales",
    href: "/contact",
    features: [
      "Everything in Pro",
      "White-label & API access",
      "Custom models & fine-tuning",
      "SSO / SAML + audit logs",
      "SLA + dedicated support",
      "Data residency options",
    ],
  },
];

function priceLabel(plan: Plan, annual: boolean) {
  if (plan.monthly < 0) return "Custom";
  const val = annual ? plan.annual : plan.monthly;
  return val === 0 ? "Free" : `$${val}`;
}

export function PricingPlans({ compact = false }: { compact?: boolean }) {
  const [annual, setAnnual] = useState(true);

  return (
    <div>
      {/* billing toggle */}
      <div className="flex items-center justify-center gap-3 mb-12">
        <span className={cn("text-sm", !annual ? "text-txt-primary" : "text-txt-muted")}>Monthly</span>
        <button
          onClick={() => setAnnual((v) => !v)}
          className="relative w-12 h-6 rounded-full bg-bg-elevated border border-bg-border transition-colors"
          aria-label="Toggle annual billing"
        >
          <span
            className={cn(
              "absolute top-0.5 w-4 h-4 rounded-full bg-accent transition-transform",
              annual ? "translate-x-6" : "translate-x-1",
            )}
          />
        </button>
        <span className={cn("text-sm", annual ? "text-txt-primary" : "text-txt-muted")}>
          Annual
          <span className="ml-1.5 text-xs text-status-success">Save 20%</span>
        </span>
      </div>

      {/* plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-5xl mx-auto">
        {PLANS.map((plan) => (
          <div
            key={plan.name}
            className={cn(
              "glass-card p-7 flex flex-col relative",
              plan.featured && "border-accent/50 ring-1 ring-accent/20",
            )}
          >
            {plan.featured && (
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-white
                               text-xs font-medium px-3 py-1 rounded-full">
                Most popular
              </span>
            )}

            <h3 className="font-display font-semibold text-lg text-txt-primary">{plan.name}</h3>
            <p className="text-sm text-txt-muted mt-1">{plan.tagline}</p>

            <div className="mt-5 flex items-baseline gap-1">
              <span className="text-4xl font-display font-bold text-txt-primary">
                {priceLabel(plan, annual)}
              </span>
              {plan.monthly > 0 && (
                <span className="text-txt-muted text-sm">/mo</span>
              )}
            </div>
            {plan.monthly > 0 && annual && (
              <p className="text-xs text-txt-muted mt-1">billed annually</p>
            )}
            {plan.monthly > 0 && !annual && <p className="text-xs text-transparent mt-1">.</p>}

            <Link
              href={plan.href}
              className={cn(
                "mt-6 w-full text-center py-2.5 text-sm",
                plan.featured ? "btn-primary" : "btn-secondary",
              )}
            >
              {plan.cta}
            </Link>

            {!compact && (
              <ul className="mt-7 space-y-3">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-txt-secondary">
                    <Check className="w-4 h-4 text-status-success mt-0.5 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
