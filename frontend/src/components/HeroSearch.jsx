import { ChevronDown, Search, Tag } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useFilterStore } from "../store/filterStore.js";

const KEYWORD_GROUPS = [
  {
    icon: "📚",
    label: "Books & Notebooks",
    keywords: ["note books", "exercise books", "answer books", "registers", "pass books", "receipt books", "books"],
  },
  {
    icon: "📄",
    label: "Forms & Documents",
    keywords: ["forms", "papers", "note sheets", "certificates", "prospectus", "annual reports", "catalogues"],
  },
  {
    icon: "🖼️",
    label: "Marketing",
    keywords: ["brochures", "flyers", "posters", "banners", "visiting cards", "pamphlets", "souvenir"],
  },
  {
    icon: "📦",
    label: "Packaging & Labels",
    keywords: ["labels", "tags", "sticker", "envelopes", "duplex box", "desk pads", "files"],
  },
  {
    icon: "🖨️",
    label: "Print Types",
    keywords: ["offset printing", "digital printing", "security printing", "flex printing", "screen printing", "letterpress"],
  },
  {
    icon: "🎁",
    label: "Specialty",
    keywords: ["diary", "calendars", "cards", "marks sheet", "stationary"],
  },
];

export default function HeroSearch() {
  const { q, setQ } = useFilterStore();
  const [inputVal, setInputVal] = useState(q);
  const [open, setOpen] = useState(false);
  const timer = useRef(null);
  const dropdownRef = useRef(null);

  useEffect(() => { setInputVal(q); }, [q]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleChange(e) {
    const val = e.target.value;
    setInputVal(val);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setQ(val), 400);
  }

  function handleChip(kw) {
    setInputVal(kw);
    clearTimeout(timer.current);
    setQ(kw);
    setOpen(false);
  }

  const activeKw = inputVal.trim().toLowerCase();
  const activeGroup = KEYWORD_GROUPS.find((g) =>
    g.keywords.some((kw) => kw.toLowerCase() === activeKw)
  );

  return (
    <div className="mx-auto max-w-2xl px-6 py-12 sm:px-10">
      {/* Heading */}
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-100 sm:text-4xl">
          Find{" "}
          <span className="text-gradient">Printing Tenders</span>
        </h1>
        <p className="mt-3 text-sm" style={{ color: "var(--muted)" }}>
          Live data from CPPP · GeM · State Portals — updated every 6 hours
        </p>
      </div>

      {/* Search bar */}
      <div className="relative mb-4">
        <Search
          className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2"
          style={{ color: "var(--muted)" }}
        />
        <input
          id="search-input"
          value={inputVal}
          onChange={handleChange}
          className="form-input h-14 pl-12 pr-4 text-base"
          placeholder="Search by keyword, department, state…"
          aria-label="Search tenders"
        />
      </div>

      {/* Browse keywords dropdown */}
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between rounded-xl px-4 py-2.5 text-sm transition"
          style={{
            background: "var(--surface2)",
            border: "1.5px solid " + (open ? "var(--accent)" : "rgba(255,255,255,0.08)"),
            color: activeGroup ? "var(--accent)" : "var(--muted)",
          }}
        >
          <span className="flex items-center gap-2">
            <Tag className="h-4 w-4" />
            {activeGroup
              ? `${activeGroup.icon} ${activeGroup.label} — ${activeKw}`
              : "Browse by category"}
          </span>
          <ChevronDown
            className="h-4 w-4 transition-transform"
            style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", color: "var(--muted)" }}
          />
        </button>

        {open && (
          <div
            className="absolute left-0 right-0 top-full z-50 mt-1 overflow-y-auto rounded-xl"
            style={{ maxHeight: "320px",
              background: "var(--surface)",
              border: "1px solid rgba(255,255,255,0.1)",
              boxShadow: "0 16px 48px rgba(0,0,0,0.5)",
            }}
          >
            {KEYWORD_GROUPS.map((group, gi) => (
              <div
                key={group.label}
                style={{ borderBottom: gi < KEYWORD_GROUPS.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none" }}
              >
                <p
                  className="px-4 pt-3 pb-1.5 text-xs font-semibold uppercase tracking-widest"
                  style={{ color: "var(--muted)" }}
                >
                  {group.icon} {group.label}
                </p>
                <div className="flex flex-wrap gap-1.5 px-4 pb-3">
                  {group.keywords.map((kw) => {
                    const isActive = activeKw === kw.toLowerCase();
                    return (
                      <button
                        key={kw}
                        type="button"
                        onClick={() => handleChip(kw)}
                        className="rounded-full px-3 py-1 text-xs font-medium transition"
                        style={{
                          background: isActive ? "var(--accent)" : "var(--surface2)",
                          color: isActive ? "#fff" : "var(--muted)",
                          border: isActive
                            ? "1px solid var(--accent)"
                            : "1px solid rgba(255,255,255,0.08)",
                        }}
                        onMouseEnter={(e) => {
                          if (!isActive) {
                            e.currentTarget.style.borderColor = "rgba(249,115,22,0.5)";
                            e.currentTarget.style.color = "var(--accent)";
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isActive) {
                            e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                            e.currentTarget.style.color = "var(--muted)";
                          }
                        }}
                      >
                        {kw}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
