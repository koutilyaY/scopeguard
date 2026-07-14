"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useClients, useMe, useProjects } from "@/lib/hooks";
import { Badge, EmptyState, ErrorState, LoadingState } from "@/components/ui";

const WRITE_ROLES = ["organization_admin", "finance_manager", "project_manager"];

export default function ProjectsPage() {
  const params = useSearchParams();
  const clientFilter = params.get("client") ?? undefined;
  const { data, isLoading, isError } = useProjects(clientFilter);
  const { data: clients } = useClients();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const canWrite = me && WRITE_ROLES.includes(me.role);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [clientId, setClientId] = useState(clientFilter ?? "");
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    try {
      await api.post("/projects", { client_id: clientId, name });
      setName("");
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["projects"] });
    } catch {
      setError("Could not create project.");
    }
  }

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState message="Could not load projects." />;

  const clientName = (id: string) =>
    clients?.items.find((c) => c.id === id)?.display_name ?? "—";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Projects</h1>
        {canWrite && (
          <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "New project"}
          </button>
        )}
      </div>

      {showForm && (
        <div className="card space-y-3 p-4">
          <div>
            <label className="label" htmlFor="client">
              Client
            </label>
            <select
              id="client"
              className="input"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
            >
              <option value="">Select a client…</option>
              {clients?.items.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="name">
              Project name
            </label>
            <input
              id="name"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button className="btn-primary" onClick={create} disabled={!clientId || !name}>
            Create project
          </button>
        </div>
      )}

      {data.items.length === 0 ? (
        <EmptyState title="No projects yet" hint="Create a project to import work and run reviews." />
      ) : (
        <div className="card divide-y divide-slate-100">
          {data.items.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              className="flex items-center justify-between p-4 hover:bg-slate-50"
            >
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-sm text-slate-500">{clientName(p.client_id)} · {p.currency}</p>
              </div>
              <Badge value={p.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
