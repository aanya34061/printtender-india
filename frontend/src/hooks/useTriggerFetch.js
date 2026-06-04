import { useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJSON } from "../lib/api.js";
import { useToastStore } from "../store/toastStore.js";

export function useTriggerFetch() {
  const qc = useQueryClient();
  const add = useToastStore((s) => s.add);

  return useMutation({
    mutationFn: () => fetchJSON("/api/fetch/trigger", {
      method: "POST",
      params: { scope: "live", sync: "true" },
    }),
    onSuccess: (data) => {
      add(
        data?.status === "already_running"
          ? "Sync already running — refreshing results shortly"
          : "Sync completed — refreshing results",
        "success",
      );
      [3000, 12000, 30000].forEach((delay) => window.setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["stats"] });
        qc.invalidateQueries({ queryKey: ["tenders"] });
      }, delay));
    },
    onError: () => add("⚠️ Fetch failed — retrying in 6 hours", "error"),
  });
}
