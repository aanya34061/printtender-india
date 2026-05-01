import { differenceInDays, format, parseISO } from "date-fns";
import { motion } from "framer-motion";
import { Bookmark, BookmarkCheck, ExternalLink } from "lucide-react";

export const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.28 } },
};

function portalBadge(src) {
  if (!src) return { label: "Portal", cls: "bg-slate-500/20 text-slate-400" };
  if (src === "CPPP") return { label: "CPPP", cls: "bg-blue-500/20 text-blue-400" };
  if (src === "GeM") return { label: "GeM", cls: "bg-success/20 text-success" };
  if (src.startsWith("State-")) return { label: src, cls: "bg-purple-500/20 text-purple-400" };
  return { label: src, cls: "bg-slate-500/20 text-slate-400" };
}

function deadlineInfo(dateStr) {
  if (!dateStr) return null;
  try {
    const days = differenceInDays(parseISO(dateStr), new Date());
    if (days < 0) return null;
    if (days === 0) return { label: "Closes today — Urgent!", cls: "text-danger" };
    if (days <= 3) return { label: `Closes in ${days} days — Urgent!`, cls: "text-danger" };
    if (days <= 7) return { label: `Closes in ${days} days`, cls: "text-warning" };
    return { label: `Closes in ${days} days`, cls: "text-success" };
  } catch {
    return null;
  }
}

function fmtValue(val) {
  const n = Number(val);
  if (!n) return "Value N/A";
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(2)} Cr`;
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function fmtDate(dateStr) {
  try { return format(parseISO(dateStr), "d MMM yyyy"); }
  catch { return dateStr; }
}

const STATE_EMOJI = { Delhi: "🏛️", Maharashtra: "🏙️", "Madhya Pradesh": "🌿", "Uttar Pradesh": "🎪",
  Rajasthan: "🏜️", Gujarat: "💎", Karnataka: "🌺", "Tamil Nadu": "🏛️", "West Bengal": "🐯" };

export default function TenderCard({ tender, onView, isBookmarked, onBookmark }) {
  const portal = portalBadge(tender.portal_source);
  const deadline = deadlineInfo(tender.bid_end_date);
  const emoji = STATE_EMOJI[tender.state] || "📍";

  return (
    <motion.div variants={cardVariants} className="card group relative p-4">
      {/* Top row */}
      <div className="mb-2.5 flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${portal.cls}`}>
            {portal.label}
          </span>
          {tender.state && (
            <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-400">
              {emoji} {tender.state}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onBookmark(tender); }}
          className="shrink-0 text-slate-500 transition hover:text-accent"
          title={isBookmarked ? "Remove bookmark" : "Bookmark"}
        >
          {isBookmarked
            ? <BookmarkCheck className="h-4 w-4 text-accent" />
            : <Bookmark className="h-4 w-4" />}
        </button>
      </div>

      {/* Title */}
      <h3
        className="line-clamp-2 cursor-pointer text-sm font-semibold leading-snug text-slate-100 transition group-hover:text-accent"
        onClick={() => onView(tender)}
        title={tender.title}
      >
        {tender.title}
      </h3>

      {/* Organisation */}
      {tender.organisation && (
        <p className="mt-1 truncate text-xs text-slate-500">{tender.organisation}</p>
      )}

      {/* Deadline */}
      {deadline && (
        <p className={`mt-2 text-xs font-medium ${deadline.cls}`}>
          📅 {deadline.label}
          {tender.bid_end_date && ` · ${fmtDate(tender.bid_end_date)}`}
        </p>
      )}

      {/* Value + Ref */}
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300">{fmtValue(tender.value_inr)}</span>
        <span className="font-mono text-xs text-slate-600" title="Reference Number">
          {tender.ref_number?.slice(0, 20)}
        </span>
      </div>

      {/* Actions */}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => onView(tender)}
          className="btn-outline flex-1 rounded-lg py-1.5 text-xs font-semibold"
        >
          View Details
        </button>
        {tender.portal_url && (
          <a
            href={tender.portal_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 rounded-lg border border-accent/30 bg-accent/10 px-3 py-1.5 text-xs font-semibold text-accent transition hover:bg-accent/20"
            onClick={(e) => e.stopPropagation()}
          >
            Apply
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </motion.div>
  );
}
