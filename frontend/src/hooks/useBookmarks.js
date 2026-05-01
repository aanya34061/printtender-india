import { useState } from "react";

function load() {
  try {
    return JSON.parse(localStorage.getItem("pt_bookmarks") || "{}");
  } catch {
    return {};
  }
}

function save(data) {
  localStorage.setItem("pt_bookmarks", JSON.stringify(data));
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState(load);

  function toggle(tender) {
    setBookmarks((prev) => {
      const next = { ...prev };
      if (next[tender.id]) {
        delete next[tender.id];
      } else {
        next[tender.id] = tender;
      }
      save(next);
      return next;
    });
  }

  return {
    bookmarks,
    toggle,
    isBookmarked: (id) => !!bookmarks[id],
    list: Object.values(bookmarks),
  };
}
