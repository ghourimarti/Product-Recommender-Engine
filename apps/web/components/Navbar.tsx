"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/nextjs";
import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { label: "Features",   href: "/#features" },
  { label: "Categories", href: "/#categories" },
  { label: "Pricing",    href: "/#pricing" },
  { label: "Discover",   href: "/search" },
];

export function Navbar({ variant = "landing" }: { variant?: "landing" | "app" }) {
  const { isSignedIn } = useAuth();
  const pathname = usePathname();

  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-bg-border bg-bg-base/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-6">

        {/* ── Logo ── */}
        <Link href="/" className="flex items-center gap-2 shrink-0 group">
          <span className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center
                           group-hover:bg-accent-hover transition-colors">
            <Zap className="w-4 h-4 text-white" />
          </span>
          <span className="font-display font-bold text-lg tracking-tight text-txt-primary">
            ProductIQ
          </span>
        </Link>

        {/* ── Nav links (landing only) ── */}
        {variant === "landing" && (
          <nav className="hidden md:flex items-center gap-6">
            {NAV_LINKS.map(({ label, href }) => (
              <a
                key={label}
                href={href}
                className={cn(
                  "text-sm transition-colors",
                  pathname === href
                    ? "text-txt-primary"
                    : "text-txt-secondary hover:text-txt-primary",
                )}
              >
                {label}
              </a>
            ))}
          </nav>
        )}

        {/* ── App breadcrumb (search page) ── */}
        {variant === "app" && (
          <p className="hidden md:block text-sm text-txt-muted">
            AI Product Discovery
          </p>
        )}

        {/* ── Auth area ── */}
        <div className="flex items-center gap-3 shrink-0">
          {isSignedIn ? (
            <>
              {variant === "landing" && (
                <Link href="/search" className="btn-primary px-4 py-2 text-sm">
                  Open App
                </Link>
              )}
              <UserButton />
            </>
          ) : (
            <>
              <SignInButton mode="modal" forceRedirectUrl="/search">
                <button className="btn-secondary px-4 py-2 text-sm">Sign In</button>
              </SignInButton>
              <SignUpButton mode="modal" forceRedirectUrl="/search">
                <button className="btn-primary px-4 py-2 text-sm">Get Started →</button>
              </SignUpButton>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
