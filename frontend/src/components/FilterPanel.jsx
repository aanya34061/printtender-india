import { SlidersHorizontal } from "lucide-react";

import { useFilterStore } from "../store/filterStore.js";

const states = ["", "Delhi", "Maharashtra", "Madhya Pradesh", "Rajasthan", "Uttar Pradesh"];
const sources = ["", "cppp", "gem", "mp_tenders", "up_tenders", "maharashtra_tenders", "rajasthan_sppp", "tenderdekho"];

export default function FilterPanel() {
  const { state, source, activeOnly, setFilter } = useFilterStore();

  return (
    <section className="rounded border border-neutral-200 bg-white p-4">
      <div className="mb-4 flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-neutral-600" />
        <h2 className="text-sm font-semibold">Filters</h2>
      </div>

      <div className="space-y-4">
        <Field label="State">
          <select
            value={state}
            onChange={(event) => setFilter("state", event.target.value)}
            className="h-10 w-full rounded border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-sky-600 focus:ring-2 focus:ring-sky-100"
          >
            {states.map((item) => (
              <option key={item || "all"} value={item}>
                {item || "All states"}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Source">
          <select
            value={source}
            onChange={(event) => setFilter("source", event.target.value)}
            className="h-10 w-full rounded border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-sky-600 focus:ring-2 focus:ring-sky-100"
          >
            {sources.map((item) => (
              <option key={item || "all"} value={item}>
                {item || "All sources"}
              </option>
            ))}
          </select>
        </Field>

        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(event) => setFilter("activeOnly", event.target.checked)}
            className="h-4 w-4 rounded border-neutral-300 text-sky-700"
          />
          Active tenders only
        </label>
      </div>
    </section>
  );
}

function Field({ label, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium uppercase text-neutral-500">{label}</span>
      {children}
    </label>
  );
}
