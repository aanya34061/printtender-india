import { useQuery } from "@tanstack/react-query";
import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function useTenders(filters) {
  return useQuery({
    queryKey: ["tenders", filters],
    queryFn: async () => {
      const { data } = await axios.get(`${BASE}/api/tenders`, {
        params: {
          q: filters.q || "printing",
          state: filters.state || undefined,
          portal: filters.portal || undefined,
          deadline_within_days: filters.deadline_within_days || 30,
          min_value: filters.min_value || undefined,
          max_value: filters.max_value || undefined,
          sort: filters.sort || "deadline_asc",
          page: filters.page || 1,
          limit: filters.limit || 20,
        },
      });
      return data;
    },
    staleTime: 1000 * 60 * 5,
    placeholderData: (prev) => prev,
  });
}
