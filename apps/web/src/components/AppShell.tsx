"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { api } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import { LoadingState } from "./ui";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/clients", label: "Clients" },
  { href: "/projects", label: "Projects" },
  { href: "/findings", label: "Finding inbox" },
  { href: "/audit", label: "Audit log" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me, isLoading, isError } = useMe();

  useEffect(() => {
    if (isError) router.replace("/login");
  }, [isError, router]);

  if (isLoading) return <LoadingState label="Loading your workspace…" />;
  if (!me) return null;

  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      router.replace("/login");
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold text-brand-700">ScopeGuard</span>
            <span className="hidden text-xs text-slate-400 sm:inline">
              evidence-backed billing review
            </span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {me.full_name} · <span className="text-slate-400">{me.role.replace(/_/g, " ")}</span>
            </span>
            <button className="btn-secondary" onClick={logout}>
              Log out
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-2" aria-label="Main">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${
                  active
                    ? "border-brand-600 text-brand-700"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
