"use client";

import { useState } from "react";
import {
  useSkillsQuery,
  useCreateSkillMutation,
  useUploadSkillMutation,
  useImportSkillMutation,
  useInstallUrlSkillMutation,
  useDeleteSkillMutation,
  useUpdateSkillMutation,
  type SkillRequestBody,
} from "@/hooks/useQueries";
import { useToastStore } from "@/store/useToastStore";
import { Skeleton } from "@/components/Skeleton";
import type { Skill } from "@/types/game";

const CATEGORIES = ["technical", "management", "creative", "operations"];
const LEVELS = ["company", "department", "role", "personal"];
type InstallTab = "create" | "paste" | "url" | "upload";

const EMPTY: SkillRequestBody = {
  name: "",
  description: "",
  prompt_injection: "",
  category: "technical",
  level: "company",
  scope: [],
};

/** /skills: list (click to edit) + install (create / paste / url / upload) + delete. */
export default function SkillsPage() {
  const { data: skills = [], isLoading } = useSkillsQuery();
  const toast = useToastStore((s) => s.push);
  const [tab, setTab] = useState<InstallTab>("create");
  const [form, setForm] = useState<SkillRequestBody>(EMPTY);
  const [scopeText, setScopeText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Skill | null>(null);

  const createMut = useCreateSkillMutation();
  const uploadMut = useUploadSkillMutation();
  const importMut = useImportSkillMutation();
  const installUrlMut = useInstallUrlSkillMutation();
  const deleteMut = useDeleteSkillMutation();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.prompt_injection.trim()) {
      setError("Name and prompt_injection are required.");
      return;
    }
    setError(null);
    const scope =
      form.level === "company" ? [] : scopeText.split(",").map((s) => s.trim()).filter(Boolean);
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

  return (
    <main className="h-full overflow-auto p-4">
      <div className="grid gap-4 md:grid-cols-[1fr_24rem]">
        <section className="pixel-panel p-3 text-sm">
          <h2 className="mb-2 text-base font-bold">Skills ({skills.length})</h2>
          <p className="mb-2 text-xs text-gray-500">Click a skill name to view / edit.</p>
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
                    <button className="font-bold hover:text-cyan-300" onClick={() => setSelected(s)}>
                      {s.name}
                    </button>
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

        <section className="pixel-panel p-3 text-sm">
          <div className="mb-3 flex gap-3 border-b border-gray-700 pb-1 text-xs">
            {(["create", "paste", "url", "upload"] as const).map((t) => (
              <button
                key={t}
                className={tab === t ? "text-cyan-300" : "text-gray-500 hover:text-gray-300"}
                onClick={() => setTab(t)}
              >
                {t === "create" ? "Create" : t === "paste" ? "Paste" : t === "url" ? "URL" : "Upload"}
              </button>
            ))}
          </div>

          {tab === "create" && (
            <form className="space-y-2 text-xs" onSubmit={submit}>
              <SkillFields form={form} setForm={setForm} scopeText={scopeText} setScopeText={setScopeText} />
              {error && <p className="text-bad">{error}</p>}
              <button type="submit" className="pixel-panel w-full py-1 hover:text-cyan-300" disabled={createMut.isPending}>
                {createMut.isPending ? "Creating…" : "Create Skill"}
              </button>
            </form>
          )}

          {tab === "paste" && <PasteInstall importMut={importMut} toast={toast} />}
          {tab === "url" && <UrlInstall installMut={installUrlMut} toast={toast} />}
          {tab === "upload" && <UploadInstall uploadMut={uploadMut} toast={toast} />}
        </section>
      </div>

      {selected && <SkillEditModal skill={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}

function SkillFields({
  form,
  setForm,
  scopeText,
  setScopeText,
}: {
  form: SkillRequestBody;
  setForm: (f: SkillRequestBody) => void;
  scopeText: string;
  setScopeText: (s: string) => void;
}) {
  return (
    <>
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
              <option key={c} value={c}>{c}</option>
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
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </label>
      </div>
      {form.level !== "company" && (
        <label className="block">
          Scope ({form.level === "department" ? "department names" : form.level === "role" ? "role names" : "agent_ids"}, comma-separated)
          <input
            className="mt-1 w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
            value={scopeText}
            onChange={(e) => setScopeText(e.target.value)}
            placeholder={form.level === "department" ? "Engineering, Design" : form.level === "role" ? "senior-engineer, junior-engineer" : "ceo-alex, eng-jordan"}
          />
        </label>
      )}
    </>
  );
}

function PasteInstall({
  importMut,
  toast,
}: {
  importMut: ReturnType<typeof useImportSkillMutation>;
  toast: (text: string, kind?: "info" | "error" | "success") => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="space-y-2 text-xs">
      <p className="text-gray-500">Paste a skill definition (JSON / YAML / Markdown with frontmatter).</p>
      <textarea
        className="h-40 w-full resize-y rounded border border-gray-600 bg-black/40 px-2 py-1 font-mono"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={'---\nname: Deployment Checklist\ndescription: Pre-release steps\ncategory: operations\nlevel: company\nscope: []\n---\n\nRun all tests; bump version; tag before release.'}
      />
      <button
        className="pixel-panel w-full py-1 hover:text-cyan-300"
        disabled={importMut.isPending || !text.trim()}
        onClick={() =>
          importMut.mutate(text, {
            onSuccess: () => {
              toast("Skill imported.", "success");
              setText("");
            },
            onError: (e: Error) => toast(e.message, "error"),
          })
        }
      >
        {importMut.isPending ? "Importing…" : "Import"}
      </button>
    </div>
  );
}

function UrlInstall({
  installMut,
  toast,
}: {
  installMut: ReturnType<typeof useInstallUrlSkillMutation>;
  toast: (text: string, kind?: "info" | "error" | "success") => void;
}) {
  const [url, setUrl] = useState("");
  return (
    <div className="space-y-2 text-xs">
      <p className="text-gray-500">Install from a URL (skill.json / skill.yaml / .zip).</p>
      <input
        className="w-full rounded border border-gray-600 bg-black/40 px-2 py-1"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://example.com/skill.json"
      />
      <button
        className="pixel-panel w-full py-1 hover:text-cyan-300"
        disabled={installMut.isPending || !url.trim()}
        onClick={() =>
          installMut.mutate(url, {
            onSuccess: () => {
              toast("Skill installed.", "success");
              setUrl("");
            },
            onError: (e: Error) => toast(e.message, "error"),
          })
        }
      >
        {installMut.isPending ? "Installing…" : "Install"}
      </button>
    </div>
  );
}

function UploadInstall({
  uploadMut,
  toast,
}: {
  uploadMut: ReturnType<typeof useUploadSkillMutation>;
  toast: (text: string, kind?: "info" | "error" | "success") => void;
}) {
  return (
    <div className="space-y-2 text-xs">
      <p className="text-gray-500">.zip with skill.json (or skill.yaml) + optional prompt.md</p>
      <input
        type="file"
        accept=".zip"
        disabled={uploadMut.isPending}
        className="block w-full"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          uploadMut.mutate(f, {
            onSuccess: () => toast(`Uploaded ${f.name}.`, "success"),
            onError: (err: Error) => toast(err.message, "error"),
          });
          e.target.value = "";
        }}
      />
      {uploadMut.isPending && <p className="text-gray-500">Uploading…</p>}
    </div>
  );
}

function SkillEditModal({ skill, onClose }: { skill: Skill; onClose: () => void }) {
  const toast = useToastStore((s) => s.push);
  const updateMut = useUpdateSkillMutation();
  const [form, setForm] = useState<SkillRequestBody>({
    name: skill.name,
    description: skill.description,
    prompt_injection: skill.prompt_injection,
    category: skill.category,
    level: skill.level,
    scope: skill.scope,
  });
  const [scopeText, setScopeText] = useState(skill.scope.join(", "));

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const scope =
      form.level === "company" ? [] : scopeText.split(",").map((s) => s.trim()).filter(Boolean);
    updateMut.mutate(
      { id: skill.id, body: { ...form, scope } },
      {
        onSuccess: () => {
          toast(`Updated ${form.name}`, "success");
          onClose();
        },
        onError: (e: Error) => toast(e.message, "error"),
      },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="pixel-panel w-full max-w-lg space-y-3 p-4 text-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">Edit Skill</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white" aria-label="Close">✕</button>
        </div>
        <form className="space-y-2 text-xs" onSubmit={save}>
          <SkillFields form={form} setForm={setForm} scopeText={scopeText} setScopeText={setScopeText} />
          <button type="submit" className="pixel-panel w-full py-1 hover:text-cyan-300" disabled={updateMut.isPending}>
            {updateMut.isPending ? "Saving…" : "Save"}
          </button>
        </form>
      </div>
    </div>
  );
}
