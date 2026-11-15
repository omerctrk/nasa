import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/cosmic.css'
// Keep the frontend branch's original interface as the landing page. Its
// simulated readings are labeled in the UI; real backend data is one click away.
const App = new URLSearchParams(location.search).get('view') === 'live'
  ? lazy(() => import('./live/LiveApp.tsx'))
  : lazy(() => import('./App.tsx'))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={<div className="p-8 text-slate-600">Yükleniyor…</div>}><App /></Suspense>
  </StrictMode>,
)
