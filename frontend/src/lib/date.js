const DAY_MS = 24 * 60 * 60 * 1000;

const shortDate = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const shortDateTime = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function parseDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function differenceInCalendarDays(value, base = new Date()) {
  const date = parseDate(value);
  if (!date) return null;

  const start = Date.UTC(base.getFullYear(), base.getMonth(), base.getDate());
  const end = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.round((end - start) / DAY_MS);
}

export function formatShortDate(value) {
  const date = parseDate(value);
  return date ? shortDate.format(date) : null;
}

export function formatShortDateTime(value) {
  const date = parseDate(value);
  return date ? shortDateTime.format(date) : null;
}

export function formatRelativeStrict(value) {
  const date = parseDate(value);
  if (!date) return null;

  const diffMs = Date.now() - date.getTime();
  const future = diffMs < 0;
  const absMs = Math.abs(diffMs);
  const units = [
    ["year", 365 * DAY_MS],
    ["month", 30 * DAY_MS],
    ["day", DAY_MS],
    ["hour", 60 * 60 * 1000],
    ["minute", 60 * 1000],
  ];

  const [unit, size] = units.find(([, unitMs]) => absMs >= unitMs) || ["second", 1000];
  const amount = Math.max(1, Math.round(absMs / size));
  return future
    ? `in ${amount} ${unit}${amount === 1 ? "" : "s"}`
    : `${amount} ${unit}${amount === 1 ? "" : "s"} ago`;
}
