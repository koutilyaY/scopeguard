"use client";

import Link from "next/link";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useContracts, useDocuments, useMe } from "@/lib/hooks";
import { Badge, EmptyState, LoadingState } from "@/components/ui";

const WRITE_ROLES = ["organization_admin", "finance_manager", "project_manager"];

export function ContractsTab({ projectId, clientId }: { projectId: string; clientId: string }) {
  const { data, isLoading } = useContracts(projectId);
  const { data: documents } = useDocuments(projectId);
  const { data: me } = useMe();
  const qc = useQueryClient();
  const canWrite = me && WRITE_ROLES.includes(me.role);

  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [docId, setDocId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function createContract() {
    setMsg(null);
    try {
      await api.post("/contracts", {
        client_id: clientId,
        project_id: projectId,
        title,
        governing_document_id: docId || null,
        effective_from: from || null,
        effective_to: to || null,
        status: "active",
      });
      setShowForm(false);
      setTitle("");
      qc.invalidateQueries({ queryKey: ["contracts", projectId] });
    } catch {
      setMsg("Could not create contract.");
    }
  }

  async function extract(contractId: string) {
    setMsg(null);
    try {
      await api.post(`/contracts/${contractId}/extract`);
      setMsg("Clause extraction queued. Review extracted clauses shortly.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Extraction could not be queued.");
    }
  }

  if (isLoading) return <LoadingState />;

  const extractableDocs = documents?.items.filter((d) => d.extraction_status === "completed") ?? [];

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="flex justify-end">
          <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "New contract"}
          </button>
        </div>
      )}

      {showForm && (
        <div className="card space-y-3 p-4">
          <div>
            <label className="label" htmlFor="ctitle">
              Title
            </label>
            <input id="ctitle" className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="cdoc">
              Governing document (extracted text required for clause extraction)
            </label>
            <select id="cdoc" className="input" value={docId} onChange={(e) => setDocId(e.target.value)}>
              <option value="">None</option>
              {extractableDocs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.original_filename}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label" htmlFor="cfrom">
                Effective from
              </label>
              <input id="cfrom" type="date" className="input" value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="cto">
                Effective to
              </label>
              <input id="cto" type="date" className="input" value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
          </div>
          <button className="btn-primary" onClick={createContract} disabled={!title}>
            Create contract
          </button>
        </div>
      )}

      {msg && <p className="text-sm text-slate-600">{msg}</p>}

      {!data || data.items.length === 0 ? (
        <EmptyState title="No contracts yet" hint="Create a contract from an uploaded document." />
      ) : (
        <div className="card divide-y divide-slate-100">
          {data.items.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-3 text-sm">
              <div>
                <p className="font-medium">{c.title}</p>
                <p className="text-slate-500">
                  {c.effective_from ?? "—"} → {c.effective_to ?? "—"} · {c.currency}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge value={c.status} />
                {canWrite && c.governing_document_id && (
                  <button className="btn-secondary" onClick={() => extract(c.id)}>
                    Extract clauses
                  </button>
                )}
                <Link className="text-brand-600 hover:underline" href={`/contracts/${c.id}`}>
                  Review clauses →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
