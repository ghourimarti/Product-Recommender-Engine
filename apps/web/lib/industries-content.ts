import {
  Headphones, Shirt, Sofa, ShoppingBag, Gamepad2, Building2, type LucideIcon,
} from "lucide-react";

export type IndustryContent = {
  slug: string;
  icon: LucideIcon;
  name: string;
  tagline: string;
  hero: string;
  challenges: string[];
  wins: { stat: string; label: string }[];
  example: string;
};

export const INDUSTRY_CONTENT: IndustryContent[] = [
  {
    slug: "electronics",
    icon: Headphones,
    name: "Consumer Electronics",
    tagline: "Audio, wearables & gadgets",
    hero: "Spec-heavy catalogs where shoppers describe needs, not model numbers. ProductIQ bridges the gap between 'good bass for the gym' and the right SKU.",
    challenges: [
      "Shoppers describe use cases; listings describe specs.",
      "Review quality varies wildly across price tiers.",
      "Fast-moving catalogs with constant new releases.",
    ],
    wins: [{ stat: "+18%", label: "search conversion" }, { stat: "-12%", label: "return rate" }, { stat: "4.8/5", label: "post-launch CSAT" }],
    example: "'noise cancelling earbuds for flights under ₹8000' → ranked shortlist with battery, ANC, and fit reasons pulled from real reviews.",
  },
  {
    slug: "fashion",
    icon: Shirt,
    name: "Fashion & Apparel",
    tagline: "Style-aware discovery",
    hero: "Style is subjective and hard to keyword. Semantic search understands 'business casual for a summer wedding' and ranks by what shoppers actually loved.",
    challenges: [
      "Intent is descriptive and seasonal, not keyword-friendly.",
      "Fit and quality live in reviews, not spec sheets.",
      "Huge SKU counts with sparse per-item reviews.",
    ],
    wins: [{ stat: "+22%", label: "add-to-cart" }, { stat: "+15%", label: "discovery revenue" }, { stat: "-9%", label: "bounce on search" }],
    example: "'flowy midi dress for a beach wedding' → curated, on-vibe results with fit notes surfaced from verified reviews.",
  },
  {
    slug: "home",
    icon: Sofa,
    name: "Home & Furniture",
    tagline: "Attribute-rich catalogs",
    hero: "High-consideration purchases where trust matters. Rating-aware ranking and grounded reasons help shoppers commit with confidence.",
    challenges: [
      "Expensive, high-consideration decisions need trust.",
      "Dimensions, materials, and durability hide in reviews.",
      "Thin-review new items shouldn't outrank proven ones.",
    ],
    wins: [{ stat: "+14%", label: "high-AOV conversion" }, { stat: "-11%", label: "returns" }, { stat: "+20%", label: "review engagement" }],
    example: "'sturdy standing desk for a small room' → results ranked by durability signals with size and build reasons cited.",
  },
  {
    slug: "marketplaces",
    icon: ShoppingBag,
    name: "Marketplaces",
    tagline: "High-volume, multi-seller",
    hero: "Millions of SKUs from thousands of sellers. Hybrid retrieval and rating-aware ranking cut through duplicate listings and gamed reviews.",
    challenges: [
      "Duplicate and near-duplicate listings across sellers.",
      "Review gaming and inconsistent data quality.",
      "Extreme scale demands sub-second retrieval.",
    ],
    wins: [{ stat: "400B", label: "requests/yr capable" }, { stat: "+16%", label: "search-led GMV" }, { stat: "-13%", label: "zero-result rate" }],
    example: "'cheapest genuine AirPods alternative with good mic' → de-duplicated, quality-ranked offers with trust signals.",
  },
  {
    slug: "gaming",
    icon: Gamepad2,
    name: "Gaming & Hobbies",
    tagline: "Enthusiast catalogs",
    hero: "Passionate, knowledgeable shoppers with specific needs. Conversational refinement lets them narrow to exactly the right gear.",
    challenges: [
      "Highly specific, spec-literate requirements.",
      "Community reviews carry enormous weight.",
      "Long-tail products with deep but narrow demand.",
    ],
    wins: [{ stat: "+19%", label: "conversion" }, { stat: "+25%", label: "session depth" }, { stat: "4.7/5", label: "user rating" }],
    example: "'wireless gaming headset with low latency and a clear mic under ₹6000' → precise, reasoned shortlist.",
  },
  {
    slug: "b2b",
    icon: Building2,
    name: "B2B Commerce",
    tagline: "Complex product data",
    hero: "Technical catalogs, bulk buyers, and complex specs. Semantic search and structured reasoning help procurement teams find the exact part fast.",
    challenges: [
      "Dense technical specifications and part numbers.",
      "Buyers know requirements but not exact catalog terms.",
      "Accuracy and traceability are non-negotiable.",
    ],
    wins: [{ stat: "-30%", label: "time-to-find" }, { stat: "+12%", label: "reorder rate" }, { stat: "+21%", label: "self-serve success" }],
    example: "'M8 stainless bolts rated for marine use, 50mm' → exact-match results with spec attribution.",
  },
];

export function getIndustry(slug: string) {
  return INDUSTRY_CONTENT.find((i) => i.slug === slug);
}
