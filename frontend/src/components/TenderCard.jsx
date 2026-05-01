import { CalendarDays, ExternalLink, MapPin } from "lucide-react";
import { formatDistanceToNowStrict, parseISO } from "date-fns";

export default function TenderCard({ tender, isSelected, onSelect }) {
  const deadline = tender.deadline ? formatDistanceToNowStrict(parseISO(tender.deadline), { addSuffix: true }) : "No deadline";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded border bg-white p-4 text-left transition hover:border-sky-500 ${
        isSelected ? "border-sky-600 ring-2 ring-sky-100" : "border-neutral-200"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-neutral-950">{tender.title}</h3>
          <p className="mt-1 truncate text-xs text-neutral-500">{tender.buyer || tender.source}</p>
        </div>
        <ExternalLink className="h-4 w-4 shrink-0 text-neutral-400" />
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-neutral-600">
        <span className="inline-flex items-center gap-1">
          <MapPin className="h-3.5 w-3.5" />
          {tender.state || "India"}
        </span>
        <span className="inline-flex items-center gap-1">
          <CalendarDays className="h-3.5 w-3.5" />
          {deadline}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {(tender.keywords || []).slice(0, 4).map((keyword) => (
          <span key={keyword} className="rounded bg-neutral-100 px-2 py-1 text-xs text-neutral-700">
            {keyword}
          </span>
        ))}
      </div>
    </button>
  );
}
