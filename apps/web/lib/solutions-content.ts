import {
  Search, Star, Sparkles, Shield, MessageSquare, Layers, type LucideIcon,
} from "lucide-react";

export type SolutionContent = {
  slug: string;
  icon: LucideIcon;
  name: string;
  tagline: string;
  hero: string;
  benefits: { title: string; desc: string }[];
  how: string[];
  metric: { value: string; label: string };
};

export const SOLUTION_CONTENT: SolutionContent[] = [
  {
    slug: "semantic-search",
    icon: Search,
    name: "Semantic Search",
    tagline: "Understands intent, not keywords",
    hero: "Turn a vague, human request into the right products — even when the words don't match the listing.",
    benefits: [
      { title: "Meaning over strings", desc: "Query and catalog share one vector space, so 'survives a sweaty gym session' finds sweat-resistant, secure-fit products." },
      { title: "Hybrid retrieval", desc: "Dense embeddings for recall, BM25 sparse matching for exact model numbers and brands — the best of both." },
      { title: "Multilingual-ready", desc: "Embeddings capture meaning across phrasings, typos, and synonyms out of the box." },
    ],
    how: [
      "Every product and query is embedded into a shared vector space.",
      "A hybrid retriever combines dense (semantic) and sparse (keyword) signals.",
      "Top candidates pass to the ranking layer for quality-aware ordering.",
    ],
    // Was "10,000+ products" — fabricated. Offers are fetched live per query.
    metric: { value: "Live", label: "offers fetched per query, ranked on evidence" },
  },
  {
    slug: "rating-intelligence",
    icon: Star,
    name: "Rating Intelligence",
    tagline: "Confidence-weighted review ranking",
    hero: "A 5.0 from two reviews shouldn't beat a 4.6 from four hundred. Our ranking blend knows the difference.",
    benefits: [
      { title: "Confidence weighting", desc: "Ratings are weighted by review volume, so genuinely-loved products rise and thin outliers can't game the top." },
      { title: "Resists review gaming", desc: "Volume-aware scoring neutralizes the handful-of-5-stars trick that fools naive star sorts." },
      { title: "Blended with relevance", desc: "The final score fuses semantic fit with quality, matching how shoppers actually judge." },
    ],
    how: [
      "Each product's raw rating is combined with a confidence factor from review volume.",
      "That quality score is blended with semantic relevance to your query.",
      "Results are ordered by the blend — fit and trust together.",
    ],
    // Was "500k+ reviews" — fabricated. Ranking weights each offer's real rating by its
    // real review count, whatever that count happens to be.
    metric: { value: "Rating × volume", label: "how every result is ranked" },
  },
  {
    slug: "ai-explanations",
    icon: Sparkles,
    name: "AI Explanations",
    tagline: "Grounded, streamed reasoning",
    hero: "Every recommendation comes with a plain-language reason — grounded in the reviews it actually read.",
    benefits: [
      { title: "Grounded, not guessed", desc: "Explanations cite the retrieved reviews, with the matched-review count shown. No hallucinated specs." },
      { title: "Streamed live", desc: "Reasoning appears token-by-token so there's always motion — the app feels alive, not frozen." },
      { title: "Builds trust", desc: "Attribution ('12 reviews matched') tells shoppers the AI is summarizing evidence, not inventing it." },
    ],
    how: [
      "Retrieved reviews for the top products are passed to the language model as grounding.",
      "The model streams a concise explanation of why each product fits.",
      "The matched-review count is surfaced as transparent attribution.",
    ],
    metric: { value: "<800ms", label: "to first streamed token" },
  },
  {
    slug: "recommendations",
    icon: Layers,
    name: "Recommendations",
    tagline: "Personalized product discovery",
    hero: "Surface the right products proactively — ranked by relevance and quality, tuned to each request.",
    benefits: [
      { title: "Context-aware", desc: "Recommendations reflect the full request — budget, use case, constraints — not just a category." },
      { title: "Quality-first", desc: "The same rating-aware blend keeps recommendations trustworthy, not just popular." },
      { title: "Explainable", desc: "Each suggestion carries its relevance score and a grounded reason." },
    ],
    how: [
      "The request is embedded and matched against the catalog.",
      "Candidates are ranked with the rating-aware blend.",
      "The top shortlist is returned with scores and explanations.",
    ],
    metric: { value: "3–10", label: "ranked results per query" },
  },
  {
    slug: "conversational",
    icon: MessageSquare,
    name: "Conversational AI",
    tagline: "Follow-ups, refine, compare",
    hero: "Discovery is a conversation. Ask follow-ups, narrow requirements, and compare — with context kept across the session.",
    benefits: [
      { title: "Session memory", desc: "The assistant remembers what you asked, so refinements build on prior turns." },
      { title: "Natural refinement", desc: "'Cheaper', 'with a mic', 'more bass' — refine without starting over." },
      { title: "Compare on demand", desc: "Ask how two results differ and get a grounded, side-by-side answer." },
    ],
    how: [
      "Each query is understood in the context of the ongoing session.",
      "Follow-ups re-rank against the accumulated intent.",
      "Explanations adapt to what you've already seen.",
    ],
    metric: { value: "per-session", label: "context retention" },
  },
  {
    slug: "security",
    icon: Shield,
    name: "Enterprise Security",
    tagline: "Auth, quotas, rate limits",
    hero: "Production-grade from day one: authenticated, rate-limited, quota-metered, and resilient under provider failure.",
    benefits: [
      { title: "Authenticated access", desc: "JWT auth with per-user isolation — no session or data bleeds between users." },
      { title: "Quotas & rate limits", desc: "Per-user daily quotas and per-minute rate limits protect cost and availability." },
      { title: "Graceful degradation", desc: "Circuit breakers keep the app responsive — you still get ranked products if the LLM is down." },
    ],
    how: [
      "Every request is authenticated and checked against the user's quota.",
      "Rate limits and circuit breakers guard upstream providers.",
      "On provider failure, the system degrades to ranked results without explanations.",
    ],
    // Was "99.9% designed availability" — never measured. This IS verified: the API keeps
    // serving (popularity-ranked) with the vector DB killed, and fails over across 3 LLM providers.
    metric: { value: "Degrades", label: "keeps serving when the vector DB or LLM dies" },
  },
];

export function getSolution(slug: string) {
  return SOLUTION_CONTENT.find((s) => s.slug === slug);
}
