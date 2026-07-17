"use client";

import { useState } from "react";
import { useFilesQuery, useFileContentQuery } from "@/hooks/useQueries";

/** /files: browse the workspace (shared/ or personal/) produced by agents. */
export default function FilesPage() {
  const [scope, setScope] = useState<"shared" | "personal">("shared");
  const [path, setPath] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const { data: entries = [], isLoading } = useFilesQuery(path, scope);
  const { data: fileData } = useFileContentQuery(selected ?? "", scope);

  const navigate = (name: string, isDir: boolean) => {
    const next = path ? `${path}/${name}` : name;
    if (isDir) {
      setPath(next);
      setSelected(null);
    } else {
      setSelected(next);
    }
  };

  const crumbs = path ? path.split("/") : [];

  return (
    <main className="h-full overflow-auto p-4">
      <div className="pixel-panel grid grid-cols-1 gap-3 p-3 text-sm md:grid-cols-[1fr_1.5fr]">
        <section className="min-h-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <strong>Workspace</strong>
            <select
              className="rounded border border-gray-600 bg-black/40 px-1 py-0.5 text-xs"
              value={scope}
              onChange={(e) => {
                setScope(e.target.value as "shared" | "personal");
                setPath("");
                setSelected(null);
              }}
            >
              <option value="shared">shared</option>
              <option value="personal">personal</option>
            </select>
            <button
              className="text-xs text-gray-500 hover:text-gray-300"
              onClick={() => setPath("")}
            >
              root
            </button>
            {crumbs.map((c, i) => (
              <button
                key={i}
                className="text-xs text-cyan-300 hover:underline"
                onClick={() => {
                  setPath(crumbs.slice(0, i + 1).join("/"));
                  setSelected(null);
                }}
              >
                / {c}
              </button>
            ))}
          </div>
          {isLoading ? (
            <div className="text-gray-500">Loading…</div>
          ) : entries.length === 0 ? (
            <div className="italic text-gray-500">(empty)</div>
          ) : (
            <ul className="text-xs">
              {entries.map((e) => (
                <li key={e.name}>
                  <button
                    className="block w-full py-0.5 text-left hover:text-cyan-300"
                    onClick={() => navigate(e.name, e.is_dir)}
                  >
                    {e.is_dir ? "📁 " : "📄 "}
                    {e.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="min-h-0 border-gray-700 pl-0 md:border-l md:pl-3">
          <div className="mb-2 text-gray-400">{selected ?? "(select a file)"}</div>
          {fileData ? (
            <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap break-all text-xs text-gray-300">
              {fileData.content}
            </pre>
          ) : (
            <div className="text-gray-500">No file selected.</div>
          )}
        </section>
      </div>
    </main>
  );
}
