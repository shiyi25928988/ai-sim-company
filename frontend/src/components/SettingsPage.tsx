"use client";

/** 设置页: LLM 配置 (API Key + 模型路由) / 仿真控制 / Skill 池管理 (TODO)。 */
export function SettingsPage() {
  return (
    <div className="pixel-panel space-y-4 p-4 text-sm">
      <section>
        <h3 className="mb-2 font-bold">LLM 网关</h3>
        <p className="text-gray-400">API Key 仅在 Company Hub 配置一次，前端不持有。</p>
        {/* TODO: 模型路由表编辑 */}
      </section>
      <section>
        <h3 className="mb-2 font-bold">仿真控制</h3>
        <p className="text-gray-400">(启停 / 速度 / 回放)</p>
      </section>
      <section>
        <h3 className="mb-2 font-bold">Skill 池</h3>
        <p className="text-gray-400">(公司级 Skill 审核与发布)</p>
      </section>
    </div>
  );
}
