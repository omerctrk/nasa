import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

/**
 * Arayüz tercihleri: dil (TR/EN) ve tema (açık/koyu).
 *
 * Çeviri kullanımı:
 *   const { t } = usePrefs();
 *   t('Nabız', 'Heart Rate')   // Türkçe, İngilizce
 *
 * Backend'den gelecek metinler için de aynı yapı kullanılabilir:
 *   pick({ tr: '...', en: '...' })
 */

export type Lang = 'tr' | 'en';
export type Theme = 'light' | 'dark';
export type Localized = { tr: string; en: string };

interface PreferencesContextType {
  lang: Lang;
  setLang: (lang: Lang) => void;
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  /** Kısa çeviri yardımcısı: t('Türkçe', 'English') */
  t: (tr: string, en: string) => string;
  /** { tr, en } nesnesinden aktif dili seçer */
  pick: (text: Localized | string) => string;
}

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined);

const readStored = <T extends string>(key: string, allowed: readonly T[], fallback: T): T => {
  try {
    const v = localStorage.getItem(key);
    return v && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
};

const store = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* gizli sekme vb. durumlarda yok say */
  }
};

export const PreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => readStored('ahms-lang', ['tr', 'en'] as const, 'en'));
  const [theme, setThemeState] = useState<Theme>(() =>
    readStored(
      'ahms-theme',
      ['light', 'dark'] as const,
      typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    )
  );

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    store('ahms-lang', l);
  }, []);

  const setTheme = useCallback((th: Theme) => {
    setThemeState(th);
    store('ahms-theme', th);
  }, []);

  const toggleTheme = useCallback(() => setTheme(theme === 'dark' ? 'light' : 'dark'), [theme, setTheme]);

  const t = useCallback((tr: string, en: string) => (lang === 'tr' ? tr : en), [lang]);
  const pick = useCallback((text: Localized | string) => (typeof text === 'string' ? text : text[lang]), [lang]);

  return (
    <PreferencesContext.Provider value={{ lang, setLang, theme, setTheme, toggleTheme, t, pick }}>
      {children}
    </PreferencesContext.Provider>
  );
};

export const usePrefs = () => {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error('usePrefs must be used within a PreferencesProvider');
  return ctx;
};
