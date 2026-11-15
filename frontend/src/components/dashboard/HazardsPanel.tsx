import React from 'react';
import { ArrowDownToLine, Radiation, Satellite, Users, Wind } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';

const entries = [
  { id: 'radiation', Icon: Radiation, tr: 'Radyasyon', en: 'Radiation', source: 'Doz kaynağı bağlı değil' },
  { id: 'isolation', Icon: Users, tr: 'İzolasyon', en: 'Isolation', source: 'Davranış kaynağı bağlı değil' },
  { id: 'distance', Icon: Satellite, tr: 'Uzaklık', en: 'Distance', source: 'Gecikme kaynağı bağlı değil' },
  { id: 'gravity', Icon: ArrowDownToLine, tr: 'Yerçekimi', en: 'Gravity', source: 'Görev profili' },
  { id: 'environment', Icon: Wind, tr: 'Kapalı ortam', en: 'Closed environment', source: 'Kabin sensörü bağlı değil' },
] as const;

export const HazardsPanel: React.FC = () => {
  const { missionProfile } = useTelemetry();
  const { t, pick } = usePrefs();
  // Yerçekimi bir ölçüm değil, görev ortamının sabitidir (görev senaryosu → missionProfiles.gravityG).
  // Birim g = standart yerçekimi ivmesi (9.80665 m/s²). Yörüngede serbest düşüş: mikro yerçekimi (~10⁻⁶ g).
  const g = missionProfile.gravityG;
  const gravityValue = g === 0 ? '≈0 g' : `${g} g`;
  const gravitySub = g === 0
    ? t(`Mikro yerçekimi (~10⁻⁶ g) · ${pick(missionProfile.name)}`, `Microgravity (~10⁻⁶ g) · ${pick(missionProfile.name)}`)
    : `${(g * 9.80665).toFixed(2)} m/s² · ${pick(missionProfile.name)}`;
  return <section aria-labelledby="hazards-heading">
    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 px-1"><h2 id="hazards-heading" className="text-sm font-bold text-slate-800">{t('Görev Ortam Koşulları', 'Mission Environment Conditions')}</h2>
      <span className="text-xs text-slate-500">{t('Yalnızca bağlı veri kaynakları gösterilir', 'Only connected data sources are shown')}</span></div>
    <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">{entries.map(({ id, Icon, tr, en, source }) => {
      const value = id === 'gravity' ? gravityValue : t('Kayıt yok', 'No record');
      const sub = id === 'gravity' ? gravitySub : t(source, source);
      return <div key={id} className="flex min-w-0 flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600"><Icon className="h-4 w-4 text-slate-500" />{t(tr, en)}</div>
        <div className="truncate font-mono text-base font-bold text-slate-900">{value}</div><div className="text-xs text-slate-500">{sub}</div>
      </div>;
    })}</div>
  </section>;
};
