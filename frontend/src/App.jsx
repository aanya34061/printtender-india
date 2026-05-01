import { Bell, FileText, Menu, X } from "lucide-react";
import { useState } from "react";

import AlertSignup from "./components/AlertSignup.jsx";
import FilterPanel from "./components/FilterPanel.jsx";
import SearchBar from "./components/SearchBar.jsx";
import StatsBar from "./components/StatsBar.jsx";
import TenderCard from "./components/TenderCard.jsx";
import TenderDetail from "./components/TenderDetail.jsx";
import { useTenders } from "./hooks/useTenders.js";
import { useFilterStore } from "./store/filterStore.js";

export default function App() {
  const filters = useFilterStore();
  const { data, isLoading, isError } = useTenders(filters);
  const tenders = data?.tenders ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const [selectedId, setSelectedId] = useState(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertKeyword, setAlertKeyword] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function openAlert(keyword) {
    setAlertKeyword(keyword || filters.query);
    setAlertOpen(true);
  }

  return (
    <div className="min-h-screen bg-paper">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-navy/10 bg-navy shadow-md">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-crimson">
              <FileText className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold leading-none text-white">PrintTender India</h1>
              <p className="text-xs text-white/60 leading-tight">Free Tender Alerts for Printing Industry</p>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <button
              type="button"
              onClick={() => openAlert(null)}
              className="flex items-center gap-2 rounded-lg bg-crimson px-3 py-2 text-sm font-semibold text-white transition hover:bg-crimson/90"
            >
              <Bell className="h-4 w-4" />
              <span className="hidden sm:inline">Get Alerts</span>
            </button>
            {/* Mobile sidebar toggle */}
            <button
              type="button"
              onClick={() => setSidebarOpen((o) => !o)}
              className="rounded-lg p-2 text-white/70 hover:bg-white/10 lg:hidden"
            >
              {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Stats + Search */}
      <div className="border-b border-navy/10 bg-white shadow-sm">
        <div className="mx-auto max-w-7xl space-y-3 px-4 py-4 sm:px-6 lg:px-8">
          <StatsBar />
          <SearchBar />
        </div>
      </div>

      {/* Main content */}
      <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex gap-5">
          {/* Filter sidebar — desktop always visible, mobile overlay */}
          <aside
            className={`${
              sidebarOpen ? "block" : "hidden"
            } w-64 shrink-0 lg:block`}
          >
            <FilterPanel />
          </aside>

          {/* Tender grid */}
          <main className="min-w-0 flex-1">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-navy">
                {isLoading ? "Loading…" : `${total} tenders found`}
              </h2>
              {pages > 1 && (
                <Pagination
                  page={filters.page}
                  pages={pages}
                  setPage={filters.setPage}
                />
              )}
            </div>

            {isLoading && <SkeletonGrid />}

            {isError && (
              <EmptyState message="Unable to load tenders. Is the API running?" />
            )}

            {!isLoading && !isError && tenders.length === 0 && (
              <EmptyState message="No tenders found. Try a different keyword." />
            )}

            {!isLoading && !isError && tenders.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-2">
                {tenders.map((tender) => (
                  <TenderCard
                    key={tender.id}
                    tender={tender}
                    onViewDetails={(t) => setSelectedId(t.id)}
                  />
                ))}
              </div>
            )}

            {pages > 1 && !isLoading && (
              <div className="mt-5 flex justify-center">
                <Pagination
                  page={filters.page}
                  pages={pages}
                  setPage={filters.setPage}
                />
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-8 border-t border-navy/10 bg-white py-4 text-center text-xs text-navy/50">
        Data sourced from{" "}
        <span className="font-semibold">CPPP · GeM · State Portals</span> | Always free
      </footer>

      {/* Modals */}
      {selectedId && (
        <TenderDetail
          tenderId={selectedId}
          onClose={() => setSelectedId(null)}
          onAlertKeyword={(kw) => { setSelectedId(null); openAlert(kw); }}
        />
      )}
      {alertOpen && (
        <AlertSignup
          onClose={() => { setAlertOpen(false); setAlertKeyword(null); }}
          prefillKeyword={alertKeyword}
        />
      )}
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-navy/10 bg-white p-8 text-center">
      <FileText className="h-8 w-8 text-navy/20" />
      <p className="text-sm text-navy/50">{message}</p>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-36 animate-pulse rounded-xl bg-white" />
      ))}
    </div>
  );
}

function Pagination({ page, pages, setPage }) {
  return (
    <div className="flex items-center gap-2 text-xs font-semibold text-navy">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => setPage(page - 1)}
        className="rounded-lg border border-navy/20 px-2.5 py-1.5 disabled:opacity-40 hover:bg-navy hover:text-white transition"
      >
        ← Prev
      </button>
      <span className="text-navy/50">
        {page} / {pages}
      </span>
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => setPage(page + 1)}
        className="rounded-lg border border-navy/20 px-2.5 py-1.5 disabled:opacity-40 hover:bg-navy hover:text-white transition"
      >
        Next →
      </button>
    </div>
  );
}
