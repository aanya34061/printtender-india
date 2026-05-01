import { Activity, Database, Globe } from "lucide-react";
import { formatDistanceToNowStrict, parseISO } from "date-fns";
import { useStats } from "../hooks/useStats.js";

export default function StatsBar() {
  const { data, isLoading } = useStats();

  const lastFetch = data?.last_fetch
    ? formatDistanceToNowStrict(parseISO(data.last_fetch), { addSuffix: true })
    : null;

  if (isLoading) {
    return (
      <div className="flex flex-wrap gap-4 text-sm text-navy/60">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-5 w-32 animate-pulse rounded bg-navy/10" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-navy/10 bg-white px-4 py-3 text-sm shadow-sm">
      <Stat icon={<Database className="h-4 w-4" />} value={data?.total_active ?? 0} label="Active Tenders" />
      <span className="hidden text-navy/20 sm:block">|</span>
      <Stat icon={<Globe className="h-4 w-4" />} value={data?.portals_count ?? 0} label="Portals" />
      <span className="hidden text-navy/20 sm:block">|</span>
      <Stat
        icon={<Activity className="h-4 w-4" />}
        value={lastFetch ? `Updated ${lastFetch}` : "Fetching…"}
        label={null}
      />
    </div>
  );
}

function Stat({ icon, value, label }) {
  return (
    <div className="flex items-center gap-1.5 font-medium text-navy">
      <span className="text-teal">{icon}</span>
      <span>{value}</span>
      {label && <span className="font-normal text-navy/50">{label}</span>}
    </div>
  );
}
