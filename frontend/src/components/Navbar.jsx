import { formatDistanceToNowStrict, parseISO } from "date-fns";
import { motion } from "framer-motion";
import { Loader2, Printer, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useStats } from "../hooks/useStats.js";
import { useTriggerFetch } from "../hooks/useTriggerFetch.js";

export default function Navbar({ onAlertOpen }) {
  const { data: stats } = useStats();
  const trigger = useTriggerFetch();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  const lastSynced = stats?.last_fetch
    ? formatDistanceToNowStrict(parseISO(stats.last_fetch), { addSuffix: true })
    : null;

  return (
    <nav
      className={`sticky top-0 z-50 transition-all duration-200 ${
        scrolled ? "bg-navbar/95 backdrop-blur-md shadow-lg" : "bg-navbar"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/20">
            <Printer className="h-5 w-5 text-accent" />
          </div>
          <span className="text-gradient text-lg font-bold">PrintTender India</span>
        </div>

        {/* Last synced — center */}
        <div className="hidden flex-1 items-center justify-center md:flex">
          {lastSynced && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <motion.span
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="h-2 w-2 rounded-full bg-success"
              />
              Last synced {lastSynced}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
            className="btn-outline flex items-center gap-2 text-sm"
            title="Sync Now"
          >
            {trigger.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">Sync Now</span>
          </button>
          <button onClick={onAlertOpen} className="btn-accent text-sm">
            🔔 Get Alerts
          </button>
        </div>
      </div>
    </nav>
  );
}
