import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
export default defineConfig({ plugins: [react()], cacheDir: ".vitest-cache", resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } }, test: { environment: "jsdom", environmentOptions: { jsdom: { url: "http://localhost:3000" } }, setupFiles: ["./test/setup.ts"], css: true } });
