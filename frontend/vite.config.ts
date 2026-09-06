import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const djangoTarget = "http://127.0.0.1:8000";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/product_ui/" : "/",
  build: {
    outDir: "../backend/web/product_ui",
    emptyOutDir: true,
  },
  plugins: [react()],
  test: {
    coverage: {
      reportsDirectory: "../test-results/coverage/frontend",
    },
    include: [
      "tests/**/*.test.{ts,tsx}",
      "packages/spl-api/src/**/__tests__/**/*.test.ts",
    ],
  },
  server: {
    port: 5174,
    proxy: {
      "/.well-known": djangoTarget,
      "/api": djangoTarget,
      "/media": djangoTarget,
      "/admin": djangoTarget,
      "/login": djangoTarget,
      "/logout": djangoTarget,
      "/setup": djangoTarget,
      "/static": djangoTarget,
    },
  },
}));
