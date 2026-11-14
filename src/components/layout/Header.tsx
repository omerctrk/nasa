import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Globe2,
  Clock,
  AlertTriangle,
  ChevronDown,
  LayoutDashboard,
  Brain,
  FileBarChart,
  Settings,
  Sun,
  Smile,
  Moon,
  Check,
} from 'lucide-react';
import { useTelemetry, NavigationTab } from '../../context/TelemetryContext';
import { usePrefs } from '../../context/PreferencesContext';
import { playUiBeep } from '../../utils/audio';
import { MissionSwitcher } from './MissionSwitcher';
import { DisplayOnlyTag } from '../common/DisplayOnlyNotice';

export const Header: React.FC = () => {
  const {
    currentTab,
    setCurrentTab,
    astronaut,
    setAstronautId,
    availableAstronauts,
    currentAlert,
    setOpenActionPlanModal,
  } = useTelemetry();
  const { t, pick, lang, setLang, theme, toggleTheme } = usePrefs();

  const [timeUtc, setTimeUtc] = useState<string>('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateTime = () => setTimeUtc(new Date().toUTCString().slice(17, 25) + ' UTC');
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Dışarı tıklanınca astronot menüsünü kapat
  useEffect(() => {
    if (!dropdownOpen) return;
    const onDown = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setDropdownOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [dropdownOpen]);

  const navItems: { id: NavigationTab; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: t('Ana Panel', 'Dashboard'), icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: 'anatomy', label: t('Anatomi 3D', 'Body 3D'), icon: <Brain className="w-4 h-4" /> },
    { id: 'tests', label: t('Testler', 'Tests'), icon: <Activity className="w-4 h-4" /> },
    { id: 'behavior', label: t('Davranış', 'Behavior'), icon: <Smile className="w-4 h-4" /> },
    { id: 'reports', label: t('Raporlar', 'Reports'), icon: <FileBarChart className="w-4 h-4" /> },
    { id: 'settings', label: t('Ayarlar', 'Settings'), icon: <Settings className="w-4 h-4" /> },
  ];

  const isTabActive = (id: NavigationTab) =>
    currentTab === id || (id === 'tests' && (currentTab === 'vision-test' || currentTab === 'cognitive-test'));

  const handleNavClick = (tab: NavigationTab) => {
    playUiBeep(750);
    setCurrentTab(tab);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <header className="sticky top-0 z-40 w-full bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3 h-16">
          {/* Marka + görev ortamı */}
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              className="flex items-center gap-3 text-left"
              onClick={() => handleNavClick('dashboard')}
              aria-label={t('Ana panele git', 'Go to dashboard')}
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-sky-500 to-cyan-400 shadow-md shadow-blue-500/20 flex items-center justify-center">
                <Globe2 className="w-5 h-5 text-white" />
              </div>
              <div className="hidden sm:block">
                <span className="text-lg font-extrabold tracking-tight text-slate-900 leading-none">AHMS</span>
                <p className="text-xs text-slate-500 font-medium mt-0.5 whitespace-nowrap hidden 2xl:block">
                  {t('Astronot Sağlık İzleme Sistemi', 'Astronaut Health Monitoring System')}
                </p>
              </div>
            </button>
            <MissionSwitcher />
          </div>

          {/* Ana menü */}
          <nav
            aria-label={t('Ana menü', 'Main menu')}
            className="hidden lg:flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200"
          >
            {navItems.map((item) => {
              const active = isTabActive(item.id);
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all ${
                    active ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
                  }`}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Sağ taraf */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Saat */}
            <div className="hidden 2xl:flex flex-col items-end text-right font-mono text-xs text-slate-500 pr-3 border-r border-slate-200">
              <div className="flex items-center gap-1 text-slate-800 font-bold text-sm">
                <Clock className="w-3.5 h-3.5 text-blue-500" />
                <span>{timeUtc}</span>
              </div>
              <span className="whitespace-nowrap">{t('Görev günü', 'Mission day')} {astronaut.solDay}</span>
            </div>

            {/* Acil eylem planı */}
            {currentAlert && (
              <button
                onClick={() => {
                  playUiBeep(900);
                  setOpenActionPlanModal(true);
                }}
                className={`relative hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-bold whitespace-nowrap transition-all shadow-sm text-white ${
                  currentAlert.severity === 'critical' ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-500 hover:bg-amber-600'
                }`}
              >
                <span className="absolute -top-1 -right-1 flex h-3 w-3">
                  <span
                    className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                      currentAlert.severity === 'critical' ? 'bg-red-400' : 'bg-amber-300'
                    }`}
                  />
                  <span
                    className={`relative inline-flex rounded-full h-3 w-3 border-2 border-white ${
                      currentAlert.severity === 'critical' ? 'bg-red-500' : 'bg-amber-400'
                    }`}
                  />
                </span>
                <AlertTriangle className="w-4 h-4" />
                <span className="hidden sm:inline">{t('Eylem Planı', 'Action Plan')}</span>
              </button>
            )}

            {/* Dil seçici */}
            <div
              role="group"
              aria-label={t('Dil', 'Language')}
              className="flex items-center bg-slate-100 border border-slate-200 rounded-lg p-0.5 text-xs font-bold"
            >
              {(['tr', 'en'] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => {
                    playUiBeep(820);
                    setLang(l);
                  }}
                  aria-pressed={lang === l}
                  className={`px-2 py-1 rounded-md uppercase transition-colors ${
                    lang === l ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>

            {/* Tema */}
            <button
              onClick={() => {
                playUiBeep(820);
                toggleTheme();
              }}
              aria-label={theme === 'dark' ? t('Açık temaya geç', 'Switch to light mode') : t('Koyu temaya geç', 'Switch to dark mode')}
              title={theme === 'dark' ? t('Açık tema', 'Light mode') : t('Koyu tema', 'Dark mode')}
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-slate-100 border border-slate-200 text-slate-600 hover:text-blue-600 transition-colors"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            {/* Astronot seçici */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                aria-expanded={dropdownOpen}
                className="flex items-center gap-2 p-1 pr-2 rounded-xl bg-white border border-slate-200 hover:border-sky-300 shadow-sm transition-all"
              >
                <img
                  src={astronaut.avatarUrl}
                  alt={astronaut.name}
                  className="w-8 h-8 rounded-lg object-cover border border-sky-200"
                />
                <div className="text-left hidden 2xl:block">
                  <div className="text-sm font-bold text-slate-900 whitespace-nowrap leading-tight">{astronaut.name}</div>
                  <div className="text-xs text-slate-500 whitespace-nowrap">
                    {astronaut.bloodType} • Sol {astronaut.solDay}
                  </div>
                </div>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl border border-slate-200 shadow-xl p-2 z-50 animate-fadeIn">
                  <div className="px-2 py-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider">
                    {t('Mürettebat', 'Crew')}
                  </div>
                  {availableAstronauts.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => {
                        playUiBeep(700);
                        setAstronautId(a.id);
                        setDropdownOpen(false);
                      }}
                      className={`w-full flex items-center gap-3 p-2 rounded-xl text-left transition-colors ${
                        a.id === astronaut.id ? 'bg-blue-50 text-blue-700' : 'hover:bg-slate-50 text-slate-700'
                      }`}
                    >
                      <img src={a.avatarUrl} alt={a.name} className="w-9 h-9 rounded-full object-cover" />
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

        {/* Mobil / tablet menü */}
        <nav className="flex lg:hidden items-center justify-between gap-0.5 py-1.5 border-t border-slate-100 overflow-x-auto">
          {navItems.map((item) => {
            const active = isTabActive(item.id);
            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`flex flex-col items-center shrink-0 min-w-[52px] py-1 px-1 rounded-lg ${
                  active ? 'text-blue-600 font-bold' : 'text-slate-500'
                }`}
              >
                {item.icon}
                <span className="text-[11px] mt-0.5 whitespace-nowrap">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
