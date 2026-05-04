import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { format, parseISO } from "date-fns";
import { AnimatePresence, motion } from "framer-motion";
import { CheckSquare, Copy, ExternalLink, Square, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToastStore } from "../store/toastStore.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function useDetail(id) {
  return useQuery({
    queryKey: ["tender", id],
    queryFn: async () => (await axios.get(`${BASE}/api/tenders/${id}`)).data,
    enabled: !!id,
    staleTime: 1000 * 60 * 5,
  });
}

export default function TenderDetailDrawer({ tenderId, onClose, onSetAlert }) {
  const { data: tender, isLoading } = useDetail(tenderId);
  const [checked, setChecked] = useState({});
  const add = useToastStore((s) => s.add);

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

  function handleApply() {
    if (!tender?.portal_url) return;
    if (tender.link_type === "search") {
      add("🔍 No direct link — opening portal search", "info");
    } else if (tender.link_type === "deep" && tender.portal_source === "GeM") {
      add("Opening GeM — click the bid in search results to view full details", "info");
    }
    window.open(tender.portal_url, "_blank", "noreferrer");
  }

  return (
    <AnimatePresence>
      {tenderId && (
        <>
          {/* Backdrop */}
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40"
            style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)" }}
          />

          {/* Drawer */}
          <motion.aside
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col"
            style={{ background: "var(--surface)", borderLeft: "1px solid rgba(255,255,255,0.08)" }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4"
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
            <div className="flex-1 overflow-y-auto px-5 py-4">
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
                    {tender.portal_source && (
                      <span className={`badge badge-${tender.portal_source === "CPPP" ? "cppp" : tender.portal_source === "GeM" ? "gem" : tender.portal_source?.startsWith("State-") ? "state" : "other"}`}>
                        {tender.portal_source}
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

                  {/* Details grid */}
                  <dl
                    className="mb-5 grid grid-cols-2 gap-4 rounded-xl p-4 text-sm"
                    style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.06)" }}
                  >
                    <Detail label="Ref No" value={<span className="font-mono text-xs">{tender.ref_number || "—"}</span>} />
                    <Detail label="Deadline" value={tender.bid_end_date ? format(parseISO(tender.bid_end_date), "d MMM yyyy") : "—"} />
                    <Detail label="Value" value={tender.value_inr && Number(tender.value_inr) ? `₹${Number(tender.value_inr).toLocaleString("en-IN")}` : "—"} />
                    <Detail label="EMD" value={tender.emd_amount && Number(tender.emd_amount) ? `₹${Number(tender.emd_amount).toLocaleString("en-IN")}` : "—"} />
                    <Detail label="Fetched" value={tender.fetched_at ? format(parseISO(tender.fetched_at), "d MMM, HH:mm") : "—"} />
                  </dl>

                  {/* Apply steps checklist */}
                  {tender.apply_steps?.length > 0 && (
                    <div>
                      <h4 className="mb-3 text-sm font-semibold text-slate-300">How to Apply</h4>
                      <ol className="space-y-2">
                        {tender.apply_steps.map((step, i) => (
                          <li
                            key={i}
                            onClick={() => setChecked(p => ({ ...p, [i]: !p[i] }))}
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
                className="space-y-2 p-4"
                style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
              >
                {tender.portal_url && (
                  <button
                    type="button"
                    onClick={handleApply}
                    className="btn-primary w-full justify-center py-3"
                    style={
                      tender.link_type === "search"
                        ? { opacity: 0.75, border: "1.5px solid var(--muted)", background: "transparent", color: "var(--muted)" }
                        : {}
                    }
                  >
                    {tender.link_type === "search"
                      ? "🔍 Search by Ref No"
                      : tender.link_type === "deep" && tender.portal_source === "GeM"
                      ? "🔍 Search on GeM (click result to open)"
                      : "View Official Tender"}
                    <ExternalLink className="h-4 w-4" />
                  </button>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onSetAlert((tender.keywords ?? [])[0] || "printing")}
                    className="btn-ghost flex-1 justify-center py-2 text-sm"
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
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="mb-0.5 text-xs" style={{ color: "var(--muted)" }}>{label}</dt>
      <dd className="font-semibold text-slate-200">{value ?? "—"}</dd>
    </div>
  );
}
