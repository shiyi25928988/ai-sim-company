"use client";

import { useState } from "react";
import {
  useMcpQuery,
  useAddMcpMutation,
  useDeleteMcpMutation,
  useConnectMcpMutation,
  type McpServerBody,
} from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";

const TRANSPORTS = ["stdio", "sse", "streamableHttp"];
type Tab = "form" | "paste";

/** /mcp: configure external MCP servers (form or paste JSON), stdio/sse/streamableHttp. */
export default function McpPage() {
  const { data, isLoading } = useMcpQuery();
  const toast = useToastStore((s) => s.push);
  const addMut = useAddMcpMutation();
  const deleteMut = useDeleteMcpMutation();
  const connectMut = useConnectMcpMutation();
  const [tab, setTab] = useState<Tab>("form");
  const [form, setForm] = useState<McpServerBody>({
    name: "",
    transport: "stdio",
    command: "",
    url: "",
  });
  const [pasteText, setPasteText] = useState("");

  const submitForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    addMut.mutate(form, {
      onSuccess: () => {
        toast(`MCP server "${form.name}" added.`, "success");
        setForm({ name: "", transport: "stdio", command: "", url: "" });
      },
      onError: (e: Error) => toast(e.message, "error"),
    });
  };

  const submitPaste = () => {
    let body: McpServerBody;
    try {
      body = JSON.parse(pasteText);
    } catch {
      toast("Invalid JSON", "error");
      return;
    }
    if (!body.name) {
      toast("name is required", "error");
      return;
    }
    addMut.mutate(body, {
      onSuccess: () => {
        toast(`MCP server "${body.name}" added.`, "success");
        setPasteText("");
      },
      onError: (e: Error) => toast(e.message, "error"),
    });
  };

  return (
    <main className="h-full overflow-auto p-4">
      <div className="grid gap-4 md:grid-cols-[1fr_24rem]">
        <section className="pixel-panel p-3 text-sm">
          <h2 className="mb-2 text-base font-bold">MCP Servers ({data?.servers?.length ?? 0})</h2>
          <p className="mb-2 text-xs text-gray-500">
            Tools exposed to all agents as mcp_&#123;server&#125;_&#123;tool&#125;.
          </p>
          {isLoading ? (
            <Skeleton className="h-8 w-full" />
          ) : data?.servers?.length ? (
            <ul className="space-y-2 text-xs">
              {data.servers.map((s) => (
                <li key={s.name} className="border-l-2 border-cyan-700 pl-2">
                  <div className="flex items-center justify-between">
                    <strong>{s.name}</strong>
                    <span className="flex gap-2">
                      <button
                        className="hover:text-cyan-300"
                        aria-label="Reconnect"
                        onClick={() =>
                          connectMut.mutate(s.name, {
                            onSuccess: () => toast(`Reconnected ${s.name}`, "info"),
                            onError: (e: Error) => toast(e.message, "error"),
                          })
                        }
                      >
                        ⟳
                      </button>
                      <button
                        className="text-bad hover:text-red-300"
                        aria-label={`Remove ${s.name}`}
                        onClick={() =>
                          deleteMut.mutate(s.name, {
                            onSuccess: () => toast(`Removed ${s.name}`, "info"),
                            onError: (e: Error) => toast(e.message, "error"),
                          })
                        }
                      >
                        ✕
                      </button>
                    </span>
                  </div>
                  <div className="text-gray-500">
                    {s.transport} · {s.connected ? "✅ connected" : "❌ disconnected"} · {s.tools.length} tools
                  </div>
                  {s.tools.length > 0 && (
                    <div className="text-gray-600">{s.tools.join(", ")}</div>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-gray-500">(no MCP servers)</p>
          )}
        </section>

        <section className="pixel-panel p-3 text-sm">
          <div className="mb-3 flex gap-3 border-b border-gray-700 pb-1 text-xs">
            {(["form", "paste"] as const).map((t) => (
              <button
                key={t}
                className={tab === t ? "text-cyan-300" : "text-gray-500 hover:text-gray-300"}
                onClick={() => setTab(t)}
              >
                {t === "form" ? "Form" : "Paste JSON"}
              </button>
            ))}
          </div>

          {tab === "form" ? (
            <form className="space-y-2 text-xs" onSubmit={submitForm}>
              <label className="block">
                Name
                <input
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="filesystem"
                />
              </label>
              <label className="block">
                Transport
                <select
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.transport}
                  onChange={(e) => setForm({ ...form, transport: e.target.value })}
                >
                  {TRANSPORTS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </label>
              {form.transport === "stdio" ? (
                <label className="block">
                  Command (shell-style)
                  <input
                    className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                    value={form.command}
                    onChange={(e) => setForm({ ...form, command: e.target.value })}
                    placeholder="npx -y @modelcontextprotocol/server-filesystem /tmp"
                  />
                </label>
              ) : (
                <label className="block">
                  URL ({form.transport})
                  <input
                    className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                    placeholder="http://localhost:8080/sse"
                  />
                </label>
              )}
              <button
                type="submit"
                className="pixel-panel w-full py-1 hover:text-cyan-300"
                disabled={addMut.isPending}
              >
                {addMut.isPending ? "Adding…" : "Add MCP Server"}
              </button>
            </form>
          ) : (
            <div className="space-y-2 text-xs">
              <p className="text-gray-500">
                Paste an MCP server config (JSON). Supports stdio / sse / streamableHttp.
              </p>
              <textarea
                className="h-40 w-full resize-y rounded border border-gray-600 bg-black/40 px-2 py-1 font-mono"
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder={'{\n  "name": "filesystem",\n  "transport": "stdio",\n  "command": "npx -y @modelcontextprotocol/server-filesystem /tmp"\n}\n\n// sse / streamableHttp:\n// {\n//   "name": "remote",\n//   "transport": "streamableHttp",\n//   "url": "http://localhost:8080/mcp"\n// }'}
              />
              <button
                className="pixel-panel w-full py-1 hover:text-cyan-300"
                disabled={addMut.isPending || !pasteText.trim()}
                onClick={submitPaste}
              >
                {addMut.isPending ? "Adding…" : "Add"}
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
