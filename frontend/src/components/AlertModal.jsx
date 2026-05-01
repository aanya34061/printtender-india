import axios from "axios";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useToastStore } from "../store/toastStore.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const KEYWORDS = [
  "printing","offset printing","digital printing","stationery","packaging",
  "security printing","textbook","calendar","toner","booklet",
];

export default function AlertModal({ open, onClose, prefillKeyword }) {
  const [email, setEmail] = useState("");
  const [keywords, setKeywords] = useState([prefillKeyword ?? "printing"]);
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
      await axios.post(`${BASE}/api/alerts`, {
        email,
        keyword: keywords[0],
        frequency,
      });
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
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="fixed inset-x-4 top-1/2 z-50 -translate-y-1/2 rounded-2xl bg-surface shadow-2xl sm:inset-x-auto sm:left-1/2 sm:w-full sm:max-w-md sm:-translate-x-1/2"
          >
            <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-accent" />
                <h2 className="font-bold text-slate-100">Set Tender Alert</h2>
              </div>
              <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-200">
                <X className="h-5 w-5" />
              </button>
            </div>

            {status === "success" ? (
              <div className="flex flex-col items-center gap-3 p-8 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-success/20">
                  <Check className="h-7 w-7 text-success" />
                </div>
                <p className="font-bold text-slate-100">You&apos;re subscribed!</p>
                <p className="text-sm text-slate-500">
                  Check your inbox to confirm. You&apos;ll receive {frequency} alerts for:{" "}
                  <span className="text-accent">{keywords.join(", ")}</span>
                </p>
                <button type="button" onClick={onClose} className="btn-accent mt-2 rounded-xl px-6 py-2">
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-4 p-5">
                {/* Email */}
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Email
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setEmailErr(""); }}
                    placeholder="you@company.com"
                    className={`input-field w-full px-3 py-2.5 ${emailErr ? "border-danger" : ""}`}
                  />
                  {emailErr && <p className="mt-1 text-xs text-danger">{emailErr}</p>}
                </div>

                {/* Keywords */}
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Keywords {keywords.length === 0 && <span className="text-danger">— select at least 1</span>}
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {KEYWORDS.map((kw) => (
                      <button
                        key={kw}
                        type="button"
                        onClick={() => toggleKw(kw)}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                          keywords.includes(kw)
                            ? "bg-accent text-white"
                            : "border border-white/10 text-slate-400 hover:border-accent/50 hover:text-accent"
                        }`}
                      >
                        {kw}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Frequency */}
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Frequency
                  </label>
                  <div className="flex rounded-xl border border-white/10 p-1">
                    {["daily", "instant"].map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setFrequency(f)}
                        className={`flex-1 rounded-lg py-1.5 text-sm font-semibold capitalize transition ${
                          frequency === f ? "bg-accent text-white" : "text-slate-500 hover:text-slate-200"
                        }`}
                      >
                        {f === "daily" ? "Daily Digest" : "Instant"}
                      </button>
                    ))}
                  </div>
                </div>

                {status === "error" && (
                  <p className="text-xs text-danger">Something went wrong. Please try again.</p>
                )}

                <button
                  type="submit"
                  disabled={status === "saving" || keywords.length === 0}
                  className="btn-accent flex w-full items-center justify-center gap-2 rounded-xl py-3 disabled:opacity-60"
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
