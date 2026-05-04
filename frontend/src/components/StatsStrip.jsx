import CountUp from "react-countup";
import { useStats } from "../hooks/useStats.js";
import { useFilterStore } from "../store/filterStore.js";

const CARDS = [
  {
    key: "total_today",
    label: "Tenders Today",
    icon: "📋",
    color: "#3b82f6",
    bg: "rgba(59,130,246,0.1)",
    onClick: null,
  },
  {
    key: "expiring_7_days",
    label: "Expiring in 7 Days",
    icon: "⏰",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.1)",
    onClick: (store) => store.setDeadlineDays(7),
    tip: "Click to filter",
  },
  {
    key: "new_since_yesterday",
    label: "New Yesterday",
    icon: "✨",
    color: "#22c55e",
    bg: "rgba(34,197,94,0.1)",
    onClick: null,
  },
  {
    key: "states_covered",
    label: "States Covered",
    icon: "🗺️",
    color: "#a855f7",
    bg: "rgba(168,85,247,0.1)",
    onClick: null,
  },
];

export default function StatsStrip() {
  const { data: stats, isLoading } = useStats();
  const store = useFilterStore();
  const noSync = !stats?.last_fetch;

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-6 sm:px-10">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-28 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6 sm:px-10">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {CARDS.map(({ key, label, icon, color, bg, onClick, tip }) => {
          const value = stats?.[key] ?? 0;
          const isClickable = !!onClick;

          return (
            <button
              key={key}
              type="button"
              onClick={isClickable ? () => onClick(store) : undefined}
              title={tip}
              className={`card group flex items-center gap-4 p-5 text-left ${
                isClickable ? "cursor-pointer" : "cursor-default"
              }`}
              style={{
                transition: isClickable ? "border-color 150ms, background 150ms" : undefined,
              }}
              onMouseEnter={isClickable ? (e) => {
                e.currentTarget.style.borderColor = "rgba(249,115,22,0.4)";
              } : undefined}
              onMouseLeave={isClickable ? (e) => {
                e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
              } : undefined}
            >
              {/* Icon circle */}
              <div
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl"
                style={{ background: bg }}
              >
                {icon}
              </div>

              {/* Number + label */}
              <div className="min-w-0">
                <div
                  className="text-3xl font-bold tabular-nums"
                  style={{ color }}
                >
                  {noSync ? "—" : <CountUp end={value} duration={1.2} separator="," />}
                </div>
                <p className="mt-0.5 truncate text-xs font-medium" style={{ color: "var(--muted)" }}>
                  {label}
                </p>
                {noSync && (
                  <p className="mt-0.5 text-xs" style={{ color: "var(--muted)", opacity: 0.6 }}>
                    Run a sync
                  </p>
                )}
              </div>

              {/* Filter badge — visible on hover for clickable cards */}
              {isClickable && (
                <span
                  className="ml-auto self-start rounded px-1.5 py-0.5 text-xs font-semibold opacity-0 transition-opacity group-hover:opacity-100"
                  style={{ background: "rgba(249,115,22,0.15)", color: "var(--accent)" }}
                >
                  Filter →
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
