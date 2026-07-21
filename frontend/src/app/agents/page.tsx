"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAgentsQuery } from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";
import { API_URL } from "@/lib/config";

const ROLES = ["ceo", "hr-director", "senior-engineer", "junior-engineer", "designer", "product-manager", "marketer", "data-analyst", "qa-engineer"];
const CUSTOM_ROLE = "__custom__";

interface CreateBody {
  name: string;
  role: string;
  department: string;
  salary: number;
  description: string;
}

interface FormState {
  name: string;
  roleSelect: string;
  customRole: string;
  department: string;
  salary: number;
  description: string;
}

const EMPTY: FormState = {
  name: "",
  roleSelect: "senior-engineer",
  customRole: "",
  department: "Engineering",
  salary: 80000,
  description: "",
};

/** /agents: agent list + hire form (POST /api/agents). */
export default function AgentsPage() {
  const { data: agents = [], isLoading } = useAgentsQuery();
  const qc = useQueryClient();
  const toast = useToastStore((s) => s.push);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation<unknown, Error, CreateBody>({
    mutationFn: async (body) => {
      const r = await fetch(`${API_URL}/api/agents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "create failed");
      return j;
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      setForm(EMPTY);
      setError(null);
      toast(`Hired ${variables.name}`, "success");
    },
    onError: (e) => {
      setError(e.message);
      toast(e.message, "error");
    },
  });

  return (
    <main className="h-full overflow-auto p-4">
      <div className="grid gap-4 md:grid-cols-[1fr_24rem]">
        <section className="pixel-panel p-3 text-sm">
          <h2 className="mb-2 text-base font-bold">Agents ({agents.length})</h2>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-4 w-56" />
              ))}
            </div>
          ) : agents.length === 0 ? (
            <p className="italic text-gray-500">(none)</p>
          ) : (
            <ul className="space-y-1 text-xs">
              {agents.map((a) => (
                <li
                  key={a.agent_id}
                  className="flex justify-between border-l-2 border-cyan-700 pl-2"
                >
                  <Link href={`/agents/${a.agent_id}`} className="hover:text-cyan-300">
                    {a.name} <span className="text-gray-500">({a.role})</span>
                  </Link>
                  <span className="text-gray-500">{a.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="pixel-panel p-3 text-sm">
          <h2 className="mb-2 text-base font-bold">Hire Agent</h2>
          <form
            className="space-y-2 text-xs"
            onSubmit={(e) => {
              e.preventDefault();
              const role = form.roleSelect === CUSTOM_ROLE ? form.customRole.trim() : form.roleSelect;
              if (!form.name.trim() || !role) {
                setError("Name and role are required.");
                return;
              }
              createMutation.mutate({
                name: form.name,
                role,
                department: form.department,
                salary: form.salary,
                description: form.description,
              });
            }}
          >
            <label className="block">
              Name
              <input
                className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Jordan"
              />
            </label>
            <label className="block">
              Role
              <select
                className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.roleSelect}
                onChange={(e) => setForm({ ...form, roleSelect: e.target.value })}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
                <option value={CUSTOM_ROLE}>Custom…</option>
              </select>
            </label>
            {form.roleSelect === CUSTOM_ROLE && (
              <label className="block">
                Custom role name
                <input
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.customRole}
                  onChange={(e) => setForm({ ...form, customRole: e.target.value })}
                  placeholder="e.g. data-scientist"
                />
              </label>
            )}
            <label className="block">
              Department
              <input
                className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </label>
            <label className="block">
              Salary
              <input
                type="number"
                className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.salary}
                onChange={(e) => setForm({ ...form, salary: Number(e.target.value) })}
              />
            </label>
            <label className="block">
              Description (markdown)
              <textarea
                className="mt-1 h-24 w-full resize-y rounded border border-gray-600 bg-black/40 px-2 py-1 font-mono"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder={"Optional. Becomes the agent's system prompt. For custom roles, describe responsibilities & behavior.\ne.g.\n- Analyze large datasets and build models\n- Report findings via send_message"}
              />
            </label>
            {error && <p className="text-bad">{error}</p>}
            <button
              type="submit"
              className="pixel-panel w-full py-1 hover:text-cyan-300"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Hiring…" : "Hire"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
