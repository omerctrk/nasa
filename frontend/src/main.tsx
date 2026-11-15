import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/cosmic.css'
// Load the large simulation UI only when explicitly requested. Live mode is
// the default and never displays synthetic vitals as patient measurements.
const App = import.meta.env.VITE_USE_MOCK === 'true'
  ? lazy(() => import('./App.tsx'))
  : lazy(() => import('./live/LiveApp.tsx'))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={<div className="p-8 text-slate-600">Yükleniyor…</div>}><App /></Suspense>
  </StrictMode>,
)
