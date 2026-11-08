import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Chunks follow the dynamic imports in App.tsx: Recharts loads only with Profile and Compare.
// (scripts/budget.mjs fails the build if it ever leaks into the initial load.)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, 'src') } },
})
