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
  // Server-side proxy so a browser hitting the public domain (where only
  // this frontend container is reverse-proxied, not the backend) can still
  // reach the API on the same origin. See app/utils/apiConfig.ts —
  // getApiBaseUrl() falls back to window.location.origin for exactly this
  // case, but that only works if something actually forwards /api/* here.
  // `backend` resolves via Docker Compose's internal network; 8000 is the
  // container's own listen port, independent of any host port mapping.
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://backend:8000/api/:path*' },
      { source: '/oai', destination: 'http://backend:8000/oai' },
    ];
  },
};

module.exports = nextConfig;
