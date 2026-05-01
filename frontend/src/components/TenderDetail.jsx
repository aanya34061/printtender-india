import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { format, parseISO } from "date-fns";
import { CheckSquare, Copy, ExternalLink, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function useTenderDetail(id) {
  return useQuery({
    queryKey: ["tender", id],
    queryFn: async () => {
      const { data } = await axios.get(`${BASE}/tenders/${id}`);
      return data;
    },
    enabled: !!id,
    staleTime: 1000 * 60 * 5,
  });
}

export default function TenderDetail({ tenderId, onClose, onAlertKeyword }) {
  const overlayRef = useRef(null);
  const { data: tender, isLoading } = useTenderDetail(tenderId);
  const [checked, setChecked] = useState({});
  const [copied, setCopied] = useState(false);

  // close on Escape
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose();
  }

  function toggleCheck(i) {
    setChecked((prev) => ({ ...prev, [i]: !prev[i] }));
  }

  function copyLink() {
    navigator.clipboard.writeText(tender?.portal_url || window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!tenderId) return null;

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/60 p-4 backdrop-blur-sm"
    >
      <div className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-navy/10 bg-white px-6 py-4">
          <h2 className="text-base font-bold text-navy">Tender Details</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-navy/50 hover:bg-paper hover:text-navy"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="space-y-3 p-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-5 animate-pulse rounded bg-navy/10" />
            ))}
          </div>
        ) : tender ? (
          <div className="p-6">
            {/* Meta badges */}
            <div className="mb-3 flex flex-wrap gap-2">
              {tender.portal_source && (
                <span className="rounded-full bg-teal/10 px-2.5 py-0.5 text-xs font-semibold text-teal">
                  {tender.portal_source}
                </span>
              )}
              {tender.state && (
                <span className="rounded-full bg-navy px-2.5 py-0.5 text-xs font-semibold text-white">
                  {tender.state}
                </span>
              )}
              {tender.category && (
                <span className="rounded-full bg-paper px-2.5 py-0.5 text-xs font-semibold text-navy">
                  {tender.category}
                </span>
              )}
            </div>

            <h3 className="text-lg font-bold leading-tight text-navy">{tender.title}</h3>
            {tender.organisation && (
              <p className="mt-1 text-sm text-navy/60">{tender.organisation}</p>
            )}

            {/* Key details */}
            <dl className="mt-4 grid gap-2 rounded-xl border border-navy/10 bg-paper/50 p-4 text-sm sm:grid-cols-2">
              <Detail label="Ref Number" value={tender.ref_number} />
              <Detail
                label="Deadline"
                value={tender.bid_end_date ? format(parseISO(tender.bid_end_date), "dd MMM yyyy, HH:mm") : "—"}
              />
              <Detail
                label="Estimated Value"
                value={tender.value_inr ? `₹${Number(tender.value_inr).toLocaleString("en-IN")}` : "—"}
              />
              <Detail
                label="EMD Amount"
                value={tender.emd_amount && Number(tender.emd_amount) > 0
                  ? `₹${Number(tender.emd_amount).toLocaleString("en-IN")}`
                  : "—"}
              />
            </dl>

            {/* Apply steps */}
            {tender.apply_steps?.length > 0 && (
              <div className="mt-5">
                <h4 className="mb-2.5 text-sm font-bold text-navy">How to Apply</h4>
                <ol className="space-y-2">
                  {tender.apply_steps.map((step, i) => (
                    <li
                      key={i}
                      className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-navy/10 p-2.5 text-sm transition hover:bg-paper/60"
                      onClick={() => toggleCheck(i)}
                    >
                      {checked[i] ? (
                        <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-teal" />
                      ) : (
                        <Square className="mt-0.5 h-4 w-4 shrink-0 text-navy/30" />
                      )}
                      <span className={checked[i] ? "text-navy/40 line-through" : "text-navy"}>
                        {i + 1}. {step}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Actions */}
            <div className="mt-6 flex flex-wrap gap-3">
              {tender.portal_url && (
                <a
                  href={tender.portal_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-crimson px-4 py-3 font-semibold text-white transition hover:bg-crimson/90"
                >
                  Go to Official Portal
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
              <button
                type="button"
                onClick={() => onAlertKeyword((tender.keywords ?? [])[0] || tender.title)}
                className="flex items-center gap-2 rounded-xl border border-navy/20 px-4 py-3 text-sm font-semibold text-navy transition hover:border-navy hover:bg-navy hover:text-white"
              >
                Alert me for this keyword
              </button>
              <button
                type="button"
                onClick={copyLink}
                className="flex items-center gap-2 rounded-xl border border-navy/20 px-3 py-3 text-sm text-navy transition hover:bg-paper"
              >
                <Copy className="h-4 w-4" />
                {copied ? "Copied!" : "Copy link"}
              </button>
            </div>
          </div>
        ) : (
          <p className="p-6 text-sm text-navy/50">Tender not found.</p>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-navy/50">{label}</dt>
      <dd className="font-semibold text-navy">{value ?? "—"}</dd>
    </div>
  );
}
