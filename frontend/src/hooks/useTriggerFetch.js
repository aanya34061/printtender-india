import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useToastStore } from "../store/toastStore.js";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function useTriggerFetch() {
  const qc = useQueryClient();
  const add = useToastStore((s) => s.add);

  return useMutation({
    mutationFn: () => axios.post(`${BASE}/api/fetch/trigger`),
    onSuccess: () => {
      add("✅ Fetch triggered — new tenders loading shortly", "success");
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["stats"] });
        qc.invalidateQueries({ queryKey: ["tenders"] });
      }, 5000);
    },
    onError: () => add("⚠️ Fetch failed — retrying in 6 hours", "error"),
  });
}
