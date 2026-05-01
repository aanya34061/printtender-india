import { Database, Landmark, Timer } from "lucide-react";

import { useStats } from "../hooks/useStats.js";

export default function StatsBar() {
  const { data } = useStats();

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Stat icon={<Database />} label="Total tenders" value={data?.total_tenders ?? 0} />
      <Stat icon={<Timer />} label="Active tenders" value={data?.active_tenders ?? 0} />
      <Stat icon={<Landmark />} label="Sources" value={Object.keys(data?.sources ?? {}).length} />
    </div>
  );
}

function Stat({ icon, label, value }) {
  return (
    <div className="flex items-center gap-3 rounded border border-neutral-200 bg-white px-4 py-3">
      <span className="text-sky-700 [&>svg]:h-5 [&>svg]:w-5">{icon}</span>
      <div>
        <p className="text-xs text-neutral-500">{label}</p>
        <p className="text-lg font-semibold">{value}</p>
      </div>
    </div>
  );
}
