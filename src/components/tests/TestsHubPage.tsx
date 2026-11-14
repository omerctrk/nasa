import React from 'react';
import { Eye, Brain, ArrowRight, Clock, CalendarCheck, Info } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { DisplayOnlyNotice } from '../common/DisplayOnlyNotice';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep } from '../../utils/audio';

export const TestsHubPage: React.FC = () => {
  const { setCurrentTab, visionTestHistory, cognitiveTestHistory, astronaut } = useTelemetry();
  const readOnly = !!astronaut.isDisplayOnly;
  const { t, pick } = usePrefs();

  const lastV = visionTestHistory[0];
  const lastC = cognitiveTestHistory[0];

  const cards = [
    {
      tab: 'vision-test' as const,
      icon: <Eye className="w-7 h-7" />,
      gradient: 'from-sky-500 to-blue-700',
      button: 'bg-blue-600 hover:bg-blue-700',
      tag: t('Göz sağlığı', 'Eye health'),
      tagCls: 'bg-sky-100 text-sky-800 border-sky-200',
      title: t('Görme Keskinliği Testi', 'Visual Acuity Test'),
      why: t(
        'Uzayda vücut sıvısı kafaya doğru kayar ve göz arkasındaki basıncı artırabilir (SANS). Görmedeki küçük değişiklikleri erken yakalamak için düzenli test önemlidir.',
        'In space, body fluid shifts toward the head and can raise pressure behind the eyes (SANS). Regular testing catches small changes in vision early.'
      ),
      how: t(
        'Ekranda giderek küçülen harfleri görün ve doğru seçeneği işaretleyin.',
        'Read letters that get smaller and pick the matching option.'
      ),
      minutes: 2,
      freq: t('Haftada 1', 'Weekly'),
      last: lastV ? `${lastV.acuityScore} • ${pick(lastV.date)}` : null,
      cta: t('Görme testine başla', 'Start vision test'),
    },
    {
      tab: 'cognitive-test' as const,
      icon: <Brain className="w-7 h-7" />,
      gradient: 'from-indigo-500 to-purple-700',
      button: 'bg-indigo-600 hover:bg-indigo-700',
      tag: t('Dikkat & bellek', 'Alertness & memory'),
      tagCls: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      title: t('Refleks & Bilişsel Test', 'Reflex & Cognitive Test'),
      why: t(
        'Uyku düzensizliği, izolasyon ve radyasyon dikkat ile tepki süresini etkileyebilir. Bu test, kritik görevlerden önce zihinsel hazır olup olmadığınızı gösterir.',
        'Disrupted sleep, isolation and radiation can affect alertness and reaction time. This test shows whether you are mentally ready before critical tasks.'
      ),
      how: t(
        'Işık yandığında hızla tıklayın, ardından gösterilen sırayı tekrar edin.',
        'Click as soon as the light appears, then repeat the sequence you are shown.'
      ),
      minutes: 3,
      freq: t('Günde 1', 'Daily'),
      last: lastC ? `${lastC.reactionTimeMs} ms • ${pick(lastC.date)}` : null,
      cta: t('Refleks testine başla', 'Start reflex test'),
    },
  ];

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 pb-12 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t('Öz Değerlendirme Testleri', 'Self-Assessment Tests')}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {t(
            'Kısa testlerle sağlığınızı kendiniz kontrol edin. Sonuçlar raporlarınıza kaydedilir.',
            'Check your own health with short tests. Results are saved to your reports.'
          )}
        </p>
      </div>

      {readOnly && <DisplayOnlyNotice compact />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {cards.map((c) => (
          <article key={c.tab} className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-all flex flex-col">
            <div className="flex items-center justify-between">
              <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${c.gradient} text-white flex items-center justify-center shadow-md`}>
                {c.icon}
              </div>
              <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold border ${c.tagCls}`}>{c.tag}</span>
            </div>

            <h2 className="text-xl font-bold text-slate-900 mt-4">{c.title}</h2>

            <div className="mt-3 space-y-3 flex-1">
              <div>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide">{t('Neden?', 'Why?')}</h3>
                <p className="text-sm text-slate-700 leading-relaxed mt-1">{c.why}</p>
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide">{t('Nasıl?', 'How?')}</h3>
                <p className="text-sm text-slate-700 leading-relaxed mt-1">{c.how}</p>
              </div>
            </div>

            <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <dt className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock className="w-3.5 h-3.5" />
                  {t('Süre', 'Time')}
                </dt>
                <dd className="font-semibold text-slate-800 mt-0.5">~{c.minutes} {t('dk', 'min')}</dd>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
                <dt className="flex items-center gap-1 text-xs text-slate-500">
                  <CalendarCheck className="w-3.5 h-3.5" />
                  {t('Sıklık', 'How often')}
                </dt>
                <dd className="font-semibold text-slate-800 mt-0.5">{c.freq}</dd>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 min-w-0">
                <dt className="text-xs text-slate-500">{t('Son sonuç', 'Last result')}</dt>
                <dd className="font-semibold text-slate-800 mt-0.5 font-mono truncate" title={c.last ?? undefined}>
                  {c.last?.split(' • ')[0] ?? '—'}
                </dd>
              </div>
            </dl>

            <button
              disabled={readOnly}
              onClick={() => {
                playUiBeep(880);
                setCurrentTab(c.tab);
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              className={`mt-5 w-full flex items-center justify-center gap-2 px-5 py-3 ${c.button} active:scale-[0.98] text-white rounded-xl text-sm font-bold shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              {c.cta}
              <ArrowRight className="w-4 h-4" />
            </button>
          </article>
        ))}
      </div>

      <p className="flex items-start gap-2 text-sm text-slate-500">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        {t(
          'Bu testler tıbbi muayenenin yerini tutmaz. Sonuç olağandışıysa uçuş cerrahınıza danışın.',
          'These tests do not replace a medical exam. If a result looks unusual, consult your flight surgeon.'
        )}
      </p>
    </div>
  );
};
