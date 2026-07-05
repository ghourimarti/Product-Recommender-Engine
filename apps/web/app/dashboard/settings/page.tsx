"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import { User, Bell, Palette, Key, Shield } from "lucide-react";
import { Topbar } from "@/components/dashboard/Topbar";
import { cn } from "@/lib/utils";

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative w-11 h-6 rounded-full transition-colors shrink-0",
        on ? "bg-accent" : "bg-bg-elevated border border-bg-border",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform",
          on ? "translate-x-6" : "translate-x-1",
        )}
      />
    </button>
  );
}

function Row({
  icon: Icon, title, desc, children,
}: {
  icon: typeof Bell; title: string; desc: string; children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-4 border-b border-bg-border last:border-0">
      <div className="flex items-start gap-3 min-w-0">
        <span className="w-9 h-9 rounded-lg bg-bg-elevated flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4 text-txt-secondary" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-txt-primary">{title}</p>
          <p className="text-xs text-txt-muted mt-0.5">{desc}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useUser();
  const [emailNotif, setEmailNotif] = useState(true);
  const [productNotif, setProductNotif] = useState(false);
  const [reranker, setReranker] = useState(true);

  return (
    <>
      <Topbar title="Settings" subtitle="Manage your account and preferences" />

      <div className="p-6 max-w-3xl mx-auto space-y-6">

        {/* profile */}
        <div className="glass-card p-6">
          <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2 mb-5">
            <User className="w-4 h-4 text-txt-muted" /> Profile
          </h3>
          <div className="flex items-center gap-4">
            <span className="w-16 h-16 rounded-full bg-gradient-to-br from-accent/30 to-purple-500/30
                             flex items-center justify-center text-2xl font-display font-bold text-accent">
              {(user?.firstName?.[0] ?? user?.primaryEmailAddress?.emailAddress?.[0] ?? "U").toUpperCase()}
            </span>
            <div>
              <p className="text-txt-primary font-medium">
                {user?.fullName ?? "ProductIQ User"}
              </p>
              <p className="text-txt-muted text-sm">
                {user?.primaryEmailAddress?.emailAddress ?? "you@example.com"}
              </p>
              <p className="text-xs text-txt-muted mt-1">
                Manage name, email, and password via the account menu (top-right).
              </p>
            </div>
          </div>
        </div>

        {/* notifications */}
        <div className="glass-card p-6">
          <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2 mb-2">
            <Bell className="w-4 h-4 text-txt-muted" /> Notifications
          </h3>
          <Row icon={Bell} title="Email notifications" desc="Product updates and weekly digest">
            <Toggle on={emailNotif} onClick={() => setEmailNotif((v) => !v)} />
          </Row>
          <Row icon={Bell} title="Product alerts" desc="When a saved search finds better matches">
            <Toggle on={productNotif} onClick={() => setProductNotif((v) => !v)} />
          </Row>
        </div>

        {/* preferences */}
        <div className="glass-card p-6">
          <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2 mb-2">
            <Palette className="w-4 h-4 text-txt-muted" /> Search preferences
          </h3>
          <Row icon={Shield} title="Cross-encoder reranking" desc="Higher-quality ordering (Pro feature)">
            <Toggle on={reranker} onClick={() => setReranker((v) => !v)} />
          </Row>
          <Row icon={Palette} title="Theme" desc="Dark mode (light mode coming soon)">
            <span className="text-xs text-txt-muted border border-bg-border rounded-full px-3 py-1">Dark</span>
          </Row>
        </div>

        {/* API */}
        <div className="glass-card p-6">
          <h3 className="font-display font-semibold text-txt-primary flex items-center gap-2 mb-4">
            <Key className="w-4 h-4 text-txt-muted" /> API access
          </h3>
          <p className="text-sm text-txt-secondary mb-3">
            Programmatic access to ProductIQ is available on the Pro and Enterprise plans.
          </p>
          <div className="flex items-center gap-2 bg-bg-elevated border border-bg-border rounded-lg px-3 py-2.5">
            <code className="text-xs font-mono text-txt-muted flex-1 truncate">
              piq_live_••••••••••••••••••••••••  (upgrade to reveal)
            </code>
            <button className="btn-secondary px-3 py-1.5 text-xs shrink-0" disabled>Copy</button>
          </div>
        </div>

        {/* danger zone */}
        <div className="glass-card p-6 border-status-error/20">
          <h3 className="font-display font-semibold text-status-error mb-2">Danger zone</h3>
          <p className="text-sm text-txt-secondary mb-4">
            Permanently delete your account and all associated data (GDPR right-to-be-forgotten).
          </p>
          <button className="btn-secondary border-status-error/40 text-status-error hover:bg-status-error/10 px-4 py-2 text-sm">
            Delete account
          </button>
        </div>
      </div>
    </>
  );
}
