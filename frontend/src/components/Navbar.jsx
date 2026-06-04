import { Loader2, Printer, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useStats } from "../hooks/useStats.js";
import { useTriggerFetch } from "../hooks/useTriggerFetch.js";
import { formatRelativeStrict } from "../lib/date.js";

export default function Navbar({ onAlertOpen }) {
  const [statsEnabled, setStatsEnabled] = useState(false);
  const { data: stats } = useStats({ enabled: statsEnabled });
  const trigger = useTriggerFetch();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  useEffect(() => {
    const schedule = window.requestIdleCallback || ((fn) => window.setTimeout(fn, 1200));
    const cancel = window.cancelIdleCallback || window.clearTimeout;
    const id = schedule(() => setStatsEnabled(true));
    return () => cancel(id);
  }, []);

  const lastSynced = formatRelativeStrict(stats?.last_fetch);

  return (
    <nav
      style={{
        background: scrolled ? "rgba(26,31,53,0.96)" : "#1a1f35",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        backdropFilter: scrolled ? "blur(16px)" : "none",
        WebkitBackdropFilter: scrolled ? "blur(16px)" : "none",
      }}
      className="sticky top-0 z-[100] transition-all duration-200"
    >
      <div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-10">

        {/* Logo */}
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
            style={{ background: "rgba(249,115,22,0.15)" }}
          >
            <Printer className="h-4.5 w-4.5" style={{ color: "var(--accent)" }} />
          </div>
          <span className="min-w-0 text-base font-bold tracking-tight sm:text-lg">
            <span className="text-slate-100">Print</span>
            <span style={{ color: "var(--accent)" }}>Tender</span>
            <span className="hidden xs:inline" style={{ color: "var(--accent)" }}> India</span>
          </span>
        </div>

        {/* Live sync badge — hidden on xs */}
        {lastSynced && (
          <div className="hidden items-center gap-2 text-xs sm:flex" style={{ color: "var(--muted)" }}>
            <span
              className="pulse-dot h-2 w-2 rounded-full"
              style={{ background: "var(--green)" }}
            />
            Live · synced {lastSynced}
          </div>
        )}

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
            className="btn-ghost flex items-center gap-1.5 text-sm"
          >
            {trigger.isPending
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <RefreshCw className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">Sync Now</span>
          </button>

          <button onClick={onAlertOpen} className="btn-primary text-sm">
            🔔 <span className="hidden sm:inline">Subscribe</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
