import React, { useId } from 'react';
import { Activity, Droplet, Eye, Gauge, Heart, Info, Thermometer, Wind } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import type { MetricStatus, VitalMetric } from '../../types/telemetry';
import { AiInsightPanel } from './AiInsightPanel';
import { TodayGoals } from './TodayGoals';
import { statusMeta } from '../../utils/status';

const ScoreRing: React.FC<{ count: number; total: number }> = ({ count, total }) => {
  const gid = useId().replace(/:/g, '');
  const radius = 51, size = 136, c = size / 2, stroke = 9, circ = 2 * Math.PI * radius;
  const ratio = total ? count / total : 0;
  return <div className="relative shrink-0" style={{ width: size, height: size }}>
    <svg width={size} height={size} aria-hidden>
      <defs><linearGradient id={gid} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#38bdf8" /><stop offset="1" stopColor="#0284c7" /></linearGradient></defs>
      <circle cx={c} cy={c} r={radius} stroke="#e2e8f0" strokeWidth={stroke} fill="none" />
      <g transform={`rotate(-90 ${c} ${c})`}><circle cx={c} cy={c} r={radius} stroke={`url(#${gid})`} strokeWidth={stroke} strokeDasharray={circ} strokeDashoffset={circ - ratio * circ} strokeLinecap="round" fill="none" /></g>
    </svg>
    <div className="absolute inset-0 grid place-items-center text-center"><div><div className="font-mono text-3xl font-black text-sky-800">{count}</div><div className="text-[11px] text-slate-500">/ {total || '—'} kayıt</div></div></div>
  </div>;
};

const ICONS: Record<string, React.ReactNode> = {
  pulse: <Heart className="h-3.5 w-3.5 text-rose-500" />, oxygen: <Wind className="h-3.5 w-3.5 text-cyan-500" />,
  glucose: <Droplet className="h-3.5 w-3.5 text-sky-500" />, temperature: <Thermometer className="h-3.5 w-3.5 text-amber-500" />,
  iop: <Eye className="h-3.5 w-3.5 text-indigo-500" />, bp: <Gauge className="h-3.5 w-3.5 text-blue-500" />,
};

const rank: Record<MetricStatus, number> = { normal: 0, warning: 1, critical: 2 };

/** Tansiyon tek kart: büyük/küçük tansiyon ayrı ölçülür ve ayrı eşikle karşılaştırılır */
const bloodPressure = (sys: VitalMetric, dia: VitalMetric): VitalMetric & { display: string } => {
  const both = [sys, dia].filter((m) => Number.isFinite(m.value));
  const status = both.reduce<MetricStatus>((w, m) => (rank[m.status] > rank[w] ? m.status : w), 'normal');
  return {
    ...sys, id: 'bp', shortName: 'Tansiyon', unit: 'mmHg', status,
    value: both.length ? sys.value : Number.NaN,
    rangeKnown: both.length === 2 && both.every((m) => m.rangeKnown),
    display: `${Number.isFinite(sys.value) ? sys.value : '—'}/${Number.isFinite(dia.value) ? dia.value : '—'}`,
  };
};

