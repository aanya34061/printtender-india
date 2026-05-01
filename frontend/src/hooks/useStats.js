import { useQuery } from "@tanstack/react-query";
import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: async () => {
      const response = await axios.get(`${apiBaseUrl}/api/stats`);
      return response.data;
    },
  });
}
