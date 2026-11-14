/** Tarih yardımcıları. "Bugün" her zaman UTC günüdür. */

/** "2026-11-14" (UTC) */
export const todayUtc = (d: Date = new Date()): string => d.toISOString().slice(0, 10);

/** UTC tarihine gün ekler: addDaysUtc("2026-11-14", 1) → "2026-11-15" */
export const addDaysUtc = (date: string, days: number): string => {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
};

/** İki UTC tarihi arasındaki gün farkı (b - a) */
export const daysBetween = (a: string, b: string): number =>
  Math.round((Date.parse(`${b.slice(0, 10)}T00:00:00Z`) - Date.parse(`${a.slice(0, 10)}T00:00:00Z`)) / 86400000);

/** "14 Kasım" / "14 November" (UTC) */
export const formatDayMonth = (date: string, lang: 'tr' | 'en'): string =>
  new Date(`${date.slice(0, 10)}T00:00:00Z`).toLocaleDateString(lang === 'tr' ? 'tr-TR' : 'en-GB', {
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  });

/** "07:02" (UTC) — ISO zaman damgasından */
export const formatTimeUtc = (iso: string): string => iso.slice(11, 16);

/**
 * Uyku süresi önizlemesi (dakika). Yalnızca bilgi amaçlı; kaydedilen değer backend'in hesabıdır.
 * Gece yarısını geçen uykuyu doğru hesaplar: 23:30 → 06:45 = 435 dk (7 sa 15 dk).
 */
export const sleepMinutes = (bed: string, wake: string): number | null => {
  const m = (s: string) => {
    const [h, mm] = s.split(':').map(Number);
    return Number.isFinite(h) && Number.isFinite(mm) ? h * 60 + mm : NaN;
  };
  const b = m(bed);
  const w = m(wake);
  if (Number.isNaN(b) || Number.isNaN(w)) return null;
  const diff = w - b;
  return diff <= 0 ? diff + 24 * 60 : diff;
};

export const formatDuration = (minutes: number, lang: 'tr' | 'en'): string => {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (lang === 'tr') return m ? `${h} saat ${m} dakika` : `${h} saat`;
  return m ? `${h} h ${m} min` : `${h} h`;
};
