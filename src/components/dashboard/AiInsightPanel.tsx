import React, { useEffect, useId, useState } from 'react';
import {
  BrainCircuit,
  BellRing,
  Clock,
  BookOpen,
  Rocket,
  CheckCircle2,
  ChevronDown,
  ShieldCheck,
} from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { AI_INSIGHTS, PERSONAL_BASELINES } from '../../data/aiInsights';
import { vitalLabel } from '../../utils/status';
import { AnalysisStatus } from './AnalysisStatus';

/** Olasılık arttıkça yeşilden sarıya, oradan kırmızıya geçen renk */
const likelihoodColor = (p: number) => {
  // %15 ve altı tam yeşil, %70 ve üstü tam kırmızı
  const q = Math.min(1, Math.max(0, (p - 0.15) / 0.55));
  return `hsl(${Math.round(125 * (1 - q))} 82% 48%)`;
};

/** Bir sonraki 30 dakikalık UTC ölçüm anına kalan süre */
const useNextReading = () => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const period = 30 * 60 * 1000;
  const left = period - (now % period);
  const m = Math.floor(left / 60000);
  const s = Math.floor((left % 60000) / 1000);
  return { label: `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`, ratio: 1 - left / period };
};

/** Ölçümleri kişisel referans bandıyla birlikte gösteren küçük grafik */
const BaselineChart: React.FC<{ data: number[]; mean: number; sd: number; color: string }> = ({ data, mean, sd, color }) => {
  const gid = useId().replace(/:/g, '');
  const w = 260;
  const h = 92;
  const pad = 8;
  const lo = mean - 2 * sd;
  const hi = mean + 2 * sd;
  const min = Math.min(...data, lo) - sd * 0.4;
  const max = Math.max(...data, hi) + sd * 0.4;
  const y = (v: number) => h - pad - ((v - min) / (max - min)) * (h - 2 * pad);
  const x = (i: number) => pad + (i / Math.max(1, data.length - 1)) * (w - 2 * pad);
  const pts = data.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const last = data[data.length - 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-24" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.08" />
        </linearGradient>
      </defs>
      {/* Kişisel referans bandı (±2σ) */}
      <rect x={pad} y={y(hi)} width={w - 2 * pad} height={y(lo) - y(hi)} fill={`url(#${gid})`} rx="4" />
      <line x1={pad} x2={w - pad} y1={y(mean)} y2={y(mean)} stroke="#22d3ee" strokeOpacity="0.55" strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
      {data.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={i === data.length - 1 ? 3.5 : 1.6} fill={i === data.length - 1 ? color : 'currentColor'} className="text-slate-400" vectorEffect="non-scaling-stroke" />
      ))}
      <circle cx={x(data.length - 1)} cy={y(last)} r="7" fill={color} opacity="0.25" className="ai-ping" />
    </svg>
  );
};

/**
 * Yapay zekâ sağlık asistanı:
 * ölçüm → kişisel referans → RAG (NASA + hakemli yayın) → LLM yorumu → öneri/aksiyon → takip & bildirim
 */
