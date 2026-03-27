import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Reduce dev-time compile cost by letting Next optimize common deps imports.
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  turbopack: {
    // Use frontend dir as workspace root so Next does not pick a parent lockfile.
    root: process.cwd(),
  },
};

export default nextConfig;
