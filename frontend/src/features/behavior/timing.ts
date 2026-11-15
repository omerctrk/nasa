/**
 * PVT ve zihinsel döndürme testlerinin ORTAK zamanlama kuralları.
 *
 * - Süre ölçümü yalnızca performance.now() ile (Date.now() kullanılmaz).
 * - Sekme görünmez olursa (visibilitychange) test geçersiz sayılır.
 * - Pencere boyutu değişimi veya tam ekrandan çıkma testi durdurmaz.
 */

export const now = (): number => performance.now();

/** Bir sonraki karede çalıştırır; uyarıcının ekrana çizildiği anı yakalamak için */
export const onNextPaint = (cb: (t: number) => void): number =>
  requestAnimationFrame(() => {
    cb(performance.now());
  });

/**
 * Sekme gizlenince `onInvalid` çağrılır. Dönen fonksiyon dinleyiciyi kaldırır.
 */
export const watchVisibility = (onInvalid: () => void): (() => void) => {
  const handler = () => {
    if (document.visibilityState === 'hidden') onInvalid();
  };
  document.addEventListener('visibilitychange', handler);
  return () => document.removeEventListener('visibilitychange', handler);
};

/** Tekdüze rastgele tam sayı [min, max] */
export const randomInt = (min: number, max: number): number => Math.floor(min + Math.random() * (max - min + 1));

/** Fisher–Yates karıştırma */
export const shuffle = <T,>(arr: T[]): T[] => {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

/** Örn. "chrome-desktop-keyboard", "safari-tablet-touch" */
export const deviceString = (input: 'keyboard' | 'touch' | 'mouse'): string => {
  const ua = navigator.userAgent.toLowerCase();
  const browser = ua.includes('edg/')
    ? 'edge'
    : ua.includes('firefox')
      ? 'firefox'
      : ua.includes('chrome')
        ? 'chrome'
        : ua.includes('safari')
          ? 'safari'
          : 'other';
  const form = /ipad|tablet/.test(ua) ? 'tablet' : /mobi|iphone|android/.test(ua) ? 'phone' : 'desktop';
  return `${browser}-${form}-${input}`;
};

export const requestFullscreen = (el: HTMLElement | null) => {
  if (!el || document.fullscreenElement) return;
  el.requestFullscreen?.().catch(() => {
    /* tam ekran reddedilirse test yine de devam eder */
  });
};

export const exitFullscreen = () => {
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
};
