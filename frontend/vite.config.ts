import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type Plugin } from 'vite'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Yerel demo astronot hesapları: backend/config/demo-accounts.json (seed.py ile ortak tek kaynak).
// Her istekte okunur; dosyaya eklenen hesap seed'den sonra Vite yeniden başlatılmadan listeye gelir.
const ACCOUNTS_FILE = fileURLToPath(new URL('../backend/config/demo-accounts.json', import.meta.url))
const API = 'http://127.0.0.1:8001/api/v1'
function demoAccounts(): { astronaut_id: string; email: string }[] {
  return JSON.parse(readFileSync(ACCOUNTS_FILE, 'utf-8'))
}

function localSession(mode: string): Plugin {
  const root = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, root, '')
  return {
    name: 'local-dev-session',
    configureServer(server) {
      // Hesap listesi: kule hesabıyla okunan astronot profilleri, giriş yapabilenlerle sınırlı.
      server.middlewares.use('/__dev/accounts', async (_req, res) => {
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('Content-Type', 'application/json')
        try {
          const ids = demoAccounts().map((account) => account.astronaut_id)
          const login = await fetch(`${API}/auth/login`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'kule@astra.local', password: env.SEED_GROUND_PASSWORD }),
          })
          const token = login.ok ? (await login.json()).access_token : null
          const crew = token ? await fetch(`${API}/ground/astronauts`, { headers: { Authorization: `Bearer ${token}` } }) : null
          if (!crew?.ok) { res.statusCode = 503; res.end('[]'); return }
          const profiles: { astronaut_id: string; is_display_only: boolean }[] = await crew.json()
          res.end(JSON.stringify(ids.flatMap((id) => profiles.filter((p) => p.astronaut_id === id && !p.is_display_only))))
        } catch { res.statusCode = 503; res.end('[]') }
      })
      server.middlewares.use('/__dev/session', async (req, res) => {
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('Content-Type', 'application/json')
        if (req.method !== 'POST') { res.statusCode = 405; res.end('{}'); return }
        const chunks: Buffer[] = []
        for await (const chunk of req) chunks.push(Buffer.from(chunk))
        let role: string
        let astronaut: unknown
        try { ({ role, astronaut } = JSON.parse(Buffer.concat(chunks).toString())) }
        catch { res.statusCode = 400; res.end('{}'); return }
        if (role !== 'ASTRONAUT' && role !== 'GROUND_CONTROL') {
          res.statusCode = 400; res.end('{}'); return
        }
        // astronaut verilmezse A007 (eski davranış); bilinmeyen kimlik reddedilir.
        const wanted = typeof astronaut === 'string' ? astronaut : 'A007'
        let astronautEmail: string | undefined
        try { astronautEmail = demoAccounts().find((account) => account.astronaut_id === wanted)?.email }
        catch { res.statusCode = 503; res.end('{"detail":"demo-accounts.json okunamadı."}'); return }
        if (role === 'ASTRONAUT' && !astronautEmail) { res.statusCode = 400; res.end('{}'); return }
        const password = role === 'ASTRONAUT' ? env.SEED_ASTRONAUT_PASSWORD : env.SEED_GROUND_PASSWORD
        if (!password) { res.statusCode = 503; res.end('{"detail":"Yerel demo hesabı ayarlı değil."}'); return }
        try {
          const response = await fetch(`${API}/auth/login`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: role === 'ASTRONAUT' ? astronautEmail : 'kule@astra.local', password }),
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