export const LeftColumnVitals: React.FC = () => {
  const { vitals, setSelectedAnatomyZone, currentAlert } = useTelemetry();
  const { t } = usePrefs();
  const bp = bloodPressure(vitals.bp_systolic, vitals.bp_diastolic);
  const cards: { id: string; metric: VitalMetric; display?: string }[] = [
    { id: 'pulse', metric: vitals.pulse }, { id: 'bp', metric: bp, display: bp.display },
    { id: 'oxygen', metric: vitals.oxygen }, { id: 'glucose', metric: vitals.glucose },
    { id: 'temperature', metric: vitals.temperature }, { id: 'iop', metric: vitals.iop },
  ];
  const measured = cards.filter(({ metric }) => Number.isFinite(metric.value));
  // Eşiği olmayan ölçüm "normal" sayılmaz: ayrı satırda gösterilir
  const judged = measured.filter(({ metric }) => metric.rangeKnown);
  const counts = { normal: judged.filter(({ metric }) => metric.status === 'normal').length, warning: judged.filter(({ metric }) => metric.status === 'warning').length, critical: judged.filter(({ metric }) => metric.status === 'critical').length, unknown: measured.length - judged.length };
  const worst: MetricStatus = counts.critical ? 'critical' : counts.warning ? 'warning' : 'normal';
  const anySynthetic = measured.some(({ metric }) => metric.synthetic || (metric.id === 'bp' && vitals.bp_systolic.synthetic));
  const zoneFor = (id: string) => id === 'pulse' || id === 'oxygen' || id === 'bp' ? 'chest' : id === 'glucose' || id === 'temperature' ? 'abdomen' : 'head';
  const limitOf = (m: VitalMetric) => {
    if (m.id === 'bp') {
      const s = vitals.bp_systolic, d = vitals.bp_diastolic;
      return s.rangeKnown && d.rangeKnown ? t(`Üst sınır ${s.upperLimit}/${d.upperLimit} mmHg`, `Upper limit ${s.upperLimit}/${d.upperLimit} mmHg`) : t('Eşik tanımlı değil', 'No threshold defined');
    }
    if (!m.rangeKnown) return t('Eşik tanımlı değil', 'No threshold defined');
    const parts = [m.lowerLimit != null ? t(`alt ${m.lowerLimit}`, `min ${m.lowerLimit}`) : null, m.upperLimit != null ? t(`üst ${m.upperLimit}`, `max ${m.upperLimit}`) : null].filter(Boolean);
    return `${t('Sınır', 'Limit')}: ${parts.join(' · ')} ${m.unit}`;
  };
  return <div className="flex flex-col gap-5">
    <section className="bg-white rounded-2xl border border-slate-200 p-5">
      <div className="flex items-center justify-between"><h2 className="flex items-center gap-1.5 text-base font-bold text-slate-900">{t('Sağlık Özeti', 'Health Summary')}<Info className="h-3.5 w-3.5 text-slate-400" /></h2>
        <span className="flex items-center gap-1.5 text-xs font-semibold text-sky-700"><span className="h-2 w-2 rounded-full bg-sky-500" />{t('Veritabanı', 'Database')}</span></div>
      <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-center">
        <div className="flex flex-1 items-center gap-3 md:justify-center"><ScoreRing count={measured.length} total={cards.length} />
          <div className="text-sm text-slate-600"><div className="font-bold text-slate-900">{measured.length ? t('Kayıtlı ölçümler', 'Stored measurements') : t('Ölçüm kaydı yok', 'No measurement record')}</div>
            <ul className="mt-2 space-y-1"><li><b>{counts.normal}</b> {t('aralık içinde', 'within range')}</li><li className={counts.warning ? 'font-semibold text-amber-700' : ''}><b>{counts.warning}</b> {t('aralık dışı (dikkat)', 'out of range (caution)')}</li><li><b>{counts.critical}</b> {t('kritik', 'critical')}</li>{counts.unknown > 0 && <li><b>{counts.unknown}</b> {t('eşik tanımsız', 'no threshold')}</li>}</ul>
            <p className="mt-2 text-xs text-slate-500">{t('Durum, analizin kullandığı eşiklerden (demo eşikleri, klinik değil).', 'Status from the thresholds the analysis uses (demo limits, not clinical).')}</p>
            {anySynthetic && <p className="mt-1 text-xs font-medium text-slate-500">{t('Kaynak: veritabanındaki sentetik demo ölçümleri.', 'Source: synthetic demo measurements in the database.')}</p>}</div>
        </div>
        <div className="min-w-0 md:border-l md:border-slate-200 md:pl-4"><div className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">{t('Yaşamsal bulgular', 'Vital signs')}</div>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">{cards.map(({ id, metric, display }) => {
            const available = Number.isFinite(metric.value); const judgedHere = available && metric.rangeKnown;
            const meta = statusMeta(judgedHere ? metric.status : 'normal', t);
            const out = judgedHere && metric.status !== 'normal';
            return <button type="button" key={id} onClick={() => setSelectedAnatomyZone(zoneFor(id))} title={available ? limitOf(metric) : undefined} className={`rounded-lg border px-2.5 py-1.5 text-left transition-all hover:-translate-y-0.5 ${judgedHere ? meta.card : 'border-slate-200 bg-slate-50'}`}>
              <div className="flex items-center gap-1">{ICONS[id] ?? <Activity className="h-3.5 w-3.5" />}<span className="text-[11px] font-semibold text-slate-500">{id === 'bp' ? t('Tansiyon', 'Blood pressure') : metric.shortName}</span></div>
              <div className={`mt-0.5 whitespace-nowrap text-sm font-bold font-mono ${judgedHere ? meta.text : 'text-slate-400'}`}>{available ? (display ?? metric.value) : '—'} <span className="text-[10px] font-normal text-slate-500">{metric.unit}</span></div>
              {available && <div className={`text-[10px] ${out ? 'font-semibold text-amber-700' : 'text-slate-400'}`}>{out ? `${meta.label} · ${limitOf(metric)}` : judgedHere ? t('Aralıkta', 'In range') : t('Eşik yok', 'No threshold')}</div>}
            </button>;
          })}</div>
        </div>
      </div>
      {currentAlert && <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t('Açık alarm kaydı var. Eylem planından ayrıntıyı görüntüleyin.', 'There is an open alert record. View details in the action plan.')}</div>}
    </section>
    <AiInsightPanel />
    <TodayGoals horizontal />
  </div>;
};
