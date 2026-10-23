import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // maplibre يحمّل الـ worker من حزمته؛ التجميع المسبق في وضع التطوير يكسر رابطه
  optimizeDeps: { exclude: ["maplibre-gl"] },
  server: {
    port: 5173,
    proxy: { "/api": process.env.VITE_API_TARGET ?? "http://localhost:8000" },
  },
  test: { environment: "node" },
});
