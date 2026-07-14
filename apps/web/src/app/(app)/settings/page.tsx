"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import { Disclaimer, LoadingState } from "@/components/ui";

export default function SettingsPage() {
  const { data: me, isLoading } = useMe();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [ollama, setOllama] = useState<null | {
    reachable: boolean;
    missing_models: string[];
    install_commands: string[];
    message: string;
  }>(null);

  if (isLoading) return <LoadingState />;

  async function changePassword() {
    setMsg(null);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      setMsg("Password changed. You will need to sign in again.");
      setCurrent("");
      setNext("");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Could not change password.");
    }
  }

  async function checkOllama() {
    const res = await api.get<typeof ollama>("/health/ollama");
    setOllama(res);
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <div className="card p-4">
        <h2 className="font-medium">Account</h2>
        <p className="mt-1 text-sm text-slate-600">
          {me?.full_name} · {me?.email} · {me?.role.replace(/_/g, " ")}
        </p>
      </div>

      <div className="card space-y-3 p-4">
        <h2 className="font-medium">Change password</h2>
        <input
          className="input"
          type="password"
          placeholder="Current password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
        />
        <input
          className="input"
          type="password"
          placeholder="New password (min 12 chars, mixed case, a digit)"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
        />
        <button className="btn-primary" onClick={changePassword} disabled={!current || !next}>
          Change password
        </button>
        {msg && <p className="text-sm text-slate-600">{msg}</p>}
      </div>

      <div className="card space-y-3 p-4">
        <h2 className="font-medium">Local AI model status</h2>
        <p className="text-sm text-slate-500">
          ScopeGuard uses a local Ollama model. Check which configured models are installed.
        </p>
        <button className="btn-secondary" onClick={checkOllama}>
          Check Ollama models
        </button>
        {ollama && (
          <div className="rounded bg-slate-50 p-3 text-sm">
            <p className={ollama.reachable ? "text-green-700" : "text-red-700"}>{ollama.message}</p>
            {ollama.install_commands.length > 0 && (
              <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-2 text-xs text-slate-100">
                {ollama.install_commands.join("\n")}
              </pre>
            )}
          </div>
        )}
      </div>

      <Disclaimer />
    </div>
  );
}
