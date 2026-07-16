/** Pixel-style skeleton placeholder for loading states. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-white/10 ${className ?? ""}`} />;
}
