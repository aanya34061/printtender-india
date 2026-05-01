import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useFilterStore } from "../store/filterStore.js";

const KEYWORDS = [
  "offset printing", "digital printing", "packaging", "stationery",
  "booklet", "brochure", "label", "flex printing", "security printing",
  "textbook", "calendar", "gazette", "toner", "ballot paper",
];

export default function HeroSearch() {
  const { q, setQ } = useFilterStore();
  const [inputVal, setInputVal] = useState(q);
  const timer = useRef(null);

  useEffect(() => {
    setInputVal(q);
  }, [q]);

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
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6">
      <h1 className="text-center text-3xl font-bold text-slate-100 sm:text-4xl">
        Find <span className="text-gradient">Printing Tenders</span>
      </h1>
      <p className="text-center text-sm text-slate-500">
        Live government tender data from CPPP · GeM · State Portals. Updated every 6 hours.
      </p>

      {/* Search input */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
        <input
          value={inputVal}
          onChange={handleChange}
          className="input-field h-14 w-full pl-12 pr-4 text-base"
          placeholder="Search by keyword, department, state…"
          aria-label="Search tenders"
        />
      </div>

      {/* Keyword chips */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {KEYWORDS.map((kw) => (
          <button
            key={kw}
            type="button"
            onClick={() => handleChip(kw)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition ${
              inputVal.toLowerCase() === kw.toLowerCase()
                ? "bg-accent text-white"
                : "border border-white/10 bg-surface text-slate-400 hover:border-accent/50 hover:text-accent"
            }`}
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  );
}
