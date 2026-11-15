import React, { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Orbit } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { MISSION_PROFILES, formatDelay } from '../../data/missionProfiles';
import { playUiBeep } from '../../utils/audio';

/** Görev ortamı seçici: ISS / Ay / Mars yolculuğu / Mars yüzeyi */
export const MissionSwitcher: React.FC = () => {
  const { missionProfile, setMissionProfileId } = useTelemetry();
  const { t, pick, lang } = usePrefs();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={t('Görev ortamını değiştir', 'Change mission environment')}
        className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-mono font-bold bg-sky-100 text-sky-800 border border-sky-200 hover:border-sky-400 whitespace-nowrap transition-colors"
      >
        <Orbit className="w-3.5 h-3.5" />
        {missionProfile.short}
        <ChevronDown className="w-3 h-3" />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label={t('Görev ortamı', 'Mission environment')}
          className="absolute left-0 mt-2 w-80 bg-white rounded-2xl border border-slate-200 shadow-xl p-2 z-50 animate-fadeIn"
        >
          <div className="px-2 py-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider">{t('Görev ortamı', 'Mission environment')}</div>
          {MISSION_PROFILES.map((p) => {
            const active = p.id === missionProfile.id;
            return (
              <button
                key={p.id}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => {
                  playUiBeep(760);
                  setMissionProfileId(p.id);
                  setOpen(false);
                }}
                className={`w-full text-left flex items-start gap-3 p-2.5 rounded-xl transition-colors ${
                  active ? 'bg-blue-50' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-bold ${active ? 'text-blue-700' : 'text-slate-900'}`}>{pick(p.name)}</div>
                  <div className="text-xs text-slate-500 mt-0.5 font-mono">
                    {p.gravityG === 0 ? '0 g' : `${p.gravityG} g`} · {t('gecikme', 'delay')} {formatDelay(p.oneWayDelaySec, lang)} ·{' '}
                    {p.dailyDoseMSv} mSv/{t('gün', 'day')}
                  </div>
                </div>
                {active && <Check className="w-4 h-4 text-blue-600 mt-0.5" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
