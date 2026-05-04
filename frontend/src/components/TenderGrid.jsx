import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import EmptyState from "./EmptyState.jsx";
import SkeletonCard from "./SkeletonCard.jsx";
import TenderCard, { cardVariants } from "./TenderCard.jsx";
import { useFilterStore } from "../store/filterStore.js";

const SORT_OPTIONS = [
  { value: "deadline_asc", label: "Deadline Soon" },
  { value: "newest", label: "Newest First" },
  { value: "value_desc", label: "Value: High → Low" },
  { value: "value_asc", label: "Value: Low → High" },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

export default function TenderGrid({ data, isLoading, isError, onView, onBookmark, isBookmarked }) {
  const { q, sort, page, setSort, setPage } = useFilterStore();
  const tenders = data?.tenders ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  return (
    <div className="space-y-5">
      {/* Sort bar */}
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm" style={{ color: "var(--muted)" }}>
          {isLoading ? "Loading…" : `${total.toLocaleString()} result${total !== 1 ? "s" : ""}`}
        </span>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="form-select h-9 px-3 text-xs"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Error state */}
      {isError && (
        <div
          className="rounded-[12px] p-6 text-center"
          style={{
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.2)",
          }}
        >
          <div className="mb-3 text-4xl">⚠️</div>
          <h3 className="mb-1 font-semibold text-slate-200">Backend not reachable</h3>
          <p className="mb-4 text-sm" style={{ color: "var(--muted)" }}>
            Make sure the FastAPI server is running on port 8000
          </p>
          <button
            onClick={() => window.location.reload()}
            className="btn-outline text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {/* Skeleton loaders */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && tenders.length === 0 && (
        <EmptyState query={q} />
      )}

      {/* Cards grid */}
      {!isLoading && !isError && tenders.length > 0 && (
        <AnimatePresence mode="wait">
          <motion.div
            key={`${q}-${page}-${sort}`}
            variants={container}
            initial="hidden"
            animate="show"
            className="grid gap-4 sm:grid-cols-2"
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
        <div className="flex items-center justify-center gap-1.5 pt-2">
          <PagBtn
            disabled={page <= 1}
            onClick={() => { setPage(page - 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}
          >
            <ChevronLeft className="h-4 w-4" /> Prev
          </PagBtn>

          {buildPageRange(page, totalPages).map((p, i) =>
            p === "…" ? (
              <span key={`ellipsis-${i}`} className="px-1 text-sm" style={{ color: "var(--muted)" }}>…</span>
            ) : (
              <PagBtn
                key={p}
                active={p === page}
                onClick={() => { setPage(p); window.scrollTo({ top: 0, behavior: "smooth" }); }}
              >
                {p}
              </PagBtn>
            )
          )}

          <PagBtn
            disabled={page >= totalPages}
            onClick={() => { setPage(page + 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}
          >
            Next <ChevronRight className="h-4 w-4" />
          </PagBtn>
        </div>
      )}
    </div>
  );
}

function PagBtn({ children, onClick, disabled, active }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-9 min-w-[36px] items-center justify-center gap-0.5 rounded-lg px-2 text-xs font-semibold transition disabled:opacity-40"
      style={{
        background: active ? "var(--accent)" : "var(--surface2)",
        color: active ? "white" : "var(--muted)",
        border: active ? "1.5px solid var(--accent)" : "1px solid rgba(255,255,255,0.08)",
      }}
      onMouseEnter={!active && !disabled ? (e) => {
        e.currentTarget.style.borderColor = "var(--accent)";
        e.currentTarget.style.color = "var(--accent)";
      } : undefined}
      onMouseLeave={!active && !disabled ? (e) => {
        e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
        e.currentTarget.style.color = "var(--muted)";
      } : undefined}
    >
      {children}
    </button>
  );
}

function buildPageRange(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
  if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
  return [1, "…", current - 1, current, current + 1, "…", total];
}
