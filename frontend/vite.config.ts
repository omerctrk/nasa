import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import { fileURLToPath } from 'node:url'

function localSession(mode: string): Plugin {
  const root = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, root, '')
  return {
    name: 'local-dev-session',
    configureServer(server) {
      server.middlewares.use('/__dev/session', async (req, res) => {
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('Content-Type', 'application/json')
        if (req.method !== 'POST') { res.statusCode = 405; res.end('{}'); return }
        const chunks: Buffer[] = []
        for await (const chunk of req) chunks.push(Buffer.from(chunk))
        let role: string
        try { role = JSON.parse(Buffer.concat(chunks).toString()).role }
        catch { res.statusCode = 400; res.end('{}'); return }
        if (role !== 'ASTRONAUT' && role !== 'GROUND_CONTROL') {
          res.statusCode = 400; res.end('{}'); return
        }
        const password = role === 'ASTRONAUT' ? env.SEED_ASTRONAUT_PASSWORD : env.SEED_GROUND_PASSWORD
        if (!password) { res.statusCode = 503; res.end('{"detail":"Yerel demo hesabı ayarlı değil."}'); return }
        try {
          const response = await fetch('http://127.0.0.1:8001/api/v1/auth/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: role === 'ASTRONAUT' ? 'astronaut@astra.local' : 'kule@astra.local', password }),
          })
          res.statusCode = response.status
          res.end(await response.text())
        } catch {
          res.statusCode = 503
          res.end('{"detail":"Backend bağlantısı kurulamadı."}')
        }
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), localSession(mode)],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/v1': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/ws/v1': { target: 'ws://127.0.0.1:8001', ws: true },
    },
  },
}))
