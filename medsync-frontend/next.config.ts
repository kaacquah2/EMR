import type { NextConfig } from "next";
import withPWA from "next-pwa";

const nextConfig: NextConfig = {
  // Reduce dev-time compile cost by letting Next optimize common deps imports.
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  images: {
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
  },
  turbopack: {
    // Use frontend dir as workspace root so Next does not pick a parent lockfile.
    root: process.cwd(),
  },

  // PWA specific settings
  reactStrictMode: true,

  // Security headers
  // SECURITY_FIX_CORS_CSP_T4: Production-grade CSP headers (Mar 2025)
  // Removed 'unsafe-inline' from script-src to prevent XSS token theft
  // Kept in style-src only as Next.js/Tailwind v4 requires inline styles
  async headers() {
    // Extract origin (scheme + host + port) from API URL for CSP
    const apiOrigin = 'http://localhost:8000';
    const isProduction = process.env.NODE_ENV === 'production';
    
    let finalApiOrigin = apiOrigin;
    if (process.env.NEXT_PUBLIC_API_URL) {
      try {
        const url = new URL(process.env.NEXT_PUBLIC_API_URL);
        finalApiOrigin = `${url.protocol}//${url.host}`;
        
        // Production: enforce HTTPS for API origin
        if (isProduction && !finalApiOrigin.startsWith('https://')) {
          console.warn(
            'WARNING: Production environment detected with non-HTTPS API URL. ' +
            `Got: ${finalApiOrigin}. Set NEXT_PUBLIC_API_URL to HTTPS endpoint.`
          );
        }
      } catch {
        // Invalid URL, fall back to default
        console.error('Invalid NEXT_PUBLIC_API_URL:', process.env.NEXT_PUBLIC_API_URL);
      }
    }

    // CSP directives for production safety
    const cspDirectives = [
      "default-src 'self'",
      // script-src: Handle inline scripts needed for hydration and theme initialization
      isProduction
        ? "script-src 'self'" // Production: self only
        : "script-src 'self' 'unsafe-eval' 'unsafe-inline'", // Dev: allow eval for hot reload and inline scripts
      "style-src 'self' 'unsafe-inline'", // Required: Next.js inline critical CSS + Tailwind
      "img-src 'self' data: blob: https:", // Allow images from self, data URIs, blobs, https
      "font-src 'self' data:", // Allow fonts from self and data URIs
      `connect-src 'self' ${finalApiOrigin}`, // API communication to configured backend
      "frame-ancestors 'none'", // Prevent clickjacking
      "base-uri 'self'", // Restrict base URL
      "form-action 'self'", // Restrict form submissions
    ];

    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          {
            key: "Content-Security-Policy",
            value: cspDirectives.join("; "),
          },
          // Production-only headers
          ...(isProduction ? [
            {
              key: "Strict-Transport-Security",
              value: "max-age=31536000; includeSubDomains; preload",
            },
          ] : []),
        ],
      },
    ];
  },
};

const pwaConfig = withPWA({
  dest: "public",
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === "development", // Disable in dev
  runtimeCaching: [
    // API calls - network first
    {
      urlPattern: /^https?:\/\/.*\/api\/.*/i,
      handler: "NetworkFirst",
      options: {
        cacheName: "api-cache",
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 60 * 60, // 1 hour
        },
        networkTimeoutSeconds: 10,
      },
    },
    // Static assets - cache first
    {
      urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i,
      handler: "CacheFirst",
      options: {
        cacheName: "image-cache",
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
        },
      },
    },
    // Fonts - cache first
    {
      urlPattern: /\.(?:woff|woff2|ttf|otf|eot)$/i,
      handler: "CacheFirst",
      options: {
        cacheName: "font-cache",
        expiration: {
          maxEntries: 20,
          maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
        },
      },
    },
    // JS/CSS - stale while revalidate
    {
      urlPattern: /\.(?:js|css)$/i,
      handler: "StaleWhileRevalidate",
      options: {
        cacheName: "static-resources",
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
        },
      },
    },
    // Reference data endpoints - stale while revalidate with long cache
    {
      urlPattern: /\/api\/v1\/(drugs|icd10|wards|departments)/i,
      handler: "StaleWhileRevalidate",
      options: {
        cacheName: "reference-data",
        expiration: {
          maxEntries: 50,
          maxAgeSeconds: 60 * 60 * 24, // 24 hours
        },
      },
    },
  ],
})(nextConfig);

export default pwaConfig;
