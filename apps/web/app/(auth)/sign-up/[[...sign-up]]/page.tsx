import { SignUp } from "@clerk/nextjs";
import { Zap } from "lucide-react";
import Link from "next/link";

export const metadata = {
  title: "Get Started — ProductIQ",
};

export default function SignUpPage() {
  return (
    <div className="theme-light min-h-screen flex flex-col items-center justify-center
                    bg-mkt-surface px-4 relative overflow-hidden">
      <div className="absolute inset-0 mkt-hero-glow pointer-events-none" />

      {/* Logo */}
      <Link href="/" className="relative flex items-center gap-2 mb-8 group">
        <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-mkt-brand to-mkt-teal
                         flex items-center justify-center group-hover:scale-105 transition-transform">
          <Zap className="w-4 h-4 text-white" />
        </span>
        <span className="font-display font-bold text-xl text-mkt-ink">ProductIQ</span>
      </Link>

      <div className="relative w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-display font-bold text-mkt-ink">Start for free</h1>
          <p className="text-mkt-body mt-1.5 text-sm">
            100 queries/day · No credit card required
          </p>
        </div>
        <div className="flex justify-center"><SignUp /></div>
      </div>

      <p className="relative mt-8 text-mkt-muted text-xs text-center">
        Already have an account?{" "}
        <Link href="/sign-in" className="text-mkt-brand hover:underline">Sign in →</Link>
      </p>
    </div>
  );
}
