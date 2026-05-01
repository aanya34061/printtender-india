import { CalendarDays, ExternalLink, IndianRupee } from "lucide-react";

export default function TenderDetail({ tender }) {
  if (!tender) {
    return (
      <aside className="rounded border border-neutral-200 bg-white p-5 text-sm text-neutral-500">
        Select a tender to inspect details.
      </aside>
    );
  }

  return (
    <aside className="rounded border border-neutral-200 bg-white p-5">
      <div className="space-y-2">
        <span className="text-xs font-medium uppercase text-neutral-500">{tender.source}</span>
        <h2 className="text-lg font-semibold leading-6">{tender.title}</h2>
        <p className="text-sm text-neutral-600">{tender.buyer || "Buyer not listed"}</p>
      </div>

      <dl className="mt-5 grid gap-3 text-sm">
        <Detail icon={<CalendarDays />} label="Deadline" value={formatValue(tender.deadline)} />
        <Detail icon={<IndianRupee />} label="Estimated value" value={tender.estimated_value ? `₹${tender.estimated_value}` : "Not disclosed"} />
      </dl>

      <div className="mt-5 flex flex-wrap gap-1.5">
        {(tender.keywords || []).map((keyword) => (
          <span key={keyword} className="rounded bg-sky-50 px-2 py-1 text-xs text-sky-800">
            {keyword}
          </span>
        ))}
      </div>

      {tender.tender_url && (
        <a
          href={tender.tender_url}
          target="_blank"
          rel="noreferrer"
          className="mt-6 inline-flex h-10 items-center gap-2 rounded bg-sky-700 px-4 text-sm font-medium text-white hover:bg-sky-800"
        >
          <ExternalLink className="h-4 w-4" />
          Open tender
        </a>
      )}
    </aside>
  );
}

function Detail({ icon, label, value }) {
  return (
    <div className="flex items-center gap-3 rounded border border-neutral-200 p-3">
      <span className="text-neutral-500 [&>svg]:h-4 [&>svg]:w-4">{icon}</span>
      <div>
        <dt className="text-xs text-neutral-500">{label}</dt>
        <dd className="font-medium text-neutral-900">{value}</dd>
      </div>
    </div>
  );
}

function formatValue(value) {
  return value ? new Date(value).toLocaleString() : "Not listed";
}
