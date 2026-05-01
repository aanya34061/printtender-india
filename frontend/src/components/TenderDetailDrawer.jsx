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
    add("📋 Link copied to clipboard", "success");
  }

  return (
    <AnimatePresence>
      {tenderId && (
        <>
          {/* Overlay */}
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          />

          {/* Drawer */}
          <motion.aside
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col bg-surface shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
              <h2 className="font-bold text-slate-100">Tender Details</h2>
              <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-200">
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {isLoading ? (
                <div className="space-y-3">
                  {[1,2,3,4].map(i => <div key={i} className="h-6 rounded shimmer" />)}
                </div>
              ) : tender ? (
                <>
                  {/* Badges */}
                  <div className="mb-3 flex flex-wrap gap-2">
                    {tender.portal_source && (
                      <span className="rounded-full bg-blue-500/20 px-2.5 py-0.5 text-xs font-semibold text-blue-400">
                        {tender.portal_source}
                      </span>
                    )}
                    {tender.state && (
                      <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-400">
                        {tender.state}
                      </span>
                    )}
                    {tender.category && (
                      <span className="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs text-accent">
                        {tender.category}
                      </span>
                    )}
                  </div>

                  <h3 className="text-base font-bold leading-snug text-slate-100">{tender.title}</h3>
                  {tender.organisation && (
                    <p className="mt-1 text-sm text-slate-500">{tender.organisation}</p>
                  )}

                  {/* Key details */}
                  <dl className="mt-4 grid grid-cols-2 gap-3 rounded-xl border border-white/5 bg-bg/60 p-4 text-sm">
                    <Detail label="Ref No" value={<span className="font-mono text-xs">{tender.ref_number}</span>} />
                    <Detail label="Deadline" value={tender.bid_end_date ? format(parseISO(tender.bid_end_date), "d MMM yyyy") : "—"} />
                    <Detail label="Value" value={tender.value_inr && Number(tender.value_inr) ? `₹${Number(tender.value_inr).toLocaleString("en-IN")}` : "—"} />
                    <Detail label="EMD" value={tender.emd_amount && Number(tender.emd_amount) ? `₹${Number(tender.emd_amount).toLocaleString("en-IN")}` : "—"} />
                    <Detail label="Fetched" value={tender.fetched_at ? format(parseISO(tender.fetched_at), "d MMM, HH:mm") : "—"} />
                  </dl>

                  {/* Apply steps */}
                  {tender.apply_steps?.length > 0 && (
                    <div className="mt-5">
                      <h4 className="mb-2.5 text-sm font-semibold text-slate-300">How to Apply</h4>
                      <ol className="space-y-2">
                        {tender.apply_steps.map((step, i) => (
                          <li
                            key={i}
                            onClick={() => setChecked(p => ({ ...p, [i]: !p[i] }))}
                            className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-white/5 p-2.5 text-sm transition hover:bg-white/5"
                          >
                            {checked[i]
                              ? <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                              : <Square className="mt-0.5 h-4 w-4 shrink-0 text-slate-600" />}
                            <span className={checked[i] ? "text-slate-500 line-through" : "text-slate-300"}>
                              {i + 1}. {step}
                            </span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500">Tender not found.</p>
              )}
            </div>

            {/* Footer actions */}
            {tender && (
              <div className="border-t border-white/5 p-4 space-y-2">
                {tender.portal_url && (
                  <a
                    href={tender.portal_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-3 font-semibold text-white transition hover:bg-accent/90"
                  >
                    View Official Tender →
                    <ExternalLink className="h-4 w-4" />
                  </a>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onSetAlert((tender.keywords ?? [])[0] || "printing")}
                    className="btn-outline flex-1 rounded-xl py-2 text-sm"
                  >
                    🔔 Set Alert for this keyword
                  </button>
                  <button
                    type="button"
                    onClick={copyLink}
                    className="btn-outline rounded-xl px-3 py-2"
                  >
                    <Copy className="h-4 w-4" />
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
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-semibold text-slate-200">{value ?? "—"}</dd>
    </div>
  );
}
