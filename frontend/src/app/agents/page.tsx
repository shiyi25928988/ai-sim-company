"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAgentsQuery } from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";
import { API_URL } from "@/lib/config";

const ROLES = ["ceo", "hr-director", "senior-engineer", "junior-engineer", "designer", "product-manager", "marketer", "data-analyst", "qa-engineer"];

interface CreateBody {
  name: string;
  role: string;
  department: string;
  salary: number;
}

const EMPTY: CreateBody = {
  name: "",
  role: "senior-engineer",
  department: "Engineering",
  salary: 80000,
};

/** /agents: agent list + hire form (POST /api/agents). */
export default function AgentsPage() {
  const { data: agents = [], isLoading } = useAgentsQuery();
  const qc = useQueryClient();
  const toast = useToastStore((s) => s.push);
  const [form, setForm] = useState<CreateBody>(EMPTY);
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
              if (!form.name.trim()) return;
              createMutation.mutate(form);
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
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
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
