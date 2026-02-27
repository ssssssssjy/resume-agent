import type { NextConfig } from "next";

/** 开发环境默认后端地址，与 api/config.ts 保持一致 */
const DEV_API_URL = "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",

  // 开发环境代理配置
  // 生产环境通过 Nginx 反向代理，不需要这个
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || DEV_API_URL;

    return [
      {
        source: "/api/langgraph/:path*",
        destination: `${apiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
