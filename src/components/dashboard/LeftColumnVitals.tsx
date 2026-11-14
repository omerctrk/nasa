import React, { useId } from 'react';
import {
  Activity,
  Heart,
  Droplet,
  Thermometer,
  Moon,
  Gauge,
  Info,
  FlaskConical,
} from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { MetricStatus } from '../../types/telemetry';
import { AiInsightPanel } from './AiInsightPanel';
import { TodayGoals } from './TodayGoals';
import { playUiBeep } from '../../utils/audio';
import { statusMeta, vitalLabel } from '../../utils/status';
import { HAZARDS, METRIC_HAZARD } from '../../data/hazards';

// Normal aralıktaki gösterge oranı (ortak "sağlık puanı" değildir; backend böyle bir puan üretmez).
// Neon görünüm: parlayan halka, yavaş dönen yörünge, ışıldayan sayı.
const ScoreRing: React.FC<{ normal: number; total: number; color: string }> = ({ normal, total, color }) => {
  const gid = useId().replace(/:/g, '');
  const ratio = total ? normal / total : 0;
  const size = 136;
  const c = size / 2;
  const radius = 51;
  const stroke = 9;
  const circ = 2 * Math.PI * radius;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      {/* Arka ışıma */}
      <div
        className="absolute inset-3 rounded-full neon-ring"
        style={{ background: `radial-gradient(circle, ${color}33 0%, transparent 70%)` }}
        aria-hidden
      />
      <svg width={size} height={size} className="relative" aria-hidden>
        <defs>
          <linearGradient id={`${gid}-g`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.55" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id={`${gid}-glow`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* Yavaş dönen yörünge */}
        <g className="orbit-spin">
          <circle cx={c} cy={c} r={radius + 13} fill="none" stroke={color} strokeOpacity="0.35" strokeWidth="1" strokeDasharray="2 7" />
          <circle cx={c} cy={c - radius - 13} r="2.5" fill={color} filter={`url(#${gid}-glow)`} />
        </g>
        {/* İz */}
        <circle cx={c} cy={c} r={radius} stroke={color} strokeOpacity="0.14" strokeWidth={stroke} fill="none" />
        {/* İlerleme */}
        <g transform={`rotate(-90 ${c} ${c})`} className="neon-ring">
          <circle
            cx={c}
            cy={c}
            r={radius}
            stroke={`url(#${gid}-g)`}
            strokeWidth={stroke}
            strokeDasharray={circ}
            strokeDashoffset={circ - ratio * circ}
            strokeLinecap="round"
            fill="none"
            filter={`url(#${gid}-glow)`}
            className="transition-all duration-700 ease-out"
          />
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-black tracking-tight leading-none font-mono neon-text" style={{ color }}>
          {normal}
        </span>
        <span className="text-xs font-semibold text-slate-500 mt-1">/ {total}</span>
      </div>
    </div>
  );
};

const METRIC_ICONS: Record<string, React.ReactNode> = {
  pulse: <Heart className="w-3.5 h-3.5 text-rose-500" />,
  bp: <Gauge className="w-3.5 h-3.5 text-blue-500" />,
  glucose: <Droplet className="w-3.5 h-3.5 text-sky-500" />,
  temperature: <Thermometer className="w-3.5 h-3.5 text-amber-500" />,
  sleep: <Moon className="w-3.5 h-3.5 text-purple-500" />,
};

