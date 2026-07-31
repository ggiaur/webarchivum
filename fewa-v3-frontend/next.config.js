/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // Required for ReplayWeb.page's self-hosted embed: its service worker is
  // scoped to /replay/ (trailing slash), but Next.js's default trailing-slash
  // redirect strips it from /replay/?source=... before the SW ever sees the
  // request, so it falls through to the real server (404) instead of being
  // intercepted. See app/(public)/documents/[id]/page.tsx.
  trailingSlash: true,
  devIndicators: {
    appIsrStatus: false,
  },
  webpack: (config, { isServer }) => {
    return config;
  },
};

module.exports = nextConfig;
