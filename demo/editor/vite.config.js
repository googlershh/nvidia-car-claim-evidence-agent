import { defineConfig } from 'vite';
export default defineConfig({
  base: './',
  build: { outDir: '../dist/docx-editor', emptyOutDir: true, chunkSizeWarningLimit: 2500 },
});
