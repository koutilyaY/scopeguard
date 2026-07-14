"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { formatMinor } from "@/lib/api";
import { useFindings } from "@/lib/hooks";
import { Badge, Disclaimer, EmptyState, ErrorState, LoadingState } from "@/components/ui";

const FINDING_TYPES = [
  "potentially_out_of_scope",
  "exhausted_allowance",
  "unbilled_time",
  "rate_mismatch",
  "possible_duplicate",
  "already_invoiced",
  "missing_customer_authorization",
  "insufficient_evidence",
  "contract_ambiguity",
];
const STATUSES = [
  "pending",
  "approved_for_followup",
  "approved_for_billing",
  "rejected",
  "needs_more_evidence",
  "already_resolved",
];
const CLASSIFICATIONS = [
  "in_scope",
  "potentially_out_of_scope",
  "clearly_out_of_scope",
  "insufficient_information",
];

export default function FindingInboxPage() {
  const params = useSearchParams();
  const reviewRunId = params.get("review_run_id") ?? "";
  const [filters, setFilters] = useState<Record<string, string>>({});
  const effective = { ...filters, ...(reviewRunId ? { review_run_id: reviewRunId } : {}) };
  const { data, isLoading, isError } = useFindings(effective);

  function setFilter(key: string, value: string) {
    setFilters((f) => {
      const next = { ...f };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Finding inbox</h1>
        <p className="text-sm text-slate-500">
          Every finding requires human review before any follow-up or billing action.
        </p>
      </div>

      <div className="card grid grid-cols-1 gap-3 p-4 sm:grid-cols-4">
        <FilterSelect
          label="Type"
          options={FINDING_TYPES}
          onChange={(v) => setFilter("finding_type", v)}
        />
        <FilterSelect
          label="Classification"
          options={CLASSIFICATIONS}
          onChange={(v) => setFilter("classification", v)}
        />
        <FilterSelect
          label="Review status"
          options={STATUSES}
          onChange={(v) => setFilter("review_status", v)}
        />
        <FilterSelect
          label="Risk"
          options={["low", "medium", "high"]}
          onChange={(v) => setFilter("risk_level", v)}
        />
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError || !data ? (
        <ErrorState message="Could not load findings." />
      ) : data.items.length === 0 ? (
        <EmptyState
          title="No findings match"
          hint="Run a billing-period review from a project, or clear the filters."
        />
      ) : (
        <div className="card divide-y divide-slate-100">
          {data.items.map((f) => (
            <Link
              key={f.id}
              href={`/findings/${f.id}`}
              className="block p-4 hover:bg-slate-50"
              data-testid="finding-row"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{f.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge value={f.classification} />
                    <Badge value={f.review_status} />
                    <Badge value={f.risk_level} />
                    {f.evidence_score != null && (
                      <span className="text-xs text-slate-500">
                        evidence {(f.evidence_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <p className="font-semibold text-amber-700">
                    {f.potential_value_minor != null
                      ? formatMinor(f.potential_value_minor, f.currency)
                      : "value unavailable"}
                  </p>
                  {f.confidence != null && (
                    <p className="text-xs text-slate-500">
                      confidence {(f.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
      <Disclaimer />
    </div>
  );
}

function FilterSelect({
  label,
  options,
  onChange,
}: {
  label: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const id = `filter-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div>
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        aria-label={label}
        className="input"
        onChange={(e) => onChange(e.target.value)}
        defaultValue=""
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o.replace(/_/g, " ")}
          </option>
        ))}
      </select>
    </div>
  );
}
