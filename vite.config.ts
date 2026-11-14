import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Gerçek backend (VITE_USE_MOCK=false) için: istekler aynı adresten backend'e aktarılır, CORS gerekmez.
    // Sahte modda (varsayılan) bu ayar hiçbir şeyi değiştirmez.
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
