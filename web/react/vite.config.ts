import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const djangoTarget = "http://127.0.0.1:8000";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/react/" : "/",
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": djangoTarget,
      "/media": djangoTarget,
      "/admin": djangoTarget,
      "/api-auth": djangoTarget,
    },
  },
}));
