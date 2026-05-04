import { useEffect, useState } from "react";
import AlertModal from "./components/AlertModal.jsx";
import BottomNav from "./components/BottomNav.jsx";
import FilterRow from "./components/FilterRow.jsx";
import HeroSearch from "./components/HeroSearch.jsx";
import Navbar from "./components/Navbar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import StatsStrip from "./components/StatsStrip.jsx";
import TenderDetailDrawer from "./components/TenderDetailDrawer.jsx";
import TenderGrid from "./components/TenderGrid.jsx";
import ToastContainer from "./components/ToastContainer.jsx";
import { useBookmarks } from "./hooks/useBookmarks.js";
import { useTenders } from "./hooks/useTenders.js";
import { useToastStore } from "./store/toastStore.js";
import { useFilterStore } from "./store/filterStore.js";

export default function App() {
  const filters = useFilterStore();
  const { data, isLoading, isError } = useTenders(filters);
  const { toggle, isBookmarked, list: bookmarkList } = useBookmarks();
  const add = useToastStore((s) => s.add);

  const [selectedId, setSelectedId] = useState(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertKeyword, setAlertKeyword] = useState(null);
  const [offline, setOffline] = useState(!navigator.onLine);

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

  function handleBookmark(tender) {
    const wasBookmarked = isBookmarked(tender.id);
    toggle(tender);
    add(wasBookmarked ? "Bookmark removed" : "🔖 Tender saved to bookmarks", "info");
  }

  function openAlert(keyword) {
    setAlertKeyword(keyword ?? filters.q);
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
        <StatsStrip />
      </section>

      {/* ── Main content ─────────────────────────────────────── */}
      <div className="mx-auto max-w-6xl px-6 py-8 pb-24 sm:px-10 lg:flex lg:gap-8 lg:pb-8">
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
        <div className="hidden lg:block">
          <Sidebar bookmarks={bookmarkList} onView={(t) => setSelectedId(t.id)} />
        </div>
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
        Data sourced from{" "}
        <a href="https://eprocure.gov.in" target="_blank" rel="noreferrer" style={{ color: "var(--muted)", textDecoration: "underline" }}>
          CPPP
        </a>
        {" · "}
        <a href="https://gem.gov.in" target="_blank" rel="noreferrer" style={{ color: "var(--muted)", textDecoration: "underline" }}>
          GeM
        </a>
        {" · "}State Portals
        {" · "}Updated every 6 hours{" · "}Always free
      </footer>

      {/* ── FAB ──────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => openAlert(null)}
        className="fab-pulse fixed bottom-20 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full text-xl text-white transition hover:scale-110 lg:bottom-6 lg:right-6"
        style={{ background: "var(--accent)" }}
        aria-label="Set Alert"
      >
        🔔
      </button>

      {/* ── Mobile bottom nav ─────────────────────────────────── */}
      <BottomNav
        onAlertOpen={() => openAlert(null)}
        bookmarkCount={bookmarkList.length}
      />

      {/* ── Drawers & Modals ──────────────────────────────────── */}
      <TenderDetailDrawer
        tenderId={selectedId}
        onClose={() => setSelectedId(null)}
        onSetAlert={(kw) => { setSelectedId(null); openAlert(kw); }}
      />

      <AlertModal
        open={alertOpen}
        onClose={() => { setAlertOpen(false); setAlertKeyword(null); }}
        prefillKeyword={alertKeyword}
      />

      <ToastContainer />
    </div>
  );
}
