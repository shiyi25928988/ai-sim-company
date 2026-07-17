"use client";

import { useLlmConfigQuery } from "@/hooks/useQueries";
import { Skeleton } from "@/components/Skeleton";

/** Settings page: LLM gateway config (routing/budget/usage) / simulation control / skill pool. */
export function SettingsPage() {
  const { data: cfg, isLoading, isError } = useLlmConfigQuery();

  return (
    <div className="pixel-panel space-y-4 p-4 text-sm">
      <section>
        <h3 className="mb-2 font-bold">LLM Gateway</h3>
        <p className="text-gray-400">
          API Key is configured once in Company Hub; the frontend never holds it.
        </p>
        {isLoading ? (
          <div className="mt-2 space-y-2">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-3 w-48" />
          </div>
        ) : isError ? (
          <p className="text-bad">Failed to load LLM config (is the backend running?).</p>
        ) : cfg ? (
          <div className="mt-2 space-y-1 text-xs">
            <div>Provider: {cfg.provider}</div>
            <div>Default model: {cfg.default_model}</div>
            <div>Daily budget: {cfg.daily_budget.toLocaleString()} tokens</div>
            <div>Usage today: {cfg.usage_today.toLocaleString()} tokens</div>
            <div className="mt-2">
              <div className="mb-1 text-gray-400">Role -&gt; model routing</div>
              <ul className="list-inside list-disc">
                {Object.entries(cfg.routing).map(([role, model]) => (
                  <li key={role}>
                    {role} -&gt; {model}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
      </section>
      <section>
        <h3 className="mb-2 font-bold">Simulation Control</h3>
        <p className="text-gray-400">(start/stop / speed / replay - see Console)</p>
      </section>
      <section>
        <h3 className="mb-2 font-bold">Skill Pool</h3>
        <p className="text-gray-400">
          <a href="/skills" className="text-cyan-300 hover:underline">Manage skills →</a> (upload / install / delete)
        </p>
      </section>
    </div>
  );
}
