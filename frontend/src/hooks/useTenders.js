import { useQuery } from "@tanstack/react-query";
import { fetchJSON } from "../lib/api.js";

export const TENDER_LIST_STALE_MS = 1000 * 60;

export function fetchTenders(filters) {
  return fetchJSON("/api/tenders", {
    params: {
      q: filters.q || undefined,
      state: filters.state || undefined,
      portal: filters.portal || undefined,
      deadline_within_days: filters.deadline_within_days || undefined,
      min_value: filters.min_value || undefined,
      max_value: filters.max_value || undefined,
      sort: filters.sort || "deadline_asc",
      page: filters.page || 1,
      limit: filters.limit || 6,
    },
  });
}

export function useTenders(filters) {
  return useQuery({
    queryKey: ["tenders", filters],
    queryFn: () => fetchTenders(filters),
    staleTime: TENDER_LIST_STALE_MS,
    placeholderData: (prev) => prev,
    refetchOnWindowFocus: false,
  });
}
