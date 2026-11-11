/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// The live tape runs over a WebSocket, which is a *different* origin scheme
// for CSP purposes: http://host:8000 must also allow ws://host:8000.
const wsUrl = apiUrl.replace(/^http/, "ws");
// Supabase Auth runs in the browser, so its origin must be allowed too.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";

const csp = [
  "default-src 'self'",
  // Next injects inline bootstrap scripts; allow them without unsafe-eval.
  "script-src 'self' 'unsafe-inline'" + (isProd ? "" : " 'unsafe-eval'"),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  // Backend is cross-origin (Render) for both fetch and the tick stream.
  `connect-src 'self' ${apiUrl} ${wsUrl} ${supabaseUrl}`.trim(),
  "worker-src 'self'",
  "manifest-src 'self'",
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
