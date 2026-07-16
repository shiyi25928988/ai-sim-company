import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ai-sim-company",
  description: "Multi-Agent AI Company Simulation - Pixel Office",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
