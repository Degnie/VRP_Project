import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // maplibre-gl trae su propio worker (maplibre-gl-worker.mjs); el dep
    // optimizer de Vite no lo reescribe correctamente y el worker resuelve
    // en 404. Se sirve sin pre-bundlear.
    exclude: ["maplibre-gl"],
  },
})
