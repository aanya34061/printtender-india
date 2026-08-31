export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" && window.location.hostname === "localhost"
    ? window.location.origin
    : "https://printtender-india-backend.vercel.app");



export async function fetchJSON(path, { params, json, headers, ...options } = {}) {
  const url = new URL(path, API_BASE);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const response = await fetch(url, {
    ...options,
    headers: json
      ? { "Content-Type": "application/json", ...headers }
      : headers,
    body: json ? JSON.stringify(json) : options.body,
  });
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      detail = body?.detail || detail;
    } catch {
      // Keep the status-only fallback when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}
