import { Bookmark, BookmarkCheck, ClipboardCopy, ExternalLink, Link, Search } from "lucide-react";
import { differenceInCalendarDays, formatShortDate } from "../lib/date.js";
import { useToastStore } from "../store/toastStore.js";

function portalBadgeClass(src) {
  if (!src) return "badge badge-other";
  if (src === "CPPP") return "badge badge-cppp";
  if (src === "GeM" || src === "gem.gov.in") return "badge badge-gem";
  if (isMpPortal(src)) return "badge badge-mp";
  if (isBankPortal(src)) return "badge badge-bank";
  if (src === "TenderTiger") return "badge badge-tendertiger";
  if (src === "TenderDekho") return "badge badge-tenderdekho";
  if (src === "BidAssist") return "badge badge-bidassist";
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
  ].includes(src)) return "badge badge-newspaper";
  return "badge badge-other";
}

function isBankPortal(src) {
  return [
    "PNB Tenders",
    "Canara Bank Tenders",
    "Central Bank of India Tenders",
    "Bank of India Tenders",
    "Indian Bank Tenders",
    "UCO Bank Tenders",
    "Indian Overseas Bank Tenders",
    "LIC Tenders",
  ].includes(src);
}

function isMpPortal(src) {
  return [
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
  ].includes(src);
}

function deadlineInfo(dateStr) {
  const days = differenceInCalendarDays(dateStr);
  if (days === null || days < 0) return null;
  if (days === 0) return { label: "⚠ Closes today — Urgent!", color: "var(--red)" };
  if (days <= 3) return { label: `⚠ Closes in ${days} days — Urgent!`, color: "var(--red)" };
  if (days <= 7) return { label: `⏰ Closes in ${days} days`, color: "var(--amber)" };
  return { label: `✓ Closes: ${formatShortDate(dateStr)}`, color: "var(--green)" };
}

function fmtValue(val) {
  const n = Number(val);
  if (!n || n < 1_000) return null;
  const exact = `₹${n.toLocaleString("en-IN")}`;
  const formatUnit = (amount, unit) => {
    const rounded = amount.toFixed(amount >= 10 ? 1 : 2).replace(/\.0+$/, "").replace(/(\.\d)0$/, "$1");
    return `₹${rounded} ${unit} (${exact})`;
  };
  if (n >= 10_000_000) return formatUnit(n / 10_000_000, "Crore");
  if (n >= 100_000) return formatUnit(n / 100_000, "Lakh");
  if (n >= 1_000) return formatUnit(n / 1_000, "Thousand");
  return `${exact} Rupees`;
}

const STATE_EMOJI = {
  Delhi: "🏛️", Maharashtra: "🏙️", "Madhya Pradesh": "🌿",
  "Uttar Pradesh": "🎪", Rajasthan: "🏜️", Gujarat: "💎",
  Karnataka: "🌺", "Tamil Nadu": "🏛️", "West Bengal": "🐯",
};

const LINK_STYLES = {
  direct: { border: "1.5px solid var(--accent)", background: "rgba(249,115,22,0.12)", color: "var(--accent)" },
  deep:   { border: "1.5px solid var(--accent)", background: "transparent", color: "var(--accent)" },
  search: { border: "1.5px solid var(--muted)",  background: "transparent", color: "var(--muted)", opacity: 0.75 },
};

function isPortalSearchFlowTender(portalSource, linkType) {
  return (
    linkType === "search" &&
    [
      "CPPP",
      "MP Tenders",
      "eproc.mp.gov.in",
      "Maharashtra Tenders",
      "State-MP",
      "State-UP",
      "State-MH",
      "State-RJ",
    ].includes(portalSource || "")
  );
}

function isOrangePortalCtaTender(portalSource) {
  return ["MP Tenders", "eproc.mp.gov.in", "Maharashtra Tenders", "State-MP", "State-MH"].includes(portalSource || "");
}

