import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/QueryProvider";
import { GameProvider } from "@/components/GameProvider";
import { TopNav } from "@/components/TopNav";
import { Toaster } from "@/components/Toaster";

export const metadata: Metadata = {
  title: "ai-sim-company",
  description: "Multi-Agent AI Company Simulation - Pixel Office",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <GameProvider>
            <div className="flex h-screen flex-col">
              <TopNav />
              <div className="flex-1 overflow-hidden">{children}</div>
            </div>
            <Toaster />
          </GameProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
