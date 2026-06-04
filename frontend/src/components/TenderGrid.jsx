import { ChevronLeft, ChevronRight } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import EmptyState from "./EmptyState.jsx";
import SkeletonCard from "./SkeletonCard.jsx";
import TenderCard from "./TenderCard.jsx";
import { fetchTenders, TENDER_LIST_STALE_MS } from "../hooks/useTenders.js";
import { useFilterStore } from "../store/filterStore.js";
import { useShallow } from "zustand/react/shallow";

const SORT_OPTIONS = [
  { value: "deadline_asc", label: "Deadline Soon" },
  { value: "newest", label: "Newest First" },
  { value: "value_desc", label: "Value: High → Low" },
  { value: "value_asc", label: "Value: Low → High" },
];

export default function TenderGrid({ data, isLoading, isError, onView, onBookmark, isBookmarked }) {
  const {
    q,
    sort,
    page,
    setSort,
    setPage,
    categories,
    state,
    portal,
    deadline_within_days,
    min_value,
    max_value,
    limit,
  } = useFilterStore(
    useShallow((s) => ({
      q: s.q,
      sort: s.sort,
      page: s.page,
      setSort: s.setSort,
      setPage: s.setPage,
      categories: s.categories,
      state: s.state,
      portal: s.portal,
      deadline_within_days: s.deadline_within_days,
      min_value: s.min_value,
      max_value: s.max_value,
      limit: s.limit,
    })),
  );
  const queryClient = useQueryClient();
  const tenders = data?.tenders ?? [];

  // Prefetch nearby pages so pagination is instant after the first response.
  useEffect(() => {
    if (data?.pages && page < data.pages) {
      const pagesToPrefetch = [page + 1, page + 2].filter((p) => p <= data.pages);
      const prefetch = () => {
        pagesToPrefetch.forEach((nextPage) => {
          const filters = { q, state, portal, deadline_within_days, min_value, max_value, sort, page: nextPage, limit: limit || 6 };

          if (queryClient.getQueryData(["tenders", filters])) return;

          queryClient.prefetchQuery({
            queryKey: ["tenders", filters],
            queryFn: () => fetchTenders(filters),
            staleTime: TENDER_LIST_STALE_MS,
          });
        });
      };

      pagesToPrefetch.forEach((nextPage) => {
        const filters = { q, state, portal, deadline_within_days, min_value, max_value, sort, page: nextPage, limit: limit || 6 };
        queryClient.prefetchQuery({
          queryKey: ["tenders", filters],
          queryFn: () => fetchTenders(filters),
          staleTime: TENDER_LIST_STALE_MS,
        });
      });

      const timeoutId = window.setTimeout(prefetch, 2500);
      return () => window.clearTimeout(timeoutId);
    }
  }, [data?.pages, page, q, state, portal, deadline_within_days, min_value, max_value, sort, limit, queryClient]);

  // Apply multi-category client-side filtering (OR semantics)
  // Categories are still filtered client-side as backend support is pending full multi-select integration
  const selectedCategories = categories || [];
  let displayTenders = (selectedCategories.length === 0)
    ? tenders
    : tenders.filter((t) => selectedCategories.some((cat) => (t.category || '').toLowerCase().includes(cat.toLowerCase())));

  // Fallback safety: if client-side filters remove everything but we do have server data, show all tenders instead of empty UI
  if ((displayTenders?.length || 0) === 0 && (tenders?.length || 0) > 0) {
    displayTenders = tenders;
  }

  const total = data?.total ?? displayTenders.length ?? 0;
  // Keep server-side pagination info for controls
  const totalPages = data?.pages ?? 1;

  return (
    <div className="space-y-5">
      {/* Sort bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm" style={{ color: "var(--muted)" }}>
          {isLoading ? "Loading…" : `${total.toLocaleString()} result${total !== 1 ? "s" : ""}`}
        </span>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="form-select h-9 w-full px-3 text-xs sm:w-auto"
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
      {!isLoading && !isError && displayTenders.length > 0 && (
        <div key={`${q}-${page}-${sort}`} className="grid gap-4 sm:grid-cols-2">
          {displayTenders.map((t) => (
            <TenderCard
              key={t.id}
              tender={t}
              onView={onView}
              onBookmark={onBookmark}
              isBookmarked={isBookmarked(t.id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && !isLoading && (
        <div className="flex max-w-full items-center justify-start gap-1.5 overflow-x-auto pt-2 sm:justify-center">
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
