/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";

const csp = [
  "default-src 'self'",
  // Next injects inline bootstrap scripts; allow them without unsafe-eval.
  "script-src 'self' 'unsafe-inline'" + (isProd ? "" : " 'unsafe-eval'"),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  // Backend is cross-origin (Render) for fetch + websocket.
  "connect-src 'self' " + (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"),
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000" },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
