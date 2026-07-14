"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useDocuments, useMe } from "@/lib/hooks";
import { Badge, EmptyState, LoadingState } from "@/components/ui";

const DOC_TYPES = [
  "master_service_agreement",
  "statement_of_work",
  "amendment",
  "change_order",
  "rate_card",
  "customer_request",
  "invoice",
  "other",
];
const WRITE_ROLES = ["organization_admin", "finance_manager", "project_manager"];

export function DocumentsTab({ projectId, clientId }: { projectId: string; clientId: string }) {
  const { data, isLoading } = useDocuments(projectId);
  const { data: me } = useMe();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [docType, setDocType] = useState("statement_of_work");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canWrite = me && WRITE_ROLES.includes(me.role);

  async function upload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setStatus(null);
    const form = new FormData();
    form.append("file", file);
    form.append("document_type", docType);
    form.append("client_id", clientId);
    form.append("project_id", projectId);
    try {
      const res = await api.post<{ duplicate_of: string | null }>("/documents/upload", form);
      setStatus(
        res.duplicate_of
          ? "Uploaded. Note: an identical file already exists (same SHA-256)."
          : "Uploaded. Text extraction is running in the background.",
      );
      if (fileRef.current) fileRef.current.value = "";
      qc.invalidateQueries({ queryKey: ["documents", projectId] });
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="card space-y-3 p-4">
          <h3 className="font-medium">Upload a document</h3>
          <p className="text-xs text-slate-500">
            PDF or DOCX. Scanned PDFs without machine-readable text are flagged (OCR is not
            enabled).
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label" htmlFor="doctype">
                Type
              </label>
              <select
                id="doctype"
                className="input"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
              >
                {DOC_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <input ref={fileRef} type="file" className="text-sm" aria-label="File to upload" />
            <button className="btn-primary" onClick={upload} disabled={busy}>
              {busy ? "Uploading…" : "Upload"}
            </button>
          </div>
          {status && <p className="text-sm text-slate-600">{status}</p>}
        </div>
      )}

      {!data || data.items.length === 0 ? (
        <EmptyState title="No documents yet" hint="Upload a contract or supporting document." />
      ) : (
        <div className="card divide-y divide-slate-100">
          {data.items.map((d) => (
            <div key={d.id} className="flex items-center justify-between p-3 text-sm">
              <div>
                <p className="font-medium">{d.original_filename}</p>
                <p className="text-slate-500">
                  {d.document_type.replace(/_/g, " ")} · {(d.file_size / 1024).toFixed(0)} KB
                </p>
                {d.extraction_status === "unreadable" && (
                  <p className="mt-1 text-amber-700">{d.extraction_error}</p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <Badge value={d.extraction_status} />
                <a
                  className="text-brand-600 hover:underline"
                  href={`/api/v1/documents/${d.id}/download`}
                >
                  Download
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
