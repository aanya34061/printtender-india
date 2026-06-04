import { useQuery } from "@tanstack/react-query";
import { CheckSquare, Copy, ExternalLink, Square, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchJSON } from "../lib/api.js";
import { formatShortDate, formatShortDateTime } from "../lib/date.js";
import { useToastStore } from "../store/toastStore.js";

function portalBadgeClass(src) {
  if (!src) return "badge badge-other";
  if (src === "CPPP" || src === "etenders.gov.in") return "badge badge-cppp";
  if (src === "GeM" || src === "gem.gov.in") return "badge badge-gem";
  if (isBankPortal(src)) return "badge badge-bank";
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
  ].includes(src)) return "badge badge-mp";
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

function useDetail(id) {
  return useQuery({
    queryKey: ["tender", id],
    queryFn: () => fetchJSON(`/api/tenders/${id}`),
    enabled: !!id,
    staleTime: 1000 * 60 * 5,
  });
}

function isPortalSearchFlowTender(portalSource, linkType) {
  return (
    linkType === "search" &&
    [
      "CPPP",
      "etenders.gov.in",
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

function formatMoney(value) {
  const amount = Number(value || 0);
  if (!amount || amount < 1_000) return null;
  const exact = `₹${amount.toLocaleString("en-IN")}`;
  const formatUnit = (unitAmount, unit) => {
    const rounded = unitAmount
      .toFixed(unitAmount >= 10 ? 1 : 2)
      .replace(/\.0+$/, "")
      .replace(/(\.\d)0$/, "$1");
    return `₹${rounded} ${unit} (${exact})`;
  };
  if (amount >= 10_000_000) return formatUnit(amount / 10_000_000, "Crore");
  if (amount >= 100_000) return formatUnit(amount / 100_000, "Lakh");
  if (amount >= 1_000) return formatUnit(amount / 1_000, "Thousand");
  return `${exact} Rupees`;
}

function visibleMoney(value, fallback = "Not disclosed") {
  return formatMoney(value) || fallback;
}

function buildTenderSummary(tender, portalSource) {
  if (!tender) return [];
  const points = [];
  const deadline = formatShortDate(tender.bid_end_date);
  const value = formatMoney(tender.value_inr);
  const emd = formatMoney(tender.emd_amount);
  const keywords = (tender.keywords || []).slice(0, 4).join(", ");

  if (tender.organisation) {
    points.push(`Issued by ${tender.organisation}${tender.state ? ` for ${tender.state}` : ""}.`);
  }
  if (portalSource) {
    points.push(`Published on ${portalSource}${tender.ref_number ? ` under ref ${tender.ref_number}` : ""}.`);
  }
  if (deadline) {
    points.push(`Bid submission deadline is ${deadline}.`);
  }
  points.push(
    value
      ? `Estimated tender value is ${value}.`
      : "Tender value is not disclosed by the source portal."
  );
  if (emd) {
    points.push(`EMD amount is ${emd}.`);
  }
  if (keywords) {
    points.push(`Matched printing categories: ${keywords}.`);
  }
  if (tender.link_type === "search") {
    points.push("Direct document link is unavailable; open the portal and search by reference number.");
  } else if (tender.portal_url) {
    points.push("Official tender link is available for viewing or applying.");
  }

  return points;
}

export default function TenderDetailDrawer({ tenderId, onClose, onSetAlert }) {
  const { data: tender, isLoading } = useDetail(tenderId);
  const [checked, setChecked] = useState({});
  const add = useToastStore((s) => s.add);

  function inferPortalSource(url) {
    if (!url) return null;
    try {
      const u = new URL(url);
      const host = u.hostname;
      if (host.includes("eproc.mp.gov.in")) return "eproc.mp.gov.in";
      if (host.includes("mptenders.gov.in")) return "MP Tenders";
      if (host.includes("timesofindia") || host.includes("indiatimes")) return "TOI Tenders";
      if (host.includes("etenders.gov.in")) return "etenders.gov.in";
      if (host.includes("eprocure") || host.includes("eprocure.gov.in")) return "CPPP";
      if (host.includes("gem") || host.includes("gecmart") || host.includes("gems") || host.includes("gem.gov.in")) return "gem.gov.in";
      if (host.includes("tenderdekho")) return "TenderDekho";
      return host;
    } catch {
      return null;
    }
  }
  const portalSource = tender?.portal_source || inferPortalSource(tender?.portal_url);
  const usesPortalSearchFlow = isPortalSearchFlowTender(portalSource, tender?.link_type);
  const summaryPoints = buildTenderSummary(tender, portalSource);

  useEffect(() => {
    setChecked({});
  }, [tenderId]);

  useEffect(() => {
    const fn = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [onClose]);

  function copyLink() {
    navigator.clipboard.writeText(tender?.portal_url || window.location.href);
    add("📋 Link copied to clipboard", "info");
  }

  function copyRef() {
    navigator.clipboard.writeText(tender?.ref_number || "");
    add("📋 Ref number copied — paste in portal search", "info");
  }

  async function handleApply() {
    if (!tender?.portal_url) return;
    const destination = tender.portal_url;
    if (usesPortalSearchFlow && tender.ref_number) {
      try {
        await navigator.clipboard.writeText(tender.ref_number);
        add("Tender page opened and ref copied", "info");
      } catch {
        add("Tender page opened", "info");
      }
    } else if (tender.link_type === "search") {
      add("🔍 No direct link — opening portal search", "info");
    } else if (tender.link_type === "deep" && (portalSource === "GeM" || portalSource === "gem.gov.in")) {
      add("Opening GeM — click the bid in search results to view full details", "info");
    }
    window.open(destination, "_blank");
  }

  return (
    tenderId && (
      <>
        {/* Backdrop */}
        <div
          onClick={onClose}
          className="fixed inset-0 z-40"
          style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)" }}
        />

        {/* Drawer */}
        <aside
          className="fixed right-0 top-0 z-50 flex h-dvh w-full max-w-lg flex-col"
          style={{ background: "var(--surface)", borderLeft: "1px solid rgba(255,255,255,0.08)" }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between gap-3 px-4 py-4 sm:px-5"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
          >
            <h2 className="font-bold text-slate-100">Tender Details</h2>
            <button
              type="button"
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg transition"
              style={{ color: "var(--muted)" }}
              onMouseEnter={(e) => e.currentTarget.style.color = "var(--text)"}
              onMouseLeave={(e) => e.currentTarget.style.color = "var(--muted)"}
            >
              <X className="h-5 w-5" />
            </button>
          </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-5">
              {isLoading ? (
                <div className="space-y-3">
                  {[1,2,3,4,5].map(i => (
                    <div key={i} className="skeleton h-5 rounded" style={{ width: `${60 + i * 8}%` }} />
                  ))}
                </div>
              ) : tender ? (
                <>
                  {/* Badges */}
                  <div className="mb-4 flex flex-wrap gap-2">
                    {portalSource && (
                      <span className={portalBadgeClass(portalSource)} title={portalSource}>
                        {portalSource}
                      </span>
                    )}
                    {tender.state && (
                      <span className="badge badge-other">{tender.state}</span>
                    )}
                    {tender.category && (
                      <span
                        className="badge"
                        style={{ background: "rgba(249,115,22,0.1)", color: "var(--accent)", border: "1px solid rgba(249,115,22,0.3)" }}
                      >
                        {tender.category}
                      </span>
                    )}
                  </div>

                  <h3 className="mb-1 text-base font-bold leading-snug text-slate-100">
                    {tender.title}
                  </h3>
                  {tender.organisation && (
                    <p className="mb-4 text-sm" style={{ color: "var(--muted)" }}>
                      {tender.organisation}
                    </p>
                  )}

                  {summaryPoints.length > 0 && (
                    <div
                      className="mb-5 rounded-xl p-4"
                      style={{ background: "rgba(249,115,22,0.08)", border: "1px solid rgba(249,115,22,0.18)" }}
                    >
                      <h4 className="mb-3 text-sm font-semibold text-slate-200">Tender Summary</h4>
                      <ul className="space-y-2 text-sm leading-relaxed" style={{ color: "var(--text)" }}>
                        {summaryPoints.map((point) => (
                          <li key={point} className="flex gap-2">
                            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--accent)" }} />
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Details grid */}
                  <dl
                    className="mb-5 grid grid-cols-1 gap-4 rounded-xl p-4 text-sm min-[420px]:grid-cols-2"
                    style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.06)" }}
                  >
                    <Detail label="Ref No" value={<span className="font-mono text-xs">{tender.ref_number || "—"}</span>} />
                    <Detail label="Deadline" value={formatShortDate(tender.bid_end_date) || "—"} />
                    <Detail label="Value" value={visibleMoney(tender.value_inr)} muted={!Number(tender.value_inr || 0)} />
                    <Detail label="EMD" value={visibleMoney(tender.emd_amount)} muted={!Number(tender.emd_amount || 0)} />
                    <Detail label="Fetched" value={formatShortDateTime(tender.fetched_at) || "—"} />
                  </dl>

                  {/* Apply steps checklist */}
                  {tender.apply_steps?.length > 0 && (
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-slate-300">How to Apply</h4>
                      <ol className="space-y-2">
                        {tender.apply_steps.map((step, i) => (
                          <li
                            key={i}
                            onClick={() => setChecked((p) => ({ ...p, [i]: !p[i] }))}
                            className="flex cursor-pointer items-start gap-3 rounded-lg p-3 text-sm transition"
                            style={{ border: "1px solid rgba(255,255,255,0.06)", background: "rgba(0,0,0,0.2)" }}
                            onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.04)"}
                            onMouseLeave={(e) => e.currentTarget.style.background = "rgba(0,0,0,0.2)"}
                          >
                            {checked[i]
                              ? <CheckSquare className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--green)" }} />
                              : <Square className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--muted)" }} />}
                            <span style={{ color: checked[i] ? "var(--muted)" : "var(--text)", textDecoration: checked[i] ? "line-through" : "none" }}>
                              {i + 1}. {step}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </>
              ) : (
                <p style={{ color: "var(--muted)" }}>Tender not found.</p>
              )}
            </div>

            {/* Footer */}
            {tender && (
              <div
                className="space-y-2 p-3 sm:p-4"
                style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
              >
                {tender.portal_url && (
                  <button
                    type="button"
                    onClick={handleApply}
                    className="btn-primary w-full justify-center py-3"
                    style={
                      tender.link_type === "search" && !usesPortalSearchFlow
                        ? { opacity: 0.75, border: "1.5px solid var(--muted)", background: "transparent", color: "var(--muted)" }
                        : {}
                    }
                    title={tender.link_type === "newspaper" ? "This notice was published in a newspaper and may require contacting the organisation directly to apply." : undefined}
                  >
                    {usesPortalSearchFlow
                      ? "Open Tender Page"
                      : tender.link_type === "search"
                      ? "🔍 Search by Ref No"
                      : tender.link_type === "newspaper"
                      ? "Read Notice"
                      : tender.link_type === "deep" && (portalSource === "GeM" || portalSource === "gem.gov.in")
                      ? "🔍 Search on GeM (click result to open)"
                      : "View Official Tender"}
                    <ExternalLink className="h-4 w-4" />
                  </button>
                )}
                <div className="grid grid-cols-2 gap-2 sm:flex">
                  <button
                    type="button"
                    onClick={() => onSetAlert((tender.keywords ?? [])[0] || "printing")}
                    className="btn-ghost col-span-2 min-w-0 justify-center py-2 text-sm sm:col-span-1 sm:flex-1"
                  >
                    🔔 Set Alert for this keyword
                  </button>
                  <button
                    type="button"
                    onClick={copyRef}
                    className="btn-ghost px-3 py-2"
                    title="Copy ref number"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={copyLink}
                    className="btn-ghost px-3 py-2"
                    title="Copy portal link"
                  >
                    <Copy className="h-3 w-3" />🔗
                  </button>
                </div>
              </div>
            )}
        </aside>
      </>
    )
  );
}

function Detail({ label, value, muted = false }) {
  return (
    <div>
      <dt className="mb-0.5 text-xs" style={{ color: "var(--muted)" }}>{label}</dt>
      <dd className="font-semibold" style={{ color: muted ? "#94a3b8" : "var(--text)" }}>
        {value ?? "Not disclosed"}
      </dd>
    </div>
  );
}
