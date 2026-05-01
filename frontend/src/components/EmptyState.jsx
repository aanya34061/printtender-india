import { useFilterStore } from "../store/filterStore.js";

const SUGGESTIONS = ["offset printing", "stationery", "packaging", "digital printing", "calendar"];

export default function EmptyState({ query }) {
  const { setQ } = useFilterStore();

  return (
    <div className="flex flex-col items-center justify-center gap-5 rounded-xl border border-white/5 bg-surface/40 py-16 text-center">
      {/* Inline SVG — simple printing press line art */}
      <svg width="80" height="64" viewBox="0 0 80 64" fill="none" className="opacity-30">
        <rect x="8" y="24" width="64" height="28" rx="4" stroke="#94a3b8" strokeWidth="2" />
        <rect x="20" y="8" width="40" height="20" rx="3" stroke="#94a3b8" strokeWidth="2" />
        <rect x="28" y="52" width="24" height="10" rx="2" stroke="#94a3b8" strokeWidth="2" />
        <circle cx="18" cy="38" r="5" stroke="#f97316" strokeWidth="2" />
        <circle cx="62" cy="38" r="5" stroke="#f97316" strokeWidth="2" />
        <line x1="28" y1="36" x2="52" y2="36" stroke="#94a3b8" strokeWidth="2" strokeDasharray="4 2" />
        <line x1="28" y1="42" x2="52" y2="42" stroke="#94a3b8" strokeWidth="2" strokeDasharray="4 2" />
      </svg>

      <div>
        <p className="text-lg font-semibold text-slate-300">
          No tenders found{query ? ` for "${query}"` : ""}
        </p>
        <p className="mt-1 text-sm text-slate-500">Try one of these instead:</p>
      </div>

      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((kw) => (
          <button
            key={kw}
            type="button"
            onClick={() => setQ(kw)}
            className="rounded-full border border-accent/30 bg-accent/10 px-4 py-1.5 text-sm text-accent transition hover:bg-accent/20"
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  );
}
