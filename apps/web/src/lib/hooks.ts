// TanStack Query hooks wrapping the API client.
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api";
import type {
  AuditEvent,
  Client,
  Clause,
  Contract,
  Dashboard,
  Document,
  Finding,
  FindingDetail,
  Page,
  Project,
  ReviewRun,
  User,
} from "./types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<User>("/auth/me"),
    retry: false,
  });
}

export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<Dashboard>("/dashboard") });
}

export function useClients() {
  return useQuery({
    queryKey: ["clients"],
    queryFn: () => api.get<Page<Client>>("/clients?page_size=100"),
  });
}

export function useProjects(clientId?: string) {
  return useQuery({
    queryKey: ["projects", clientId ?? "all"],
    queryFn: () =>
      api.get<Page<Project>>(`/projects?page_size=100${clientId ? `&client_id=${clientId}` : ""}`),
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.get<Project>(`/projects/${projectId}`),
  });
}

export function useDocuments(projectId?: string) {
  return useQuery({
    queryKey: ["documents", projectId ?? "all"],
    queryFn: () =>
      api.get<Page<Document>>(
        `/documents?page_size=100${projectId ? `&project_id=${projectId}` : ""}`,
      ),
  });
}

export function useContracts(projectId?: string) {
  return useQuery({
    queryKey: ["contracts", projectId ?? "all"],
    queryFn: () =>
      api.get<Page<Contract>>(
        `/contracts?page_size=100${projectId ? `&project_id=${projectId}` : ""}`,
      ),
  });
}

export function useClauses(contractId: string) {
  return useQuery({
    queryKey: ["clauses", contractId],
    queryFn: () => api.get<Page<Clause>>(`/clauses?contract_id=${contractId}&page_size=200`),
    enabled: !!contractId,
  });
}

export function useReviewRuns(projectId?: string) {
  return useQuery({
    queryKey: ["review-runs", projectId ?? "all"],
    queryFn: () =>
      api.get<Page<ReviewRun>>(
        `/review-runs?page_size=50${projectId ? `&project_id=${projectId}` : ""}`,
      ),
  });
}

export function useReviewRun(runId: string, poll: boolean) {
  return useQuery({
    queryKey: ["review-run", runId],
    queryFn: () => api.get<ReviewRun>(`/review-runs/${runId}`),
    refetchInterval: poll ? 1500 : false,
  });
}

export function useFindings(params: Record<string, string>) {
  const qs = new URLSearchParams({ page_size: "100", ...params }).toString();
  return useQuery({
    queryKey: ["findings", qs],
    queryFn: () => api.get<Page<Finding>>(`/findings?${qs}`),
  });
}

export function useFinding(findingId: string) {
  return useQuery({
    queryKey: ["finding", findingId],
    queryFn: () => api.get<FindingDetail>(`/findings/${findingId}`),
    enabled: !!findingId,
  });
}

export function useAuditEvents() {
  return useQuery({
    queryKey: ["audit-events"],
    queryFn: () => api.get<Page<AuditEvent>>("/audit-events?page_size=100"),
  });
}

export function useDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { finding_id: string; new_status: string; reason: string }) =>
      api.post<Finding>("/decisions", input),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: ["finding", input.finding_id] });
      qc.invalidateQueries({ queryKey: ["findings"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
