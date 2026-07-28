/** @type {import('next').NextConfig} */
const nextConfig = {
  // Ship only the files the server actually needs. The runtime image previously copied the FULL
  // node_modules (dev dependencies included), which made it 1.29 GB — a large deploy cost and a
  // large attack surface. Standalone output traces the real dependency graph instead.
  output: "standalone",

  async redirects() {
    return [
      // The AI tool moved from /search into the dashboard shell.
      { source: "/search", destination: "/dashboard/discover", permanent: true },
    ];
  },
};

export default nextConfig;
