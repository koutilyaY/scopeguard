"use client";

import { useAuditEvents } from "@/lib/hooks";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";

export default function AuditPage() {
  const { data, isLoading, isError } = useAuditEvents();
  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState message="Could not load the audit log." />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <p className="text-sm text-slate-500">
          Append-only record of every state-changing action in your organization.
        </p>
      </div>
      {data.items.length === 0 ? (
        <EmptyState title="No audit events yet" />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="px-4 py-2">When</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Entity</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id} className="border-b border-slate-100">
                  <td className="whitespace-nowrap px-4 py-2 text-slate-500">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 font-medium">{e.action}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {e.entity_type}
                    {e.entity_id ? ` · ${e.entity_id.slice(0, 8)}…` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
