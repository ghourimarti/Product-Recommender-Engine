import {
  Search, Star, Sparkles, Shield, Zap, BarChart3, Layers, MessageSquare,
  ShoppingBag, Building2, Shirt, Sofa, Gamepad2, Headphones,
  BookOpen, Newspaper, FileText, Calendar, Users, Award,
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
  { label: "Case Studies",   desc: "Real results",                href: "/customers",         icon: Award },
  { label: "Documentation",  desc: "API & integration guides",    href: "/resources#docs",    icon: FileText },
  { label: "News",           desc: "Announcements",               href: "/resources#news",    icon: Newspaper },
  { label: "Events",         desc: "Webinars & talks",            href: "/resources#events",  icon: Calendar },
  { label: "Wall of Love",   desc: "What customers say",          href: "/customers#love",    icon: Users },
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
  { label: "Customers", href: "/customers" },
  { label: "Pricing",   href: "/pricing" },
];

/* ── Metric badges (used in navbar CTA + homepage) ────────────────────────── */
/* Measured only. "98.9% uptime" was fabricated — there is no uptime monitor. */
export const HEADLINE_METRICS = [
  { icon: Zap,       value: "7.6ms", label: "p95 cached" },
  { icon: BarChart3, value: "66%",   label: "cache hit rate" },
];
