import { SlidersHorizontal, X } from "lucide-react";
import { useFilterStore } from "../store/filterStore.js";

const STATES = [
  "Madhya Pradesh","Andhra Pradesh","Assam","Bihar","Chhattisgarh","Delhi","Goa","Gujarat",
  "Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala",
  "Maharashtra","Odisha","Punjab","Rajasthan",
  "Tamil Nadu","Telangana","Uttar Pradesh","Uttarakhand","West Bengal",
  "Jammu & Kashmir","Puducherry","Chandigarh",
];

const PORTALS = ["CPPP", "GeM", "State-MP", "State-UP", "State-MH", "State-RJ", "TenderDekho"];

const DEADLINE_OPTS = [
  { label: "Today only", value: 1 },
  { label: "Within 3 days", value: 3 },
  { label: "Within 7 days", value: 7 },
  { label: "Within 30 days", value: 30 },
];

const VALUE_OPTS = [
  { label: "Under ₹1 L", min: null, max: 100_000 },
  { label: "₹1–10 L", min: 100_000, max: 1_000_000 },
  { label: "₹10–50 L", min: 1_000_000, max: 5_000_000 },
  { label: "₹50 L–1 Cr", min: 5_000_000, max: 10_000_000 },
  { label: "Above ₹1 Cr", min: 10_000_000, max: null },
];

export default function FilterRow() {
  const {
    state, portal, deadline_within_days, min_value, max_value,
    setState, setPortal, setDeadlineDays, setValueRange, resetFilters,
  } = useFilterStore();

  const activeCount =
    [state, portal].filter(Boolean).length +
    (deadline_within_days !== 30 ? 1 : 0) +
    (min_value !== null || max_value !== null ? 1 : 0);

  return (
    <div
      id="filter-row"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "#1a1f35" }}
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-6 pb-2 pt-3 sm:px-10">
        <SlidersHorizontal className="h-4 w-4 shrink-0" style={{ color: "var(--muted)" }} />

        <FilterSelect
          value={state ?? ""}
          onChange={(v) => setState(v || null)}
          placeholder="All States"
        >
          {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </FilterSelect>

        <FilterSelect
          value={portal ?? ""}
          onChange={(v) => setPortal(v || null)}
          placeholder="All Portals"
        >
          {PORTALS.map((p) => <option key={p} value={p}>{p}</option>)}
        </FilterSelect>

        <FilterSelect
          value={deadline_within_days !== 30 ? String(deadline_within_days) : ""}
          onChange={(v) => setDeadlineDays(v ? Number(v) : 30)}
          placeholder="Any Deadline"
        >
          {DEADLINE_OPTS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </FilterSelect>

        <FilterSelect
          value={min_value !== null || max_value !== null ? `${min_value ?? ""}:${max_value ?? ""}` : ""}
          onChange={(v) => {
            if (!v) { setValueRange(null, null); return; }
            const [mn, mx] = v.split(":").map((x) => (x === "" ? null : Number(x)));
            setValueRange(mn, mx);
          }}
          placeholder="Any Value"
        >
          {VALUE_OPTS.map((o) => (
            <option key={o.label} value={`${o.min ?? ""}:${o.max ?? ""}`}>{o.label}</option>
          ))}
        </FilterSelect>

        {activeCount > 0 && (
          <div className="flex items-center gap-2">
            <span
              className="rounded-full px-2 py-0.5 text-xs font-semibold text-white"
              style={{ background: "var(--accent)" }}
            >
              {activeCount}
            </span>
            <button
              type="button"
              onClick={resetFilters}
              className="flex items-center gap-1 text-sm"
              style={{ color: "var(--accent)", textDecoration: "underline", background: "none", border: "none", cursor: "pointer" }}
            >
              <X className="h-3 w-3" /> Clear All
            </button>
          </div>
        )}
      </div>
      <p className="mx-auto max-w-6xl px-6 pb-3 text-xs sm:px-10" style={{ color: "var(--muted)" }}>
        Covering: MP Tenders · MP PWD · MPBSE · GeM MP · CPPP MP · MP Forest · MP Info.
      </p>
    </div>
  );
}

function FilterSelect({ value, onChange, placeholder, children }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="form-select min-w-[140px] text-sm"
    >
      <option value="">{placeholder}</option>
      {children}
    </select>
  );
}
