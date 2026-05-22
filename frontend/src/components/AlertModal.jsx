import axios from "axios";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToastStore } from "../store/toastStore.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const KEYWORDS = [
  "calendars", "diary", "sticker", "registers",
  "books", "forms", "papers", "note books",
  "brochures", "flyers", "visiting cards", "certificates",
  "receipt books", "prospectus", "catalogues", "pass books",
  "duplex box", "cards", "answer books", "exercise books",
  "tags", "posters", "banners", "labels",
  "desk pads", "envelopes", "marks sheet", "stationary",
  "note sheets", "files", "pamphlets", "annual reports",
  "souvenir",
];

export default function AlertModal({ open, onClose, prefillKeyword }) {
  const [email, setEmail] = useState("");
  const [keywords, setKeywords] = useState([prefillKeyword ?? "calendars"]);
  const [frequency, setFrequency] = useState("daily");
  const [status, setStatus] = useState("idle");
  const [emailErr, setEmailErr] = useState("");
  const add = useToastStore((s) => s.add);

  useEffect(() => {
    if (prefillKeyword) setKeywords([prefillKeyword]);
  }, [prefillKeyword]);

  useEffect(() => {
    const fn = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", fn);
    return () => document.removeEventListener("keydown", fn);
  }, [onClose]);

  function toggleKw(kw) {
    setKeywords((p) => p.includes(kw) ? p.filter((k) => k !== kw) : [...p, kw]);
  }

  async function submit(e) {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setEmailErr("Enter a valid email address.");
      return;
    }
    if (keywords.length === 0) return;
    setEmailErr("");
    setStatus("saving");
    try {
      await axios.post(`${BASE}/api/alerts`, { email, keyword: keywords[0], frequency });
      setStatus("success");
      add("🔔 Alert set! Check your email to confirm.", "success");
    } catch {
      setStatus("error");
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50"
            style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)" }}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="fixed inset-x-4 top-1/2 z-50 -translate-y-1/2 rounded-2xl shadow-card sm:inset-x-auto sm:left-1/2 sm:w-full sm:max-w-[480px] sm:-translate-x-1/2"
            style={{ background: "var(--surface)", border: "1px solid rgba(255,255,255,0.08)" }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-6 py-4"
              style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
            >
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5" style={{ color: "var(--accent)" }} />
                <h2 className="font-bold text-slate-100">Set Tender Alert</h2>
              </div>
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

            {/* Success state */}
            {status === "success" ? (
              <div className="flex flex-col items-center gap-4 p-8 text-center">
                <div
                  className="flex h-16 w-16 items-center justify-center rounded-full"
                  style={{ background: "rgba(34,197,94,0.15)" }}
                >
                  <Check className="h-8 w-8" style={{ color: "var(--green)" }} />
                </div>
                <div>
                  <p className="text-lg font-bold text-slate-100">You&apos;re subscribed!</p>
                  <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                    Check your inbox to confirm. You&apos;ll receive{" "}
                    <span style={{ color: "var(--accent)" }}>{frequency}</span>{" "}
                    alerts for: <span style={{ color: "var(--accent)" }}>{keywords.join(", ")}</span>
                  </p>
                </div>
                <button type="button" onClick={onClose} className="btn-primary px-8 py-2">
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-5 p-6">
                {/* Email */}
                <div>
                  <label className="chip-group-label mb-2 block">Email Address</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setEmailErr(""); }}
                    placeholder="you@company.com"
                    className={`form-input ${emailErr ? "error" : ""}`}
                  />
                  {emailErr && (
                    <p className="mt-1.5 text-xs" style={{ color: "var(--red)" }}>{emailErr}</p>
                  )}
                </div>

                {/* Keywords */}
                <div>
                  <label className="chip-group-label mb-2 block">
                    Keywords
                    {keywords.length === 0 && (
                      <span className="ml-1" style={{ color: "var(--red)" }}>— select at least 1</span>
                    )}
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {KEYWORDS.map((kw) => (
                      <button
                        key={kw}
                        type="button"
                        onClick={() => toggleKw(kw)}
                        className={`chip ${keywords.includes(kw) ? "chip-active" : ""}`}
                      >
                        {kw}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Frequency */}
                <div>
                  <label className="chip-group-label mb-2 block">Notification Frequency</label>
                  <div
                    className="flex rounded-xl p-1"
                    style={{ background: "var(--bg)", border: "1px solid rgba(255,255,255,0.08)" }}
                  >
                    {["daily", "instant"].map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setFrequency(f)}
                        className="flex-1 rounded-lg py-2 text-sm font-semibold capitalize transition"
                        style={frequency === f
                          ? { background: "var(--accent)", color: "white" }
                          : { color: "var(--muted)" }
                        }
                      >
                        {f === "daily" ? "Daily Digest" : "Instant Alert"}
                      </button>
                    ))}
                  </div>
                </div>

                {status === "error" && (
                  <p className="rounded-lg px-3 py-2 text-xs" style={{ background: "rgba(239,68,68,0.1)", color: "var(--red)" }}>
                    Something went wrong. Please try again.
                  </p>
                )}

                <button
                  type="submit"
                  disabled={status === "saving" || keywords.length === 0}
                  className="btn-primary w-full justify-center py-3 text-sm"
                >
                  <Bell className="h-4 w-4" />
                  {status === "saving" ? "Subscribing…" : "Subscribe — It's Free"}
                </button>
              </form>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
