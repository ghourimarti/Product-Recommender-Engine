"use client";

import { UserButton } from "@clerk/nextjs";
import { Bell } from "lucide-react";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="sticky top-0 z-30 h-16 border-b border-mkt-border bg-white/85 backdrop-blur-xl
                       flex items-center justify-between px-6">
      <div>
        <h1 className="font-display font-semibold text-mkt-ink leading-tight">{title}</h1>
        {subtitle && <p className="text-xs text-mkt-muted mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* plan badge */}
        <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-mkt-body
                         border border-mkt-border rounded-full px-3 py-1 bg-white">
          <span className="w-1.5 h-1.5 rounded-full bg-mkt-teal" />
          Free plan
        </span>

        <button className="text-mkt-muted hover:text-mkt-ink transition-colors relative"
                aria-label="Notifications">
          <Bell className="w-[18px] h-[18px]" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-mkt-brand" />
        </button>

        <UserButton />
      </div>
    </header>
  );
}
