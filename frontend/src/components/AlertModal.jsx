import { Bell, Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchJSON } from "../lib/api.js";
import { useToastStore } from "../store/toastStore.js";

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
  const [keywords, setKeywords] = useState([prefillKeyword || "calendars"]);
  const [frequency, setFrequency] = useState("daily");
  const [status, setStatus] = useState("idle");
  const [emailErr, setEmailErr] = useState("");
  const [submitErr, setSubmitErr] = useState("");
  const add = useToastStore((s) => s.add);

  useEffect(() => {
    const keyword = prefillKeyword?.trim();
    if (keyword) setKeywords([keyword]);
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
    setSubmitErr("");
    setStatus("saving");
    try {
      await fetchJSON("/api/alerts/subscribe", {
        method: "POST",
        json: {
          email,
          keywords,
          states: [],
          frequency,
        },
      });
      setStatus("success");
      add("Check your email for a test tender mail and confirmation link.", "success");
    } catch (err) {
      setStatus("error");
      setSubmitErr(err.message || "Email delivery failed. Please try again.");
    }
  }

  return (
    open && (
      <>
        {/* Backdrop */}
        <div
          onClick={onClose}
          className="fixed inset-0 z-50"
          style={{ background: "rgba(0,0,0,0.65)", backdropFilter: "blur(4px)" }}
        />

        {/* Modal */}
        <div
          className="fixed inset-x-3 top-1/2 z-50 max-h-[calc(100dvh-2rem)] -translate-y-1/2 overflow-y-auto rounded-2xl shadow-card sm:inset-x-auto sm:left-1/2 sm:w-full sm:max-w-[480px] sm:-translate-x-1/2"
          style={{ background: "var(--surface)", border: "1px solid rgba(255,255,255,0.08)" }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between gap-3 px-4 py-4 sm:px-6"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
          >
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5" style={{ color: "var(--accent)" }} />
              <h2 className="text-sm font-bold text-slate-100 sm:text-base">Subscribe to Tender Mails</h2>
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
                <p className="text-lg font-bold text-slate-100">Subscription created</p>
                <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                  Check your inbox for a test tender mail and confirmation link. After confirmation, you&apos;ll receive{" "}
                  <span style={{ color: "var(--accent)" }}>{frequency}</span>{" "}
                  tender mails for: <span style={{ color: "var(--accent)" }}>{keywords.join(", ")}</span>
                </p>
              </div>
              <button type="button" onClick={onClose} className="btn-primary px-8 py-2">
                Done
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5 p-4 sm:p-6">
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
                    Tender Keywords
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
                    {["instant", "daily", "weekly"].map((f) => (
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
                        {f === "instant" ? "Instant" : f === "daily" ? "Daily" : "Weekly"}
                      </button>
                    ))}
                  </div>
                </div>

                {status === "error" && (
                  <p className="rounded-lg px-3 py-2 text-xs" style={{ background: "rgba(239,68,68,0.1)", color: "var(--red)" }}>
                    {submitErr || "Something went wrong. Please try again."}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={status === "saving" || keywords.length === 0}
                  className="btn-primary w-full justify-center py-3 text-sm"
                >
                  <Bell className="h-4 w-4" />
                  {status === "saving" ? "Subscribing..." : "Subscribe for Mail Alerts"}
                </button>
              </form>
          )}
        </div>
      </>
    )
  );
}
