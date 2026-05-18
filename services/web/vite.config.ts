import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const API_TARGET = process.env.API_INTERNAL_URL || "http://tessa-api:8000";

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/ws": { target: API_TARGET, ws: true, changeOrigin: true },
    },
  },
});
