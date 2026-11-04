import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Local CPU inference can exceed the default 30-second rewrite proxy timeout.
  experimental: { proxyClientMaxBodySize: "17mb", proxyTimeout: 210_000 },
  async rewrites() {
    return {
      beforeFiles: [
        { source: "/", destination: "/landing.html" },
        { source: "/api/rag/:path*", destination: "http://127.0.0.1:8000/api/rag/:path*" },
        { source: "/api/chemistry/:path*", destination: "http://127.0.0.1:8000/api/chemistry/:path*" },
        { source: "/api/auth/:path*", destination: "http://127.0.0.1:8000/api/auth/:path*" },
        { source: "/api/workspace/:path*", destination: "http://127.0.0.1:8000/api/workspace/:path*" }
      ],
      afterFiles: [],
      fallback: []
    };
  },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'" }
    ] }];
  }
};
export default nextConfig;
