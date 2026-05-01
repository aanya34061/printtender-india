export default function SkeletonCard() {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded-full shimmer" />
        <div className="h-5 w-20 rounded-full shimmer" />
      </div>
      <div className="h-4 w-full rounded shimmer" />
      <div className="h-4 w-4/5 rounded shimmer" />
      <div className="h-3 w-1/2 rounded shimmer" />
      <div className="flex gap-2 pt-1">
        <div className="h-8 w-28 rounded-lg shimmer" />
        <div className="h-8 w-20 rounded-lg shimmer" />
      </div>
    </div>
  );
}
