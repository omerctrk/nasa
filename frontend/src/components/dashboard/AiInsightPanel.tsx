import React, { useEffect, useRef } from 'react';
import { BellRing, BrainCircuit, Database, Rocket, ShieldAlert, ShieldCheck, Stethoscope } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { adviceOf, breachText, isBreach } from '../../lib/backend/resultView';
import { usePrefs } from '../../context/PreferencesContext';
import { AnalysisStatus } from './AnalysisStatus';

/**
 * Yapay zekâ sağlık asistanı = backend anomali analizinin sonucu (anomaly_results).
 * Kararı (seviye, öneri, hekime yükseltme) backend KODU verir; model yalnız açıklama yazar.
 * Burada hiçbir değer üretilmez: gösterilen her şey sonucun kendi alanlarıdır.
 */
export const AiInsightPanel: React.FC = () => {
  const { currentAlert, setOpenActionPlanModal, astronaut, latestResult, reload } = useTelemetry();
  const { t, lang } = usePrefs();
  const pendingOpen = useRef(false);

  // Kullanıcının başlattığı analiz riskli bittiyse: veri yenilenince aksiyon planını aç
  useEffect(() => {
    if (pendingOpen.current && currentAlert) {
      pendingOpen.current = false;
      setOpenActionPlanModal(true);
    }
  }, [currentAlert, setOpenActionPlanModal]);

  const r = latestResult;
  const breaches = r ? r.drivers.filter(isBreach) : [];
  const advice = adviceOf(r);
  const levelMeta = r && {
    normal: { label: t('Normal', 'Normal'), cls: 'bg-emerald-100 text-emerald-800 border-emerald-200', Icon: ShieldCheck },
    watch: { label: t('İzle', 'Watch'), cls: 'bg-amber-100 text-amber-800 border-amber-300', Icon: BellRing },
    review: { label: t('İncele · hekime yükselt', 'Review · escalate'), cls: 'bg-red-100 text-red-800 border-red-300', Icon: Stethoscope },
  }[r.level];
  const source = r && (r.algorithm === 'threshold_rules_plus_llm'
    ? t(`Eşik kuralları + bilgi kartları · açıklama: ${r.model_version ?? 'model'}`, `Threshold rules + knowledge cards · explanation: ${r.model_version ?? 'model'}`)
    : t('Eşik kuralları + bilgi kartları (model açıklaması yok)', 'Threshold rules + knowledge cards (no model explanation)'));
  const recs = advice?.recommendations.map((x) => x.action).filter(Boolean) ?? [];

  return <section className="bg-white rounded-2xl border border-slate-200 p-5 ai-panel overflow-hidden" aria-labelledby="ai-heading">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3"><span className="ai-orb"><BrainCircuit className="w-5 h-5 text-white" /></span>
        <div><h2 id="ai-heading" className="text-base font-bold text-slate-900">{t('Yapay Zekâ Sağlık Asistanı', 'AI Health Assistant')}</h2>
          <p className="text-xs text-slate-500">{t('Anomali tespitinin son sonucu', 'Latest anomaly detection result')}</p></div>
      </div>
      <span className="flex items-center gap-1.5 rounded-lg border border-cyan-300/60 bg-cyan-50/50 px-2 py-1 text-xs font-semibold font-mono text-cyan-700"><Database className="h-3.5 w-3.5" />SQL Server</span>
    </div>

    {r && levelMeta ? <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-bold ${levelMeta.cls}`}><levelMeta.Icon className="h-3.5 w-3.5" />{levelMeta.label}</span>
        <span className="font-mono text-xs text-slate-500">{r.created_at.slice(0, 10)} {r.created_at.slice(11, 16)} UTC</span>
      </div>
      <p className="text-sm leading-relaxed text-slate-800">{r.summary}</p>

      {breaches.length > 0 && <div>
        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{t('Aralık dışı ölçümler', 'Out-of-range measurements')}</div>
        <ul className="mt-1 space-y-0.5 text-sm text-amber-800">{breaches.map((d) => <li key={d.record_id}>• {breachText(d, lang)}</li>)}</ul>
      </div>}

      {(recs.length > 0 || (advice?.escalation_reasons.length ?? 0) > 0) && <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-3">
        <div className="text-[11px] font-bold uppercase tracking-wider text-blue-800">{t('Yapılacaklar', 'What to do')}</div>
        <ul className="mt-1 space-y-1 text-sm text-slate-800">
          {advice && advice.escalation_reasons.length > 0 && <li className="flex gap-1.5"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
            <span><b>{t('Uçuş hekimine bildirin', 'Notify the flight surgeon')}</b>: {advice.escalation_reasons.join('; ')}.</span></li>}
          {recs.map((a, i) => <li key={i}>• {a}</li>)}
        </ul>
      </div>}

      {currentAlert && currentAlert.backend?.anomalyResultId === r.id && <button type="button" onClick={() => setOpenActionPlanModal(true)} disabled={!!astronaut.isDisplayOnly}
        className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"><Rocket className="h-3.5 w-3.5" />{t('Aksiyon planı', 'Action plan')}</button>}

      <p className="text-[11px] text-slate-500">{source}{advice?.disclaimer ? ` · ${advice.disclaimer}` : ''}</p>
    </div> : <div className="mt-4 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <ShieldCheck className="h-6 w-6 shrink-0 text-slate-400" />
      <div className="text-sm"><div className="font-semibold text-slate-900">{t('Henüz analiz sonucu yok', 'No analysis result yet')}</div>
        <div className="text-slate-500">{t('Aşağıdan analizi başlatın; sonuç burada görünür.', 'Start an analysis below; the result appears here.')}</div></div>
    </div>}

    <AnalysisStatus onFinished={(job, result) => {
      if (job.state === 'COMPLETED' && result && result.level !== 'normal') pendingOpen.current = true;
      reload();
    }} />
  </section>;
};
