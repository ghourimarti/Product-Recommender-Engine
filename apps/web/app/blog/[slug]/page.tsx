import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { MarketingShell } from "@/components/MarketingShell";
import { POSTS, getPost } from "@/lib/posts";

export function generateStaticParams() {
  return POSTS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  return { title: post ? `${post.title} — ProductIQ` : "Post — ProductIQ" };
}

export default async function BlogPost({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const idx = POSTS.findIndex((p) => p.slug === slug);
  const next = POSTS[(idx + 1) % POSTS.length];

  return (
    <MarketingShell>
      <article className="max-w-2xl mx-auto px-6 py-16">
        <Link href="/blog" className="inline-flex items-center gap-1.5 text-sm text-txt-muted hover:text-txt-primary mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" /> All articles
        </Link>

        {/* header */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-xs font-medium bg-accent-muted text-accent px-2.5 py-1 rounded-full">
            {post.category}
          </span>
          <span className="text-xs text-txt-muted">{post.date} · {post.readTime}</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-display font-bold tracking-tight text-txt-primary leading-tight mb-4">
          {post.title}
        </h1>
        <div className="flex items-center gap-3 pb-8 mb-8 border-b border-bg-border">
          <span className="w-9 h-9 rounded-full bg-gradient-to-br from-accent/30 to-purple-500/30
                           flex items-center justify-center text-sm font-semibold text-accent">
            P
          </span>
          <span className="text-sm text-txt-secondary">{post.author}</span>
        </div>

        {/* body */}
        <div className="space-y-5">
          {post.body.map((para, i) =>
            para.startsWith("## ") ? (
              <h2 key={i} className="text-xl font-display font-bold text-txt-primary pt-4">
                {para.slice(3)}
              </h2>
            ) : (
              <p key={i} className="text-txt-secondary leading-relaxed">{para}</p>
            ),
          )}
        </div>

        {/* next post */}
        <div className="mt-16 pt-8 border-t border-bg-border">
          <p className="text-xs text-txt-muted uppercase tracking-widest mb-3">Read next</p>
          <Link href={`/blog/${next.slug}`} className="glass-card p-5 block hover:border-accent/30 transition-colors group">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="font-display font-semibold text-txt-primary group-hover:text-accent transition-colors">
                  {next.title}
                </h3>
                <p className="text-sm text-txt-muted mt-1">{next.readTime}</p>
              </div>
              <ArrowRight className="w-5 h-5 text-txt-muted group-hover:text-accent shrink-0 transition-colors" />
            </div>
          </Link>
        </div>

        {/* CTA */}
        <div className="mt-10 text-center">
          <Link href="/dashboard/discover" className="btn-primary px-6 py-3 text-base inline-flex">
            Try ProductIQ free <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </article>
    </MarketingShell>
  );
}
