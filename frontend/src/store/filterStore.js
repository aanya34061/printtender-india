import { create } from "zustand";

export const useFilterStore = create((set) => ({
  query: "printing",
  state: null,
  portal: null,
  category: null,
  days: 30,
  page: 1,

  setQuery: (query) => set({ query, page: 1 }),
  setState: (state) => set({ state, page: 1 }),
  setPortal: (portal) => set({ portal, page: 1 }),
  setCategory: (category) => set({ category, page: 1 }),
  setDays: (days) => set({ days, page: 1 }),
  setPage: (page) => set({ page }),
  resetFilters: () =>
    set({ query: "printing", state: null, portal: null, category: null, days: 30, page: 1 }),
}));
