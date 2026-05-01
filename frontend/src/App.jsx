import { useState } from "react";
import { Search } from "lucide-react";

import AlertSignup from "./components/AlertSignup.jsx";
import FilterPanel from "./components/FilterPanel.jsx";
import SearchBar from "./components/SearchBar.jsx";
import StatsBar from "./components/StatsBar.jsx";
import TenderCard from "./components/TenderCard.jsx";
import TenderDetail from "./components/TenderDetail.jsx";
import { useTenders } from "./hooks/useTenders.js";
import { useFilterStore } from "./store/filterStore.js";

export default function App() {
  const [selectedTender, setSelectedTender] = useState(null);
  const filters = useFilterStore();
  const { data, isLoading, isError } = useTenders(filters);
  const tenders = data?.items ?? [];

  return (
    <main className="min-h-screen bg-neutral-50 text-neutral-950">
      <section className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-normal">PrintTender India</h1>
            <p className="max-w-3xl text-sm text-neutral-600">
              Search live government tenders for printing, presses, consumables, stationery, labels, and packaging work.
            </p>
          </div>
          <SearchBar />
          <StatsBar />
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[280px_minmax(0,1fr)_360px] lg:px-8">
        <aside className="space-y-5">
          <FilterPanel />
          <AlertSignup />
        </aside>

        <div className="min-w-0 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold">Tender Results</h2>
            <span className="text-sm text-neutral-500">{data?.total ?? 0} matches</span>
          </div>

          {isLoading && <StatusMessage label="Loading tenders" />}
          {isError && <StatusMessage label="Unable to load tenders" />}
          {!isLoading && !isError && tenders.length === 0 && <StatusMessage label="No matching tenders found" />}

          <div className="space-y-3">
            {tenders.map((tender) => (
              <TenderCard
                key={tender.id}
                tender={tender}
                isSelected={selectedTender?.id === tender.id}
                onSelect={() => setSelectedTender(tender)}
              />
            ))}
          </div>
        </div>

        <TenderDetail tender={selectedTender ?? tenders[0]} />
      </section>
    </main>
  );
}

function StatusMessage({ label }) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded border border-dashed border-neutral-300 bg-white text-sm text-neutral-500">
      <Search className="mr-2 h-4 w-4" />
      {label}
    </div>
  );
}
