export default function SkeletonCard() {
  return (
    <div
      className="flex flex-col gap-3 rounded-[12px] p-5"
      style={{ background: "var(--surface)", border: "1px solid rgba(255,255,255,0.08)" }}
    >
      {/* Badges row */}
      <div className="flex gap-2">
        <div className="skeleton h-5 w-14 rounded-full" />
        <div className="skeleton h-5 w-20 rounded-full" />
      </div>
      {/* Title */}
      <div className="space-y-1.5">
        <div className="skeleton h-4 w-full rounded" />
        <div className="skeleton h-4 w-4/5 rounded" />
      </div>
      {/* Org */}
      <div className="skeleton h-3 w-2/3 rounded" />
      {/* Deadline */}
      <div className="skeleton h-3 w-1/2 rounded" />
      {/* Value + ref */}
      <div className="flex justify-between pt-1">
        <div className="skeleton h-4 w-16 rounded" />
        <div className="skeleton h-3 w-24 rounded" />
      </div>
      {/* Buttons */}
      <div className="flex gap-2 pt-1">
        <div className="skeleton h-8 flex-1 rounded-lg" />
        <div className="skeleton h-8 w-20 rounded-lg" />
      </div>
    </div>
  );
}
