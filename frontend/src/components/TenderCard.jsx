import { differenceInDays, parseISO } from "date-fns";
import { ExternalLink, Eye, MapPin } from "lucide-react";

function formatValue(val) {
  const n = Number(val);
  if (!n) return null;
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(2)} Cr`;
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(2)} Lakh`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function deadlineBadge(bid_end_date) {
  if (!bid_end_date) return null;
  const days = differenceInDays(parseISO(bid_end_date), new Date());
  if (days < 0) return null;
  const label = days === 0 ? "Today!" : `${days} day${days !== 1 ? "s" : ""} left`;
  const cls =
    days < 7
      ? "bg-crimson/10 text-crimson border-crimson/20"
      : days < 30
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-teal/10 text-teal border-teal/20";
  return { label, cls };
}

function portalBadge(portal_source) {
  if (!portal_source) return { label: "Portal", cls: "bg-gray-100 text-gray-600" };
  if (portal_source === "CPPP") return { label: "CPPP", cls: "bg-blue-100 text-blue-700" };
  if (portal_source === "GeM") return { label: "GeM", cls: "bg-green-100 text-green-700" };
  if (portal_source.startsWith("State-"))
    return { label: portal_source, cls: "bg-orange-100 text-orange-700" };
  return { label: portal_source, cls: "bg-purple-100 text-purple-700" };
}

function toTitleCase(str) {
  return str
    ? str.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    : str;
}

export default function TenderCard({ tender, onViewDetails }) {
  const deadline = deadlineBadge(tender.bid_end_date);
  const portal = portalBadge(tender.portal_source);
  const value = formatValue(tender.value_inr);

  return (
    <div className="group rounded-xl border border-navy/10 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      {/* Badges row */}
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${portal.cls}`}>
          {portal.label}
        </span>
        {tender.state && (
          <span className="rounded-full bg-navy px-2 py-0.5 text-xs font-semibold text-white">
            <MapPin className="mr-0.5 inline h-3 w-3" />
            {tender.state}
          </span>
        )}
        {deadline && (
          <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${deadline.cls}`}>
            {deadline.label}
          </span>
        )}
        {value && (
          <span className="ml-auto text-xs font-semibold text-navy/70">{value}</span>
        )}
      </div>

      {/* Title */}
      <h3 className="line-clamp-2 text-sm font-bold leading-snug text-navy">
        {toTitleCase(tender.title)}
      </h3>

      {/* Organisation */}
      {tender.organisation && (
        <p className="mt-1 truncate text-xs text-navy/50">{tender.organisation}</p>
      )}

      {/* Actions */}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => onViewDetails(tender)}
          className="flex items-center gap-1.5 rounded-lg border border-navy/20 px-3 py-1.5 text-xs font-semibold text-navy transition hover:border-navy hover:bg-navy hover:text-white"
        >
          <Eye className="h-3.5 w-3.5" />
          View Details
        </button>
        {tender.portal_url && (
          <a
            href={tender.portal_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 rounded-lg bg-crimson px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-crimson/90"
          >
            Apply Now
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}
