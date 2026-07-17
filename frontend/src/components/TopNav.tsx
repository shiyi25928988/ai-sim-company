"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useGameStore } from "@/store/useGameStore";

const NAV = [
  { href: "/", label: "Console" },
  { href: "/setup", label: "Setup" },
  { href: "/agents", label: "Agents" },
  { href: "/skills", label: "Skills" },
  { href: "/files", label: "Files" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/settings", label: "Settings" },
];

/** Global top nav: brand + route links + WS connection status. */
export function TopNav() {
  const pathname = usePathname();
  const wsStatus = useGameStore((s) => s.wsStatus);
  const company = useGameStore((s) => s.snapshot.company);

  const dot = wsStatus === "open" ? "🟢" : wsStatus === "connecting" ? "🟡" : "🔴";

  return (
    <nav className="pixel-panel flex items-center gap-4 px-4 py-2 text-sm">
      <span className="font-bold">ai-sim-company</span>
      {company && <span className="text-gray-400">{company}</span>}
      <div className="flex gap-3">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={pathname === n.href ? "text-cyan-300" : "hover:text-cyan-300"}
          >
            {n.label}
          </Link>
        ))}
      </div>
      <span className="ml-auto">
        {dot} {wsStatus}
      </span>
    </nav>
  );
}