export const AiInsightPanel: React.FC = () => {
  const { vitals, currentAlert, setOpenActionPlanModal, astronaut } = useTelemetry();
  const { t, pick } = usePrefs();
  const next = useNextReading();
  const [showSources, setShowSources] = useState(false);

  // Odak gösterge: önce kritik, sonra dikkat; yoksa kişisel bandın en uzağındaki gösterge
  const candidates = Object.keys(AI_INSIGHTS).filter((k) => vitals[k as keyof typeof vitals]);
  const z = (k: string) => {
    const b = PERSONAL_BASELINES[k];
    const v = Number(vitals[k as keyof typeof vitals]?.value);
    return b && isFinite(v) ? (v - b.mean) / b.sd : 0;
  };
  const rank = (k: string) => {
    const s = vitals[k as keyof typeof vitals]?.status;
    return (s === 'critical' ? 100 : s === 'warning' ? 50 : 0) + Math.abs(z(k));
  };
  // Sapan gösterge yoksa açık uyarının göstergesi (demo uyarısı SANS → göz basıncı) odakta kalır;
  // böylece canlı değerler dalgalanırken panel göstergeler arasında atlamaz.
  const sorted = [...candidates].sort((a, b) => rank(b) - rank(a));
  const anyAbnormal = sorted.some((k) => vitals[k as keyof typeof vitals]?.status !== 'normal');
  const focus = anyAbnormal || !currentAlert ? sorted[0] ?? 'iop' : 'iop';
  const metric = vitals[focus as keyof typeof vitals];
  const base = PERSONAL_BASELINES[focus];
  const insight = AI_INSIGHTS[focus];
  const value = Number(metric.value);
  const zf = z(focus);
  const deviating = Math.abs(zf) >= 2 || metric.status !== 'normal' || (!anyAbnormal && !!currentAlert);
  const pct = ((value - base.mean) / base.mean) * 100;
  const severe = metric.status === 'critical' || Math.abs(zf) >= 4;
  const escalated = severe || (deviating && !!currentAlert?.notifiedGroundControl);
  const color = metric.status === 'critical' ? '#EF4444' : deviating ? '#F59E0B' : '#10B981';
  const history = metric.history.slice(-12);


  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 ai-panel overflow-hidden" aria-labelledby="ai-heading">
      {/* Başlık */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="ai-orb shrink-0">
            <BrainCircuit className="w-5 h-5 text-white" />
          </span>
          <div className="min-w-0">
            <h2 id="ai-heading" className="text-base font-bold text-slate-900 leading-tight">
              {t('Yapay Zekâ Sağlık Asistanı', 'AI Health Assistant')}
            </h2>
            <p className="text-xs text-slate-500">
              {t('Kişisel referans + NASA ve hakemli yayınlar', 'Personal baseline + NASA & peer-reviewed sources')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded-lg border border-cyan-300/60 text-cyan-700 font-semibold font-mono bg-cyan-50/50">RAG · LLM</span>
          <span className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-slate-200 text-slate-600" title={t('Bir sonraki ölçüm', 'Next reading')}>
            <Clock className="w-3.5 h-3.5" />
            <span className="font-mono font-semibold">{next.label}</span>
          </span>
        </div>
      </div>


      {!deviating ? (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
          <ShieldCheck className="w-6 h-6 text-emerald-600 shrink-0" />
          <div className="text-sm">
            <div className="font-semibold text-slate-900">{t('Tüm ölçümler kişisel referans bandınızda', 'All readings are within your personal baseline')}</div>
            <div className="text-slate-500">{t('Yeni bir sapma olursa yorum ve öneriler burada görünecek.', 'If a new deviation appears, interpretation and advice will show here.')}</div>
          </div>
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* Tespit */}
            <div className="md:col-span-2 rounded-xl border border-slate-200 bg-slate-50/40 p-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{t('Tespit edilen sapma', 'Detected deviation')}</div>
              <div className="mt-1 text-sm font-semibold text-slate-800">{vitalLabel(focus, t)}</div>
              <div className="mt-2 flex items-end gap-3">
                <div>
                  <div className="text-[10px] text-slate-400">{t('Şimdi', 'Now')}</div>
                  <div className="text-2xl font-bold font-mono leading-none" style={{ color }}>
                    {value}
                    <span className="ml-1 text-xs font-normal text-slate-500">{metric.unit}</span>
                  </div>
                </div>
                <div className="pb-0.5">
                  <div className="text-[10px] text-slate-400">{t('Kişisel referans', 'Personal baseline')}</div>
                  <div className="text-sm font-mono text-slate-600 whitespace-nowrap">
                    {base.mean} ± {base.sd}
                  </div>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-semibold">
                <span className="px-1.5 py-0.5 rounded-md border" style={{ color, borderColor: `${color}66`, background: `${color}14` }}>
                  {pct >= 0 ? '+' : ''}
                  {pct.toFixed(0)}%
                </span>
                <span className="px-1.5 py-0.5 rounded-md border border-slate-200 text-slate-600 font-mono">
                  {zf >= 0 ? '+' : ''}
                  {zf.toFixed(1)}σ
                </span>
                {metric.status === 'normal' && (
                  <span className="px-1.5 py-0.5 rounded-md border border-slate-200 text-slate-500 font-normal">
                    {t('Genel aralıkta normal', 'Normal by population range')}
                  </span>
                )}
              </div>
              <div className="mt-2 text-slate-400">
                <BaselineChart data={history} mean={base.mean} sd={base.sd} color={color} />
              </div>
              <div className="flex justify-between text-[10px] text-slate-400">
                <span>{t(`Son ${history.length} ölçüm`, `Last ${history.length} readings`)}</span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2 rounded-sm bg-cyan-400/40" />
                  {t('Kişisel bant (±2σ)', 'Personal band (±2σ)')}
                </span>
              </div>
            </div>

            {/* LLM yorumu */}
            <div className="md:col-span-3 flex flex-col">
              <div className="flex-1 rounded-xl border border-cyan-300/50 bg-gradient-to-br from-cyan-50/60 to-indigo-50/40 p-4 flex gap-3">
                <p key={focus} className="text-sm leading-relaxed text-slate-700 ai-reveal">
                  {pick(insight.interpretation)}
                </p>
              </div>
            </div>
          </div>

          {/* Destekleyici aksiyon protokolleri */}
          <div className="mt-4">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">{t('Destekleyici aksiyon protokolleri', 'Supporting action protocols')}</div>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {insight.recommendations.map((r, i) => (
                <li key={i} className="flex gap-2 rounded-lg border border-slate-200 bg-white/40 px-3 py-2 text-sm text-slate-700 leading-snug">
                  <CheckCircle2 className="w-4 h-4 text-cyan-500 shrink-0 mt-0.5" />
                  {pick(r)}
                </li>
              ))}
            </ul>
          </div>

          {/* Takip: tek satırlık kompakt şerit */}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-slate-200 px-3 py-2 text-xs">
            <div className="flex items-center gap-2 min-w-[11rem] flex-1">
              <Clock className="w-3.5 h-3.5 text-cyan-600 shrink-0" />
              <span className="text-slate-600 whitespace-nowrap">{t('Sonraki ölçüm', 'Next reading')}</span>
              <span className="font-mono font-semibold text-slate-800">{next.label}</span>
              <span className="flex-1 min-w-[2.5rem] h-1 rounded-full bg-slate-200/70 overflow-hidden">
                <span className="block h-full rounded-full ai-bar" style={{ width: `${next.ratio * 100}%` }} />
              </span>
              <span
                className="text-slate-400 whitespace-nowrap"
                title={t(
                  `${insight.followUpReadings} ölçüm sonra yeniden değerlendirilecek.`,
                  `Re-evaluated after ${insight.followUpReadings} more reading${insight.followUpReadings > 1 ? 's' : ''}.`
                )}
              >
                ↻ {insight.followUpReadings}
              </span>
            </div>
            <span
              className={`flex items-center gap-1 whitespace-nowrap ${escalated ? 'text-amber-700 font-semibold' : 'text-slate-500'}`}
            >
              <BellRing className="w-3.5 h-3.5" />
              {escalated ? t('Ekibe bildirildi', 'Team notified') : t('İzlemede', 'Monitoring')}
            </span>
            <button
              type="button"
              onClick={() => setOpenActionPlanModal(true)}
              disabled={!currentAlert || !!astronaut.isDisplayOnly}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Rocket className="w-3.5 h-3.5" />
              {t('Aksiyon planı', 'Action plan')}
            </button>
          </div>

          {/* Olası nedenler */}
          <div className="mt-4">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">{t('Olası nedenler', 'Possible causes')}</div>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5">
              {insight.causes.map((c) => {
                const col = likelihoodColor(c.likelihood);
                return (
                  <li key={pick(c.text)} className="text-sm">
                    <div className="flex justify-between gap-2">
                      <span className="text-slate-700 leading-snug">{pick(c.text)}</span>
                      <span className="font-mono text-xs font-semibold shrink-0" style={{ color: col }}>
                        {Math.round(c.likelihood * 100)}%
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-slate-200/70 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${c.likelihood * 100}%`,
                          background: `linear-gradient(90deg, ${likelihoodColor(0)}, ${col})`,
                          boxShadow: `0 0 8px ${col}`,
                        }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Kaynaklar */}
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setShowSources((v) => !v)}
              aria-expanded={showSources}
              className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900"
            >
              <BookOpen className="w-3.5 h-3.5 text-cyan-600" />
              {t(`Dayanak: ${insight.sources.length} kaynak`, `Grounded in ${insight.sources.length} sources`)}
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showSources ? 'rotate-180' : ''}`} />
            </button>
            {showSources && (
              <ul className="mt-2 space-y-1.5">
                {insight.sources.map((s) => (
                  <li key={s.title} className="flex items-start gap-2 text-xs rounded-lg border border-slate-200 px-3 py-2">
                    <span
                      className={`px-1.5 py-0.5 rounded font-bold shrink-0 ${
                        s.kind === 'nasa' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 border border-slate-200'
                      }`}
                    >
                      {s.kind === 'nasa' ? 'NASA' : t('Makale', 'Paper')}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-slate-800 leading-snug">{s.title}</span>
                      <span className="block text-slate-500">{s.ref}</span>
                    </span>
                    <span className="font-mono text-slate-500 shrink-0" title={t('Eşleşme', 'Relevance')}>
                      {Math.round(s.relevance * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      {/* Backend analiz işi (elle yeniden çalıştırma) */}
      <AnalysisStatus />

      <p className="mt-3 text-[10px] text-slate-400">
        {t(
          'Örnek çıktı. Öneriler uçuş cerrahının kararının yerine geçmez.',
          'Sample output. Advice does not replace the flight surgeon’s decision.'
        )}
      </p>
    </section>
  );
};
