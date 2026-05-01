import { useEffect, useState } from "react";
import AlertModal from "./components/AlertModal.jsx";
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
  const { bookmarks, toggle, isBookmarked, list: bookmarkList } = useBookmarks();
  const add = useToastStore((s) => s.add);

  const [selectedId, setSelectedId] = useState(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertKeyword, setAlertKeyword] = useState(null);
  const [offline, setOffline] = useState(!navigator.onLine);

  // Detect confirmed alert from URL
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("confirmed") === "true") {
      add("✅ Email confirmed! Your alerts are now active.", "success");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  // Offline detection
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
    add(wasBookmarked ? "Bookmark removed" : "🔖 Tender bookmarked", "info");
  }

  function openAlert(keyword) {
    setAlertKeyword(keyword ?? filters.q);
    setAlertOpen(true);
  }

  return (
    <div className="min-h-screen bg-bg text-slate-200">
      {/* Offline banner */}
      {offline && (
        <div className="sticky top-0 z-[60] bg-danger/90 px-4 py-2 text-center text-xs font-semibold text-white">
          You are offline — showing cached data
        </div>
      )}

      <Navbar onAlertOpen={() => openAlert(null)} />
      <HeroSearch />
      <FilterRow />
      <StatsStrip />

      {/* Main content */}
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:flex lg:gap-6">
        {/* Tender grid */}
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
          <Sidebar
            bookmarks={bookmarkList}
            onView={(t) => setSelectedId(t.id)}
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-8 border-t border-white/5 py-6 text-center text-xs text-slate-600">
        Data sourced from{" "}
        <span className="text-slate-500">CPPP · GeM · State Portals</span>
        {" "}| Updated every 6 hours | Always free
      </footer>

      {/* FAB — Get Alerts */}
      <button
        type="button"
        onClick={() => openAlert(null)}
        className="fab-pulse fixed bottom-6 right-6 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg shadow-accent/30 transition hover:scale-110 lg:hidden"
        aria-label="Set Alert"
      >
        🔔
      </button>

      {/* Modals / Drawers */}
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
