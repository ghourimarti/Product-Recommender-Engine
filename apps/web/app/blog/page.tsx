import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { MarketingShell, PageHeader } from "@/components/MarketingShell";
import { POSTS } from "@/lib/posts";

export const metadata = { title: "Blog — ProductIQ" };

export default function BlogIndex() {
  const [featured, ...rest] = POSTS;

  return (
    <MarketingShell>
      <PageHeader
        eyebrow="Blog"
        title="Insights on AI product discovery"
        subtitle="How we build search that understands you — engineering deep-dives, product thinking, and design notes."
      />

      <div className="max-w-5xl mx-auto px-6 py-16">

        {/* featured post */}
        <Link
          href={`/blog/${featured.slug}`}
          className="glass-card p-8 md:p-10 block hover:border-accent/30 transition-colors group mb-8 bg-grid-glow"
        >
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs font-medium bg-accent-muted text-accent px-2.5 py-1 rounded-full">
              {featured.category}
            </span>
            <span className="text-xs text-txt-muted">{featured.date} · {featured.readTime}</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-display font-bold text-txt-primary group-hover:text-accent transition-colors mb-3">
            {featured.title}
          </h2>
          <p className="text-txt-secondary leading-relaxed mb-4 max-w-2xl">{featured.excerpt}</p>
          <span className="inline-flex items-center gap-1 text-sm text-accent">
            Read article <ArrowUpRight className="w-4 h-4" />
          </span>
        </Link>

        {/* rest */}
        <div className="grid md:grid-cols-2 gap-5">
          {rest.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="glass-card p-6 block hover:border-accent/30 transition-colors group flex flex-col"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-medium bg-bg-elevated text-txt-secondary px-2.5 py-1 rounded-full">
                  {post.category}
                </span>
                <span className="text-xs text-txt-muted">{post.readTime}</span>
              </div>
              <h3 className="font-display font-semibold text-txt-primary group-hover:text-accent transition-colors mb-2 leading-snug">
                {post.title}
              </h3>
              <p className="text-sm text-txt-secondary leading-relaxed flex-1">{post.excerpt}</p>
              <span className="text-xs text-txt-muted mt-4">{post.date}</span>
            </Link>
          ))}
        </div>
      </div>
    </MarketingShell>
  );
}
