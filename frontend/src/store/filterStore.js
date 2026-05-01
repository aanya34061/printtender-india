import { create } from "zustand";

export const useFilterStore = create((set) => ({
  q: "printing",
  state: null,
  portal: null,
  deadline_within_days: 30,
  min_value: null,
  max_value: null,
  sort: "deadline_asc",
  page: 1,
  limit: 20,

  setQ: (q) => set({ q, page: 1 }),
  setState: (state) => set({ state, page: 1 }),
  setPortal: (portal) => set({ portal, page: 1 }),
  setDeadlineDays: (deadline_within_days) => set({ deadline_within_days, page: 1 }),
  setValueRange: (min_value, max_value) => set({ min_value, max_value, page: 1 }),
  setSort: (sort) => set({ sort, page: 1 }),
  setPage: (page) => set({ page }),
  resetFilters: () =>
    set({ q: "printing", state: null, portal: null, deadline_within_days: 30,
          min_value: null, max_value: null, sort: "deadline_asc", page: 1 }),
}));
