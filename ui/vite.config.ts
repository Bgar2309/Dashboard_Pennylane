import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev : proxy /api vers le backend FastAPI local pour éviter le CORS.
// (En build, l'UI tape directement VITE_API_BASE.)
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
