import { create } from "zustand";

export const useFilterStore = create((set) => ({
  q: "",
  state: "",
  source: "",
  activeOnly: true,
  setFilter: (key, value) => set({ [key]: value }),
  resetFilters: () => set({ q: "", state: "", source: "", activeOnly: true }),
}));
