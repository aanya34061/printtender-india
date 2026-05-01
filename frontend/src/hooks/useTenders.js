import { useQuery } from "@tanstack/react-query";
import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function useTenders(filters) {
  const { query, state, portal, category, days, page } = filters;

  return useQuery({
    queryKey: ["tenders", query, state, portal, category, days, page],
    queryFn: async () => {
      const { data } = await axios.get(`${BASE}/tenders`, {
        params: {
          q: query || "printing",
          state: state || undefined,
          portal: portal || undefined,
          category: category || undefined,
          days: days || 30,
          page: page || 1,
          limit: 20,
        },
      });
      return data;
    },
    staleTime: 1000 * 60 * 5,
    select: (data) => ({
      tenders: data.tenders ?? [],
      total: data.total ?? 0,
      pages: data.pages ?? 1,
    }),
  });
}
