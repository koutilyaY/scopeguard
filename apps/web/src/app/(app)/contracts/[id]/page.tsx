"use client";

import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useClauses, useMe } from "@/lib/hooks";
import { Badge, BackLink, Disclaimer, EmptyState, ErrorState, LoadingState } from "@/components/ui";

const DECISION_ROLES = ["organization_admin", "finance_manager", "project_manager", "reviewer"];

export default function ContractReviewPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError } = useClauses(id);
  const { data: me } = useMe();
  const qc = useQueryClient();
  const canDecide = me && DECISION_ROLES.includes(me.role);

  async function act(clauseId: string, action: "approve" | "reject") {
    await api.post(`/clauses/${clauseId}/${action}`);
    qc.invalidateQueries({ queryKey: ["clauses", id] });
  }

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState message="Could not load clauses." />;

  const verified = data.items.filter((c) => c.human_verified).length;

  return (
    <div className="space-y-4">
      <BackLink href="/projects">Projects</BackLink>
      <div>
        <h1 className="text-2xl font-semibold">Contract clause review</h1>
        <p className="text-sm text-slate-500">
          {verified} of {data.items.length} clauses human-verified. Unverified clauses cannot drive
          high-confidence billing recommendations.
        </p>
      </div>

      {data.items.length === 0 ? (
        <EmptyState
          title="No extracted clauses yet"
          hint="Trigger clause extraction from the project's Contracts tab, then review here."
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((c) => (
            <div key={c.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{c.title}</span>
                    <Badge value={c.clause_type} />
                    {c.human_verified && <Badge value="approved_for_billing" />}
                    {c.rejected && <Badge value="rejected" />}
                  </div>
                  <p className="mt-2 rounded bg-slate-50 p-2 text-sm italic text-slate-700">
                    “{c.source_text}”
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {c.page_number ? `Page ${c.page_number}` : ""}
                    {c.section_reference ? ` · §${c.section_reference}` : ""}
                    {c.confidence != null ? ` · model confidence ${(c.confidence * 100).toFixed(0)}%` : ""}
                  </p>
                  {c.normalized_interpretation && (
                    <p className="mt-1 text-sm text-slate-600">{c.normalized_interpretation}</p>
                  )}
                </div>
                {canDecide && !c.human_verified && (
                  <div className="flex shrink-0 gap-2">
                    <button className="btn-primary" onClick={() => act(c.id, "approve")}>
                      Approve
                    </button>
                    <button className="btn-secondary" onClick={() => act(c.id, "reject")}>
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <Disclaimer />
    </div>
  );
}
