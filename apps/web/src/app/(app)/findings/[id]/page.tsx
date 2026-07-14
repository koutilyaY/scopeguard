"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, formatMinor } from "@/lib/api";
import { useDecide, useFinding, useMe } from "@/lib/hooks";
import { Badge, BackLink, ErrorState, LoadingState } from "@/components/ui";
import { CalculationBreakdown } from "@/components/finding/CalculationBreakdown";
import { EvidenceList } from "@/components/finding/EvidenceList";
import { DecisionForm } from "@/components/finding/DecisionForm";
import { ArtifactsPanel } from "@/components/finding/ArtifactsPanel";

export default function FindingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: finding, isLoading, isError } = useFinding(id);

  if (isLoading) return <LoadingState />;
  if (isError || !finding) return <ErrorState message="Could not load this finding." />;

  const supporting = finding.evidence.filter((e) => e.evidence_type === "supporting");
  const contradicting = finding.evidence.filter((e) => e.evidence_type === "contradicting");

  return (
    <div className="space-y-5">
      <BackLink href="/findings">Finding inbox</BackLink>

      <div className="card p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">{finding.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge value={finding.finding_type} />
              <Badge value={finding.classification} />
              <Badge value={finding.review_status} />
              <Badge value={finding.risk_level} />
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-semibold text-amber-700">
              {finding.potential_value_minor != null
                ? formatMinor(finding.potential_value_minor, finding.currency)
                : "value unavailable"}
            </p>
            <p className="text-xs text-slate-500">
              {finding.value_unavailable_reason ?? "Potential value — not approved or invoiced"}
            </p>
            {finding.confidence != null && (
              <p className="text-xs text-slate-500">
                model confidence {(finding.confidence * 100).toFixed(0)}%
              </p>
            )}
          </div>
        </div>
        <p className="mt-3 whitespace-pre-line text-sm text-slate-700">{finding.explanation}</p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <EvidenceList title="Supporting evidence" items={supporting} />
          {contradicting.length > 0 && (
            <EvidenceList title="Contradicting evidence" items={contradicting} tone="red" />
          )}
          {finding.contradicting_summary && (
            <div className="card p-4">
              <h2 className="mb-1 font-medium text-red-700">Contradicting summary</h2>
              <p className="text-sm text-slate-700">{finding.contradicting_summary}</p>
            </div>
          )}
          <CalculationBreakdown
            calculation={finding.calculation_breakdown}
            evidence={finding.evidence_score_breakdown}
          />
          {finding.missing_evidence && finding.missing_evidence.length > 0 && (
            <div className="card p-4">
              <h2 className="mb-1 font-medium">Missing evidence</h2>
              <ul className="list-disc pl-5 text-sm text-slate-700">
                {finding.missing_evidence.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="space-y-5">
          <DecisionForm finding={finding} />
          <ArtifactsPanel finding={finding} />
          <div className="card p-4">
            <h2 className="mb-2 font-medium">Review history</h2>
            {finding.decisions.length === 0 ? (
              <p className="text-sm text-slate-500">No decisions recorded yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {finding.decisions.map((d) => (
                  <li key={d.id} className="border-l-2 border-slate-200 pl-3">
                    <p>
                      <Badge value={d.previous_status} /> → <Badge value={d.new_status} />
                    </p>
                    <p className="mt-1 text-slate-600">{d.reason}</p>
                    <p className="text-xs text-slate-400">
                      {new Date(d.created_at).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="card p-4">
            <h2 className="mb-2 font-medium">Export</h2>
            <div className="flex flex-col gap-2 text-sm">
              <a
                className="text-brand-600 hover:underline"
                href={`/api/v1/reports/findings/${finding.id}.pdf`}
              >
                Evidence report (PDF)
              </a>
              <a
                className="text-brand-600 hover:underline"
                href={`/api/v1/reports/findings/${finding.id}.json`}
              >
                Audit JSON
              </a>
            </div>
          </div>
        </div>
      </div>

      <p className="rounded-md bg-amber-50 p-3 text-xs text-amber-800">{finding.disclaimer}</p>
    </div>
  );
}
