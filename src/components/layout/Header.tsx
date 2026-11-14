import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Globe2,
  Clock,
  AlertTriangle,
  ChevronUp,
  LayoutDashboard,
  Brain,
  FileBarChart,
  Settings,
  Sun,
  Smile,
  Moon,
  Check,
  Menu,
  X,
} from 'lucide-react';
import { useTelemetry, NavigationTab } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep } from '../../utils/audio';
import { MissionSwitcher } from './MissionSwitcher';
import { DisplayOnlyTag } from '../common/DisplayOnlyNotice';

/** Menü içeriği: masaüstü kenar çubuğu ve mobil çekmece aynı içeriği kullanır. */
const SidebarContent: React.FC<{ onNavigate?: () => void }> = ({ onNavigate }) => {
  const { currentTab, setCurrentTab, astronaut, setAstronautId, availableAstronauts, currentAlert, setOpenActionPlanModal } =
    useTelemetry();
  const { t, pick, lang, setLang, theme, toggleTheme } = usePrefs();

  const [timeUtc, setTimeUtc] = useState<string>('');
  const [crewOpen, setCrewOpen] = useState(false);
  const crewRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateTime = () => setTimeUtc(new Date().toUTCString().slice(17, 25) + ' UTC');
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!crewOpen) return;
    const onDown = (e: MouseEvent) => {
      if (crewRef.current && !crewRef.current.contains(e.target as Node)) setCrewOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [crewOpen]);

  const navItems: { id: NavigationTab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: t('Ana Panel', 'Dashboard'), icon: <LayoutDashboard className="w-[18px] h-[18px]" /> },
    { id: 'anatomy', label: t('Anatomi 3D', 'Body 3D'), icon: <Brain className="w-[18px] h-[18px]" /> },
    { id: 'tests', label: t('Testler', 'Tests'), icon: <Activity className="w-[18px] h-[18px]" /> },
    { id: 'behavior', label: t('Davranış', 'Behavior'), icon: <Smile className="w-[18px] h-[18px]" /> },
    { id: 'reports', label: t('Raporlar', 'Reports'), icon: <FileBarChart className="w-[18px] h-[18px]" /> },
    { id: 'settings', label: t('Ayarlar', 'Settings'), icon: <Settings className="w-[18px] h-[18px]" /> },
  ];

  const isTabActive = (id: NavigationTab) =>
    currentTab === id || (id === 'tests' && (currentTab === 'vision-test' || currentTab === 'cognitive-test'));

  const go = (tab: NavigationTab) => {
    playUiBeep(750);
    setCurrentTab(tab);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    onNavigate?.();
  };

  const critical = currentAlert?.severity === 'critical';

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Marka */}
      <button type="button" className="flex items-center gap-3 text-left px-1" onClick={() => go('dashboard')}>
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-sky-500 to-cyan-400 flex items-center justify-center shadow-[0_0_20px_-2px_rgba(56,189,248,0.7)]">
          <Globe2 className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <div className="text-lg font-extrabold tracking-[0.12em] text-slate-900 leading-none">AHMS</div>
          <div className="text-[11px] text-slate-500 mt-1 leading-tight">
            {t('Astronot Sağlık İzleme', 'Astronaut Health Monitor')}
          </div>
        </div>
      </button>

      <div className="px-1">
        <MissionSwitcher />
      </div>

      {/* Sayfalar */}
      <nav aria-label={t('Ana menü', 'Main menu')} className="flex flex-col gap-1">
        {navItems.map((item) => {
          const active = isTabActive(item.id);
          return (
            <button
              key={item.id}
              onClick={() => go(item.id)}
              aria-current={active ? 'page' : undefined}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all border ${
                active
                  ? 'nav-active'
                  : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100/60'
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Aktif uyarı */}
      {currentAlert && (
        <button
          onClick={() => {
            playUiBeep(900);
            setOpenActionPlanModal(true);
            onNavigate?.();
          }}
          className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-bold text-white transition-colors ${
            critical ? 'bg-red-600 hover:bg-red-700 neon-red' : 'bg-amber-500 hover:bg-amber-600 neon-amber'
          }`}
        >
          <AlertTriangle className="w-[18px] h-[18px]" />
          {t('Eylem Planı', 'Action Plan')}
        </button>
      )}

      <div className="mt-auto flex flex-col gap-3">
        {/* Saat */}
        <div className="flex items-center justify-between px-1 text-xs font-mono text-slate-500">
          <span className="flex items-center gap-1.5 text-slate-800 font-bold">
            <Clock className="w-3.5 h-3.5 text-sky-500" />
            {timeUtc}
          </span>
          <span>
            {t('Gün', 'Day')} {astronaut.solDay}
          </span>
        </div>

        {/* Dil + tema */}
        <div className="flex items-center gap-2">
          <div role="group" aria-label={t('Dil', 'Language')} className="flex flex-1 items-center bg-slate-100/70 border border-slate-200 rounded-xl p-0.5 text-xs font-bold">
            {(['tr', 'en'] as const).map((l) => (
              <button
                key={l}
                onClick={() => {
                  playUiBeep(820);
                  setLang(l);
                }}
                aria-pressed={lang === l}
                className={`flex-1 py-1.5 rounded-lg uppercase transition-colors ${
                  lang === l ? 'bg-sky-500 text-white shadow-[0_0_12px_-2px_rgba(14,165,233,0.8)]' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <button
            onClick={() => {
              playUiBeep(820);
              toggleTheme();
            }}
            aria-label={theme === 'dark' ? t('Açık temaya geç', 'Switch to light mode') : t('Koyu temaya geç', 'Switch to dark mode')}
            title={theme === 'dark' ? t('Açık tema', 'Light mode') : t('Koyu tema', 'Dark mode')}
            className="w-10 h-9 flex items-center justify-center rounded-xl bg-slate-100/70 border border-slate-200 text-slate-600 hover:text-sky-600 transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>

        {/* Astronot */}
        <div className="relative" ref={crewRef}>
          <button
            onClick={() => setCrewOpen((o) => !o)}
            aria-expanded={crewOpen}
            className="w-full flex items-center gap-2.5 p-2 rounded-xl bg-white border border-slate-200 transition-all text-left"
          >
            <img src={astronaut.avatarUrl} alt="" className="w-9 h-9 rounded-lg object-cover border border-sky-300/60" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-slate-900 truncate leading-tight">{astronaut.name}</div>
              <div className="text-xs text-slate-500 font-mono">{astronaut.astronautId ?? astronaut.id}</div>
            </div>
            <ChevronUp className={`w-4 h-4 text-slate-400 transition-transform ${crewOpen ? '' : 'rotate-180'}`} />
          </button>

          {crewOpen && (
            <div className="absolute left-0 bottom-full mb-2 w-72 bg-white rounded-2xl border border-slate-200 shadow-xl p-2 z-50 animate-fadeIn">
              <div className="px-2 py-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider">{t('Mürettebat', 'Crew')}</div>
              {availableAstronauts.map((a) => (
                <button
                  key={a.id}
                  onClick={() => {
                    playUiBeep(700);
                    setAstronautId(a.id);
                    setCrewOpen(false);
                  }}
                  className={`w-full flex items-center gap-3 p-2 rounded-xl text-left transition-colors ${
                    a.id === astronaut.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <img src={a.avatarUrl} alt="" className="w-9 h-9 rounded-full object-cover" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold">{a.name}</div>
                    <div className="text-xs text-slate-500 truncate">{pick(a.role).split('/')[0]}</div>
                  </div>
                  {a.isDisplayOnly && <DisplayOnlyTag />}
                  {a.id === astronaut.id && <Check className="w-4 h-4 text-blue-600" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Gezinme: masaüstünde solda sabit dikey cam menü, telefon/tablette üst çubuk + çekmece.
 * (Dosya adı geçmişle uyumlu kalsın diye Header olarak duruyor.)
 */
export const Header: React.FC = () => {
  const { t } = usePrefs();
  const { currentAlert, setOpenActionPlanModal } = useTelemetry();
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawer(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawer]);

  return (
    <>
      {/* Masaüstü kenar çubuğu */}
      <aside className="hidden lg:block fixed left-4 top-4 bottom-4 w-60 z-40 glass-bar rounded-3xl p-4 overflow-y-auto">
        <SidebarContent />
      </aside>

      {/* Mobil üst çubuk */}
      <header className="lg:hidden sticky top-0 z-40 glass-bar border-x-0 border-t-0 rounded-none px-4 h-14 flex items-center justify-between gap-3">
        <button
          onClick={() => setDrawer(true)}
          aria-label={t('Menüyü aç', 'Open menu')}
          aria-expanded={drawer}
          className="w-10 h-10 flex items-center justify-center rounded-xl border border-slate-200 text-slate-700"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 via-sky-500 to-cyan-400 flex items-center justify-center">
            <Globe2 className="w-4 h-4 text-white" />
          </div>
          <span className="font-extrabold tracking-[0.12em] text-slate-900">AHMS</span>
        </div>
        {currentAlert ? (
          <button
            onClick={() => setOpenActionPlanModal(true)}
            aria-label={t('Eylem planı', 'Action plan')}
            className={`w-10 h-10 flex items-center justify-center rounded-xl text-white ${
              currentAlert.severity === 'critical' ? 'bg-red-600 neon-red' : 'bg-amber-500 neon-amber'
            }`}
          >
            <AlertTriangle className="w-5 h-5" />
          </button>
        ) : (
          <span className="w-10" />
        )}
      </header>

      {/* Mobil çekmece */}
      {drawer && (
        <div className="lg:hidden fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={t('Menü', 'Menu')}>
          <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <div className="absolute left-3 top-3 bottom-3 w-[min(18rem,85vw)] glass-bar rounded-3xl p-4 overflow-y-auto animate-fadeIn">
            <button
              onClick={() => setDrawer(false)}
              aria-label={t('Menüyü kapat', 'Close menu')}
              className="absolute right-3 top-3 w-9 h-9 flex items-center justify-center rounded-xl text-slate-500 hover:text-slate-900"
            >
              <X className="w-5 h-5" />
            </button>
            <SidebarContent onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}
    </>
  );
};
