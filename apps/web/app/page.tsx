"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useInView } from "framer-motion";
import Link from "next/link";
import { SignInButton, SignUpButton } from "@clerk/nextjs";
import {
  Brain, Star, MessageSquare, Zap, Shield, BarChart3,
  Headphones, Volume2, Mic, Gamepad2, Music, Radio,
  Check, ArrowRight, Sparkles, ChevronRight,
} from "lucide-react";
import { Navbar }  from "@/components/Navbar";
import { Footer }  from "@/components/Footer";
import { cn }      from "@/lib/utils";

/* ══════════════════════════════════════════════════════════════════════════
   DATA
══════════════════════════════════════════════════════════════════════════ */
const EXAMPLE_QUERIES = [
  "noise cancelling for long flights",
  "earphones under ₹2000 with bass",
  "wireless headphones for home office",
  "gaming headset with clear mic",
];

const STATS = [
  { value: 10000, suffix: "+",  label: "Products Indexed"  },
  { value: 4,     suffix: ".2★", label: "Avg Rating Analyzed" },
  { value: 800,   suffix: "ms", label: "Avg Response Time"  },
  { value: 98,    suffix: ".9%", label: "Uptime SLA"         },
];

const FEATURES = [
  {
    icon: Brain,
    title: "Semantic Search",
    description:
      "Ask in natural language. ProductIQ understands context, synonyms, and intent — not just keyword matches.",
  },
  {
    icon: Star,
    title: "Rating Intelligence",
    description:
      "Every recommendation weighs real user ratings and review volume, not just raw averages.",
  },
  {
    icon: MessageSquare,
    title: "Conversational AI",
    description:
      "Ask follow-ups. Refine requirements. Compare options. The AI remembers your session context.",
  },
  {
    icon: Zap,
    title: "Real-time Streaming",
    description:
      "Product cards appear instantly while the AI explanation streams in token by token.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description:
      "JWT auth, per-user rate limiting, quotas, encrypted sessions, and circuit-breaker fallbacks.",
  },
  {
    icon: BarChart3,
    title: "Transparent Scoring",
    description:
      "See exactly why each product ranked where it did — relevance score, matched reviews, and reasoning.",
  },
];

const STEPS = [
  {
    title: "Describe What You Need",
    body:  "Type in natural language — be as specific or vague as you like. No filters to configure.",
  },
  {
    title: "AI Analyses Real Reviews",
    body:  "ProductIQ scans thousands of products and genuine user reviews for relevance and quality signals.",
  },
  {
    title: "Get Ranked Results",
    body:  "Receive ranked product cards with AI-generated explanations and transparent relevance scores.",
  },
];

const CATEGORIES = [
  { label: "Earphones",    count: "247 products",  icon: Music,      q: "earphones" },
  { label: "Headphones",   count: "156 products",  icon: Headphones, q: "over ear headphones" },
  { label: "TWS Earbuds",  count: "183 products",  icon: Radio,      q: "true wireless earbuds" },
  { label: "Speakers",     count: "94 products",   icon: Volume2,    q: "bluetooth speakers" },
  { label: "Gaming",       count: "61 products",   icon: Gamepad2,   q: "gaming headset" },
  { label: "Professional", count: "28 products",   icon: Mic,        q: "studio headphones" },
];

const PLANS = [
  {
    name:        "Free",
    price:       "$0",
    period:      "/month",
    description: "Perfect for personal use and exploration.",
    cta:         "Get Started Free",
    ctaVariant:  "secondary" as const,
    highlighted: false,
    features: [
      "100 queries / day",
      "3 results per search",
      "Standard response time",
      "Community support",
    ],
  },
  {
    name:        "Pro",
    price:       "$29",
    period:      "/month",
    description: "For power users who discover daily.",
    cta:         "Start 14-Day Trial",
    ctaVariant:  "primary" as const,
    highlighted: true,
    features: [
      "Unlimited queries",
      "10 results per search",
      "Priority response time",
      "Search history & export",
      "Email support",
      "API access (1k req/day)",
    ],
  },
  {
    name:        "Enterprise",
    price:       "Custom",
    period:      "",
    description: "White-label, custom integrations, SLA.",
    cta:         "Contact Sales",
    ctaVariant:  "secondary" as const,
    highlighted: false,
    features: [
      "Unlimited everything",
      "White-label option",
      "Dedicated API quota",
      "SLA guarantee",
      "Dedicated support",
      "Custom integrations",
    ],
  },
];

