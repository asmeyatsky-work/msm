import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const RECONCILIATION_API =
  process.env.VITE_RECONCILIATION_API ??
  "https://reconciliation-staging-794974391956.europe-west2.run.app";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: RECONCILIATION_API,
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
