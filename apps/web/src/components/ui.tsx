"use client";

import Link from "next/link";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-slate-500" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      className="m-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      role="alert"
    >
      {message}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

const BADGE_COLORS: Record<string, string> = {
  // classifications
  in_scope: "bg-green-100 text-green-800",
  potentially_out_of_scope: "bg-amber-100 text-amber-800",
  clearly_out_of_scope: "bg-red-100 text-red-800",
  insufficient_information: "bg-slate-100 text-slate-700",
  // review status
  pending: "bg-blue-100 text-blue-800",
  approved_for_followup: "bg-indigo-100 text-indigo-800",
  approved_for_billing: "bg-green-100 text-green-800",
  rejected: "bg-slate-200 text-slate-700",
  needs_more_evidence: "bg-amber-100 text-amber-800",
  already_resolved: "bg-slate-100 text-slate-600",
  // risk
  low: "bg-slate-100 text-slate-700",
  medium: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
  // run status
  completed: "bg-green-100 text-green-800",
  running: "bg-blue-100 text-blue-800",
  failed: "bg-red-100 text-red-800",
  completed_with_errors: "bg-amber-100 text-amber-800",
};

export function Badge({ value }: { value: string }) {
  const color = BADGE_COLORS[value] ?? "bg-slate-100 text-slate-700";
  return <span className={`badge ${color}`}>{value.replace(/_/g, " ")}</span>;
}

export function Disclaimer({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs text-slate-500 ${className}`}>
      ScopeGuard provides operational review assistance. Findings are{" "}
      <strong>not legal or accounting advice</strong>; contract interpretation may be ambiguous and
      human verification is required. Potential value does not equal invoiced or collected revenue.
    </p>
  );
}

export function ConfirmButton({
  onConfirm,
  label,
  confirmLabel = "Are you sure? Click again",
  className = "btn-danger",
}: {
  onConfirm: () => void;
  label: string;
  confirmLabel?: string;
  className?: string;
}) {
  return (
    <button
      className={className}
      onClick={(e) => {
        const el = e.currentTarget;
        if (el.dataset.armed === "1") {
          onConfirm();
          el.dataset.armed = "0";
        } else {
          el.dataset.armed = "1";
          el.textContent = confirmLabel;
          setTimeout(() => {
            el.dataset.armed = "0";
            el.textContent = label;
          }, 3000);
        }
      }}
    >
      {label}
    </button>
  );
}

export function BackLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-sm text-brand-600 hover:underline">
      ← {children}
    </Link>
  );
}
