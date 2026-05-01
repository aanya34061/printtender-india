import { Bell } from "lucide-react";
import { useState } from "react";
import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function AlertSignup() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("idle");

  async function submit(event) {
    event.preventDefault();
    setStatus("saving");
    await axios.post(`${apiBaseUrl}/api/alerts`, { email, keywords: ["printing"], states: [] });
    setEmail("");
    setStatus("saved");
  }

  return (
    <section className="rounded border border-neutral-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <Bell className="h-4 w-4 text-neutral-600" />
        <h2 className="text-sm font-semibold">Email Alerts</h2>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="h-10 w-full rounded border border-neutral-300 px-3 text-sm outline-none focus:border-sky-600 focus:ring-2 focus:ring-sky-100"
          placeholder="you@company.com"
        />
        <button
          type="submit"
          disabled={status === "saving"}
          className="inline-flex h-10 w-full items-center justify-center rounded bg-neutral-950 px-3 text-sm font-medium text-white disabled:opacity-60"
        >
          {status === "saving" ? "Saving" : "Create alert"}
        </button>
        {status === "saved" && <p className="text-xs text-emerald-700">Alert created.</p>}
      </form>
    </section>
  );
}
