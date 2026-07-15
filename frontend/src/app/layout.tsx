import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ai-sim-company",
  description: "多智能体 AI 公司模拟 - 像素风办公室",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
