"use client";

import { useLlmConfigQuery, useUpdateClaudeCodeMutation } from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";

/** Settings page: LLM gateway / Claude Code / simulation control / skill pool. */
export function SettingsPage() {
  const { data: cfg, isLoading, isError } = useLlmConfigQuery();
  const toast = useToastStore((s) => s.push);
  const updateClaudeCode = useUpdateClaudeCodeMutation();

  const toggleClaudeCode = (enabled: boolean) => {
    updateClaudeCode.mutate(enabled, {
      onSuccess: () =>
        toast(`Claude Code ${enabled ? "enabled" : "disabled"}`, "success"),
      onError: (e: Error) => toast(e.message, "error"),
    });
  };

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
        <h3 className="mb-2 font-bold">Claude Code</h3>
        {isLoading ? (
          <Skeleton className="h-4 w-48" />
        ) : cfg?.claude_code ? (
          <div className="space-y-1 text-xs">
            <div>
              {cfg.claude_code.installed ? "✅" : "❌"} Installed:{" "}
              {cfg.claude_code.installed
                ? cfg.claude_code.path
                : "Claude Code CLI not found in PATH"}
            </div>
            {cfg.claude_code.installed && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={cfg.claude_code.enabled}
                  onChange={(e) => toggleClaudeCode(e.target.checked)}
                  disabled={updateClaudeCode.isPending}
                />
                Enable (engineers/designers can invoke run_claude_code)
              </label>
            )}
          </div>
        ) : (
          <p className="text-gray-500">Unavailable.</p>
        )}
      </section>

      <section>
        <h3 className="mb-2 font-bold">Simulation Control</h3>
        <p className="text-gray-400">(start/stop / speed / replay - see Console)</p>
      </section>
      <section>
        <h3 className="mb-2 font-bold">Skill Pool</h3>
        <p className="text-gray-400">
          <a href="/skills" className="text-cyan-300 hover:underline">
            Manage skills -&gt;
          </a>{" "}
          (upload / install / delete)
        </p>
      </section>
    </div>
  );
}
