import React from 'react';
import { Users, Sliders, Volume2, VolumeX, Play, Pause, ShieldCheck, Languages, Sun, Moon, Check } from 'lucide-react';
import { useTelemetry } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { setSoundEnabled, isSoundEnabled, playUiBeep } from '../../utils/audio';
import { DisplayOnlyTag } from '../common/DisplayOnlyNotice';

const Card: React.FC<{ icon: React.ReactNode; title: string; desc?: string; action?: React.ReactNode; children?: React.ReactNode }> = ({
  icon,
  title,
  desc,
  action,
  children,
}) => (
  <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-xl bg-slate-100 text-slate-600 shrink-0">{icon}</div>
        <div>
          <h2 className="text-base font-bold text-slate-900">{title}</h2>
          {desc && <p className="text-sm text-slate-500 mt-0.5">{desc}</p>}
        </div>
      </div>
      {action}
    </div>
    {children}
  </section>
);

export const SettingsPage: React.FC = () => {
  const {
    astronaut,
    setAstronautId,
    availableAstronauts,
    simulationScenario,
    setSimulationScenario,
    isSimulating,
    setIsSimulating,
    simulationIntervalMs,
    setSimulationIntervalMs,
  } = useTelemetry();
  const { t, pick, lang, setLang, theme, setTheme } = usePrefs();

  const [soundOn, setSoundOn] = React.useState(isSoundEnabled());

  const handleToggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    setSoundEnabled(next);
    if (next) playUiBeep(880);
  };

  const segBtn = (active: boolean) =>
    `flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
      active ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
    }`;

  const scenarios = [
    {
      id: 'normal' as const,
      title: t('Normal görev günü', 'Normal mission day'),
      desc: t('Tüm değerler normal aralıkta.', 'All values stay within normal range.'),
    },
    {
      id: 'hypertension' as const,
      title: t('Tansiyon yükselmesi', 'Blood pressure rise'),
      desc: t('Tansiyon ~146/93 mmHg seviyesine çıkar.', 'Blood pressure rises to ~146/93 mmHg.'),
    },
    {
      id: 'eva_exertion' as const,
      title: t('Uzay yürüyüşü eforu', 'Spacewalk exertion'),
      desc: t('Nabız ~108 bpm seviyesine çıkar.', 'Heart rate climbs to ~108 bpm.'),
    },
    {
      id: 'fever' as const,
      title: t('Ateş', 'Fever'),
      desc: t('Vücut ısısı ~38.4 °C seviyesine çıkar.', 'Body temperature rises to ~38.4 °C.'),
    },
  ];

  return (
    <div className="w-full max-w-4xl mx-auto space-y-5 pb-12 animate-fadeIn">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t('Ayarlar', 'Settings')}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {t('Görünüm, mürettebat ve demo verisi ayarları.', 'Display, crew and demo data settings.')}
        </p>
      </div>

      {/* Görünüm */}
      <Card icon={<Languages className="w-5 h-5" />} title={t('Görünüm', 'Display')} desc={t('Dil ve tema tercihiniz bu cihazda saklanır.', 'Your language and theme are saved on this device.')}>
        <div className="flex flex-wrap gap-4">
          <div>
            <div className="text-xs font-semibold text-slate-500 mb-1.5">{t('Dil', 'Language')}</div>
            <div className="inline-flex bg-slate-50 border border-slate-200 rounded-xl p-1">
              <button className={segBtn(lang === 'tr')} onClick={() => setLang('tr')}>Türkçe</button>
              <button className={segBtn(lang === 'en')} onClick={() => setLang('en')}>English</button>
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500 mb-1.5">{t('Tema', 'Theme')}</div>
            <div className="inline-flex bg-slate-50 border border-slate-200 rounded-xl p-1">
              <button className={segBtn(theme === 'light')} onClick={() => setTheme('light')}>
                <Sun className="w-4 h-4" />
                {t('Açık', 'Light')}
              </button>
              <button className={segBtn(theme === 'dark')} onClick={() => setTheme('dark')}>
                <Moon className="w-4 h-4" />
                {t('Koyu', 'Dark')}
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* Mürettebat */}
      <Card icon={<Users className="w-5 h-5" />} title={t('Mürettebat', 'Crew')} desc={t('Kimin verilerini görüntülemek istediğinizi seçin.', 'Choose whose data you want to view.')}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {availableAstronauts.map((astro) => {
            const isSelected = astro.id === astronaut.id;
            return (
              <button
                type="button"
                key={astro.id}
                onClick={() => {
                  playUiBeep(800);
                  setAstronautId(astro.id);
                }}
                className={`relative text-left p-4 rounded-xl border transition-all ${
                  isSelected ? 'bg-blue-50 border-blue-400 ring-2 ring-blue-200' : 'bg-white border-slate-200 hover:border-sky-300'
                }`}
              >
                {isSelected && <Check className="absolute top-3 right-3 w-4 h-4 text-blue-600" />}
                <div className="flex items-center gap-3">
                  <img src={astro.avatarUrl} alt="" className="w-12 h-12 rounded-full object-cover border border-slate-200" />
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-slate-900">{astro.name}</div>
                    {astro.isDisplayOnly && (
                      <div className="mt-0.5">
                        <DisplayOnlyTag />
                      </div>
                    )}
                    <div className="text-xs text-slate-500 line-clamp-2">{pick(astro.role)}</div>
                  </div>
                </div>
                <div className="mt-3 pt-2.5 border-t border-slate-100 grid grid-cols-3 gap-1 text-xs text-slate-600">
                  <span>
                    <span className="block text-slate-400">{t('Kan', 'Blood')}</span>
                    <strong>{astro.bloodType}</strong>
                  </span>
                  <span>
                    <span className="block text-slate-400">{t('Yaş', 'Age')}</span>
                    <strong>{astro.age}</strong>
                  </span>
                  <span>
                    <span className="block text-slate-400">EVA</span>
                    <strong>{astro.evaHours} {t('sa', 'h')}</strong>
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Demo verisi */}
      <Card
        icon={<Sliders className="w-5 h-5" />}
        title={t('Demo verisi', 'Demo data')}
        desc={t(
          'Sensör bağlantısı kurulana kadar değerler simüle edilir. Sunumda farklı durumları göstermek için bir senaryo seçin.',
          'Values are simulated until sensors are connected. Pick a scenario to show different situations in a demo.'
        )}
        action={
          <button
            onClick={() => {
              playUiBeep(700);
              setIsSimulating(!isSimulating);
            }}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-bold whitespace-nowrap transition-all ${
              isSimulating ? 'bg-emerald-600 text-white' : 'bg-amber-100 text-amber-800 border border-amber-300'
            }`}
          >
            {isSimulating ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isSimulating ? t('Çalışıyor', 'Running') : t('Duraklatıldı', 'Paused')}
          </button>
        }
      >
        <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-100">
          <div>
            <div className="text-sm font-semibold text-slate-800">{t('Güncelleme sıklığı', 'Update interval')}</div>
            <div className="text-xs text-slate-500">{t('Yeni değerlerin gelme aralığı', 'How often new values arrive')}</div>
          </div>
          <div className="inline-flex bg-white border border-slate-200 rounded-xl p-1">
            {[1000, 2500, 5000].map((ms) => (
              <button
                key={ms}
                onClick={() => {
                  playUiBeep(650);
                  setSimulationIntervalMs(ms);
                }}
                className={segBtn(simulationIntervalMs === ms)}
              >
                {ms / 1000} {t('sn', 's')}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {scenarios.map((scen) => {
            const active = simulationScenario === scen.id;
            return (
              <button
                type="button"
                key={scen.id}
                onClick={() => {
                  playUiBeep(850);
                  setSimulationScenario(scen.id);
                }}
                className={`text-left p-4 rounded-xl border transition-all ${
                  active ? 'bg-blue-50 border-blue-400 ring-2 ring-blue-200' : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold text-slate-900">{scen.title}</span>
                  {active && <Check className="w-4 h-4 text-blue-600" />}
                </div>
                <p className="text-sm text-slate-500 mt-1">{scen.desc}</p>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Ses */}
      <Card
        icon={soundOn ? <Volume2 className="w-5 h-5 text-blue-600" /> : <VolumeX className="w-5 h-5" />}
        title={t('Ses efektleri', 'Sound effects')}
        desc={t('Tıklama, uyarı ve test bildirim sesleri.', 'Click, alert and test notification sounds.')}
        action={
          <button
            role="switch"
            aria-checked={soundOn}
            onClick={handleToggleSound}
            className={`relative w-12 h-7 rounded-full transition-colors shrink-0 ${soundOn ? 'bg-blue-600' : 'bg-slate-300'}`}
          >
            <span className={`absolute top-1 w-5 h-5 rounded-full shadow transition-all ${soundOn ? 'left-6' : 'left-1'}`} style={{ backgroundColor: '#fff' }} />
          </button>
        }
      />

      {/* Bilgilendirme */}
      <section className="p-5 bg-sky-50 rounded-2xl border border-sky-200">
        <h2 className="flex items-center gap-2 text-sm font-bold text-sky-800">
          <ShieldCheck className="w-4 h-4" />
          {t('Önemli not', 'Important note')}
        </h2>
        <p className="text-sm text-slate-600 leading-relaxed mt-1.5">
          {t(
            'AHMS, NASA Space Apps Challenge 2026 için geliştirilmiş bir prototiptir. Gösterilen değerler simüle edilmiştir ve tıbbi tanı yerine geçmez.',
            'AHMS is a prototype built for the NASA Space Apps Challenge 2026. The values shown are simulated and are not a medical diagnosis.'
          )}
        </p>
      </section>
    </div>
  );
};
