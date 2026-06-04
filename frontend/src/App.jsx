import { lazy, Suspense, useEffect, useState } from "react";
import FilterRow from "./components/FilterRow.jsx";
import HeroSearch from "./components/HeroSearch.jsx";
import Navbar from "./components/Navbar.jsx";
import StatsStrip from "./components/StatsStrip.jsx";
import TenderGrid from "./components/TenderGrid.jsx";
import { useBookmarks } from "./hooks/useBookmarks.js";
import { useTenders } from "./hooks/useTenders.js";
import { useToastStore } from "./store/toastStore.js";
import { useFilterStore, useTenderFilters } from "./store/filterStore.js";

const Sidebar = lazy(() => import("./components/Sidebar.jsx"));
const TenderDetailDrawer = lazy(() => import("./components/TenderDetailDrawer.jsx"));
const AlertModal = lazy(() => import("./components/AlertModal.jsx"));
const ToastContainer = lazy(() => import("./components/ToastContainer.jsx"));

export default function App() {
  const filters = useTenderFilters();
  const { data, isLoading, isError } = useTenders(filters);
  const { toggle, isBookmarked, list: bookmarkList } = useBookmarks();
  const add = useToastStore((s) => s.add);
  const toastCount = useToastStore((s) => s.toasts.length);
  const currentQuery = useFilterStore((s) => s.q);

  const [selectedId, setSelectedId] = useState(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertKeyword, setAlertKeyword] = useState(null);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [showDesktopSidebar, setShowDesktopSidebar] = useState(false);
  const [sidebarReady, setSidebarReady] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("confirmed") === "true") {
      add("✅ Email confirmed! Your alerts are now active.", "success");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const sync = () => setShowDesktopSidebar(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!showDesktopSidebar) return;
    const schedule = window.requestIdleCallback || ((fn) => window.setTimeout(fn, 1200));
    const cancel = window.cancelIdleCallback || window.clearTimeout;
    const id = schedule(() => setSidebarReady(true));
    return () => cancel(id);
  }, [showDesktopSidebar]);

  function handleBookmark(tender) {
    const wasBookmarked = isBookmarked(tender.id);
    toggle(tender);
    add(wasBookmarked ? "Bookmark removed" : "🔖 Tender saved to bookmarks", "info");
  }

  function openAlert(keyword) {
    setAlertKeyword(keyword ?? currentQuery);
    setAlertOpen(true);
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg)", color: "var(--text)" }}>
      {/* Offline banner */}
      {offline && (
        <div
          className="sticky top-0 z-[60] px-4 py-2 text-center text-xs font-semibold text-white"
          style={{ background: "var(--red)" }}
        >
          You are offline — showing cached data
        </div>
      )}

      {/* ── Navbar ───────────────────────────────────────────── */}
      <Navbar onAlertOpen={() => openAlert(null)} />

      {/* ── Hero / Search ─────────────────────────────────────  */}
      <section style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <HeroSearch />
      </section>

      {/* ── Filters ──────────────────────────────────────────── */}
      <FilterRow />

      {/* ── Stats ────────────────────────────────────────────── */}
      <section style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <StatsStrip tenderTotal={data?.total} tenderTotalLoading={isLoading} />
      </section>

      {/* ── Main content ─────────────────────────────────────── */}
      <div className="mx-auto max-w-6xl px-4 py-6 pb-8 sm:px-6 lg:flex lg:gap-8 lg:px-10 lg:py-8">
        <div className="min-w-0 flex-1">
          <TenderGrid
            data={data}
            isLoading={isLoading}
            isError={isError}
            onView={(t) => setSelectedId(t.id)}
            onBookmark={handleBookmark}
            isBookmarked={isBookmarked}
          />
        </div>

        {/* Sidebar — desktop only */}
        {showDesktopSidebar && sidebarReady && (
          <Suspense fallback={null}>
            <div className="hidden lg:block">
              <Sidebar bookmarks={bookmarkList} onView={(t) => setSelectedId(t.id)} />
            </div>
          </Suspense>
        )}
      </div>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer
        className="px-6 py-8 text-center text-xs"
        style={{
          background: "var(--surface)",
          borderTop: "1px solid rgba(255,255,255,0.08)",
          color: "var(--muted)",
        }}
      >
        Printing tender listings updated every 6 hours{" · "}Always free
      </footer>

      {/* ── FAB ──────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => openAlert(null)}
        className="fab-pulse fixed bottom-5 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full text-xl text-white transition hover:scale-110 lg:bottom-6 lg:right-6"
        style={{ background: "var(--accent)" }}
        aria-label="Subscribe to tender mails"
      >
        🔔
      </button>

      {/* ── Drawers & Modals ──────────────────────────────────── */}
      {selectedId && (
        <Suspense fallback={null}>
          <TenderDetailDrawer
            tenderId={selectedId}
            onClose={() => setSelectedId(null)}
            onSetAlert={(kw) => { setSelectedId(null); openAlert(kw); }}
          />
        </Suspense>
      )}

      {alertOpen && (
        <Suspense fallback={null}>
          <AlertModal
            open={alertOpen}
            onClose={() => { setAlertOpen(false); setAlertKeyword(null); }}
            prefillKeyword={alertKeyword}
          />
        </Suspense>
      )}

      {toastCount > 0 && (
        <Suspense fallback={null}>
          <ToastContainer />
        </Suspense>
      )}
    </div>
  );
}
