import CountUp from "react-countup";
import { useStats } from "../hooks/useStats.js";
import { useFilterStore } from "../store/filterStore.js";

const CARDS = [
  {
    key: "total_today",
    label: "Tenders Today",
    icon: "📋",
    color: "from-blue-500/20 to-blue-600/10 border-blue-500/20",
    onClick: null,
  },
  {
    key: "expiring_7_days",
    label: "Expiring in 7 Days",
    icon: "⏰",
    color: "from-amber-500/20 to-amber-600/10 border-amber-500/20",
    onClick: (store) => store.setDeadlineDays(7),
    tip: "Click to filter",
  },
  {
    key: "new_since_yesterday",
    label: "New Since Yesterday",
    icon: "✨",
    color: "from-success/20 to-green-600/10 border-success/20",
    onClick: null,
  },
  {
    key: "states_covered",
    label: "States Covered",
    icon: "🗺️",
    color: "from-purple-500/20 to-purple-600/10 border-purple-500/20",
    onClick: null,
  },
];

export default function StatsStrip() {
  const { data: stats, isLoading } = useStats();
  const store = useFilterStore();

  if (isLoading) {
    return (
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-3 px-4 py-4 sm:px-6 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 rounded-xl shimmer" />
        ))}
      </div>
    );
  }

  return (
    <div className="mx-auto grid max-w-7xl grid-cols-2 gap-3 px-4 py-4 sm:px-6 lg:grid-cols-4">
      {CARDS.map(({ key, label, icon, color, onClick, tip }) => {
        const value = stats?.[key] ?? 0;
        return (
          <button
            key={key}
            type="button"
            onClick={onClick ? () => onClick(store) : undefined}
            className={`rounded-xl border bg-gradient-to-br p-4 text-left transition ${color} ${
              onClick ? "cursor-pointer hover:scale-[1.02]" : "cursor-default"
            }`}
            title={tip}
          >
            <div className="flex items-start justify-between">
              <span className="text-2xl">{icon}</span>
              {onClick && (
                <span className="rounded bg-white/10 px-1.5 py-0.5 text-xs text-slate-400">
                  Filter
                </span>
              )}
            </div>
            <div className="mt-2 text-3xl font-bold text-slate-100">
              <CountUp end={value} duration={1.2} separator="," />
            </div>
            <p className="mt-0.5 text-xs text-slate-400">{label}</p>
          </button>
        );
      })}
    </div>
  );
}
