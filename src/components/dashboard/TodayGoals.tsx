import React from 'react';
import { Moon, Droplet, Dumbbell, Coffee, Target } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { Text } from '../../types/telemetry';

const STYLE: Record<string, { icon: React.ReactNode; bar: string }> = {
  sleep: { icon: <Moon className="w-4 h-4 text-purple-500" />, bar: 'bg-purple-500' },
  hydration: { icon: <Droplet className="w-4 h-4 text-sky-500" />, bar: 'bg-sky-500' },
  exercise: { icon: <Dumbbell className="w-4 h-4 text-orange-500" />, bar: 'bg-orange-500' },
  rest: { icon: <Coffee className="w-4 h-4 text-emerald-500" />, bar: 'bg-emerald-500' },
};

/** "1.8 Litre" / "2.4 Litre" gibi metinlerden ilerleme yüzdesi */
const progressOf = (current: Text, target: Text) => {
  const num = (v: Text) => parseFloat((typeof v === 'string' ? v : v.en).replace(',', '.'));
  const c = num(current);
  const tg = num(target);
  if (!isFinite(c) || !isFinite(tg) || tg <= 0) return null;
  return Math.min(100, Math.round((c / tg) * 100));
};

/** Bugünkü hedefler — sade: her hedef tek satır, ayrıntı üzerine gelince */
export const TodayGoals: React.FC<{ horizontal?: boolean }> = ({ horizontal = false }) => {
  const { recommendations } = useTelemetry();
  const { t, pick } = usePrefs();

  return (
    <section className={`bg-white rounded-2xl border border-slate-200 p-5 ${horizontal ? '' : 'h-full'}`}>
      <h2 className="flex items-center gap-2 text-base font-bold text-slate-900">
        <Target className="w-4 h-4 text-sky-500" />
        {t('Bugünkü Hedefler', "Today's Goals")}
      </h2>

      <ul className={horizontal ? 'mt-4 grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-4 gap-x-8 gap-y-4' : 'mt-4 space-y-4'}>
        {recommendations.map((rec) => {
          const pct = progressOf(rec.current, rec.target);
          const st = STYLE[rec.category] ?? STYLE.rest;
          return (
            <li key={rec.id} title={pick(rec.recommendation)}>
              <div className={`flex justify-between gap-2 text-sm ${horizontal ? 'items-start' : 'items-center'}`}>
                <span className={`flex gap-2 min-w-0 text-slate-700 ${horizontal ? 'items-start' : 'items-center'}`}>
                  <span className={horizontal ? 'mt-0.5 shrink-0' : 'shrink-0'}>{st.icon}</span>
                  <span className={horizontal ? 'leading-snug' : 'truncate'}>{pick(rec.title)}</span>
                </span>
                <span className="font-mono text-xs text-slate-500 shrink-0">{pct !== null ? `${pct}%` : '—'}</span>
              </div>
              {pct !== null && (
                <div className="mt-1.5 h-1.5 rounded-full bg-slate-200/70 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${st.bar} transition-all`}
                    style={{ width: `${pct}%`, boxShadow: '0 0 8px currentColor' }}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
};
