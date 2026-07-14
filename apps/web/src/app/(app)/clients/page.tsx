"use client";

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import { useClients } from "@/lib/hooks";
import { useQueryClient } from "@tanstack/react-query";
import { Badge, EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { useMe } from "@/lib/hooks";

const WRITE_ROLES = ["organization_admin", "finance_manager", "project_manager"];

export default function ClientsPage() {
  const { data, isLoading, isError } = useClients();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [legalName, setLegalName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const canWrite = me && WRITE_ROLES.includes(me.role);

  async function create() {
    setError(null);
    try {
      await api.post("/clients", { legal_name: legalName, display_name: displayName });
      setLegalName("");
      setDisplayName("");
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["clients"] });
    } catch {
      setError("Could not create client. Check your permissions.");
    }
  }

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState message="Could not load clients." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Clients</h1>
        {canWrite && (
          <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "New client"}
          </button>
        )}
      </div>

      {showForm && (
        <div className="card space-y-3 p-4">
          <div>
            <label className="label" htmlFor="legal">
              Legal name
            </label>
            <input
              id="legal"
              className="input"
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="display">
              Display name
            </label>
            <input
              id="display"
              className="input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary" onClick={create} disabled={!legalName || !displayName}>
            Create client
          </button>
        </div>
      )}

      {data.items.length === 0 ? (
        <EmptyState title="No clients yet" hint="Create a client to start tracking projects." />
      ) : (
        <div className="card divide-y divide-slate-100">
          {data.items.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium">{c.display_name}</p>
                <p className="text-sm text-slate-500">{c.legal_name}</p>
              </div>
              <div className="flex items-center gap-3">
                <Badge value={c.status} />
                <Link
                  className="text-sm text-brand-600 hover:underline"
                  href={`/projects?client=${c.id}`}
                >
                  Projects →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
