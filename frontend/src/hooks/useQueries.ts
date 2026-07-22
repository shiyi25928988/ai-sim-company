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
  claude_code: {
    installed: boolean;
    enabled: boolean;
    path: string | null;
  };
}

export const useUpdateClaudeCodeMutation = () =>
  useMutation({
    mutationFn: async (enabled: boolean) => {
      const r = await fetch(`${API_URL}/api/llm/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claude_code_enabled: enabled }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "update failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["llm-config"] }),
  });

export interface CompanyConfig {
  name: string;
  business_description: string;
  initial_capital: number;
  monthly_budget: number; // 0 = unlimited
  workspace_dir: string;
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

export const useClearDataMutation = () =>
  useMutation({
    mutationFn: async () => {
      const r = await fetch(`${API_URL}/api/clear`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "clear failed");
      return j;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config"] });
      queryClient.invalidateQueries({ queryKey: ["state"] });
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      queryClient.invalidateQueries({ queryKey: ["files"] });
    },
  });

export interface SkillRequestBody {
  name: string;
  description: string;
  prompt_injection: string;
  category: string;
  level: string;
  scope: string[];
}

export const useSkillsQuery = () =>
  useQuery({
    queryKey: ["skills"],
    queryFn: () => fetchJson<Skill[]>("/api/skills"),
  });

export const useCreateSkillMutation = () =>
  useMutation({
    mutationFn: async (body: SkillRequestBody) => {
      const r = await fetch(`${API_URL}/api/skills`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "create skill failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
  });

export const useUploadSkillMutation = () =>
  useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch(`${API_URL}/api/skills/upload`, { method: "POST", body: form });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "upload failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
  });

export const useDeleteSkillMutation = () =>
  useMutation({
    mutationFn: async (skillId: string) => {
      const r = await fetch(`${API_URL}/api/skills/${skillId}`, { method: "DELETE" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "delete skill failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
  });

export const useUpdateSkillMutation = () =>
  useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Partial<SkillRequestBody> }) => {
      const r = await fetch(`${API_URL}/api/skills/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "update failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
  });

export const useImportSkillMutation = () =>
  useMutation({
    mutationFn: async (content: string) => {
      const r = await fetch(`${API_URL}/api/skills/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "import failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
  });

export const useInstallUrlSkillMutation = () =>
  useMutation({
    mutationFn: async (url: string) => {
      const r = await fetch(`${API_URL}/api/skills/install-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "install failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skills"] }),
  });

export interface WorkspaceEntry {
  name: string;
  is_dir: boolean;
}

export const useFilesQuery = (path: string, scope: string) =>
  useQuery({
    queryKey: ["files", scope, path],
    queryFn: () =>
      fetchJson<WorkspaceEntry[]>(
        `/api/files?path=${encodeURIComponent(path)}&scope=${scope}`,
      ),
  });

export const useFileContentQuery = (path: string, scope: string) =>
  useQuery({
    queryKey: ["file-content", scope, path],
    queryFn: () =>
      fetchJson<{ path: string; content: string }>(
        `/api/files/content?path=${encodeURIComponent(path)}&scope=${scope}`,
      ),
    enabled: !!path,
  });

export interface McpServer {
  name: string;
  transport: string;
  url: string | null;
  command: string | null;
  connected: boolean;
  tools: string[];
}

export interface McpServerBody {
  name: string;
  transport?: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
}

export const useMcpQuery = () =>
  useQuery({
    queryKey: ["mcp"],
    queryFn: () => fetchJson<{ servers: McpServer[] }>("/api/mcp"),
  });

export const useAddMcpMutation = () =>
  useMutation({
    mutationFn: async (body: McpServerBody) => {
      const r = await fetch(`${API_URL}/api/mcp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "add mcp failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mcp"] }),
  });

export const useDeleteMcpMutation = () =>
  useMutation({
    mutationFn: async (name: string) => {
      const r = await fetch(`${API_URL}/api/mcp/${name}`, { method: "DELETE" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "delete mcp failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mcp"] }),
  });

export const useConnectMcpMutation = () =>
  useMutation({
    mutationFn: async (name: string) => {
      const r = await fetch(`${API_URL}/api/mcp/${name}/connect`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "connect mcp failed");
      return j;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mcp"] }),
  });

export const useAddDirectiveMutation = () =>
  useMutation({
    mutationFn: async (text: string) => {
      const r = await fetch(`${API_URL}/api/ceo/directive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, step: true }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "directive failed");
      return j;
    },
  });
