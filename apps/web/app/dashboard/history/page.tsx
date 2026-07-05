"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Star, Trash2, Bookmark } from "lucide-react";
import { Topbar } from "@/components/dashboard/Topbar";
import { cn } from "@/lib/utils";

/* mock history — in production this comes from the DynamoDB chat-history service */
const HISTORY = [
  { id: "1", q: "noise cancelling for office",        when: "2 hours ago", results: 3, top: "Sony WH-1000XM5",  rating: 4.5, saved: true },
  { id: "2", q: "wireless earphones under ₹2000",     when: "Yesterday",   results: 3, top: "boAt Airdopes 141", rating: 4.2, saved: false },
  { id: "3", q: "gaming headset with mic",            when: "2 days ago",  results: 3, top: "HyperX Cloud II",   rating: 4.6, saved: true },
  { id: "4", q: "premium home speakers",              when: "3 days ago",  results: 3, top: "Sonos Era 100",     rating: 4.4, saved: false },
  { id: "5", q: "best earphones for gym",             when: "5 days ago",  results: 3, top: "JBL Endurance Peak", rating: 4.1, saved: false },
  { id: "6", q: "budget bass headphones",             when: "1 week ago",  results: 3, top: "boAt Rockerz 450",  rating: 4.0, saved: false },
];

export default function HistoryPage() {
  const [filter, setFilter] = useState<"all" | "saved">("all");
  const [items, setItems] = useState(HISTORY);

  const shown = filter === "saved" ? items.filter((i) => i.saved) : items;

  function toggleSave(id: string) {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, saved: !i.saved } : i)));
  }
  function remove(id: string) {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  return (
    <>
      <Topbar title="History" subtitle="Your past searches and saved results" />

      <div className="p-6 max-w-5xl mx-auto space-y-5">

        {/* filter tabs */}
        <div className="flex items-center gap-1 border-b border-bg-border">
          {(["all", "saved"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-4 py-2.5 text-sm capitalize border-b-2 -mb-px transition-colors",
                filter === f
                  ? "border-accent text-txt-primary"
                  : "border-transparent text-txt-muted hover:text-txt-secondary",
              )}
            >
              {f === "all" ? "All searches" : "Saved"}
              <span className="ml-2 text-xs text-txt-muted">
                {f === "all" ? items.length : items.filter((i) => i.saved).length}
              </span>
            </button>
          ))}
        </div>

        {/* list */}
        {shown.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <p className="text-txt-secondary">No {filter === "saved" ? "saved" : ""} searches yet.</p>
            <Link href="/dashboard/discover" className="btn-primary mt-4 px-5 py-2.5 text-sm inline-flex">
              Start searching
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {shown.map((item) => (
              <div key={item.id} className="glass-card p-4 flex items-center gap-4 group">
                <span className="w-10 h-10 rounded-lg bg-accent-muted flex items-center justify-center shrink-0">
                  <Search className="w-4 h-4 text-accent" />
                </span>

                <Link href={`/dashboard/discover?q=${encodeURIComponent(item.q)}`} className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-txt-primary group-hover:text-accent transition-colors truncate">
                    {item.q}
                  </p>
                  <p className="text-xs text-txt-muted mt-0.5 flex items-center gap-2 flex-wrap">
                    <span>{item.when}</span>
                    <span>·</span>
                    <span>{item.results} results</span>
                    <span>·</span>
                    <span className="flex items-center gap-1">
                      Top: {item.top}
                      <Star className="w-3 h-3 text-rank-gold fill-rank-gold" />
                      {item.rating}
                    </span>
                  </p>
                </Link>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => toggleSave(item.id)}
                    className={cn(
                      "p-2 rounded-lg hover:bg-bg-elevated transition-colors",
                      item.saved ? "text-accent" : "text-txt-muted hover:text-txt-primary",
                    )}
                    aria-label="Save"
                  >
                    <Bookmark className={cn("w-4 h-4", item.saved && "fill-current")} />
                  </button>
                  <button
                    onClick={() => remove(item.id)}
                    className="p-2 rounded-lg text-txt-muted hover:text-status-error hover:bg-bg-elevated transition-colors"
                    aria-label="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
