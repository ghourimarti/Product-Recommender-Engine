"use client";

import { UserButton } from "@clerk/nextjs";
import { Bell } from "lucide-react";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="sticky top-0 z-30 h-16 border-b border-bg-border bg-bg-base/80 backdrop-blur-xl
                       flex items-center justify-between px-6">
      <div>
        <h1 className="font-display font-semibold text-txt-primary leading-tight">{title}</h1>
        {subtitle && <p className="text-xs text-txt-muted mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {/* plan badge */}
        <span className="hidden sm:inline-flex items-center gap-1.5 text-xs text-txt-secondary
                         border border-bg-border rounded-full px-3 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
          Free plan
        </span>

        <button className="text-txt-muted hover:text-txt-primary transition-colors relative"
                aria-label="Notifications">
          <Bell className="w-4.5 h-4.5" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-accent" />
        </button>

        <UserButton />
      </div>
    </header>
  );
}
