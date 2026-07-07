"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, LayoutDashboard, Search, Clock, CreditCard, Settings, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { label: "Overview",  href: "/dashboard",          icon: LayoutDashboard, exact: true },
  { label: "Discover",  href: "/dashboard/discover", icon: Search },
  { label: "History",   href: "/dashboard/history",  icon: Clock },
  { label: "Billing",   href: "/dashboard/billing",  icon: CreditCard },
  { label: "Settings",  href: "/dashboard/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-mkt-border bg-white
                      fixed inset-y-0 left-0 z-40">
      {/* logo */}
      <Link href="/" className="flex items-center gap-2 h-16 px-5 border-b border-mkt-border group">
        <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-mkt-brand to-mkt-teal
                         flex items-center justify-center group-hover:scale-105 transition-transform">
          <Zap className="w-4 h-4 text-white" />
        </span>
        <span className="font-display font-bold text-lg text-mkt-ink">ProductIQ</span>
      </Link>

      {/* nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ label, href, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
                active
                  ? "bg-mkt-brand/10 text-mkt-brand font-semibold"
                  : "text-mkt-body hover:text-mkt-ink hover:bg-mkt-surface",
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* upgrade card */}
      <div className="p-3">
        <div className="rounded-xl border border-mkt-brand/20 bg-gradient-to-br from-mkt-brand/5 to-mkt-teal/5 p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <Sparkles className="w-4 h-4 text-mkt-brand" />
            <span className="text-sm font-semibold text-mkt-ink">Free plan</span>
          </div>
          <p className="text-xs text-mkt-muted mb-3 leading-relaxed">
            Upgrade to Pro for unlimited searches and reranking.
          </p>
          <Link href="/dashboard/billing" className="mkt-btn-primary w-full text-center py-2 text-xs">
            Upgrade →
          </Link>
        </div>
      </div>
    </aside>
  );
}
