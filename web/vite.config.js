import { defineConfig } from "vitest/config";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Backend target for the dev proxy. Prefer an explicit full URL
// (RONZZDOI_API_URL, e.g. https://doi-admin.ronzz.org for remote writes);
// otherwise fall back to http://localhost:${RONZZDOI_PORT || 8011}.
const apiTarget = process.env.RONZZDOI_API_URL || `http://localhost:${process.env.RONZZDOI_PORT || 8011}`;

export default defineConfig({
  plugins: [svelte({ compilerOptions: { dev: true } })],
  server: {
    port: 6025,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      // DOI redirects are served by the backend at /10.ronzz/<suffix>.
      // Proxying the path makes copied resolution URLs work from the GUI
      // origin in dev (issue #38).
      "/10.ronzz": {
        target: apiTarget,
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
  resolve: {
    conditions: ["browser", "module", "import", "default"],
  },
  ssr: {
    noExternal: ["svelte", "@sveltejs/vite-plugin-svelte"],
    resolve: {
      conditions: ["browser", "module", "import", "default"],
    },
  },
  test: {
    include: ["src/**/*.test.js"],
    environment: "jsdom",
    globals: true,
    server: {
      deps: {
        inline: ["svelte", "@sveltejs/vite-plugin-svelte"],
      },
    },
    transformMode: {
      web: ["**/*.svelte"],
    },
  },
});
