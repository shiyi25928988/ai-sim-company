"use client";

import { useState } from "react";
import {
  useSkillsQuery,
  useCreateSkillMutation,
  useUploadSkillMutation,
  useDeleteSkillMutation,
  type SkillRequestBody,
} from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";

const CATEGORIES = ["technical", "management", "creative", "operations"];
const LEVELS = ["company", "department", "role", "personal"];

const EMPTY: SkillRequestBody = {
  name: "",
  description: "",
  prompt_injection: "",
  category: "technical",
  level: "company",
  scope: [],
};

/** /skills: list + create + upload package + delete. */
export default function SkillsPage() {
  const { data: skills = [], isLoading } = useSkillsQuery();
  const toast = useToastStore((s) => s.push);
  const [form, setForm] = useState<SkillRequestBody>(EMPTY);
  const [scopeText, setScopeText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMut = useCreateSkillMutation();
  const uploadMut = useUploadSkillMutation();
  const deleteMut = useDeleteSkillMutation();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.prompt_injection.trim()) {
      setError("Name and prompt_injection are required.");
      return;
    }
    setError(null);
    const scope =
      form.level === "company"
        ? []
        : scopeText.split(",").map((s) => s.trim()).filter(Boolean);
    createMut.mutate(
      { ...form, scope },
      {
        onSuccess: () => {
          toast(`Skill "${form.name}" created.`, "success");
          setForm(EMPTY);
          setScopeText("");
        },
        onError: (err: Error) => {
          setError(err.message);
          toast(err.message, "error");
        },
      },
    );
  };

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    uploadMut.mutate(f, {
      onSuccess: () => toast(`Uploaded ${f.name}.`, "success"),
      onError: (err: Error) => toast(err.message, "error"),
    });
    e.target.value = "";
  };

  return (
    <main className="h-full overflow-auto p-4">
      <div className="grid gap-4 md:grid-cols-[1fr_24rem]">
        <section className="pixel-panel p-3 text-sm">
          <h2 className="mb-2 text-base font-bold">Skills ({skills.length})</h2>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : skills.length === 0 ? (
            <p className="italic text-gray-500">(none)</p>
          ) : (
            <ul className="space-y-2 text-xs">
              {skills.map((s) => (
                <li key={s.id} className="border-l-2 border-purple-700 pl-2">
                  <div className="flex items-center justify-between">
                    <strong>{s.name}</strong>
                    <button
                      className="text-bad hover:text-red-300"
                      aria-label={`Delete ${s.name}`}
                      onClick={() =>
                        deleteMut.mutate(s.id, {
                          onSuccess: () => toast(`Deleted ${s.name}`, "info"),
                          onError: (e: Error) => toast(e.message, "error"),
                        })
                      }
                    >
                      ✕
                    </button>
                  </div>
                  <div className="text-gray-500">
                    [{s.level}] {s.category} · scope: {s.scope.join(", ") || "(all)"} · {s.status}
                  </div>
                  {s.description && <div className="text-gray-400">{s.description}</div>}
                  {s.prompt_injection && (
                    <div className="text-gray-600">prompt: {s.prompt_injection.slice(0, 100)}</div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="pixel-panel space-y-3 p-3 text-sm">
          <div>
            <h2 className="mb-2 text-base font-bold">Create Skill</h2>
            <form className="space-y-2 text-xs" onSubmit={submit}>
              <label className="block">
                Name
                <input
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Deployment Checklist"
                />
              </label>
              <label className="block">
                Description
                <input
                  className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </label>
              <label className="block">
                Prompt injection (injected into agent system prompt)
                <textarea
                  className="mt-1 h-20 w-full resize-y rounded border border-gray-600 bg-black/40 px-2 py-1"
                  value={form.prompt_injection}
                  onChange={(e) => setForm({ ...form, prompt_injection: e.target.value })}
                  placeholder="e.g. Run all tests before deploy; never push to main directly."
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  Category
                  <select
                    className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  Level
                  <select
                    className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                    value={form.level}
                    onChange={(e) => setForm({ ...form, level: e.target.value })}
                  >
                    {LEVELS.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {form.level !== "company" && (
                <label className="block">
                  Scope (
                  {form.level === "department"
                    ? "department names"
                    : form.level === "role"
                      ? "role names"
                      : "agent_ids"}
                  , comma-separated)
                  <input
                    className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
                    value={scopeText}
                    onChange={(e) => setScopeText(e.target.value)}
                    placeholder={
                      form.level === "department"
                        ? "Engineering, Design"
                        : form.level === "role"
                          ? "senior-engineer, junior-engineer"
                          : "ceo-alex, eng-jordan"
                    }
                  />
                </label>
              )}
              {error && <p className="text-bad">{error}</p>}
              <button
                type="submit"
                className="pixel-panel w-full py-1 hover:text-cyan-300"
                disabled={createMut.isPending}
              >
                {createMut.isPending ? "Creating…" : "Create Skill"}
              </button>
            </form>
          </div>

          <div className="border-t border-gray-700 pt-3">
            <h2 className="mb-1 text-base font-bold">Upload Skill Package</h2>
            <p className="mb-2 text-xs text-gray-500">
              .zip with skill.json (or skill.yaml) + optional prompt.md
            </p>
            <input
              type="file"
              accept=".zip"
              onChange={onUpload}
              disabled={uploadMut.isPending}
              className="block w-full text-xs"
            />
            {uploadMut.isPending && <p className="mt-1 text-xs text-gray-500">Uploading…</p>}
          </div>
        </section>
      </div>
    </main>
  );
}
