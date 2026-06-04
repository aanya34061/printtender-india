import { Cell, Pie, PieChart, Tooltip } from "recharts";
import { useStats } from "../hooks/useStats.js";
import { useFilterStore } from "../store/filterStore.js";
import { useShallow } from "zustand/react/shallow";

export function portalColor(name) {
  if (name === "CPPP" || name === "etenders.gov.in") return "#3b82f6";
  if (name === "GeM" || name === "gem.gov.in") return "#22c55e";
  if ([
    "PNB Tenders",
    "Canara Bank Tenders",
    "Central Bank of India Tenders",
    "Bank of India Tenders",
    "Indian Bank Tenders",
    "UCO Bank Tenders",
    "Indian Overseas Bank Tenders",
    "LIC Tenders",
  ].includes(name)) return "#06b6d4";
  if ([
    "MP Tenders",
    "eproc.mp.gov.in",
    "MP PWD",
    "MPBSE",
    "MP Forest",
    "MP Info",
    "State-MP",
    "State-UP",
    "State-MH",
    "Maharashtra Tenders",
    "State-RJ",
  ].includes(name)) return "#f97316";
  if (name === "TenderTiger") return "#a855f7";
  if (name === "TenderDekho") return "#14b8a6";
  if (name === "BidAssist") return "#eab308";
  if ([
    "TOI Tenders",
    "HT Tenders",
    "ET Tenders",
    "The Hindu Tenders",
    "Dainik Bhaskar",
    "Patrika",
    "Nai Dunia",
    "Navbharat",
    "Dainik Jagran",
    "Amar Ujala",
    "Tender Notice India",
    "India Tender Notice",
    "Public Notice India",
  ].includes(name)) return "#ef4444";
  return "#64748b";
}

export default function PortalDistribution({ compact = false }) {
  const { data: stats, isLoading } = useStats();
  const { setPortal, setQ } = useFilterStore(
    useShallow((s) => ({ setPortal: s.setPortal, setQ: s.setQ })),
  );
  const portalData = stats?.by_portal
    ? Object.entries(stats.by_portal)
        .filter(([, value]) => Number(value) > 0)
        .map(([name, value]) => ({ name, value: Number(value) }))
    : [];

  if (isLoading) {
    return <div className="skeleton h-64 rounded-xl" />;
  }

  if (portalData.length === 0) {
    return null;
  }

  return (
    <div
      className="rounded-[12px] p-4"
      style={{ background: "var(--surface)", border: "1px solid rgba(255,255,255,0.08)" }}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-300">Tenders by Portal</h3>
        {!compact && (
          <span className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
            {stats?.portals_count ?? portalData.length} portals
          </span>
        )}
      </div>

      <div className={compact ? "" : "grid gap-4 md:grid-cols-[220px_1fr] md:items-center"}>
        <PieChart width={compact ? 200 : 220} height={compact ? 160 : 180} className="mx-auto">
          <Pie
            data={portalData}
            cx={compact ? 100 : 110}
            cy={compact ? 75 : 85}
            innerRadius={compact ? 42 : 50}
            outerRadius={compact ? 62 : 74}
            paddingAngle={2}
            dataKey="value"
          >
            {portalData.map((entry) => (
              <Cell key={entry.name} fill={portalColor(entry.name)} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#222840",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#e2e8f0" }}
            itemStyle={{ color: "#94a3b8" }}
          />
        </PieChart>

        <div className={compact ? "mt-2 space-y-1.5" : "grid gap-2 sm:grid-cols-2"}>
          {portalData.map((d) => (
            <button
              key={d.name}
              type="button"
              onClick={() => { setPortal(d.name); setQ(""); }}
              className="flex min-h-9 w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs transition"
              style={{ color: "var(--muted)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(249,115,22,0.08)";
                e.currentTarget.style.color = "var(--accent)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--muted)";
              }}
              title={`Show ${d.name} tenders`}
            >
              <span className="flex min-w-0 items-center gap-1.5">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: portalColor(d.name) }} />
                <span className="truncate">{d.name}</span>
              </span>
              <span className="shrink-0 font-semibold" style={{ color: portalColor(d.name) }}>{d.value}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
