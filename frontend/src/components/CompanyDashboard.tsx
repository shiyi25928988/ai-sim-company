"use client";

/** 公司仪表盘: 组织架构树 / 收支趋势图 / 项目看板 (TODO: 接入数据)。 */
export function CompanyDashboard() {
  return (
    <div className="pixel-panel grid grid-cols-3 gap-3 p-3 text-sm">
      <section>
        <h3 className="mb-2 font-bold">组织架构</h3>
        <div className="text-gray-400">(待渲染 OrgChart)</div>
      </section>
      <section>
        <h3 className="mb-2 font-bold">收支趋势</h3>
        <div className="text-gray-400">(待渲染 EconomyChart)</div>
      </section>
      <section>
        <h3 className="mb-2 font-bold">项目看板</h3>
        <div className="text-gray-400">(待渲染 ProjectBoard)</div>
      </section>
    </div>
  );
}
