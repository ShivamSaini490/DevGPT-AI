import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API routes served by the FastAPI backend. In dev they are proxied so the
// browser only ever talks to the Vite origin. Only /chat/stream is proxied:
// GET /chat itself is the React chat page.
const API_PATHS = ["/conversations", "/history", "/upload", "/chat/stream", "/sessions"];

export default defineConfig(({ command }) => {
  const target = process.env.VITE_API_TARGET || "http://localhost:8080";

  return {
    plugins: [react()],
    // The production build is served by FastAPI under /static.
    base: command === "build" ? "/static/" : "/",
    server: {
      port: 5173,
      host: true,
      watch: process.env.VITE_USE_POLLING ? { usePolling: true, interval: 300 } : undefined,
      proxy: Object.fromEntries(
        API_PATHS.map((path) => [path, { target, changeOrigin: true }])
      ),
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      chunkSizeWarningLimit: 900,
    },
  };
});
