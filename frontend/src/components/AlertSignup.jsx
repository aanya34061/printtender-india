import axios from "axios";
import { Bell, Check, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const KEYWORD_SUGGESTIONS = [
  "printing", "offset printing", "digital printing", "stationery",
  "textbook printing", "security printing", "packaging", "toner cartridge",
];

export default function AlertSignup({ onClose, prefillKeyword }) {
  const overlayRef = useRef(null);
  const [email, setEmail] = useState("");
  const [keywords, setKeywords] = useState(
    prefillKeyword ? [prefillKeyword] : ["printing"]
  );
  const [stateFilter, setStateFilter] = useState("");
  const [frequency, setFrequency] = useState("daily");
  const [status, setStatus] = useState("idle"); // idle | saving | success | error
  const [emailError, setEmailError] = useState("");

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

  function toggleKeyword(kw) {
    setKeywords((prev) =>
      prev.includes(kw) ? prev.filter((k) => k !== kw) : [...prev, kw]
    );
  }

  function validateEmail(val) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
  }

  async function submit(e) {
    e.preventDefault();
    if (!validateEmail(email)) {
      setEmailError("Please enter a valid email address.");
      return;
    }
    if (keywords.length === 0) {
      return;
    }
    setEmailError("");
    setStatus("saving");
    try {
      await axios.post(`${BASE}/alerts/subscribe`, {
        email,
        keywords,
        states: stateFilter ? [stateFilter] : [],
        frequency,
      });
      setStatus("success");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/60 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-navy/10 px-6 py-4">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-crimson" />
            <h2 className="font-bold text-navy">Get Tender Alerts</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-navy/50 hover:bg-paper hover:text-navy"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {status === "success" ? (
          <div className="flex flex-col items-center gap-3 p-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal/10 text-teal">
              <Check className="h-6 w-6" />
            </div>
            <p className="font-bold text-navy">You&apos;re subscribed!</p>
            <p className="text-sm text-navy/60">
              You&apos;ll receive {frequency} alerts for: {keywords.join(", ")}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-2 rounded-lg bg-navy px-4 py-2 text-sm font-semibold text-white"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4 p-6">
            {/* Email */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-navy/50 mb-1">
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); setEmailError(""); }}
                placeholder="press@yourcompany.com"
                className={`h-10 w-full rounded-lg border px-3 text-sm text-navy outline-none transition focus:ring-2 ${
                  emailError
                    ? "border-crimson focus:border-crimson focus:ring-crimson/10"
                    : "border-navy/20 focus:border-crimson focus:ring-crimson/10"
                }`}
              />
              {emailError && <p className="mt-1 text-xs text-crimson">{emailError}</p>}
            </div>

            {/* Keywords */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-navy/50 mb-2">
                Keywords {keywords.length === 0 && <span className="text-crimson">(select at least 1)</span>}
              </label>
              <div className="flex flex-wrap gap-2">
                {KEYWORD_SUGGESTIONS.map((kw) => (
                  <button
                    key={kw}
                    type="button"
                    onClick={() => toggleKeyword(kw)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      keywords.includes(kw)
                        ? "bg-crimson text-white"
                        : "border border-navy/20 text-navy hover:border-crimson hover:text-crimson"
                    }`}
                  >
                    {kw}
                  </button>
                ))}
              </div>
            </div>

            {/* Frequency */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-navy/50 mb-2">
                Frequency
              </label>
              <div className="flex rounded-lg border border-navy/20 p-1">
                {["daily", "weekly"].map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFrequency(f)}
                    className={`flex-1 rounded-md py-1.5 text-sm font-semibold capitalize transition ${
                      frequency === f ? "bg-navy text-white" : "text-navy/60 hover:text-navy"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {status === "error" && (
              <p className="text-xs text-crimson">
                Something went wrong. Please try again.
              </p>
            )}

            <button
              type="submit"
              disabled={status === "saving" || keywords.length === 0}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-crimson font-semibold text-white transition hover:bg-crimson/90 disabled:opacity-60"
            >
              <Bell className="h-4 w-4" />
              {status === "saving" ? "Subscribing…" : "Subscribe for Free"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
