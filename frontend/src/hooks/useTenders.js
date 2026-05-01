import { useQuery } from "@tanstack/react-query";
import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function useTenders(filters) {
  return useQuery({
    queryKey: ["tenders", filters],
    queryFn: async () => {
      const response = await axios.get(`${apiBaseUrl}/api/tenders`, {
        params: {
          q: filters.q || undefined,
          state: filters.state || undefined,
          source: filters.source || undefined,
          active_only: filters.activeOnly,
        },
      });
      return response.data;
    },
  });
}
