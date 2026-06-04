import { X } from "lucide-react";
import { useToastStore } from "../store/toastStore.js";

const BORDER_COLORS = {
  success: "var(--green)",
  error: "var(--red)",
  warning: "var(--amber)",
  info: "#3b82f6",
};

export default function ToastContainer() {
  const { toasts, remove } = useToastStore();

  return (
    <div className="fixed inset-x-3 bottom-24 z-[9999] flex flex-col gap-2 sm:inset-x-auto sm:right-4 lg:bottom-6">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="flex w-full items-center gap-3 rounded-[12px] px-4 py-3 text-sm font-medium shadow-card sm:min-w-[280px] sm:max-w-[360px]"
          style={{
            background: "var(--surface2)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderLeft: `3px solid ${BORDER_COLORS[t.type] ?? BORDER_COLORS.info}`,
          }}
        >
          <span className="flex-1 text-slate-200">{t.message}</span>
          <button
            type="button"
            onClick={() => remove(t.id)}
            className="shrink-0 opacity-50 transition hover:opacity-100"
            style={{ color: "var(--muted)" }}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
