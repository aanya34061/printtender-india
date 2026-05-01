import { Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useFilterStore } from "../store/filterStore.js";

const CHIPS = [
  "Offset Printing",
  "Digital Printing",
  "Stationery",
  "Textbook Printing",
  "Security Printing",
  "Packaging",
  "Calendar Printing",
  "Toner Cartridge",
];

export default function SearchBar() {
  const { query, setQuery } = useFilterStore();
  const [inputValue, setInputValue] = useState(query);
  const timerRef = useRef(null);

  // sync store → input when store changes externally (e.g. chip click or reset)
  useEffect(() => {
    setInputValue(query);
  }, [query]);

  function handleChange(e) {
    const val = e.target.value;
    setInputValue(val);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setQuery(val), 500);
  }

  function handleChip(chip) {
    setInputValue(chip);
    clearTimeout(timerRef.current);
    setQuery(chip);
  }

  return (
    <div className="space-y-3">
      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-navy/50" />
        <input
          value={inputValue}
          onChange={handleChange}
          className="h-12 w-full rounded-lg border-2 border-navy/20 bg-white pl-10 pr-4 text-base text-navy outline-none transition placeholder:text-navy/40 focus:border-crimson focus:ring-2 focus:ring-crimson/10"
          placeholder="Search printing tenders, buyer names, departments…"
        />
      </label>

      <div className="flex flex-wrap gap-2">
        {CHIPS.map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => handleChip(chip)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              inputValue.toLowerCase() === chip.toLowerCase()
                ? "border-crimson bg-crimson text-white"
                : "border-navy/20 bg-white text-navy hover:border-crimson hover:text-crimson"
            }`}
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
