import { Search } from "lucide-react";

import { useFilterStore } from "../store/filterStore.js";

export default function SearchBar() {
  const { q, setFilter } = useFilterStore();

  return (
    <label className="relative block">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-neutral-500" />
      <input
        value={q}
        onChange={(event) => setFilter("q", event.target.value)}
        className="h-12 w-full rounded border border-neutral-300 bg-white pl-10 pr-4 text-base outline-none transition focus:border-sky-600 focus:ring-2 focus:ring-sky-100"
        placeholder="Search printing tenders, buyer names, departments"
      />
    </label>
  );
}