export default function TenderCard({ tender, onView, isBookmarked, onBookmark }) {
  function inferPortalSource(url) {
    if (!url) return null;
    try {
      const u = new URL(url);
      const host = u.hostname;
      if (host.includes("eproc.mp.gov.in")) return "eproc.mp.gov.in";
      if (host.includes("mptenders.gov.in")) return "MP Tenders";
      if (host.includes("timesofindia") || host.includes("indiatimes")) return "TOI Tenders";
      if (host.includes("etenders.gov.in")) return "CPPP";
      if (host.includes("eprocure") || host.includes("eprocure.gov.in")) return "CPPP";
      if (host.includes("gem") || host.includes("gecmart") || host.includes("gems") || host.includes("gem.gov.in")) return "gem.gov.in";
      if (host.includes("tenderdekho")) return "TenderDekho";
      return host;
    } catch {
      return null;
    }
  }
  const portalSource = tender.portal_source || inferPortalSource(tender.portal_url);
  const portal = portalSource || "Other";
  const deadline = deadlineInfo(tender.bid_end_date);
  const value = fmtValue(tender.value_inr);
  const emoji = STATE_EMOJI[tender.state] || "📍";
  const linkType = tender.link_type || "deep";
  const add = useToastStore((s) => s.add);
  const usesPortalSearchFlow = isPortalSearchFlowTender(portalSource, linkType);
  const usesOrangePortalCta = isOrangePortalCtaTender(portalSource);

  async function handleApply(e) {
    e.stopPropagation();
    const destination = tender.portal_open_url || tender.portal_url;
    if (!destination) return;
    if (usesPortalSearchFlow && tender.ref_number) {
      try {
        await navigator.clipboard.writeText(tender.ref_number);
        add("Official portal opened and ref copied", "info");
      } catch {
        add("Official portal opened", "info");
      }
    } else if (linkType === "search") {
      const confirmed = window.confirm(
        `No direct tender link was found for ref ${tender.ref_number || ""}. This will search by ref number instead.`
      );
      if (!confirmed) return;
    }
    window.open(destination, "_blank", "noopener,noreferrer");
  }

  async function copyRef(e) {
    e.stopPropagation();
    await navigator.clipboard.writeText(tender.ref_number || "");
    add("Ref number copied", "success");
  }

  return (
    <article className="tender-card flex min-w-0 flex-col p-4 transition-transform duration-200 hover:-translate-y-0.5 sm:p-5">
      {/* Top row: portal/state badges + bookmark */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={portalBadgeClass(portal)} title={portal}>
            {portal}
          </span>
          {tender.state && (
            <span className="badge badge-other">
              {emoji} {tender.state}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onBookmark(tender); }}
          className="shrink-0 transition"
          style={{ color: isBookmarked ? "var(--accent)" : "var(--muted)" }}
          title={isBookmarked ? "Remove bookmark" : "Bookmark this tender"}
        >
          {isBookmarked
            ? <BookmarkCheck className="h-4 w-4" />
            : <Bookmark className="h-4 w-4" />}
        </button>
      </div>

      {/* Title */}
      <h3
        className="mb-1 line-clamp-2 cursor-pointer text-[0.95rem] font-semibold leading-snug text-slate-100 transition"
        style={{ WebkitLineClamp: 2, display: "-webkit-box", WebkitBoxOrient: "vertical", overflow: "hidden" }}
        onClick={() => onView(tender)}
        title={tender.title}
        onMouseEnter={(e) => e.currentTarget.style.color = "var(--accent)"}
        onMouseLeave={(e) => e.currentTarget.style.color = ""}
      >
        {tender.title}
      </h3>

      {/* Organisation */}
      {tender.organisation && (
        <p className="mb-2 truncate text-xs" style={{ color: "var(--muted)" }}>
          {tender.organisation}
        </p>
      )}

      {/* Deadline */}
      {deadline && (
        <p className="mb-2 text-xs font-semibold" style={{ color: deadline.color }}>
          {deadline.label}
        </p>
      )}

      {/* Value + ref row */}
      <div className="mt-auto flex flex-col gap-1.5 pt-2 min-[420px]:flex-row min-[420px]:items-center min-[420px]:justify-between">
        {value ? (
          <span
            className="text-sm font-bold font-mono"
            style={{ color: "var(--text)" }}
          >
            {value}
          </span>
        ) : (
          <span className="text-xs font-semibold" style={{ color: "#94a3b8" }}>Value not disclosed</span>
        )}
        <span
          className="truncate text-xs font-mono"
          style={{ color: "var(--muted)", maxWidth: "100%" }}
          title={tender.ref_number}
        >
          {tender.ref_number?.slice(0, 18)}
        </span>
      </div>

      {/* CTA row */}
      <div className="mt-3 grid grid-cols-[1fr_auto] gap-2 min-[430px]:flex">
        <button
          type="button"
          onClick={() => onView(tender)}
          className="btn-ghost min-w-0 justify-center py-1.5 text-xs min-[430px]:flex-1"
        >
          View Details
        </button>
        <button
          type="button"
          onClick={copyRef}
          className="flex items-center justify-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition"
          style={{ border: "1px solid rgba(255,255,255,0.12)", color: "var(--muted)" }}
          title="Copy ref number to paste in portal search"
        >
          <ClipboardCopy className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={handleApply}
          className="col-span-2 flex items-center justify-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition hover:opacity-90 min-[430px]:col-span-1"
          style={
            usesOrangePortalCta
              ? LINK_STYLES.direct
              : (LINK_STYLES[linkType] || LINK_STYLES.deep)
          }
          title={
            linkType === "newspaper" ? "This notice was published in a newspaper and may require contacting the organisation directly to apply." :
            usesPortalSearchFlow ? "Open official portal search and copy ref number" :
            linkType === "direct" ? `Open on ${portal}` :
            linkType === "deep"   ? `Deep link to ${portal}` :
            "Exact link unavailable — will search by ref number"
          }
        >
          {linkType === "search" ? <Search className="h-3 w-3" /> : linkType === "deep" ? <Link className="h-3 w-3" /> : <ExternalLink className="h-3 w-3" />}
          {linkType === "newspaper"
            ? "Read Notice"
            : usesPortalSearchFlow
            ? "View and Apply"
            : "View and Apply"}
        </button>
      </div>
    </article>
  );
}
