import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import EmptyState from "./EmptyState.jsx";
import SkeletonCard from "./SkeletonCard.jsx";
import TenderCard, { cardVariants } from "./TenderCard.jsx";
import { useFilterStore } from "../store/filterStore.js";

const SORT_OPTIONS = [
  { value: "deadline_asc", label: "Deadline Soon" },
  { value: "newest", label: "Newest" },
  { value: "value_desc", label: "Value: High → Low" },
  { value: "value_asc", label: "Value: Low → High" },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

export default function TenderGrid({ data, isLoading, isError, onView, onBookmark, isBookmarked }) {
  const { q, sort, page, pages, setSort, setPage } = useFilterStore();
  const tenders = data?.tenders ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  return (
    <div className="space-y-4">
      {/* Sort bar */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-500">
          {isLoading ? "Loading…" : `${total} result${total !== 1 ? "s" : ""}`}
        </span>
        <div className="relative">
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="select-field h-8 rounded-lg px-3 pr-8 text-xs"
          >
            {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="rounded-xl border border-danger/20 bg-danger/10 p-4 text-center text-sm text-danger">
          Unable to load tenders. Is the API running?{" "}
          <button className="underline" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {/* Skeleton */}
      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && tenders.length === 0 && <EmptyState query={q} />}

      {/* Cards */}
      {!isLoading && !isError && tenders.length > 0 && (
        <AnimatePresence mode="wait">
          <motion.div
            key={`${q}-${page}-${sort}`}
            variants={container}
            initial="hidden"
            animate="show"
            className="grid gap-3 sm:grid-cols-2"
          >
            {tenders.map((t) => (
              <TenderCard
                key={t.id}
                tender={t}
                onView={onView}
                onBookmark={onBookmark}
                isBookmarked={isBookmarked(t.id)}
              />
            ))}
          </motion.div>
        </AnimatePresence>
      )}

      {/* Pagination */}
      {totalPages > 1 && !isLoading && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => { setPage(page - 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            className="btn-outline flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
          >
            <ChevronLeft className="h-3.5 w-3.5" /> Prev
          </button>

          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            const p = i + 1;
            return (
              <button
                key={p}
                type="button"
                onClick={() => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); }}
                className={`h-8 w-8 rounded-lg text-xs font-semibold transition ${
                  p === page ? "bg-accent text-white" : "btn-outline"
                }`}
              >
                {p}
              </button>
            );
          })}

          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => { setPage(page + 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}
            className="btn-outline flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
          >
            Next <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
