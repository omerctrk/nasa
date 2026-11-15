import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/cosmic.css'
// The running application reads patient records only through the backend.
// The legacy simulation sources stay in the repository but are never loaded.
const App = lazy(() => import('./live/LiveApp.tsx'))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={<div className="p-8 text-slate-600">Yükleniyor…</div>}><App /></Suspense>
  </StrictMode>,
)