const TESTIMONIALS = [
  {
    quote:  "Found the perfect noise-cancelling headphones in seconds. The AI explanation helped me understand the trade-offs rather than just handing me a list.",
    name:   "Arjun S.",
    role:   "Freelance Music Producer",
    stars:  5,
  },
  {
    quote:  "I used to spend hours reading Amazon reviews. ProductIQ synthesises all of that and gives me a ranked result with reasoning I can actually trust.",
    name:   "Priya M.",
    role:   "UX Designer",
    stars:  5,
  },
  {
    quote:  "The relevance score is transparent and actually makes sense. I trust its recommendations more than influencer picks or sponsored results.",
    name:   "Vikram R.",
    role:   "Audio Engineer",
    stars:  5,
  },
];

/* ══════════════════════════════════════════════════════════════════════════
   ANIMATED COUNTER
══════════════════════════════════════════════════════════════════════════ */
function AnimatedCounter({ to, suffix }: { to: number; suffix: string }) {
  const ref    = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const steps    = 50;
    const duration = 1400;
    const inc      = to / steps;
    let   curr     = 0;
    let   step     = 0;
    const id = setInterval(() => {
      step++;
      curr = Math.min(to, Math.round(inc * step));
      setVal(curr);
      if (curr >= to) clearInterval(id);
    }, duration / steps);
    return () => clearInterval(id);
  }, [inView, to]);

  return (
    <span ref={ref} className="tabular-nums">
      {val.toLocaleString()}
      {suffix}
    </span>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   PAGE
══════════════════════════════════════════════════════════════════════════ */
export default function LandingPage() {
  const router = useRouter();
  const [heroQuery, setHeroQuery] = useState("");

  function handleHeroSearch() {
    const q = heroQuery.trim();
    if (!q) return;
    router.push(`/dashboard/discover?q=${encodeURIComponent(q)}`);
  }

  return (
    <div className="min-h-screen bg-bg-base text-txt-primary">
      <Navbar />

      {/* ══ HERO ═══════════════════════════════════════════════════════════ */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-16">

        {/* ambient gradient orbs */}
        <div className="absolute inset-0 -z-10 pointer-events-none">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[600px]
                          bg-accent/6 rounded-full blur-[120px]" />
          <div className="absolute top-40 left-1/4 w-[400px] h-[400px]
                          bg-purple-600/5 rounded-full blur-[100px]" />
          <div className="absolute top-60 right-1/4 w-[300px] h-[300px]
                          bg-indigo-400/4 rounded-full blur-[80px]" />
        </div>

        <div className="max-w-4xl mx-auto px-6 text-center">

          {/* eyebrow badge */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-2 px-3 py-1.5 mb-8
                       border border-accent/25 rounded-full bg-accent/5
                       text-xs text-accent font-medium"
          >
            <Sparkles className="w-3 h-3" />
            AI-Powered Product Discovery Engine
          </motion.div>

          {/* headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.08 }}
            className="text-5xl md:text-6xl font-display font-bold leading-tight mb-6 tracking-tight"
          >
            Discover Products With AI
            <span className="gradient-text block mt-1">
              That Actually Understands You
            </span>
          </motion.h1>

          {/* subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.16 }}
            className="text-lg text-txt-secondary max-w-2xl mx-auto mb-10 leading-relaxed"
          >
            Semantic search meets rating intelligence. Get personalised product
            recommendations powered by real reviews — with AI-generated explanations
            you can actually trust.
          </motion.p>

          {/* hero search */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.24 }}
            className="flex flex-col sm:flex-row gap-3 max-w-2xl mx-auto mb-5"
          >
            <input
              value={heroQuery}
              onChange={(e) => setHeroQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleHeroSearch()}
              placeholder="e.g. best earphones for gym with good bass…"
              className="input-search text-base py-4 flex-1 text-left"
            />
            <button
              onClick={handleHeroSearch}
              className="btn-primary px-7 py-4 text-base whitespace-nowrap shrink-0"
            >
              Discover →
            </button>
          </motion.div>

          {/* example query chips */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.35 }}
            className="flex flex-wrap gap-2 justify-center mb-12"
          >
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => setHeroQuery(q)}
                className="text-sm text-txt-muted hover:text-txt-secondary
                           border border-bg-border hover:border-accent/40
                           rounded-full px-4 py-1.5 transition-all duration-150"
              >
                {q}
              </button>
            ))}
          </motion.div>

          {/* trust indicators */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.4 }}
            className="flex flex-wrap items-center justify-center gap-4 text-sm text-txt-muted"
          >
            <span className="flex items-center gap-1.5">
              <span className="text-rank-gold">★★★★★</span>
              <span>4.8 / 5</span>
            </span>
            <span className="text-bg-border hidden sm:block">|</span>
            <span>Trusted by 12,000+ shoppers</span>
            <span className="text-bg-border hidden sm:block">|</span>
            <span>No credit card required</span>
          </motion.div>
        </div>
      </section>

      {/* ══ STATS BAR ══════════════════════════════════════════════════════ */}
      <div className="border-y border-bg-border bg-bg-surface/40">
        <div className="max-w-7xl mx-auto px-6 py-10">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {STATS.map((s) => (
              <div key={s.label}>
                <p className="text-3xl font-display font-bold text-txt-primary mb-1">
                  <AnimatedCounter to={s.value} suffix={s.suffix} />
                </p>
                <p className="text-txt-muted text-sm">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ══ FEATURES ═══════════════════════════════════════════════════════ */}
      <section id="features" className="section-pad">
        <div className="section-inner">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <p className="text-accent text-sm font-semibold uppercase tracking-widest mb-3">
              Why ProductIQ
            </p>
            <h2 className="text-4xl font-display font-bold mb-4">
              Everything you need to discover smarter
            </h2>
            <p className="text-txt-secondary leading-relaxed">
              We combine semantic language understanding, review-weighted ranking, and
              conversational AI into one seamless product-discovery experience.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-5">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.4, delay: i * 0.07 }}
                className="glass-card p-6 hover:border-accent/30 transition-colors group"
              >
                <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center
                                mb-4 group-hover:bg-accent/20 transition-colors">
                  <f.icon className="w-5 h-5 text-accent" />
                </div>
                <h3 className="font-semibold text-txt-primary mb-2">{f.title}</h3>
                <p className="text-txt-secondary text-sm leading-relaxed">{f.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ HOW IT WORKS ═══════════════════════════════════════════════════ */}
      <section className="section-pad bg-bg-surface/25">
        <div className="section-inner">
          <div className="text-center mb-16">
            <p className="text-accent text-sm font-semibold uppercase tracking-widest mb-3">
              The Process
            </p>
            <h2 className="text-4xl font-display font-bold">How ProductIQ Works</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* connecting line */}
            <div className="hidden md:block absolute top-8 left-[33%] right-[33%] h-px
                            bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

            {STEPS.map((step, i) => (
              <motion.div
                key={step.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="text-center"
              >
                <div className="w-16 h-16 bg-accent/10 border border-accent/20 rounded-2xl
                                flex items-center justify-center mx-auto mb-6 relative z-10">
                  <span className="text-2xl font-display font-bold text-accent">{i + 1}</span>
                </div>
                <h3 className="font-semibold text-txt-primary mb-2">{step.title}</h3>
                <p className="text-txt-secondary text-sm leading-relaxed">{step.body}</p>
              </motion.div>
            ))}
          </div>

          {/* mini demo preview */}
          <div className="mt-16 glass-card p-6 md:p-8 max-w-3xl mx-auto">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
              <div className="w-3 h-3 rounded-full bg-green-500/60" />
              <span className="ml-2 text-xs text-txt-muted font-mono">productiq.app/search</span>
            </div>
            <div className="bg-bg-elevated rounded-lg px-4 py-3 mb-4 border border-bg-border
                            flex items-center gap-2 text-txt-muted text-sm">
              <span>🔍</span>
              <span className="font-mono">best wireless earphones for gym under ₹3000</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {["🥇 Sony WH-CH720N", "🥈 boAt Airdopes 141", "🥉 JBL Tune 130NC"].map(
                (item, i) => (
                  <div key={i} className="bg-bg-base border border-bg-border rounded-lg p-3">
                    <p className="text-xs font-medium text-txt-secondary">{item}</p>
                    <p className="text-xs text-txt-muted mt-1">
                      {["★★★★★ 4.5 · 84%", "★★★★★ 4.3 · 76%", "★★★★☆ 4.1 · 67%"][i]}
                    </p>
                  </div>
                ),
              )}
            </div>
            <p className="mt-4 text-xs text-txt-muted italic leading-relaxed">
              ✦ AI Analysis streaming… "The Sony WH-CH720N leads for gym use due to its
              lightweight design and strong bass emphasis confirmed across 47 reviews…"
            </p>
          </div>
        </div>
      </section>

      {/* ══ CATEGORIES ═════════════════════════════════════════════════════ */}
      <section id="categories" className="section-pad">
        <div className="section-inner">
          <div className="text-center mb-12">
            <p className="text-accent text-sm font-semibold uppercase tracking-widest mb-3">
              Browse
            </p>
            <h2 className="text-4xl font-display font-bold mb-3">Shop by Category</h2>
            <p className="text-txt-secondary">
              10,000+ audio products across every category — all searchable by natural language.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {CATEGORIES.map((cat, i) => (
              <motion.div
                key={cat.label}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.35, delay: i * 0.06 }}
              >
                <Link
                  href={`/dashboard/discover?q=${encodeURIComponent(cat.q)}`}
                  className="glass-card p-5 flex items-center gap-4
                             hover:border-accent/40 transition-all duration-200 group block"
                >
                  <div className="w-11 h-11 bg-accent/10 rounded-xl flex items-center justify-center
                                  group-hover:bg-accent/20 transition-colors shrink-0">
                    <cat.icon className="w-5 h-5 text-accent" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-txt-primary group-hover:text-accent
                                  transition-colors truncate">
                      {cat.label}
                    </p>
                    <p className="text-txt-muted text-xs mt-0.5">{cat.count}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-txt-muted group-hover:text-accent
                                           ml-auto shrink-0 transition-colors" />
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ PRICING ════════════════════════════════════════════════════════ */}
      <section id="pricing" className="section-pad bg-bg-surface/25">
        <div className="section-inner">
          <div className="text-center mb-14">
            <p className="text-accent text-sm font-semibold uppercase tracking-widest mb-3">
              Pricing
            </p>
            <h2 className="text-4xl font-display font-bold mb-3">
              Simple, transparent pricing
            </h2>
            <p className="text-txt-secondary">
              Start free. Upgrade when you need more. No surprise charges.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className={cn(
                  "glass-card p-7 flex flex-col relative",
                  plan.highlighted &&
                    "border-accent/50 ring-1 ring-accent/20 bg-accent/[0.03]",
                )}
              >
                {plan.highlighted && (
                  <div className="absolute -top-px left-1/2 -translate-x-1/2
                                  px-4 py-1 bg-accent rounded-b-lg
                                  text-white text-xs font-semibold">
                    Most Popular
                  </div>
                )}

                <div className="mb-5">
                  <p className="text-txt-secondary text-sm font-medium mb-1">{plan.name}</p>
                  <p className="text-4xl font-display font-bold text-txt-primary">
                    {plan.price}
                    <span className="text-base font-normal text-txt-muted">{plan.period}</span>
                  </p>
                  <p className="text-txt-muted text-sm mt-2">{plan.description}</p>
                </div>

                <ul className="space-y-2.5 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2.5 text-sm text-txt-secondary">
                      <Check className="w-4 h-4 text-status-success shrink-0 mt-0.5" />
                      {f}
                    </li>
                  ))}
                </ul>

                {plan.ctaVariant === "primary" ? (
                  <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                    <button className="btn-primary py-3 w-full text-sm">{plan.cta}</button>
                  </SignUpButton>
                ) : (
                  <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                    <button className="btn-secondary py-3 w-full text-sm">{plan.cta}</button>
                  </SignUpButton>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ TESTIMONIALS ═══════════════════════════════════════════════════ */}
      <section className="section-pad">
        <div className="section-inner">
          <div className="text-center mb-12">
            <p className="text-accent text-sm font-semibold uppercase tracking-widest mb-3">
              Testimonials
            </p>
            <h2 className="text-4xl font-display font-bold">What our users say</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {TESTIMONIALS.map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className="glass-card p-6 flex flex-col"
              >
                <div className="flex gap-0.5 mb-4">
                  {[...Array(t.stars)].map((_, j) => (
                    <span key={j} className="text-rank-gold text-sm">★</span>
                  ))}
                </div>
                <p className="text-txt-secondary text-sm leading-relaxed flex-1 mb-5">
                  &ldquo;{t.quote}&rdquo;
                </p>
                <div>
                  <p className="text-txt-primary text-sm font-semibold">{t.name}</p>
                  <p className="text-txt-muted text-xs mt-0.5">{t.role}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ FINAL CTA ══════════════════════════════════════════════════════ */}
      <section className="section-pad bg-bg-surface/25">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45 }}
          >
            <div className="w-14 h-14 bg-accent/10 border border-accent/20 rounded-2xl
                            flex items-center justify-center mx-auto mb-6">
              <Sparkles className="w-6 h-6 text-accent" />
            </div>
            <h2 className="text-4xl font-display font-bold mb-4">
              Ready to discover smarter?
            </h2>
            <p className="text-txt-secondary text-lg mb-8 leading-relaxed">
              Start with 100 free queries per day. No credit card required.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <SignUpButton mode="modal" forceRedirectUrl="/dashboard">
                <button className="btn-primary px-8 py-3.5 text-base">
                  Start Free
                  <ArrowRight className="w-4 h-4" />
                </button>
              </SignUpButton>
              <SignInButton mode="modal" forceRedirectUrl="/dashboard">
                <button className="btn-secondary px-8 py-3.5 text-base">Sign In</button>
              </SignInButton>
            </div>
            <p className="text-txt-muted text-sm mt-5">
              Already exploring?{" "}
              <Link href="/dashboard" className="text-accent hover:underline">
                Open the app →
              </Link>
            </p>
          </motion.div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
