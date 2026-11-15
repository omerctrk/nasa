import React from 'react';
import { ArrowDownToLine, Radiation, Satellite, Users, Wind } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { formatDelay } from '../../data/missionProfiles';
import { statusMeta } from '../../utils/status';
import type { VitalMetric } from '../../types/telemetry';

type Card = { id: string; Icon: React.ElementType; title: string; value: string; sub: string; metric?: VitalMetric; tag?: string };

/**
 * Görev ortam koşulları. Kaynaklar:
 * - Radyasyon, kabin CO₂: veritabanı ölçümleri (anomaly.MeasurementRecords; sentetik demo kaynağı,
 *   kişisel dozimetre / modül CO₂ sensörü). Sentetikse kartta açıkça yazılır.
 * - İzolasyon: günlük check-in (yalnızlık, mürettebat ilişkisi; 0–4 puan).
 * - Uzaklık, yerçekimi: ölçüm değil, görev profilinin sabitleri (senaryo → missionProfiles).
 */
export const HazardsPanel: React.FC = () => {
  const { missionProfile, vitals } = useTelemetry();
  const { t, pick, lang } = usePrefs();
  const has = (m?: VitalMetric) => !!m && Number.isFinite(m.value);
  const synthetic = t('sentetik', 'synthetic');

  // Radyasyon: bugünkü doz + görev boyunca birikmiş (kayıtların toplamı)
  const rad = vitals.radiation;
  const cumulative = has(rad) ? rad.history.reduce((a, b) => a + b, 0) : 0;
  // Uzaklık / yerçekimi: görev profili
  const g = missionProfile.gravityG;
  const lone = vitals.loneliness, crew = vitals.crew;

  const cards: Card[] = [
    { id: 'radiation', Icon: Radiation, title: t('Radyasyon', 'Radiation'),
      value: has(rad) ? `${rad.value} ${t('mSv/gün', 'mSv/day')}` : t('Kayıt yok', 'No record'),
      sub: has(rad) ? t(`Görev toplamı ${cumulative.toFixed(1)} mSv · ${rad.history.length} gün`, `Mission total ${cumulative.toFixed(1)} mSv · ${rad.history.length} days`)
        : t('Dozimetre kaydı yok', 'No dosimeter record'),
      tag: rad.synthetic ? synthetic : undefined },
    { id: 'isolation', Icon: Users, title: t('İzolasyon', 'Isolation'),
      value: has(lone) || has(crew)
        ? `${t('Yalnızlık', 'Loneliness')} ${has(lone) ? lone.value : '—'}/4`
        : t('Kayıt yok', 'No record'),
      sub: has(crew) ? t(`Mürettebat ilişkisi ${crew.value}/4 · check-in ${crew.lastDate ?? ''}`, `Crew relations ${crew.value}/4 · check-in ${crew.lastDate ?? ''}`)
        : t('Check-in kaydı yok', 'No check-in record') },
    { id: 'distance', Icon: Satellite, title: t('Uzaklık', 'Distance'),
      value: `${formatDelay(missionProfile.oneWayDelaySec, lang)} ${t('gecikme', 'delay')}`,
      sub: t(`Tek yön iletişim · ${pick(missionProfile.name)}`, `One-way comms · ${pick(missionProfile.name)}`), tag: t('görev profili', 'mission profile') },
    { id: 'gravity', Icon: ArrowDownToLine, title: t('Yerçekimi', 'Gravity'),
      value: g === 0 ? '≈0 g' : `${g} g`,
      sub: g === 0 ? t('Mikro yerçekimi (~10⁻⁶ g)', 'Microgravity (~10⁻⁶ g)') : `${(g * 9.80665).toFixed(2)} m/s²`,
      tag: t('görev profili', 'mission profile') },
    { id: 'environment', Icon: Wind, title: t('Kapalı ortam', 'Closed environment'),
      value: has(vitals.co2) ? `CO₂ ${vitals.co2.value} mmHg` : t('Kayıt yok', 'No record'),
      sub: has(vitals.co2)
        ? (vitals.co2.rangeKnown ? t(`Kabin CO₂ · üst sınır ${vitals.co2.upperLimit} mmHg`, `Cabin CO₂ · limit ${vitals.co2.upperLimit} mmHg`) : t('Kabin CO₂ · eşik tanımsız', 'Cabin CO₂ · no threshold'))
        : t('Kabin sensörü kaydı yok', 'No cabin sensor record'),
      metric: vitals.co2, tag: vitals.co2.synthetic ? synthetic : undefined },
  ];

  return <section aria-labelledby="hazards-heading">
    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 px-1"><h2 id="hazards-heading" className="text-sm font-bold text-slate-800">{t('Görev Ortam Koşulları', 'Mission Environment Conditions')}</h2>
      <span className="text-xs text-slate-500">{t('Veritabanı kayıtları ve görev profili', 'Database records and mission profile')}</span></div>
    <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">{cards.map(({ id, Icon, title, value, sub, metric, tag }) => {
      const out = metric && has(metric) && metric.rangeKnown && metric.status !== 'normal';
      const meta = statusMeta(out ? metric!.status : 'normal', t);
      return <div key={id} className={`flex min-w-0 flex-col gap-1 rounded-xl border p-3 shadow-sm ${out ? meta.card : 'border-slate-200 bg-white'}`}>
        <div className="flex items-center justify-between gap-1.5 text-xs font-semibold text-slate-600">
          <span className="flex items-center gap-1.5"><Icon className="h-4 w-4 text-slate-500" />{title}</span>
          {tag && <span className="rounded border border-slate-200 bg-slate-50 px-1 text-[10px] font-medium text-slate-500">{tag}</span>}
        </div>
        <div className={`truncate font-mono text-base font-bold ${out ? meta.text : 'text-slate-900'}`}>{value}</div>
        <div className={`text-xs ${out ? 'font-semibold text-amber-700' : 'text-slate-500'}`}>{out ? `${meta.label} · ${sub}` : sub}</div>
      </div>;
    })}</div>
  </section>;
};
