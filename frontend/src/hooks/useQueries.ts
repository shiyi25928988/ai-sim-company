import { useMutation, useQuery } from "@tanstack/react-query";
import { API_URL } from "@/lib/config";
import { queryClient } from "@/lib/query-client";
import type { AgentState, GameSnapshot, Skill } from "@/types/game";

async function fetchJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return (await r.json()) as T;
}

export const useAgentsQuery = () =>
  useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchJson<AgentState[]>("/api/agents"),
  });

export const useStateQuery = () =>
  useQuery({
    queryKey: ["state"],
    queryFn: () => fetchJson<GameSnapshot>("/api/state"),
  });

export const useLlmConfigQuery = () =>
  useQuery({
    queryKey: ["llm-config"],
    queryFn: () => fetchJson<LlmConfig>("/api/llm/config"),
  });

export const useAgentSkillsQuery = (agentId: string | null) =>
  useQuery({
    queryKey: ["agent-skills", agentId],
    queryFn: () => fetchJson<Skill[]>(`/api/agents/${agentId}/skills`),
    enabled: !!agentId,
  });

export interface LlmConfig {
  provider: string;
  default_model: string;
  routing: Record<string, string>;
  daily_budget: number;
  usage_today: number;
}

export interface CompanyConfig {
  name: string;
  business_description: string;
  initial_capital: number;
  monthly_budget: number; // 0 = unlimited
}

export const useConfigQuery = () =>
  useQuery({
    queryKey: ["config"],
    queryFn: () => fetchJson<CompanyConfig>("/api/config"),
  });

export const useUpdateConfigMutation = () =>
  useMutation({
    mutationFn: async (body: CompanyConfig) => {
      const r = await fetch(`${API_URL}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "config update failed");
      return j;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config"] });
      queryClient.invalidateQueries({ queryKey: ["state"] });
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
