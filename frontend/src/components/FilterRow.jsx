import { SlidersHorizontal, X } from "lucide-react";
import { useFilterStore } from "../store/filterStore.js";

const STATES = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat",
  "Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
  "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab",
  "Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh",
  "Uttarakhand","West Bengal","Delhi","Jammu & Kashmir","Ladakh","Puducherry",
  "Chandigarh","Goa",
];

const PORTALS = ["CPPP", "GeM", "State-MP", "State-UP", "State-MH", "State-RJ", "TenderDekho"];

const DEADLINE_OPTS = [
  { label: "Expiring today", value: 1 },
  { label: "Within 3 days", value: 3 },
  { label: "Within 7 days", value: 7 },
  { label: "Within 30 days", value: 30 },
];

const VALUE_OPTS = [
  { label: "Under ₹1 Lakh", min: null, max: 100_000 },
  { label: "₹1–10 Lakh", min: 100_000, max: 1_000_000 },
  { label: "₹10–50 Lakh", min: 1_000_000, max: 5_000_000 },
  { label: "₹50L–1 Cr", min: 5_000_000, max: 10_000_000 },
  { label: "Above ₹1 Cr", min: 10_000_000, max: null },
];

export default function FilterRow() {
  const {
    state, portal, deadline_within_days, min_value, max_value,
    setState, setPortal, setDeadlineDays, setValueRange, resetFilters,
  } = useFilterStore();

  const activeCount = [state, portal].filter(Boolean).length
    + (deadline_within_days !== 30 ? 1 : 0)
    + (min_value !== null || max_value !== null ? 1 : 0);

  return (
    <div className="border-b border-white/5 bg-surface/60 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-4 py-3 sm:px-6">
        <SlidersHorizontal className="h-4 w-4 shrink-0 text-slate-500" />

        <Select
          value={state ?? ""}
          onChange={(v) => setState(v || null)}
          placeholder="All States"
        >
          {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>

        <Select
          value={portal ?? ""}
          onChange={(v) => setPortal(v || null)}
          placeholder="All Portals"
        >
          {PORTALS.map((p) => <option key={p} value={p}>{p}</option>)}
        </Select>

        <Select
          value={deadline_within_days !== 30 ? String(deadline_within_days) : ""}
          onChange={(v) => setDeadlineDays(v ? Number(v) : 30)}
          placeholder="Any Deadline"
        >
          {DEADLINE_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>

        <Select
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
        </Select>

        {activeCount > 0 && (
          <button
            type="button"
            onClick={resetFilters}
            className="flex items-center gap-1.5 rounded-full bg-accent/10 px-3 py-1.5 text-xs font-semibold text-accent transition hover:bg-accent/20"
          >
            <X className="h-3 w-3" />
            Clear All ({activeCount})
          </button>
        )}
      </div>
    </div>
  );
}

function Select({ value, onChange, placeholder, children }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="select-field h-9 rounded-full px-3 pr-8 text-xs font-medium"
      >
        <option value="">{placeholder}</option>
        {children}
      </select>
      <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 text-xs">▾</span>
    </div>
  );
}
