import {
  Search, Star, Sparkles, Shield, Zap, BarChart3, Layers, MessageSquare,
  ShoppingBag, Building2, Shirt, Sofa, Gamepad2, Headphones,
  BookOpen, Newspaper, FileText, Calendar, Award,
} from "lucide-react";

export type NavLeaf = { label: string; desc?: string; href: string; icon?: typeof Search };
export type NavColumn = { heading: string; items: NavLeaf[] };

/* ── Solutions (per-capability pages) ─────────────────────────────────────── */
export const SOLUTIONS: NavLeaf[] = [
  { label: "Semantic Search",     desc: "Understands intent, not keywords",   href: "/solutions/semantic-search",    icon: Search },
  { label: "Rating Intelligence", desc: "Confidence-weighted review ranking",  href: "/solutions/rating-intelligence", icon: Star },
  { label: "AI Explanations",     desc: "Grounded, streamed reasoning",        href: "/solutions/ai-explanations",     icon: Sparkles },
  { label: "Recommendations",     desc: "Personalized product discovery",      href: "/solutions/recommendations",     icon: Layers },
  { label: "Conversational AI",   desc: "Follow-ups, refine, compare",         href: "/solutions/conversational",      icon: MessageSquare },
  { label: "Enterprise Security", desc: "Auth, quotas, rate limits",           href: "/solutions/security",            icon: Shield },
];

/* ── Industries ───────────────────────────────────────────────────────────── */
export const INDUSTRIES: NavLeaf[] = [
  { label: "Consumer Electronics", desc: "Audio, wearables, gadgets", href: "/industries/electronics",  icon: Headphones },
  { label: "Fashion & Apparel",    desc: "Style-aware discovery",     href: "/industries/fashion",      icon: Shirt },
  { label: "Home & Furniture",     desc: "Attribute-rich catalogs",   href: "/industries/home",         icon: Sofa },
  { label: "Marketplaces",         desc: "High-volume, multi-seller", href: "/industries/marketplaces", icon: ShoppingBag },
  { label: "Gaming & Hobbies",     desc: "Enthusiast catalogs",       href: "/industries/gaming",       icon: Gamepad2 },
  { label: "B2B Commerce",         desc: "Complex product data",      href: "/industries/b2b",          icon: Building2 },
];

/* ── Resources ────────────────────────────────────────────────────────────── */
export const RESOURCES: NavLeaf[] = [
  { label: "Blog",           desc: "Engineering & product notes", href: "/blog",              icon: BookOpen },
  // "Case Studies / Real results" and "Wall of Love / What customers say" both pointed at
  // invented customers. There are none, so they are replaced by the one honest destination:
  // the measurements the repo can reproduce.
  { label: "Evidence",       desc: "Numbers you can reproduce",   href: "/customers",         icon: Award },
  { label: "Documentation",  desc: "API & integration guides",    href: "/resources#docs",    icon: FileText },
  { label: "News",           desc: "Announcements",               href: "/resources#news",    icon: Newspaper },
  { label: "Events",         desc: "Webinars & talks",            href: "/resources#events",  icon: Calendar },
];

/* ── Mega-menu structure ──────────────────────────────────────────────────── */
export const MEGA: { label: string; columns: NavColumn[]; featured?: NavLeaf }[] = [
  {
    label: "Solutions",
    columns: [{ heading: "Capabilities", items: SOLUTIONS }],
    featured: { label: "See the platform", desc: "How ProductIQ fits together", href: "/features" },
  },
  {
    label: "Industries",
    columns: [{ heading: "Built for", items: INDUSTRIES }],
    featured: { label: "Why verticals matter", desc: "Domain-tuned ranking & eval", href: "/industries" },
  },
  {
    label: "Resources",
    columns: [{ heading: "Learn", items: RESOURCES }],
    featured: { label: "Read the blog", desc: "Deep dives on AI discovery", href: "/blog" },
  },
];

/* ── Flat links (no dropdown) ─────────────────────────────────────────────── */
export const FLAT_LINKS: NavLeaf[] = [
  { label: "Evidence", href: "/customers" },
  { label: "Pricing",  href: "/pricing" },
];

/* ── Metric badges (used in navbar CTA + homepage) ────────────────────────── */
/* Only numbers a reader can verify from this repository.
   "98.9% uptime" was fabricated — there is no uptime monitor.
   "7.6ms p95" and "66% cache hit rate" were measured locally but no artifact was ever committed,
   so a visitor had no way to check them. Unverifiable numbers under a "measured, not claimed"
   banner are the same defect as invented ones, just smaller — so they are gone too. Replaced with
   values that are true by inspection of the committed code and CI config. */
export const HEADLINE_METRICS = [
  { icon: BarChart3, value: "117", label: "tests in CI" },
  { icon: Zap,       value: "6h",  label: "result cache" },
];
