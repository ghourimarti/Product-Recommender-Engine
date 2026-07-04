import { SignIn } from "@clerk/nextjs";
import { Zap } from "lucide-react";
import Link from "next/link";

export const metadata = {
  title: "Sign In — ProductIQ",
};

export default function SignInPage() {
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
          <h1 className="text-2xl font-display font-bold text-txt-primary">Welcome back</h1>
          <p className="text-txt-secondary mt-1.5 text-sm">
            Sign in to your ProductIQ account
          </p>
        </div>
        <SignIn />
      </div>

      <p className="mt-8 text-txt-muted text-xs text-center">
        By signing in you agree to our{" "}
        <Link href="#" className="text-accent hover:underline">Terms</Link> and{" "}
        <Link href="#" className="text-accent hover:underline">Privacy Policy</Link>.
      </p>
    </div>
  );
}
