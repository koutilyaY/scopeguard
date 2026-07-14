"use client";

import { useRef, useState } from "react";

import { api } from "@/lib/api";
import type { ImportPreview } from "@/lib/types";

const IMPORT_TYPES = [
  { key: "work_items", label: "Jira work items (CSV)" },
  { key: "time_entries", label: "Timesheets (CSV / XLSX)" },
  { key: "invoices", label: "Invoices (CSV)" },
];

export function ImportsTab({ projectId }: { projectId: string }) {
  const [importType, setImportType] = useState("time_entries");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [committed, setCommitted] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function doPreview() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setCommitted(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await api.post<ImportPreview>(`/imports/${importType}/preview`, form);
      setPreview(res);
    } catch (err) {
      setCommitted(err instanceof Error ? err.message : "Preview failed.");
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  async function doCommit() {
    const file = fileRef.current?.files?.[0];
    if (!file || !preview) return;
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    form.append("project_id", projectId);
    form.append("mapping", JSON.stringify(preview.suggested_mapping));
    try {
      const res = await api.post<{ created: number; skipped_duplicates: number }>(
        `/imports/${importType}/commit`,
        form,
      );
      setCommitted(
        `Imported ${res.created} row(s); skipped ${res.skipped_duplicates} duplicate(s).`,
      );
      setPreview(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setCommitted(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-3 p-4">
        <h3 className="font-medium">Import operational data</h3>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="label" htmlFor="itype">
              Import type
            </label>
            <select
              id="itype"
              className="input"
              value={importType}
              onChange={(e) => {
                setImportType(e.target.value);
                setPreview(null);
              }}
            >
              {IMPORT_TYPES.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <input ref={fileRef} type="file" className="text-sm" aria-label="Import file" />
          <button className="btn-secondary" onClick={doPreview} disabled={busy}>
            Preview
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Preview validates every row and shows errors before anything is written.
        </p>
      </div>

      {preview && (
        <div className="card space-y-3 p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">
              Preview: {preview.valid_rows} valid of {preview.total_rows} rows
            </h3>
            <button
              className="btn-primary"
              onClick={doCommit}
              disabled={busy || preview.valid_rows === 0}
            >
              Import {preview.valid_rows} valid row(s)
            </button>
          </div>

          <div>
            <p className="mb-1 text-sm font-medium text-slate-600">Column mapping</p>
            <div className="flex flex-wrap gap-2 text-xs">
              {Object.entries(preview.suggested_mapping).map(([field, col]) => (
                <span key={field} className="rounded bg-slate-100 px-2 py-1">
                  {field} ← <strong>{col}</strong>
                </span>
              ))}
            </div>
          </div>

          {preview.errors.length > 0 && (
            <div>
              <p className="mb-1 text-sm font-medium text-red-700">
                {preview.errors.length} row error(s) — these rows will be skipped
              </p>
              <div className="max-h-48 overflow-auto rounded border border-red-100">
                <table className="w-full text-left text-xs">
                  <thead className="bg-red-50 text-red-700">
                    <tr>
                      <th className="px-2 py-1">Row</th>
                      <th className="px-2 py-1">Field</th>
                      <th className="px-2 py-1">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.errors.map((e, i) => (
                      <tr key={i} className="border-t border-red-100">
                        <td className="px-2 py-1">{e.row}</td>
                        <td className="px-2 py-1">{e.field}</td>
                        <td className="px-2 py-1">{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {preview.warnings.length > 0 && (
            <details className="text-xs text-amber-700">
              <summary>{preview.warnings.length} warning(s)</summary>
              <ul className="mt-1 list-disc pl-5">
                {preview.warnings.map((w, i) => (
                  <li key={i}>
                    Row {w.row}: {w.message}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {committed && (
        <p className="rounded-md bg-slate-50 p-3 text-sm text-slate-700">{committed}</p>
      )}
    </div>
  );
}
