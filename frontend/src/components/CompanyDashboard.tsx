"use client";

/** Company dashboard: org chart tree / cash-flow trend / project board (TODO: wire up data). */
export function CompanyDashboard() {
  return (
    <div className="pixel-panel grid grid-cols-3 gap-3 p-3 text-sm">
      <section>
        <h3 className="mb-2 font-bold">Org Chart</h3>
        <div className="text-gray-400">(OrgChart pending)</div>
      </section>
      <section>
        <h3 className="mb-2 font-bold">Cash Flow</h3>
        <div className="text-gray-400">(EconomyChart pending)</div>
      </section>
      <section>
        <h3 className="mb-2 font-bold">Project Board</h3>
        <div className="text-gray-400">(ProjectBoard pending)</div>
      </section>
    </div>
  );
}
