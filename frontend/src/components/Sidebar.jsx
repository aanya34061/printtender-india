import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { differenceInDays, parseISO } from "date-fns";
import { Bookmark } from "lucide-react";
import { Cell, Pie, PieChart, Tooltip } from "recharts";
import { useStats } from "../hooks/useStats.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const COLORS = { CPPP: "#3b82f6", GeM: "#22c55e", State: "#a855f7", Other: "#64748b" };

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

export default function Sidebar({ bookmarks, onView, onViewTender }) {
  const { data: stats } = useStats();
  const { data: expiring = [] } = useExpiringSoon();

  const portalData = stats?.by_portal
    ? Object.entries(stats.by_portal)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="space-y-4 lg:w-64 xl:w-72">
      {/* Portal distribution */}
      {portalData.length > 0 && (
        <div className="card p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">Tenders by Portal</h3>
          <PieChart width={200} height={160} className="mx-auto">
            <Pie data={portalData} cx={100} cy={75} innerRadius={42} outerRadius={62}
              paddingAngle={2} dataKey="value">
              {portalData.map((entry) => (
                <Cell key={entry.name} fill={COLORS[entry.name] ?? "#64748b"} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: "#1e2235", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8 }}
              labelStyle={{ color: "#e2e8f0" }}
              itemStyle={{ color: "#94a3b8" }}
            />
          </PieChart>
          <div className="mt-2 space-y-1">
            {portalData.map((d) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: COLORS[d.name] }} />
                  <span className="text-slate-400">{d.name}</span>
                </span>
                <span className="font-semibold text-slate-300">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Expiring soon */}
      {expiring.length > 0 && (
        <div className="card p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">⏰ Expiring Soon</h3>
          <ul className="space-y-2.5">
            {expiring.map((t) => {
              const days = t.bid_end_date
                ? differenceInDays(parseISO(t.bid_end_date), new Date())
                : null;
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => onView(t)}
                    className="w-full text-left"
                  >
                    <p className="line-clamp-2 text-xs font-medium text-slate-300 hover:text-accent">
                      {t.title}
                    </p>
                    {days !== null && (
                      <p className={`mt-0.5 text-xs ${days <= 1 ? "text-danger" : "text-warning"}`}>
                        {days === 0 ? "Closes today" : `${days}d left`}
                      </p>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Bookmarks */}
      {bookmarks.length > 0 && (
        <div className="card p-4">
          <h3 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-slate-300">
            <Bookmark className="h-4 w-4 text-accent" />
            Bookmarked ({bookmarks.length})
          </h3>
          <ul className="space-y-2.5">
            {bookmarks.slice(0, 5).map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onView(t)}
                  className="w-full text-left text-xs font-medium text-slate-400 hover:text-accent line-clamp-2"
                >
                  {t.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
