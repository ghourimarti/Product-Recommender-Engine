"use client";

import Link from "next/link";
import { useState } from "react";
import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/nextjs";
import { Zap, ChevronDown, ArrowRight, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { MEGA, FLAT_LINKS } from "@/lib/nav";

export function MarketingNavbar() {
  const { isSignedIn } = useAuth();
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur-xl border-b border-mkt-border">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-6">

        {/* ── Logo ── */}
        <Link href="/" className="flex items-center gap-2 shrink-0 group">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-mkt-brand to-mkt-teal
                           flex items-center justify-center group-hover:scale-105 transition-transform">
            <Zap className="w-4 h-4 text-white" />
          </span>
          <span className="font-display font-bold text-lg tracking-tight text-mkt-ink">
            ProductIQ
          </span>
        </Link>

        {/* ── Desktop mega-menu nav ── */}
        <nav className="hidden lg:flex items-center gap-1" onMouseLeave={() => setOpenMenu(null)}>
          {MEGA.map((menu) => (
            <div
              key={menu.label}
              className="relative"
              onMouseEnter={() => setOpenMenu(menu.label)}
            >
              <button className={cn(
                "flex items-center gap-1 px-3 py-2 text-sm font-medium rounded-lg transition-colors",
                openMenu === menu.label ? "text-mkt-brand" : "text-mkt-body hover:text-mkt-ink",
              )}>
                {menu.label}
                <ChevronDown className={cn("w-3.5 h-3.5 transition-transform",
                  openMenu === menu.label && "rotate-180")} />
              </button>

              {/* mega panel */}
              {openMenu === menu.label && (
                <div className="absolute top-full left-1/2 -translate-x-1/2 pt-3">
                  <div className="w-[640px] bg-white rounded-2xl border border-mkt-border shadow-2xl
                                  shadow-slate-300/40 p-3 grid grid-cols-3 gap-2">
                    {/* leaf items (2 cols) */}
                    <div className="col-span-2 grid grid-cols-2 gap-1">
                      {menu.columns[0].items.map((leaf) => (
                        <Link
                          key={leaf.label}
                          href={leaf.href}
                          className="flex items-start gap-3 p-3 rounded-xl hover:bg-mkt-surface transition-colors group"
                        >
                          {leaf.icon && (
                            <span className="w-9 h-9 rounded-lg bg-mkt-elevated flex items-center justify-center shrink-0
                                             group-hover:bg-mkt-brand/10 transition-colors">
                              <leaf.icon className="w-4 h-4 text-mkt-brand" />
                            </span>
                          )}
                          <span>
                            <span className="block text-sm font-semibold text-mkt-ink group-hover:text-mkt-brand transition-colors">
                              {leaf.label}
                            </span>
                            {leaf.desc && <span className="block text-xs text-mkt-muted mt-0.5 leading-snug">{leaf.desc}</span>}
                          </span>
                        </Link>
                      ))}
                    </div>

                    {/* featured card */}
                    {menu.featured && (
                      <Link
                        href={menu.featured.href}
                        className="rounded-xl bg-gradient-to-br from-mkt-brand to-mkt-teal p-4 flex flex-col justify-between
                                   text-white group"
                      >
                        <div>
                          <p className="font-semibold text-sm">{menu.featured.label}</p>
                          <p className="text-xs text-white/80 mt-1 leading-snug">{menu.featured.desc}</p>
                        </div>
                        <span className="inline-flex items-center gap-1 text-xs font-medium mt-4">
                          Learn more <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                        </span>
                      </Link>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {FLAT_LINKS.map((l) => (
            <Link key={l.label} href={l.href}
              className="px-3 py-2 text-sm font-medium text-mkt-body hover:text-mkt-ink rounded-lg transition-colors">
              {l.label}
            </Link>
          ))}
        </nav>

        {/* ── Auth / CTA ── */}
        <div className="hidden lg:flex items-center gap-3 shrink-0">
          {isSignedIn ? (
            <>
              <Link href="/dashboard" className="mkt-btn-secondary px-4 py-2 text-sm">Dashboard</Link>
              <UserButton />
            </>
          ) : (
            <>
              <SignInButton mode="modal" forceRedirectUrl="/dashboard">
                <button className="mkt-btn-ghost text-sm px-3 py-2">Sign in</button>
              </SignInButton>
              <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                <button className="mkt-btn-primary px-4 py-2 text-sm">Start free →</button>
              </SignUpButton>
            </>
          )}
        </div>

        {/* ── Mobile toggle ── */}
        <button className="lg:hidden text-mkt-body" onClick={() => setMobileOpen((v) => !v)} aria-label="Menu">
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* ── Mobile menu ── */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-mkt-border bg-white px-6 py-4 max-h-[80vh] overflow-y-auto">
          {MEGA.map((menu) => (
            <div key={menu.label} className="py-2">
              <p className="text-xs font-bold uppercase tracking-widest text-mkt-muted mb-2">{menu.label}</p>
              <div className="space-y-1">
                {menu.columns[0].items.map((leaf) => (
                  <Link key={leaf.label} href={leaf.href} onClick={() => setMobileOpen(false)}
                    className="block py-1.5 text-sm text-mkt-body">
                    {leaf.label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
          {FLAT_LINKS.map((l) => (
            <Link key={l.label} href={l.href} onClick={() => setMobileOpen(false)}
              className="block py-2 text-sm font-medium text-mkt-ink">{l.label}</Link>
          ))}
          <div className="pt-3 mt-2 border-t border-mkt-border flex flex-col gap-2">
            {isSignedIn ? (
              <Link href="/dashboard" className="mkt-btn-primary px-4 py-2.5 text-sm">Dashboard</Link>
            ) : (
              <>
                <SignInButton mode="modal" forceRedirectUrl="/dashboard">
                  <button className="mkt-btn-secondary px-4 py-2.5 text-sm w-full">Sign in</button>
                </SignInButton>
                <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                  <button className="mkt-btn-primary px-4 py-2.5 text-sm w-full">Start free →</button>
                </SignUpButton>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
