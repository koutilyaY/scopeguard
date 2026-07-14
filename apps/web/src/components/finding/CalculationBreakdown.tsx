"use client";

import { formatMinor, formatMinutes } from "@/lib/api";

interface CalcEntry {
  time_entry_id: string;
  employee?: string;
  role?: string | null;
  date?: string;
  minutes: number;
  rate_minor: number | null;
  value_minor: number | null;
  note?: string;
}

export function CalculationBreakdown({
  calculation,
  evidence,
}: {
  calculation: Record<string, unknown> | null;
  evidence: Record<string, unknown> | null;
}) {
  return (
    <div className="card p-4">
      <h2 className="mb-2 font-medium">Calculation breakdown</h2>
      <p className="mb-3 text-xs text-slate-500">
        All monetary figures are computed by deterministic application code, never by the language
        model.
      </p>

      {calculation ? (
        <CalcTable calculation={calculation} />
      ) : (
        <p className="text-sm text-slate-500">No monetary calculation for this finding.</p>
      )}

      {evidence ? <EvidenceScore evidence={evidence} /> : null}
    </div>
  );
}

function CalcTable({ calculation }: { calculation: Record<string, unknown> }) {
  const entries = (calculation.entries as CalcEntry[] | undefined) ?? [];
  const totalMinor = calculation.total_minor as number | null;
  const currency = (calculation.currency as string) ?? "USD";
  const missing = (calculation.missing_rates_for_roles as string[] | undefined) ?? [];
  const allowanceNote = calculation.allowance as string | null;

  if (calculation.duplicate_groups) {
    const groups = calculation.duplicate_groups as Array<{
      kind: string;
      explanation: string;
    }>;
    return (
      <ul className="space-y-1 text-sm">
        {groups.map((g, i) => (
          <li key={i}>
            <span className="font-medium">{g.kind} duplicate:</span> {g.explanation}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">{String(calculation.method ?? "")}</p>
      {allowanceNote && (
        <p className="rounded bg-slate-50 p-2 text-xs text-slate-600">{allowanceNote}</p>
      )}
      {entries.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-2">Employee</th>
                <th className="py-1 pr-2">Date</th>
                <th className="py-1 pr-2">Time</th>
                <th className="py-1 pr-2">Rate</th>
                <th className="py-1 pr-2">Value</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.time_entry_id} className="border-t border-slate-100">
                  <td className="py-1 pr-2">{e.employee ?? "—"}</td>
                  <td className="py-1 pr-2">{e.date ?? "—"}</td>
                  <td className="py-1 pr-2">{formatMinutes(e.minutes)}</td>
                  <td className="py-1 pr-2">
                    {e.rate_minor != null ? formatMinor(e.rate_minor, currency) : "—"}
                  </td>
                  <td className="py-1 pr-2">
                    {e.value_minor != null ? (
                      formatMinor(e.value_minor, currency)
                    ) : (
                      <span className="text-amber-700">{e.note ?? "unavailable"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {missing.length > 0 && (
        <p className="text-xs text-amber-700">
          No verified rate for: {missing.join(", ")} — value shown as unavailable rather than
          estimated.
        </p>
      )}
      <p className="border-t border-slate-200 pt-2 text-sm font-semibold">
        Total: {totalMinor != null ? formatMinor(totalMinor, currency) : "value unavailable"}
      </p>
    </div>
  );
}

function EvidenceScore({ evidence }: { evidence: Record<string, unknown> }) {
  const score = evidence.score as number;
  const components =
    (evidence.components as Array<{
      component: string;
      present: boolean;
      contribution: number;
    }>) ?? [];
  return (
    <div className="mt-4 border-t border-slate-200 pt-3">
      <p className="text-sm font-medium">Evidence completeness: {(score * 100).toFixed(0)}%</p>
      <p className="text-xs text-slate-500">{String(evidence.disclaimer ?? "")}</p>
      <ul className="mt-2 grid grid-cols-2 gap-x-4 text-xs">
        {components.map((c) => (
          <li key={c.component} className="flex justify-between">
            <span className={c.present ? "text-slate-700" : "text-slate-400"}>
              {c.present ? "✓" : "○"} {c.component.replace(/_/g, " ")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
