import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { differenceInDays, parseISO } from "date-fns";
import { Bookmark } from "lucide-react";
import { Cell, Pie, PieChart, Tooltip } from "recharts";
import { useStats } from "../hooks/useStats.js";
import { useFilterStore } from "../store/filterStore.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function portalColor(name) {
  if (name === "CPPP") return "#3b82f6";
  if (name === "GeM") return "#22c55e";
  if (["MP Tenders", "MP PWD", "MPBSE", "MP Forest", "MP Info", "State-MP"].includes(name)) return "#f97316";
  if (name === "TenderTiger") return "#a855f7";
  if (name === "TenderDekho") return "#14b8a6";
  if (name === "BidAssist") return "#eab308";
  // Newspaper sources - use red
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

function useExpiringSoon() {
  return useQuery({
    queryKey: ["expiring-soon"],
    queryFn: async () => {
      const { data } = await axios.get(`${BASE}/api/tenders`, {
        params: { q: "printing", deadline_within_days: 3, limit: 5, sort: "deadline_asc" },
      });
      return data.tenders ?? [];
    },
    staleTime: 1000 * 60 * 5,
  });
}

function SideCard({ title, children }) {
  return (
    <div
      className="rounded-[12px] p-4"
      style={{ background: "var(--surface)", border: "1px solid rgba(255,255,255,0.08)" }}
    >
      <h3 className="mb-3 text-sm font-semibold text-slate-300">{title}</h3>
      {children}
    </div>
  );
}

export default function Sidebar({ bookmarks, onView }) {
  const { data: stats } = useStats();
  const { data: expiring = [] } = useExpiringSoon();
  const { setPortal, setQ } = useFilterStore();

  const portalData = stats?.by_portal
    ? Object.entries(stats.by_portal).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="space-y-4 lg:w-64 xl:w-72">
      {/* Portal distribution */}
      {portalData.length > 0 && (
        <SideCard title="Tenders by Portal">
          <PieChart width={200} height={160} className="mx-auto">
            <Pie data={portalData} cx={100} cy={75} innerRadius={42} outerRadius={62} paddingAngle={2} dataKey="value">
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
          <div className="mt-2 space-y-1.5">
            {portalData.map((d) => (
              <button
                key={d.name}
                type="button"
                onClick={() => { setPortal(d.name); setQ("printing"); }}
                className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs transition"
                style={{ color: "var(--muted)" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(249,115,22,0.08)"; e.currentTarget.style.color = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--muted)"; }}
                title={`Show ${d.name} tenders`}
              >
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: portalColor(d.name) }} />
                  {d.name}
                </span>
                <span className="font-semibold" style={{ color: portalColor(d.name) }}>{d.value} →</span>
              </button>
            ))}
          </div>
        </SideCard>
      )}

      {/* Expiring soon */}
      {expiring.length > 0 && (
        <SideCard title="⏰ Expiring Soon">
          <ul className="space-y-3">
            {expiring.map((t) => {
              const days = t.bid_end_date ? differenceInDays(parseISO(t.bid_end_date), new Date()) : null;
              return (
                <li key={t.id}>
                  <button type="button" onClick={() => onView(t)} className="w-full text-left">
                    <p
                      className="line-clamp-2 text-xs font-medium text-slate-300 transition"
                      onMouseEnter={(e) => e.currentTarget.style.color = "var(--accent)"}
                      onMouseLeave={(e) => e.currentTarget.style.color = ""}
                    >
                      {t.title}
                    </p>
                    {days !== null && (
                      <p
                        className="mt-0.5 text-xs font-semibold"
                        style={{ color: days <= 1 ? "var(--red)" : "var(--amber)" }}
                      >
                        {days === 0 ? "Closes today" : `${days}d left`}
                      </p>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </SideCard>
      )}

      {/* Bookmarks */}
      {bookmarks.length > 0 && (
        <SideCard title="">
          <div className="mb-3 flex items-center gap-1.5">
            <Bookmark className="h-4 w-4" style={{ color: "var(--accent)" }} />
            <h3 className="text-sm font-semibold text-slate-300">Bookmarked ({bookmarks.length})</h3>
          </div>
          <ul className="space-y-2.5">
            {bookmarks.slice(0, 5).map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onView(t)}
                  className="line-clamp-2 w-full text-left text-xs font-medium transition"
                  style={{ color: "var(--muted)" }}
                  onMouseEnter={(e) => e.currentTarget.style.color = "var(--accent)"}
                  onMouseLeave={(e) => e.currentTarget.style.color = "var(--muted)"}
                >
                  {t.title}
                </button>
              </li>
            ))}
          </ul>
        </SideCard>
      )}
    </div>
  );
}