export const LeftColumnVitals: React.FC = () => {
  const { vitals, setSelectedAnatomyZone, triggerManualAlert, currentAlert } = useTelemetry();
  const { t, pick } = usePrefs();

  const worstOf = (...st: MetricStatus[]): MetricStatus =>
    st.includes('critical') ? 'critical' : st.includes('warning') ? 'warning' : 'normal';
  const bpStatus = worstOf(vitals.bp_systolic.status, vitals.bp_diastolic.status);

  // Backend'in ölçtüğü göstergeler: nabız, tansiyon (büyük/küçük), kan şekeri, vücut ısısı
  const cards: {
    id: string;
    value: string | number;
    unit: string;
    status: MetricStatus;
  }[] = [
    { id: 'pulse', value: vitals.pulse.value, unit: vitals.pulse.unit, status: vitals.pulse.status },
    { id: 'bp', value: `${vitals.bp_systolic.value}/${vitals.bp_diastolic.value}`, unit: 'mmHg', status: bpStatus },
    { id: 'glucose', value: vitals.glucose.value, unit: vitals.glucose.unit, status: vitals.glucose.status },
    { id: 'temperature', value: vitals.temperature.value, unit: vitals.temperature.unit, status: vitals.temperature.status },
  ];

  const all = cards;
  const counts = {
    normal: all.filter((m) => m.status === 'normal').length,
    warning: all.filter((m) => m.status === 'warning').length,
    critical: all.filter((m) => m.status === 'critical').length,
  };

  // Genel durum: göstergelerin ve açık uyarının EN KÖTÜ seviyesi (sayısal puan yok).
  // Backend'de seviyeler: anomali watch → WARNING, review → WARNING/CRITICAL.
  const worst =
    counts.critical > 0 || currentAlert?.severity === 'critical'
      ? 'critical'
      : counts.warning > 0 || currentAlert?.severity === 'warning'
        ? 'warning'
        : 'normal';
  const verdict =
    worst === 'normal'
      ? { text: t('Görev için uygun', 'Fit for duty'), color: '#10B981', cls: 'text-emerald-700' }
      : worst === 'warning'
        ? { text: t('Yakından izleniyor', 'Under close watch'), color: '#F59E0B', cls: 'text-amber-700' }
        : { text: t('Müdahale gerekli', 'Action required'), color: '#EF4444', cls: 'text-red-700' };

  const zoneFor = (id: string) =>
    id === 'pulse' || id === 'bp'
      ? 'chest'
      : id === 'glucose' || id === 'temperature'
        ? 'abdomen'
        : 'head';

  const handleCardClick = (metricId: string) => {
    playUiBeep(750);
    setSelectedAnatomyZone(zoneFor(metricId));
  };

  const ranges: Record<string, string> = {
    pulse: '60–90 bpm',
    bp: '90–130 / 60–85',
    glucose: '70–110 mg/dL',
    temperature: '36.3–37.2 °C',
    sleep: t('7–8.5 saat', '7–8.5 h'),
  };

  // Küçük kutucuklar için kısa adlar (tam ad üzerine gelince görünür)
  const shortLabel: Record<string, string> = {
    pulse: t('Nabız', 'Pulse'),
    bp: t('Tansiyon', 'BP'),
    glucose: t('Şeker', 'Glucose'),
    temperature: t('Isı', 'Temp.'),
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Üst: sağlık özeti (tam genişlik, yatay) */}
      <section className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 text-base font-bold text-slate-900">
              {t('Sağlık Özeti', 'Health Summary')}
              <span
                title={t(
                  'Halka, normal aralıktaki gösterge sayısını; durum metni en yüksek uyarı seviyesini gösterir.',
                  'The ring shows how many indicators are in range; the status reflects the highest alert level.'
                )}
              >
                <Info className="w-3.5 h-3.5 text-slate-400" />
              </span>
            </h2>
            <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              {t('Canlı', 'Live')}
            </span>
          </div>

          <div className="mt-3 flex flex-col md:flex-row md:items-center gap-4">
            {/* Odak: halka */}
            <div className="flex flex-1 items-center md:justify-center gap-3 min-w-0">
              <ScoreRing normal={counts.normal} total={all.length} color={verdict.color} />
              <div className="min-w-0">
                <div className={`text-base font-bold leading-snug ${verdict.cls}`}>{verdict.text}</div>
                <ul className="mt-2 space-y-1 text-sm text-slate-600">
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="font-mono font-bold text-slate-800">{counts.normal}</span> {t('normal', 'normal')}
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    <span className="font-mono font-bold text-slate-800">{counts.warning}</span> {t('dikkat', 'caution')}
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    <span className="font-mono font-bold text-slate-800">{counts.critical}</span> {t('kritik', 'critical')}
                  </li>
                </ul>
              </div>
            </div>

            {/* Yaşamsal bulgular: küçük kutucuklar */}
            <div className="min-w-0 md:flex-none md:pl-4 md:border-l md:border-slate-200/70" aria-label={t('Yaşamsal bulgular', 'Vital signs')}>
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">
                {t('Yaşamsal bulgular', 'Vital signs')}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-[repeat(2,max-content)] gap-1.5">
                {cards.map((c) => {
                  const meta = statusMeta(c.status, t);
                  const hazard = METRIC_HAZARD[c.id];
                  const tip = [
                    `${vitalLabel(c.id, t)}: ${c.value} ${c.unit}`,
                    `${t('Aralık', 'Range')}: ${ranges[c.id]}`,
                    c.status !== 'normal' ? meta.label : '',
                    hazard ? `${t('İlişkili tehlike', 'Related hazard')}: ${pick(HAZARDS[hazard].name)}` : '',
                  ]
                    .filter(Boolean)
                    .join(' · ');
                  return (
                    <button
                      type="button"
                      key={c.id}
                      onClick={() => handleCardClick(c.id)}
                      title={tip}
                      className={`text-left rounded-lg border px-2.5 py-1.5 md:min-w-[5.75rem] transition-all hover:-translate-y-0.5 ${meta.card}`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="flex items-center gap-1 min-w-0">
                          {METRIC_ICONS[c.id] ?? <Activity className="w-3.5 h-3.5 text-slate-500" />}
                          <span className="text-[11px] font-semibold text-slate-500 truncate">{shortLabel[c.id] ?? vitalLabel(c.id, t)}</span>
                        </span>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-baseline gap-x-1 whitespace-nowrap">
                        <span className={`text-sm font-bold font-mono tracking-tight ${meta.text}`}>{c.value}</span>
                        <span className="text-[10px] text-slate-500">{c.unit}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

      {/* Yapay zekâ sağlık asistanı */}
      <AiInsightPanel />

      {/* Bugünkü hedefler: yatay */}
      <TodayGoals horizontal />

      {/* Demo: sunumda uyarı akışını göstermek için (sade) */}
      <div className="flex flex-wrap items-center gap-2 px-1 text-xs text-slate-400">
        <FlaskConical className="w-3.5 h-3.5" />
        <span>{t('Demo uyarısı:', 'Demo alert:')}</span>
        {[
          { k: 'bp', l: t('Tansiyon', 'Blood pressure') },
          { k: 'pulse', l: t('Nabız', 'Heart rate') },
          { k: 'temperature', l: t('Ateş', 'Fever') },
        ].map((d) => (
          <button
            key={d.k}
            onClick={() => triggerManualAlert(d.k)}
            className="px-2 py-0.5 rounded-md border border-slate-200 text-slate-500 hover:text-slate-800 hover:border-slate-400 transition-colors"
          >
            {d.l}
          </button>
        ))}
      </div>
    </div>
  );
};
