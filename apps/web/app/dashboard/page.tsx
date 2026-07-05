import Link from "next/link";
import { currentUser } from "@clerk/nextjs/server";
import {
  Search, Clock, TrendingUp, Zap, ArrowRight, Sparkles, Star, BarChart3,
} from "lucide-react";
import { Topbar } from "@/components/dashboard/Topbar";

/* mock usage data — in production this comes from the backend quota service */
const USAGE = { used: 27, limit: 100 };

const STATS = [
  { label: "Searches today",   value: "27",    sub: "of 100 daily",     icon: Search },
  { label: "Avg relevance",    value: "84%",   sub: "last 7 days",      icon: BarChart3 },
  { label: "Products explored", value: "142",  sub: "all time",         icon: TrendingUp },
  { label: "Avg rating found", value: "4.3★",  sub: "recommendations",  icon: Star },
];

const RECENT = [
  { q: "noise cancelling for office", when: "2 hours ago",  results: 3 },
  { q: "wireless earphones under ₹2000", when: "yesterday", results: 3 },
  { q: "gaming headset with mic",     when: "2 days ago",   results: 3 },
];

const QUICK = [
  "best earphones for gym",
  "premium home speakers",
  "budget bass headphones",
  "studio monitors",
];

export default async function DashboardHome() {
  const user = await currentUser();
  const name = user?.firstName ?? "there";
  const pct = Math.round((USAGE.used / USAGE.limit) * 100);

  return (
    <>
      <Topbar title="Overview" subtitle="Your product discovery workspace" />

      <div className="p-6 max-w-6xl mx-auto space-y-6">

        {/* greeting + quota */}
        <div className="glass-card p-6 md:p-8 relative overflow-hidden">
          <div className="absolute inset-0 bg-grid-glow pointer-events-none" />
          <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <h2 className="text-2xl font-display font-bold text-txt-primary">
                Welcome back, {name} 👋
              </h2>
              <p className="text-txt-secondary mt-1.5 text-sm">
                Ask for anything in plain language — the AI does the rest.
              </p>
              <Link href="/dashboard/discover" className="btn-primary mt-5 px-5 py-2.5 text-sm inline-flex">
                <Sparkles className="w-4 h-4" />
                Start a new search
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            {/* quota meter */}
            <div className="w-full md:w-64 shrink-0">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-txt-secondary">Daily quota</span>
                <span className="font-mono text-txt-primary">{USAGE.used}/{USAGE.limit}</span>
              </div>
              <div className="h-2 rounded-full bg-bg-border overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-accent to-purple-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-xs text-txt-muted mt-2">
                Resets in 6h · <Link href="/dashboard/billing" className="text-accent hover:underline">Upgrade for unlimited</Link>
              </p>
            </div>
          </div>
        </div>

        {/* stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {STATS.map(({ label, value, sub, icon: Icon }) => (
            <div key={label} className="glass-card p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="w-9 h-9 rounded-lg bg-accent-muted flex items-center justify-center">
                  <Icon className="w-4 h-4 text-accent" />
                </span>
              </div>
              <p className="text-2xl font-display font-bold text-txt-primary">{value}</p>
              <p className="text-sm text-txt-secondary mt-0.5">{label}</p>
              <p className="text-xs text-txt-muted mt-0.5">{sub}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* recent searches */}
          <div className="lg:col-span-2 glass-card p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2">
                <Clock className="w-4 h-4 text-txt-muted" />
                Recent searches
              </h3>
              <Link href="/dashboard/history" className="text-xs text-accent hover:underline">
                View all →
              </Link>
            </div>
            <div className="space-y-2">
              {RECENT.map((r) => (
                <Link
                  key={r.q}
                  href={`/dashboard/discover?q=${encodeURIComponent(r.q)}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-bg-elevated
                             transition-colors group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Search className="w-4 h-4 text-txt-muted shrink-0" />
                    <span className="text-sm text-txt-primary group-hover:text-accent transition-colors truncate">
                      {r.q}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-txt-muted">{r.results} results</span>
                    <span className="text-xs text-txt-muted hidden sm:block">{r.when}</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* quick actions */}
          <div className="glass-card p-6">
            <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2 mb-5">
              <Zap className="w-4 h-4 text-txt-muted" />
              Quick search
            </h3>
            <div className="space-y-2">
              {QUICK.map((q) => (
                <Link
                  key={q}
                  href={`/dashboard/discover?q=${encodeURIComponent(q)}`}
                  className="block text-sm text-txt-secondary hover:text-accent py-1.5 transition-colors"
                >
                  → {q}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
