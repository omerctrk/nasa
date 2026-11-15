import React from 'react';
import { AlertTriangle, CheckCircle2, ChevronRight, MapPin } from 'lucide-react';
import { LeftColumnVitals } from './LeftColumnVitals';
import { Anatomy3D } from '../anatomy/Anatomy3D';
import { HazardsPanel } from './HazardsPanel';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep } from '../../utils/audio';

/** Sayfanın üstünde: karşılama + aktif uyarı (ilk bakışta "ne yapmalıyım?") */
const StatusBanner: React.FC = () => {
  const { astronaut, currentAlert, setOpenActionPlanModal, missionProfile } = useTelemetry();
  const { t, pick } = usePrefs();

  const hour = new Date().getUTCHours();
  const greeting =
    hour < 12 ? t('Günaydın', 'Good morning') : hour < 18 ? t('İyi günler', 'Good afternoon') : t('İyi akşamlar', 'Good evening');

  const critical = currentAlert?.severity === 'critical';

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <div className="xl:col-span-5 bg-white rounded-2xl border border-slate-200 px-4 py-3 shadow-sm flex items-center gap-3">
        <img src={astronaut.avatarUrl} alt="" className="w-10 h-10 rounded-xl object-cover border border-slate-200" />
        <div className="min-w-0">
          <h1 className="text-base sm:text-lg font-bold text-slate-900 leading-tight">
            <span className="font-normal text-slate-500">{greeting}, </span>
            {astronaut.name}
          </h1>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
            <MapPin className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">
              {missionProfile.id === 'iss' ? astronaut.spaceStationModule : pick(missionProfile.habitat)} • {t('Görev günü', 'Mission day')}{' '}
              {astronaut.solDay}
            </span>
          </p>
        </div>
      </div>

      {currentAlert ? (
        <div
          role="alert"
          className={`xl:col-span-7 rounded-2xl border-2 px-4 py-3 shadow-sm flex flex-col sm:flex-row sm:items-center gap-3 ${
            critical ? 'bg-red-50 border-red-300 neon-red' : 'bg-amber-50 border-amber-300 neon-amber'
          }`}
        >
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 text-white ${
              critical ? 'bg-red-600' : 'bg-amber-500'
            }`}
          >
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded-md text-xs font-bold uppercase tracking-wide text-white ${
                  critical ? 'bg-red-600' : 'bg-amber-600'
                }`}
              >
                {critical ? t('Kritik', 'Critical') : t('Dikkat', 'Caution')}
              </span>
              <span className="text-xs font-mono text-slate-500">{currentAlert.protocolCode}</span>
            </div>
            <h2 className={`mt-0.5 text-sm font-bold leading-snug ${critical ? 'text-red-800' : 'text-amber-800'}`}>
              {pick(currentAlert.title)}
            </h2>
            <p className="text-xs text-slate-700 mt-0.5 line-clamp-1">{pick(currentAlert.description)}</p>
          </div>
          <button
            onClick={() => {
              playUiBeep(800);
              setOpenActionPlanModal(true);
            }}
            className={`flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-bold text-white shadow-sm whitespace-nowrap transition-colors ${
              critical ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-600 hover:bg-amber-700'
            }`}
          >
            {t('Ne yapmalıyım?', 'What should I do?')}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="xl:col-span-7 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-500 flex items-center justify-center text-white shrink-0">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800">{t('Açık alarm kaydı yok', 'No open alert record')}</h2>
            <p className="text-xs text-slate-700">
              {t(
                'Bu durum klinik değerlendirme yapıldığı veya tüm göstergelerin normal olduğu anlamına gelmez.',
                'This does not mean that a clinical evaluation ran or all indicators are normal.'
              )}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export const DashboardLayout: React.FC = () => {
  const { setSelectedAnatomyZone } = useTelemetry();

  return (
    <div className="w-full max-w-7xl mx-auto space-y-5 pb-6 animate-fadeIn">
      <StatusBanner />
      <HazardsPanel />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Sol: sağlık özeti, hedefler, yaşamsal bulgular */}
        <div className="lg:col-span-5 xl:col-span-7 order-2 lg:order-1">
          <LeftColumnVitals />
        </div>

        {/* Sağ: 3D vücut haritası (boyutu aynı, yeri sağda). Testler yalnız "Testler" sayfasında. */}
        <div className="lg:col-span-7 xl:col-span-5 h-[620px] xl:h-[780px] lg:sticky lg:top-6 order-1 lg:order-2">
          <Anatomy3D onSelectZone={(zone) => setSelectedAnatomyZone(zone)} />
        </div>
      </div>
    </div>
  );
};
