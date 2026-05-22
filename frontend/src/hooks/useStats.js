import { useQuery } from "@tanstack/react-query";
import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: async () => {
      const { data } = await axios.get(`${BASE}/api/stats`);
      return data;
    },
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
  });
}

export function usePortalStatus() {
  return useQuery({
    queryKey: ["portal-status"],
    queryFn: async () => {
      const { data } = await axios.get(`${BASE}/api/stats/portals/status`);
      return data;
    },
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
  });
}
