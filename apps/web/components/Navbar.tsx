"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/nextjs";
import { Zap, ChevronDown, Search, Star, Sparkles, Shield, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

/* ── feature dropdown items ───────────────────────────────────────────────── */
const FEATURE_ITEMS = [
  { label: "Semantic Search",     desc: "Understands intent, not keywords",  icon: Search,   href: "/features#semantic" },
  { label: "Rating Intelligence", desc: "Weighs real reviews, not averages", icon: Star,     href: "/features#rating" },
  { label: "AI Explanations",     desc: "Transparent, grounded reasoning",   icon: Sparkles, href: "/features#explain" },
  { label: "Enterprise Security", desc: "Auth, quotas, rate limits",         icon: Shield,   href: "/features#security" },
];

const NAV_LINKS = [
  { label: "Pricing", href: "/pricing" },
  { label: "Blog",    href: "/blog" },
  { label: "About",   href: "/about" },
  { label: "Contact", href: "/contact" },
];

export function Navbar() {
  const { isSignedIn } = useAuth();
  const pathname = usePathname();
  const [featOpen, setFeatOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-bg-border bg-bg-base/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-6">

        {/* ── Logo ── */}
        <Link href="/" className="flex items-center gap-2 shrink-0 group">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-purple-500
                           flex items-center justify-center group-hover:scale-105 transition-transform">
            <Zap className="w-4 h-4 text-white" />
          </span>
          <span className="font-display font-bold text-lg tracking-tight text-txt-primary">
            ProductIQ
          </span>
        </Link>

        {/* ── Desktop nav ── */}
        <nav className="hidden lg:flex items-center gap-1">
          {/* Features dropdown */}
          <div
            className="relative"
            onMouseEnter={() => setFeatOpen(true)}
            onMouseLeave={() => setFeatOpen(false)}
          >
            <button className="flex items-center gap-1 px-3 py-2 text-sm text-txt-secondary
                               hover:text-txt-primary transition-colors">
              Features
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", featOpen && "rotate-180")} />
            </button>

            {featOpen && (
              <div className="absolute top-full left-0 pt-2 w-80">
                <div className="glass-card p-2 shadow-2xl shadow-black/40">
                  {FEATURE_ITEMS.map(({ label, desc, icon: Icon, href }) => (
                    <Link
                      key={label}
                      href={href}
                      className="flex items-start gap-3 p-3 rounded-lg hover:bg-bg-elevated transition-colors group"
                    >
                      <span className="w-9 h-9 rounded-lg bg-accent-muted flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4 text-accent" />
                      </span>
                      <span>
                        <span className="block text-sm font-medium text-txt-primary group-hover:text-accent transition-colors">
                          {label}
                        </span>
                        <span className="block text-xs text-txt-muted mt-0.5">{desc}</span>
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          {NAV_LINKS.map(({ label, href }) => (
            <Link
              key={label}
              href={href}
              className={cn(
                "px-3 py-2 text-sm transition-colors",
                pathname === href ? "text-txt-primary" : "text-txt-secondary hover:text-txt-primary",
              )}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* ── Auth area ── */}
        <div className="hidden lg:flex items-center gap-3 shrink-0">
          {isSignedIn ? (
            <>
              <Link href="/dashboard" className="btn-secondary px-4 py-2 text-sm">Dashboard</Link>
              <UserButton />
            </>
          ) : (
            <>
              <SignInButton mode="modal" forceRedirectUrl="/dashboard">
                <button className="btn-ghost text-sm px-3 py-2">Sign In</button>
              </SignInButton>
              <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                <button className="btn-primary px-4 py-2 text-sm">Start Free →</button>
              </SignUpButton>
            </>
          )}
        </div>

        {/* ── Mobile toggle ── */}
        <button
          className="lg:hidden text-txt-secondary hover:text-txt-primary"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* ── Mobile menu ── */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-bg-border bg-bg-base px-6 py-4 space-y-1">
          <Link href="/features" className="block py-2 text-sm text-txt-secondary">Features</Link>
          {NAV_LINKS.map(({ label, href }) => (
            <Link key={label} href={href} className="block py-2 text-sm text-txt-secondary">
              {label}
            </Link>
          ))}
          <div className="pt-3 border-t border-bg-border flex flex-col gap-2">
            {isSignedIn ? (
              <Link href="/dashboard" className="btn-primary px-4 py-2 text-sm text-center">Dashboard</Link>
            ) : (
              <>
                <SignInButton mode="modal" forceRedirectUrl="/dashboard">
                  <button className="btn-secondary px-4 py-2 text-sm w-full">Sign In</button>
                </SignInButton>
                <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                  <button className="btn-primary px-4 py-2 text-sm w-full">Start Free →</button>
                </SignUpButton>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
