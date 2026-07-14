"use client";

import type { Evidence } from "@/lib/types";

export function EvidenceList({
  title,
  items,
  tone = "slate",
}: {
  title: string;
  items: Evidence[];
  tone?: "slate" | "red";
}) {
  if (items.length === 0) {
    return (
      <div className="card p-4">
        <h2 className="mb-1 font-medium">{title}</h2>
        <p className="text-sm text-slate-500">None recorded.</p>
      </div>
    );
  }
  return (
    <div className="card p-4">
      <h2 className={`mb-2 font-medium ${tone === "red" ? "text-red-700" : ""}`}>{title}</h2>
      <ul className="space-y-3">
        {items.map((e) => (
          <li key={e.id} className="rounded border border-slate-100 p-3">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                {e.entity_type.replace(/_/g, " ")}
              </span>
              {e.document_page && <span>page {e.document_page}</span>}
              {e.section_reference && <span>§{e.section_reference}</span>}
            </div>
            {e.quotation && (
              <p className="mt-1 text-sm italic text-slate-700">“{e.quotation}”</p>
            )}
            {e.relevance_explanation && (
              <p className="mt-1 text-sm text-slate-600">{e.relevance_explanation}</p>
            )}
            {e.entity_summary && (
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-slate-500">
                {Object.entries(e.entity_summary).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <dt>{k.replace(/_/g, " ")}</dt>
                    <dd className="font-medium text-slate-700">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
