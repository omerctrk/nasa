import React from 'react';
import { BellRing, BrainCircuit, Database, Rocket, ShieldCheck } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';

export const AiInsightPanel: React.FC = () => {
  const { currentAlert, setOpenActionPlanModal, astronaut } = useTelemetry();
  const { t, pick } = usePrefs();
  return <section className="bg-white rounded-2xl border border-slate-200 p-5 ai-panel overflow-hidden" aria-labelledby="ai-heading">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3"><span className="ai-orb"><BrainCircuit className="w-5 h-5 text-white" /></span>
        <div><h2 id="ai-heading" className="text-base font-bold text-slate-900">{t('Yapay Zekâ Sağlık Asistanı', 'AI Health Assistant')}</h2>
          <p className="text-xs text-slate-500">{t('Backend analiz sonuçları burada görünür', 'Backend analysis results appear here')}</p></div>
      </div>
      <span className="flex items-center gap-1.5 rounded-lg border border-cyan-300/60 bg-cyan-50/50 px-2 py-1 text-xs font-semibold font-mono text-cyan-700"><Database className="h-3.5 w-3.5" />SQL Server</span>
    </div>
    {currentAlert ? <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/60 p-4">
      <div className="flex items-center gap-2 text-sm font-bold text-amber-900"><BellRing className="h-4 w-4" />{pick(currentAlert.title)}</div>
      <p className="mt-2 text-sm text-slate-700">{pick(currentAlert.description)}</p>
      <button type="button" onClick={() => setOpenActionPlanModal(true)} disabled={!!astronaut.isDisplayOnly} className="mt-3 flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"><Rocket className="h-3.5 w-3.5" />{t('Aksiyon planı', 'Action plan')}</button>
    </div> : <div className="mt-4 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <ShieldCheck className="h-6 w-6 shrink-0 text-slate-400" />
      <div className="text-sm"><div className="font-semibold text-slate-900">{t('Analiz sonucu bulunmuyor', 'No analysis result')}</div>
        <div className="text-slate-500">{t('Model servisi ve eşikler tamamlandığında doğrulanmış sonuçlar burada gösterilecek.', 'Verified results will appear here when the model service and thresholds are ready.')}</div></div>
    </div>}
  </section>;
};
