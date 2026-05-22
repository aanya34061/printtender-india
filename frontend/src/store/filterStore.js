import { create } from "zustand";

export const useFilterStore = create((set) => ({
  q: "",
  state: null,
  portal: null,
  // categories now supports multiple selections
  categories: [],
  deadline_within_days: 30,
  min_value: null,
  max_value: null,
  sort: "deadline_asc",
  page: 1,
  limit: 6,

  setQ: (q) => set({ q, page: 1 }),
  setState: (state) => set({ state, page: 1 }),
  setPortal: (portal) => set({ portal, page: 1 }),
  // toggle a category in the selected categories array
  toggleCategory: (category) => set((s) => {
    const exists = (s.categories || []).includes(category);
    const cats = exists ? s.categories.filter((c) => c !== category) : [...(s.categories || []), category];
    return { categories: cats, page: 1 };
  }),
  setCategories: (categories) => set({ categories, page: 1 }),
  setDeadlineDays: (deadline_within_days) => set({ deadline_within_days, page: 1 }),
  setValueRange: (min_value, max_value) => set({ min_value, max_value, page: 1 }),
  setSort: (sort) => set({ sort, page: 1 }),
  setPage: (page) => set({ page }),
  resetFilters: () =>
    set({ q: "", state: null, portal: null, categories: [], deadline_within_days: 30,
          min_value: null, max_value: null, sort: "deadline_asc", page: 1, limit: 6 }),
}));
