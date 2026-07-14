"use client";

import { formatMinor, formatMinutes } from "@/lib/api";
import { useDashboard } from "@/lib/hooks";
import { Disclaimer, ErrorState, LoadingState } from "@/components/ui";
import type { ValueByCurrency } from "@/lib/types";

function ValueCard({
  title,
  values,
  tone,
  note,
}: {
  title: string;
  values: ValueByCurrency[];
  tone: string;
  note?: string;
}) {
  return (
    <div className="card p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <div className={`mt-1 text-2xl font-semibold ${tone}`}>
        {values.length === 0
          ? formatMinor(0, "USD")
          : values.map((v) => (
              <div key={v.currency}>{formatMinor(v.amount_minor, v.currency)}</div>
            ))}
      </div>
      {note && <p className="mt-1 text-xs text-slate-400">{note}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, isError } = useDashboard();
  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState message="Could not load the dashboard." />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-500">
          {data.pending_review_count} finding(s) awaiting human review.
        </p>
      </div>

      <section aria-label="Value by stage" className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <ValueCard
          title="Potential value identified"
          values={data.potential_value}
          tone="text-amber-700"
          note="Unreviewed — not recoverable revenue"
        />
        <ValueCard
          title="Approved for billing"
          values={data.approved_for_billing_value}
          tone="text-green-700"
          note="Human-approved findings"
        />
        <ValueCard
          title="Invoiced (issued/paid)"
          values={data.invoiced_value}
          tone="text-brand-700"
          note="From imported invoices"
        />
        <ValueCard title="Rejected" values={data.rejected_value} tone="text-slate-500" />
      </section>

      <p className="rounded-md bg-amber-50 p-3 text-xs text-amber-800">{data.value_disclaimer}</p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="card p-4">
          <h2 className="mb-2 font-medium">Findings by type</h2>
          <BreakdownList data={data.findings_by_type} />
        </div>
        <div className="card p-4">
          <h2 className="mb-2 font-medium">Findings by client</h2>
          <BreakdownList data={data.findings_by_client} />
        </div>
        <div className="card p-4">
          <h2 className="mb-2 font-medium">Findings by project</h2>
          <BreakdownList data={data.findings_by_project} />
        </div>
      </div>

      <div className="card p-4">
        <h2 className="mb-2 font-medium">Allowances approaching exhaustion</h2>
        {data.allowances_nearing_exhaustion.length === 0 ? (
          <p className="text-sm text-slate-500">No allowances are near exhaustion.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {data.allowances_nearing_exhaustion.map((a) => (
              <li key={a.allowance_id} className="flex justify-between">
                <span>
                  {a.allowance_type.replace(/_/g, " ")} · {a.period_label}
                </span>
                <span className="text-amber-700">
                  {formatMinutes(a.remaining_minutes)} of {formatMinutes(a.included_minutes)} left
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card p-4">
        <h2 className="mb-2 font-medium">Recent review runs</h2>
        {data.recent_review_runs.length === 0 ? (
          <p className="text-sm text-slate-500">No review runs yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {data.recent_review_runs.map((run, i) => (
              <li key={i} className="flex justify-between py-1.5">
                <span>
                  {String(run.billing_period_start)} → {String(run.billing_period_end)}
                </span>
                <span className="text-slate-500">
                  {String(run.status)} · {String(run.findings ?? 0)} findings
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Disclaimer />
    </div>
  );
}

function BreakdownList({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <p className="text-sm text-slate-500">None yet.</p>;
  return (
    <ul className="space-y-1 text-sm">
      {entries.map(([key, count]) => (
        <li key={key} className="flex justify-between">
          <span className="text-slate-600">{key.replace(/_/g, " ")}</span>
          <span className="font-medium">{count}</span>
        </li>
      ))}
    </ul>
  );
}
