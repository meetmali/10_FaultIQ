/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend always calls the API on the same origin (/api/...).
// In development, Vite proxies /api to the API. In production, Caddy does (see web/Caddyfile).
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // ECharts (~570 kB) is its own lazily loaded chunk, fetched only by screens with charts
  // (ADR 0009). The limit sits just above it, so any other large chunk still warns.
  build: { chunkSizeWarningLimit: 600 },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: apiProxyTarget, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"], // Playwright specs in e2e/ run separately
    css: false,
  },
});
