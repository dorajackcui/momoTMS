import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: frontendRoot,
  base: "/static/product-app/",
  plugins: [react()],
  build: {
    outDir: path.resolve(frontendRoot, "../app/static/product-app"),
    emptyOutDir: true,
  },
});
