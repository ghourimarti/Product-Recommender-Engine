export function SkeletonCard() {
  return (
    <div className="glass-card p-5 space-y-4 overflow-hidden">
      {/* rank badge */}
      <div className="skeleton-base h-5 w-24 rounded-full" />
      {/* title (2 lines) */}
      <div className="space-y-2">
        <div className="skeleton-base h-4 w-full rounded" />
        <div className="skeleton-base h-4 w-3/4 rounded" />
      </div>
      {/* stars + count */}
      <div className="flex items-center gap-2">
        <div className="flex gap-0.5">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton-base w-3.5 h-3.5 rounded-sm" />
          ))}
        </div>
        <div className="skeleton-base h-3 w-10 rounded" />
        <div className="skeleton-base h-3 w-16 rounded" />
      </div>
      {/* relevance bar */}
      <div className="space-y-1.5">
        <div className="flex justify-between">
          <div className="skeleton-base h-3 w-16 rounded" />
          <div className="skeleton-base h-3 w-8 rounded" />
        </div>
        <div className="skeleton-base h-1.5 w-full rounded-full" />
      </div>
      {/* footer row */}
      <div className="flex justify-between pt-1 border-t border-bg-border">
        <div className="skeleton-base h-3 w-24 rounded" />
        <div className="skeleton-base h-3 w-16 rounded" />
      </div>
    </div>
  );
}
