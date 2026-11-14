import React from 'react';
import { Eye, ArrowRightLeft } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';

/**
 * core.Astronauts.is_display_only: ikinci profil yalnız gösterimdir;
 * canlı test ve veri girişi kapalıdır, verisi aktif kişinin geçmişine karışmaz.
 */
export const DisplayOnlyNotice: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { astronaut, availableAstronauts, setAstronautId } = useTelemetry();
  const { t } = usePrefs();
  const active = availableAstronauts.find((a) => !a.isDisplayOnly);

  return (
    <div className={`flex flex-wrap items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 ${compact ? 'p-3' : 'p-5'}`}>
      <Eye className="w-5 h-5 text-slate-500 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-[200px]">
        <p className="text-sm font-semibold text-slate-800">
          {t(`${astronaut.name} yalnız gösterim profilidir.`, `${astronaut.name} is a display-only profile.`)}
        </p>
        <p className="text-sm text-slate-600 mt-0.5">
          {t(
            'Bu profil için canlı test ve veri girişi kapalıdır. Testler aktif astronot tarafından yapılır.',
            'Live tests and data entry are disabled for this profile. Tests are taken by the active astronaut.'
          )}
        </p>
      </div>
      {active && (
        <button
          type="button"
          onClick={() => setAstronautId(active.id)}
          className="flex items-center gap-1.5 min-h-11 px-4 rounded-xl bg-white border border-slate-300 text-sm font-semibold text-slate-800 hover:border-blue-400"
        >
          <ArrowRightLeft className="w-4 h-4" />
          {t(`${active.name} profiline geç`, `Switch to ${active.name}`)}
        </button>
      )}
    </div>
  );
};

/** Küçük "Yalnız gösterim" etiketi */
export const DisplayOnlyTag: React.FC = () => {
  const { t } = usePrefs();
  return (
    <span className="px-1.5 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-[10px] font-semibold text-slate-500 whitespace-nowrap">
      {t('Yalnız gösterim', 'Display only')}
    </span>
  );
};
