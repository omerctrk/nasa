import React from 'react';
import { Radiation, Users, Satellite, ArrowDownToLine, Wind, ChevronRight } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { HAZARDS, type HazardId } from '../../data/hazards';
import { CAREER_LIMIT_MSV, cumulativeDose, formatDelay } from '../../data/missionProfiles';
import { statusMeta } from '../../utils/status';
import { MetricStatus } from '../../types/telemetry';
import { playUiBeep } from '../../utils/audio';

const ICONS: Record<HazardId, React.ReactNode> = {
  radiation: <Radiation className="w-4 h-4" />,
  isolation: <Users className="w-4 h-4" />,
  distance: <Satellite className="w-4 h-4" />,
  gravity: <ArrowDownToLine className="w-4 h-4" />,
  environment: <Wind className="w-4 h-4" />,
};

const HazardCard: React.FC<{
  id: HazardId;
  status: MetricStatus | null; // null = bilgi amaçlı, renk yok
  value: React.ReactNode;
  sub: React.ReactNode;
  extra?: React.ReactNode;
  onClick?: () => void;
}> = ({ id, status, value, sub, extra, onClick }) => {
  const { t, pick } = usePrefs();
  const meta = status ? statusMeta(status, t) : null;
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      title={pick(HAZARDS[id].desc)}
      className={`group text-left w-full bg-white rounded-xl border border-slate-200 p-3 shadow-sm flex flex-col gap-1 min-w-0 ${
        onClick ? 'hover:border-sky-300 hover:shadow-md transition-all' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 min-w-0">
          <span className="text-slate-500 shrink-0">{ICONS[id]}</span>
          <span className="truncate">{pick(HAZARDS[id].short)}</span>
        </span>
        {meta ? (
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${meta.dot}`} title={meta.label} />
        ) : onClick ? (
          <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 shrink-0" />
        ) : null}
      </div>
      <div className="text-base font-bold text-slate-900 font-mono leading-tight whitespace-nowrap truncate">{value}</div>
      <div className="text-xs text-slate-500 leading-snug">{sub}</div>
      {extra}
    </Tag>
  );
};

/** NASA'nın 5 uzay uçuşu tehlikesi: bu görevde her biri ne durumda? */
export const HazardsPanel: React.FC = () => {
  const { missionProfile: p, astronaut, vitals, systemTelemetery, setCurrentTab, setSelectedAnatomyZone } = useTelemetry();
  const { t, lang } = usePrefs();

  // Radyasyon: görev boyunca biriken doz / kariyer limiti
  const dose = cumulativeDose(p, astronaut.solDay);
  const dosePct = Math.min(100, Math.round((dose / CAREER_LIMIT_MSV) * 100));
  const radStatus: MetricStatus = dosePct >= 80 ? 'critical' : dosePct >= 50 ? 'warning' : 'normal';

  // Yerçekimi: sıvı kayması (göz basıncı) ve kalp-damar göstergeleri
  const gravStatus: MetricStatus = [vitals.iop.status, vitals.pulse.status].includes('critical')
    ? 'critical'
    : [vitals.iop.status, vitals.pulse.status].includes('warning')
      ? 'warning'
      : 'normal';

  // Kapalı ortam: kabin CO₂ (NASA hedefi < ~0.5%) ve kan oksijeni
  const co2 = systemTelemetery.co2Percent;
  const envStatus: MetricStatus =
    vitals.oxygen.status === 'critical' || co2 > 0.7 ? 'critical' : vitals.oxygen.status === 'warning' || co2 > 0.5 ? 'warning' : 'normal';

  const open = (fn: () => void) => () => {
    playUiBeep(760);
    fn();
  };

  return (
    <section aria-labelledby="hazards-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2 px-1">
        <h2 id="hazards-heading" className="text-sm font-bold text-slate-800">
          {t('Görev Ortam Koşulları', 'Mission Environment Conditions')}
        </h2>
        <span className="text-xs text-slate-500">{t('NASA İnsan Araştırma Programı çerçevesi', 'NASA Human Research Program framework')}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-2.5">
        <HazardCard
          id="radiation"
          status={radStatus}
          value={`${dose} mSv`}
          sub={t(`Görev boyunca · günde ${p.dailyDoseMSv} mSv`, `This mission · ${p.dailyDoseMSv} mSv/day`)}
          extra={
            <div className="mt-1" title={t(`Kariyer limiti ${CAREER_LIMIT_MSV} mSv`, `Career limit ${CAREER_LIMIT_MSV} mSv`)}>
              <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
                <div className={`h-full rounded-full ${statusMeta(radStatus, t).dot}`} style={{ width: `${Math.max(2, dosePct)}%` }} />
              </div>
              <div className="flex justify-between text-[11px] text-slate-500 mt-0.5 font-mono">
                <span>{dosePct}%</span>
                <span>
                  {t('limit', 'limit')} {CAREER_LIMIT_MSV}
                </span>
              </div>
            </div>
          }
        />
        <HazardCard
          id="isolation"
          status={null}
          value={`${vitals.sleep.value} ${t('sa uyku', 'h sleep')}`}
          sub={t('Ruh hali ve tepki testi: Davranış modülü', 'Mood and reaction test: Behavior module')}
          onClick={open(() => setCurrentTab('behavior'))}
        />
        <HazardCard
          id="distance"
          status={null}
          value={formatDelay(p.oneWayDelaySec, lang)}
          sub={t(`Tek yön mesaj gecikmesi · dönüş: ${p.returnTime.tr}`, `One-way message delay · return: ${p.returnTime.en}`)}
        />
        <HazardCard
          id="gravity"
          status={gravStatus}
          value={p.gravityG === 0 ? t('0 g (ağırlıksız)', '0 g (weightless)') : `${p.gravityG} g`}
          sub={t(`Göz basıncı ${vitals.iop.value} mmHg · nabız ${vitals.pulse.value}`, `Eye pressure ${vitals.iop.value} mmHg · HR ${vitals.pulse.value}`)}
          onClick={open(() => setSelectedAnatomyZone('musculoskeletal'))}
        />
        <HazardCard
          id="environment"
          status={envStatus}
          value={`CO₂ ${co2}%`}
          sub={t(`Kabin O₂ ${systemTelemetery.cabinO2Percent}% · SpO₂ ${vitals.oxygen.value}%`, `Cabin O₂ ${systemTelemetery.cabinO2Percent}% · SpO₂ ${vitals.oxygen.value}%`)}
          onClick={open(() => setSelectedAnatomyZone('chest'))}
        />
      </div>
    </section>
  );
};
