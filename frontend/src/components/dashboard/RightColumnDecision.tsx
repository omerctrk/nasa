import React from 'react';
import { Eye, Brain, Lightbulb, ArrowRight, Moon, Droplet, Dumbbell, Coffee, ClipboardCheck } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { Text } from '../../types/telemetry';
import { playUiBeep } from '../../utils/audio';

const REC_ICONS: Record<string, { icon: React.ReactNode; bar: string }> = {
  sleep: { icon: <Moon className="w-4 h-4 text-purple-500" />, bar: 'bg-purple-500' },
  hydration: { icon: <Droplet className="w-4 h-4 text-sky-500" />, bar: 'bg-sky-500' },
  exercise: { icon: <Dumbbell className="w-4 h-4 text-orange-500" />, bar: 'bg-orange-500' },
  rest: { icon: <Coffee className="w-4 h-4 text-emerald-500" />, bar: 'bg-emerald-500' },
};

/** "1.8 Litre" / "2.4 Litre" gibi metinlerden ilerleme yüzdesi çıkarır */
const progressOf = (current: Text, target: Text) => {
  const num = (v: Text) => parseFloat((typeof v === 'string' ? v : v.en).replace(',', '.'));
  const c = num(current);
  const tg = num(target);
  if (!isFinite(c) || !isFinite(tg) || tg <= 0) return null;
  return Math.min(100, Math.round((c / tg) * 100));
};

export const RightColumnDecision: React.FC = () => {
  const { recommendations, setCurrentTab, visionTestHistory, cognitiveTestHistory, astronaut } = useTelemetry();
  const readOnly = !!astronaut.isDisplayOnly;
  const { t, pick } = usePrefs();

  const lastVision = visionTestHistory[0];
  const lastCognitive = cognitiveTestHistory[0];

  const riskLabel = (r: string) =>
    r === 'high' ? t('Yüksek', 'High') : r === 'medium' ? t('Orta', 'Medium') : t('Düşük', 'Low');

  const priorityMeta = (p: string) =>
    p === 'high'
      ? { label: t('Öncelikli', 'High priority'), cls: 'bg-red-50 text-red-700 border-red-200' }
      : p === 'medium'
        ? { label: t('Orta', 'Medium'), cls: 'bg-amber-50 text-amber-700 border-amber-200' }
        : { label: t('Düşük', 'Low'), cls: 'bg-slate-100 text-slate-600 border-slate-200' };

  const tests = [
    {
      id: 'vision-test' as const,
      icon: <Eye className="w-6 h-6 text-white" />,
      gradient: 'from-sky-500 to-blue-700',
      button: 'bg-blue-600 hover:bg-blue-700',
      title: t('Görme & SANS Testi', 'Vision & SANS Test'),
      desc: t(
        'Uzayda kafaya doğru sıvı kayması gözü etkileyebilir (SANS). Harf tablosuyla görme keskinliğinizi kontrol edin.',
        'Fluid shifting toward the head in space can affect the eyes (SANS). Check your visual acuity with a letter chart.'
      ),
      minutes: 2,
      last: lastVision
        ? [
            { k: t('Skor', 'Score'), v: lastVision.acuityScore },
            { k: t('Risk', 'Risk'), v: riskLabel(lastVision.sansRisk) },
          ]
        : [],
    },
    {
      id: 'cognitive-test' as const,
      icon: <Brain className="w-6 h-6 text-white" />,
      gradient: 'from-indigo-500 to-purple-700',
      button: 'bg-indigo-600 hover:bg-indigo-700',
      title: t('Refleks & Bilişsel Test', 'Reflex & Cognitive Test'),
      desc: t(
        'Uykusuzluk, izolasyon ve radyasyon dikkati etkileyebilir. Tepki sürenizi ve kısa süreli belleğinizi ölçün.',
        'Sleep loss, isolation and radiation can affect alertness. Measure your reaction time and short-term memory.'
      ),
      minutes: 3,
      last: lastCognitive
        ? [
            { k: t('Tepki', 'Reaction'), v: `${lastCognitive.reactionTimeMs} ms` },
            { k: t('Doğruluk', 'Accuracy'), v: `${lastCognitive.accuracyPercent}%` },
          ]
        : [],
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-1 gap-4">
      {/* Testler */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-2 px-1">
          <ClipboardCheck className="w-4 h-4 text-blue-600" />
          <h2 className="text-sm font-bold text-slate-800">{t('Öz Değerlendirme Testleri', 'Self-Assessment Tests')}</h2>
        </div>

        {tests.map((test) => (
          <article key={test.id} className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm hover:shadow-md transition-all">
            <div className="flex items-start gap-3">
              <div
                className={`w-11 h-11 rounded-xl bg-gradient-to-br ${test.gradient} flex items-center justify-center shadow-md shrink-0`}
              >
                {test.icon}
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-bold text-slate-900 leading-snug">{test.title}</h3>
                <p className="text-sm text-slate-600 mt-1 leading-relaxed">{test.desc}</p>
              </div>
            </div>

            {test.last.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-xs text-slate-500 self-center">{t('Son sonuç:', 'Last result:')}</span>
                {test.last.map((s) => (
                  <span key={s.k} className="px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-xs text-slate-700">
                    {s.k}: <strong className="font-mono">{s.v}</strong>
                  </span>
                ))}
              </div>
            )}

            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                ~{test.minutes} {t('dakika', 'min')}
              </span>
              <button
                disabled={readOnly}
                title={readOnly ? t('Yalnız gösterim profili', 'Display-only profile') : undefined}
                onClick={() => {
                  playUiBeep(880);
                  setCurrentTab(test.id);
                }}
                className={`flex items-center gap-1.5 px-4 py-2 ${test.button} active:scale-95 text-white rounded-xl text-sm font-bold shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                {t('Başlat', 'Start')}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </article>
        ))}
      </section>

      {/* Günlük öneriler */}
      <section className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-bold text-slate-800">{t('Bugünkü Hedefler', "Today's Goals")}</h2>
        </div>

        <ul className="space-y-3">
          {recommendations.map((rec) => {
            const pct = progressOf(rec.current, rec.target);
            const style = REC_ICONS[rec.category] ?? REC_ICONS.rest;
            const prio = priorityMeta(rec.priority);
            return (
              <li key={rec.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 font-semibold text-sm text-slate-800">
                    {style.icon}
                    <span>{pick(rec.title)}</span>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded-md border text-xs font-semibold shrink-0 ${prio.cls}`}>
                    {prio.label}
                  </span>
                </div>

                {pct !== null && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs text-slate-500 mb-1">
                      <span>
                        <strong className="text-slate-700 font-mono">{pick(rec.current)}</strong> / {pick(rec.target)}
                      </span>
                      <span className="font-mono">{pct}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-200 overflow-hidden">
                      <div className={`h-full rounded-full ${style.bar} transition-all`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )}

                <p className="text-sm text-slate-600 mt-2 leading-relaxed">{pick(rec.recommendation)}</p>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
};
