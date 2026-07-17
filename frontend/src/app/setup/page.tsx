"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useConfigQuery,
  useUpdateConfigMutation,
  type CompanyConfig,
} from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";

const EMPTY: CompanyConfig = {
  name: "",
  business_description: "",
  initial_capital: 500_000,
  monthly_budget: 0,
  workspace_dir: "data/workspace",
};

/** /setup: configure the company's business + budget; submitting hot-reloads the Hub. */
export default function SetupPage() {
  const { data: cfg, isLoading } = useConfigQuery();
  const router = useRouter();
  const toast = useToastStore((s) => s.push);
  const [form, setForm] = useState<CompanyConfig>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cfg) setForm(cfg);
  }, [cfg]);

  const mutation = useUpdateConfigMutation();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Company name is required.");
      return;
    }
    setError(null);
    mutation.mutate(form, {
      onSuccess: () => {
        toast("Configuration applied; simulation reset.", "success");
        router.push("/");
      },
      onError: (err: Error) => {
        setError(err.message);
        toast(err.message, "error");
      },
    });
  };

  return (
    <main className="h-full overflow-auto p-4">
      <div className="pixel-panel mx-auto max-w-2xl space-y-4 p-4 text-sm">
        <h2 className="text-base font-bold">Business Setup</h2>
        <p className="text-xs text-gray-400">
          Configure the company&rsquo;s business and budget. Submitting resets the simulation and
          re-seeds the CEO, who then runs the business autonomously based on the description below.
        </p>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-4 w-32" />
          </div>
        ) : (
          <form className="space-y-3 text-xs" onSubmit={submit}>
            <label className="block">
              Company name
              <input
                className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Acme AI Inc."
              />
            </label>
            <label className="block">
              Business description
              <textarea
                className="mt-1 h-24 w-full resize-y rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.business_description}
                onChange={(e) => setForm({ ...form, business_description: e.target.value })}
                placeholder="e.g. Build and sell a SaaS tool for automated customer support. Target: small tech teams."
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                Initial capital ($)
                <input
                  type="number"
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.initial_capital}
                  onChange={(e) =>
                    setForm({ ...form, initial_capital: Number(e.target.value) })
                  }
                />
              </label>
              <label className="block">
                Monthly budget cap ($, 0 = unlimited)
                <input
                  type="number"
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.monthly_budget}
                  onChange={(e) =>
                    setForm({ ...form, monthly_budget: Number(e.target.value) })
                  }
                />
              </label>
            </div>
            <label className="block">
              Workspace directory (where produced files are saved)
              <input
                className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                value={form.workspace_dir}
                onChange={(e) =>
                  setForm({ ...form, workspace_dir: e.target.value })
                }
                placeholder="e.g. data/workspace or D:/workspace/demo-ai"
              />
            </label>
            {error && <p className="text-bad">{error}</p>}
            <button
              type="submit"
              className="pixel-panel w-full py-1 hover:text-cyan-300"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Applying…" : "Apply & Reset Simulation"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
