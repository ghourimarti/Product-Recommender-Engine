import { SignUp } from "@clerk/nextjs";
import { Zap } from "lucide-react";
import Link from "next/link";

export const metadata = {
  title: "Get Started — ProductIQ",
};

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-bg-base px-4">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 mb-8 group">
        <span className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center
                         group-hover:bg-accent-hover transition-colors">
          <Zap className="w-4 h-4 text-white" />
        </span>
        <span className="font-display font-bold text-xl text-txt-primary">ProductIQ</span>
      </Link>

      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-display font-bold text-txt-primary">Start for free</h1>
          <p className="text-txt-secondary mt-1.5 text-sm">
            100 queries/day · No credit card required
          </p>
        </div>
        <SignUp />
      </div>

      <p className="mt-8 text-txt-muted text-xs text-center">
        Already have an account?{" "}
        <Link href="/sign-in" className="text-accent hover:underline">Sign in →</Link>
      </p>
    </div>
  );
}
