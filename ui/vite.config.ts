import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En dev, /api est proxifié vers l'API FastAPI locale (port 8000) pour que la
// navigation fonctionne sans CORS ni VITE_API_BASE. En prod, VITE_API_BASE est
// injecté au build (cf. Dockerfile) et les requêtes partent en absolu.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
