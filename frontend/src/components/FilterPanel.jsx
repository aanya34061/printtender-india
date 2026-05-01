import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { useFilterStore } from "../store/filterStore.js";

const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman & Nicobar", "Chandigarh", "Dadra & Nagar Haveli", "Daman & Diu",
  "Delhi", "Jammu & Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

const PORTALS = ["CPPP", "GeM", "State-MP", "State-UP", "State-MH", "State-RJ", "TenderDekho"];

const CATEGORIES = [
  "Offset Printing", "Digital Printing", "Flexo/Gravure", "Security Print",
  "Publication", "Packaging", "Stationery", "Consumables", "Large Format",
  "General Printing",
];

const DEADLINE_OPTIONS = [
  { label: "Next 7 days", value: 7 },
  { label: "Next 30 days", value: 30 },
  { label: "Next 90 days", value: 90 },
];

export default function FilterPanel() {
  const { state, portal, category, days, setState, setPortal, setCategory, setDays, resetFilters,
    query } = useFilterStore();

  const activeCount = [state, portal, category].filter(Boolean).length + (days !== 30 ? 1 : 0);

  return (
    <aside className="rounded-xl border border-navy/10 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-navy" />
          <h2 className="text-sm font-semibold text-navy">Filters</h2>
          {activeCount > 0 && (
            <span className="rounded-full bg-crimson px-2 py-0.5 text-xs font-bold text-white">
              {activeCount}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={resetFilters}
          className="flex items-center gap-1 text-xs text-navy/50 hover:text-crimson"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
      </div>

      <div className="space-y-4">
        <FilterField label="State">
          <select
            value={state ?? ""}
            onChange={(e) => setState(e.target.value || null)}
            className={selectCls}
          >
            <option value="">All States &amp; UTs</option>
            {STATES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </FilterField>

        <FilterField label="Portal">
          <select
            value={portal ?? ""}
            onChange={(e) => setPortal(e.target.value || null)}
            className={selectCls}
          >
            <option value="">All Portals</option>
            {PORTALS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </FilterField>

        <FilterField label="Category">
          <select
            value={category ?? ""}
            onChange={(e) => setCategory(e.target.value || null)}
            className={selectCls}
          >
            <option value="">All Categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </FilterField>

        <FilterField label="Deadline">
          <div className="flex flex-col gap-1.5">
            {DEADLINE_OPTIONS.map((opt) => (
              <label key={opt.value} className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="days"
                  value={opt.value}
                  checked={days === opt.value}
                  onChange={() => setDays(opt.value)}
                  className="accent-crimson"
                />
                <span className="text-navy/80">{opt.label}</span>
              </label>
            ))}
          </div>
        </FilterField>
      </div>
    </aside>
  );
}

const selectCls =
  "h-10 w-full rounded-lg border border-navy/20 bg-white px-3 text-sm text-navy outline-none transition focus:border-crimson focus:ring-2 focus:ring-crimson/10";

function FilterField({ label, children }) {
  return (
    <div className="space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-navy/50">{label}</span>
      {children}
    </div>
  );
}
