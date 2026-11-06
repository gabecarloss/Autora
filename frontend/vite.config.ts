/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, `uv run autora-app --dev` sobe o servidor em 127.0.0.1:8765.
const servidor = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": servidor,
      "/entrar": servidor,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/testes-setup.ts"],
  },
});
