import { useQuery } from "@tanstack/react-query";
import { fetchJSON } from "../lib/api.js";

export function useStats(options = {}) {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => fetchJSON("/api/stats"),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
    ...options,
  });
}

export function usePortalStatus() {
  return useQuery({
    queryKey: ["portal-status"],
    queryFn: () => fetchJSON("/api/stats/portals/status"),
    staleTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
  });
}
