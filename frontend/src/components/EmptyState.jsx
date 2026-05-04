import { useFilterStore } from "../store/filterStore.js";

const SUGGESTIONS = [
  "offset printing", "stationery", "packaging",
  "digital printing", "calendar", "brochures",
];

export default function EmptyState({ query }) {
  const { setQ } = useFilterStore();

  return (
    <div
      className="flex flex-col items-center justify-center gap-6 rounded-[12px] py-16 text-center"
      style={{ background: "var(--surface)", border: "1px solid rgba(255,255,255,0.08)" }}
    >
      {/* Inline SVG — printing press line art */}
      <svg width="96" height="72" viewBox="0 0 96 72" fill="none" style={{ opacity: 0.3 }}>
        <rect x="10" y="26" width="76" height="32" rx="5" stroke="#94a3b8" strokeWidth="2" />
        <rect x="24" y="8"  width="48" height="24" rx="4" stroke="#94a3b8" strokeWidth="2" />
        <rect x="32" y="58" width="32" height="12" rx="3" stroke="#94a3b8" strokeWidth="2" />
        <circle cx="20" cy="42" r="6" stroke="#f97316" strokeWidth="2" />
        <circle cx="76" cy="42" r="6" stroke="#f97316" strokeWidth="2" />
        <line x1="32" y1="39" x2="64" y2="39" stroke="#94a3b8" strokeWidth="2" strokeDasharray="4 3" />
        <line x1="32" y1="46" x2="64" y2="46" stroke="#94a3b8" strokeWidth="2" strokeDasharray="4 3" />
      </svg>

      <div>
        <p className="text-lg font-semibold text-slate-200">
          No tenders found{query ? ` for "${query}"` : ""}
        </p>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          Try one of these instead:
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((kw) => (
          <button
            key={kw}
            type="button"
            onClick={() => setQ(kw)}
            className="chip chip-active"
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  );
}
