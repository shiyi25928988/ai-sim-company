"use client";

/** Settings page: LLM config (API Key + model routing) / simulation control / skill pool management (TODO). */
export function SettingsPage() {
  return (
    <div className="pixel-panel space-y-4 p-4 text-sm">
      <section>
        <h3 className="mb-2 font-bold">LLM Gateway</h3>
        <p className="text-gray-400">API Key is configured once in Company Hub; the frontend never holds it.</p>
        {/* TODO: model routing table editor */}
      </section>
      <section>
        <h3 className="mb-2 font-bold">Simulation Control</h3>
        <p className="text-gray-400">(start/stop / speed / replay)</p>
      </section>
      <section>
        <h3 className="mb-2 font-bold">Skill Pool</h3>
        <p className="text-gray-400">(company-level skill review and publishing)</p>
      </section>
    </div>
  );
}
