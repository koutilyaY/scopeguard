"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useContracts, useDocuments, useMe, useProject, useReviewRuns } from "@/lib/hooks";
import { Badge, BackLink, Disclaimer, ErrorState, LoadingState } from "@/components/ui";
import { DocumentsTab } from "@/components/project/DocumentsTab";
import { ContractsTab } from "@/components/project/ContractsTab";
import { ImportsTab } from "@/components/project/ImportsTab";
import { ReviewTab } from "@/components/project/ReviewTab";

const TABS = ["Documents", "Contracts", "Imports", "Reviews"] as const;
type Tab = (typeof TABS)[number];

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading, isError } = useProject(id);
  const [tab, setTab] = useState<Tab>("Documents");

  if (isLoading) return <LoadingState />;
  if (isError || !project) return <ErrorState message="Could not load this project." />;

  return (
    <div className="space-y-4">
      <BackLink href="/projects">All projects</BackLink>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          <p className="text-sm text-slate-500">
            {project.currency} · {project.status.replace(/_/g, " ")}
          </p>
        </div>
        <Badge value={project.status} />
      </div>

      <div className="flex gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Documents" && <DocumentsTab projectId={id} clientId={project.client_id} />}
      {tab === "Contracts" && <ContractsTab projectId={id} clientId={project.client_id} />}
      {tab === "Imports" && <ImportsTab projectId={id} />}
      {tab === "Reviews" && <ReviewTab projectId={id} />}

      <Disclaimer />
    </div>
  );
}
