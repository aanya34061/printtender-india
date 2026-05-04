export default function BottomNav({ onAlertOpen, bookmarkCount }) {
  function scrollToSearch() {
    document.getElementById("search-input")?.focus({ preventScroll: false });
    document.getElementById("search-input")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function scrollToFilters() {
    document.getElementById("filter-row")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex h-16 items-stretch lg:hidden"
      style={{ background: "var(--surface)", borderTop: "1px solid rgba(255,255,255,0.08)" }}
    >
      <NavItem icon="🔍" label="Search" onClick={scrollToSearch} />
      <NavItem icon="⚙️" label="Filters" onClick={scrollToFilters} />
      <NavItem
        icon="🔖"
        label={bookmarkCount ? `Saved (${bookmarkCount})` : "Saved"}
        onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })}
      />
      <NavItem icon="🔔" label="Alerts" onClick={onAlertOpen} accent />
    </nav>
  );
}

function NavItem({ icon, label, onClick, accent }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-1 flex-col items-center justify-center gap-0.5 transition"
      style={{ color: accent ? "var(--accent)" : "var(--muted)" }}
      onMouseEnter={(e) => { if (!accent) e.currentTarget.style.color = "var(--text)"; }}
      onMouseLeave={(e) => { if (!accent) e.currentTarget.style.color = "var(--muted)"; }}
    >
      <span className="text-lg leading-none">{icon}</span>
      <span className="text-[10px] font-medium">{label}</span>
    </button>
  );
}
