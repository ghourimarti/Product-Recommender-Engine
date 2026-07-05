export type Post = {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  date: string;
  readTime: string;
  author: string;
  /** paragraphs; strings starting with "## " render as subheadings */
  body: string[];
};

export const POSTS: Post[] = [
  {
    slug: "semantic-search-vs-keyword-search",
    title: "Semantic Search vs. Keyword Search: Why It Matters for Product Discovery",
    excerpt:
      "Keyword search matches strings. Semantic search matches meaning. Here's why that difference decides whether a shopper finds the right product — or bounces.",
    category: "Engineering",
    date: "June 24, 2026",
    readTime: "6 min read",
    author: "ProductIQ Team",
    body: [
      "When a shopper types 'earphones that survive a sweaty gym session,' a keyword search looks for the literal words: 'earphones,' 'sweaty,' 'gym.' If a great sweat-resistant product's listing says 'IPX7 water resistance, secure ear-hook fit,' keyword search misses it entirely — none of the words match.",
      "## The vector-space insight",
      "Semantic search solves this by converting both the query and every product into a numerical vector — an embedding — such that similar meanings land close together in that space. 'Sweaty gym session' ends up near 'water resistance' and 'secure fit' even though they share no words.",
      "This is the single biggest quality lever in modern product discovery. It turns search from a brittle string-matching problem into a meaning-matching one.",
      "## Where hybrid retrieval wins",
      "Pure semantic search can occasionally miss exact matches — a specific model number, a brand name. That's why production systems like ProductIQ blend dense (semantic) retrieval with sparse (BM25 keyword) retrieval. You get the best of both: meaning when you need recall, exact matches when precision matters.",
      "The result is a search that feels like it understands you — because, in the way that matters, it does.",
    ],
  },
  {
    slug: "rating-aware-ranking",
    title: "Why a 5.0 From Two Reviews Isn't Better Than a 4.6 From Four Hundred",
    excerpt:
      "Star averages lie. A rating-aware ranking blend fixes the thin-review problem that plagues most product recommendations.",
    category: "Product",
    date: "June 12, 2026",
    readTime: "5 min read",
    author: "ProductIQ Team",
    body: [
      "Imagine two products. One has a perfect 5.0 rating — from exactly two reviews. The other has a 4.6 — from four hundred. Which would you trust? Most people say the 4.6, instinctively. Yet a naive 'sort by rating' puts the 5.0 first every time.",
      "## Confidence-weighted scoring",
      "The fix is to weight ratings by how much evidence backs them. A rating from hundreds of reviews carries far more signal than one from a handful. ProductIQ blends the raw rating with a confidence factor derived from review volume, so popular, genuinely-loved products rise and thinly-reviewed outliers can't game the top spot.",
      "## Blending relevance and quality",
      "Ranking isn't only about quality, though — it's about fit. A superb product that doesn't match your request shouldn't win. So the final score is a blend: semantic relevance to your query, combined with the confidence-weighted rating. Tuning that blend is where a demo becomes a product.",
      "The payoff is rankings that match human intuition — the thing shoppers were quietly doing in their heads all along.",
    ],
  },
  {
    slug: "streaming-ai-explanations",
    title: "Streaming AI Explanations: The UX Detail That Builds Trust",
    excerpt:
      "Rendering product cards before the AI explanation streams in isn't just a nice animation — it's a deliberate trust-building choice.",
    category: "Design",
    date: "May 30, 2026",
    readTime: "4 min read",
    author: "ProductIQ Team",
    body: [
      "There's a small but important decision in how ProductIQ presents results: the ranked product cards appear first, instantly, and the AI's explanation streams in afterward, token by token. Why not wait and show everything at once?",
      "## Perceived performance",
      "Showing cards immediately means the user sees value in well under a second — before the language model has even finished thinking. The explanation then arrives as a stream, so there's always motion on screen. A frozen spinner feels slow; streaming text feels alive.",
      "## Grounding builds trust",
      "Each explanation is grounded in the reviews actually retrieved, and we show how many reviews matched. That attribution — '12 reviews matched' — quietly tells the user the AI isn't making things up. It's summarizing real evidence.",
      "## The result",
      "Cards-first, streamed, grounded, attributed. Four small choices that together turn 'an AI told me to buy this' into 'I can see exactly why this fits.' That's the difference between a demo people try once and a product they come back to.",
    ],
  },
];

export function getPost(slug: string) {
  return POSTS.find((p) => p.slug === slug);
}
