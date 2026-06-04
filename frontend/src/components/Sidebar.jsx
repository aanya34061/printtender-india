import { useQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import { fetchJSON } from "../lib/api.js";
import { differenceInCalendarDays } from "../lib/date.js";
import PortalDistribution from "./PortalDistribution.jsx";

function useExpiringSoon(enabled) {
  return useQuery({
    queryKey: ["expiring-soon"],
    enabled,
    queryFn: async () => {
      const data = await fetchJSON("/api/tenders", {
        params: { deadline_within_days: 3, limit: 5, sort: "deadline_asc" },
      });
      return data.tenders ?? [];
    },
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
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
  const { data: expiring = [] } = useExpiringSoon(true);

  return (
    <div className="space-y-4 lg:w-64 xl:w-72">
      <PortalDistribution compact />

      {/* Expiring soon */}
      {expiring.length > 0 && (
        <SideCard title="⏰ Expiring Soon">
          <ul className="space-y-3">
            {expiring.map((t) => {
              const days = differenceInCalendarDays(t.bid_end_date);
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
