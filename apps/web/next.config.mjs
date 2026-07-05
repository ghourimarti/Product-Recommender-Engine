/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      // The AI tool moved from /search into the dashboard shell.
      { source: "/search", destination: "/dashboard/discover", permanent: true },
    ];
  },
};

export default nextConfig;
