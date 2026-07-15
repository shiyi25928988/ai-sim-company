import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Phaser 依赖部分 Node/浏览器全局，按需放宽客户端打包。
  reactStrictMode: true,
};

export default nextConfig;
