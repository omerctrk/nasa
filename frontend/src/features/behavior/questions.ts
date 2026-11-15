/**
 * Davranışsal ve Refleks modülü — TÜM METİNLER BU DOSYADA.
 *
 * - Günlük check-in soru etiketleri
 * - Belirti kodları
 * - Haftalık ölçek maddeleri (WHO-5, PHQ-2, GAD-2)
 *
 * ÖNEMLİ: Ölçek maddeleri ve seçenekleri RESMİ Türkçe sürümlerinden alınacak.
 * Modül sorumlusu aşağıdaki WEEKLY_* dizilerini resmi metinlerle dolduracak.
 * O zamana kadar yer tutucu kullanılır; maddeleri kendimiz çevirmiyoruz.
 */
import type { SymptomCode, WeeklyAnswerKey } from './types';

export type L = { tr: string; en: string };

// ---------------------------------------------------------------
// Günlük check-in
// ---------------------------------------------------------------

export const CHECKIN_SLIDERS: {
  key: 'mood' | 'energy' | 'stress';
  label: L;
  min: L;
  max: L;
}[] = [
  {
    key: 'mood',
    label: { tr: 'Bugün genel olarak kendini nasıl hissediyorsun?', en: 'How do you feel overall today?' },
    min: { tr: 'Çok kötü', en: 'Very bad' },
    max: { tr: 'Çok iyi', en: 'Very good' },
  },
  {
    key: 'energy',
    label: { tr: 'Enerji düzeyin nasıl?', en: 'How is your energy level?' },
    min: { tr: 'Çok düşük', en: 'Very low' },
    max: { tr: 'Çok yüksek', en: 'Very high' },
  },
  {
    key: 'stress',
    label: { tr: 'Ne kadar stresli hissediyorsun?', en: 'How stressed do you feel?' },
    min: { tr: 'Hiç', en: 'Not at all' },
    max: { tr: 'Çok', en: 'Very' },
  },
];

export const CHECKIN_CHOICES: {
  key: 'loneliness' | 'crew';
  label: L;
  options: L[]; // indeks = değer (0–4)
}[] = [
  {
    key: 'loneliness',
    label: { tr: 'Kendini yalnız hissettin mi?', en: 'Did you feel lonely?' },
    options: [
      { tr: 'Hiç', en: 'Not at all' },
      { tr: 'Biraz', en: 'A little' },
      { tr: 'Orta', en: 'Moderately' },
      { tr: 'Oldukça', en: 'Quite' },
      { tr: 'Çok', en: 'Very' },
    ],
  },
  {
    key: 'crew',
    label: { tr: 'Mürettebatla ilişkin nasıl?', en: 'How are things with the crew?' },
    options: [
      { tr: 'Çok kötü', en: 'Very bad' },
      { tr: 'Kötü', en: 'Bad' },
      { tr: 'Orta', en: 'OK' },
      { tr: 'İyi', en: 'Good' },
      { tr: 'Çok iyi', en: 'Very good' },
    ],
  },
];

export const CHECKIN_LABELS = {
  bed_time: { tr: 'Dün gece kaçta yattın?', en: 'What time did you go to bed last night?' },
  wake_time: { tr: 'Bu sabah kaçta kalktın?', en: 'What time did you wake up this morning?' },
  sleep_quality: { tr: 'Uykunun kalitesi nasıldı?', en: 'How was your sleep quality?' },
  sleep_quality_ends: { min: { tr: 'Çok kötü', en: 'Very poor' }, max: { tr: 'Çok iyi', en: 'Very good' } },
  symptoms: { tr: 'Bugün bunlardan biri var mı?', en: 'Do you have any of these today?' },
  none: { tr: 'Hiçbiri', en: 'None' },
} satisfies Record<string, unknown>;

export const SYMPTOMS: { code: SymptomCode; label: L }[] = [
  { code: 'bas_agrisi', label: { tr: 'Baş ağrısı', en: 'Headache' } },
  { code: 'halsizlik', label: { tr: 'Halsizlik', en: 'Fatigue' } },
  { code: 'bulanti', label: { tr: 'Bulantı', en: 'Nausea' } },
  { code: 'bas_donmesi', label: { tr: 'Baş dönmesi', en: 'Dizziness' } },
  { code: 'bulanik_gorme', label: { tr: 'Bulanık görme', en: 'Blurred vision' } },
  { code: 'goz_baskisi', label: { tr: 'Gözde baskı', en: 'Eye pressure' } },
  { code: 'sirt_agrisi', label: { tr: 'Sırt ağrısı', en: 'Back pain' } },
  { code: 'oksuruk', label: { tr: 'Öksürük', en: 'Cough' } },
  { code: 'nefes_darligi', label: { tr: 'Nefes darlığı', en: 'Shortness of breath' } },
  { code: 'bogaz_agrisi', label: { tr: 'Boğaz ağrısı', en: 'Sore throat' } },
  { code: 'doku_lezyon', label: { tr: 'Döküntü / uçuk', en: 'Rash / cold sore' } },
  { code: 'sindirim', label: { tr: 'Sindirim sorunu', en: 'Digestive issue' } },
];

// ---------------------------------------------------------------
// Haftalık ölçekler — RESMİ METİNLER EKLENECEK
// ---------------------------------------------------------------

export const WEEKLY_INTRO: L = {
  tr: 'Bu soruları son iki haftayı düşünerek cevapla. Cevapların varsayılan olarak yalnızca sende kalır.',
  en: 'Answer these questions thinking about the last two weeks. By default your answers stay with you only.',
};

export const WEEKLY_SHARE_LABEL: L = {
  tr: 'Bu değerlendirmeyi görev sağlık ekibiyle paylaş.',
  en: 'Share this assessment with the mission medical team.',
};

export interface ScaleSection {
  id: 'who5' | 'phq2' | 'gad2';
  title: string;
  items: { key: WeeklyAnswerKey; text: L }[];
  /** Seçenek etiketleri; indeks = puan */
  options: L[];
}

const placeholderItem = (scale: string, n: number): L => ({
  tr: `${scale} Madde ${n} (metin eklenecek)`,
  en: `${scale} Item ${n} (text to be added)`,
});

const placeholderOptions = (count: number): L[] =>
  Array.from({ length: count }, (_, v) => ({ tr: `${v} (metin eklenecek)`, en: `${v} (text to be added)` }));

export const WEEKLY_SCALES: ScaleSection[] = [
  {
    id: 'who5',
    title: 'WHO-5',
    items: [1, 2, 3, 4, 5].map((n) => ({ key: `who5_${n}` as WeeklyAnswerKey, text: placeholderItem('WHO-5', n) })),
    options: placeholderOptions(6), // 0–5
  },
  {
    id: 'phq2',
    title: 'PHQ-2',
    items: [1, 2].map((n) => ({ key: `phq2_${n}` as WeeklyAnswerKey, text: placeholderItem('PHQ-2', n) })),
    options: placeholderOptions(4), // 0–3
  },
  {
    id: 'gad2',
    title: 'GAD-2',
    items: [1, 2].map((n) => ({ key: `gad2_${n}` as WeeklyAnswerKey, text: placeholderItem('GAD-2', n) })),
    options: placeholderOptions(4), // 0–3
  },
];

export const SUPPORT_NOTE: L = {
  tr: 'Son haftalık değerlendirmene göre psikolojik destek ekibiyle görüşmeyi düşünebilirsin.',
  en: 'Based on your last weekly assessment, you might consider talking with the psychological support team.',
};

/** Destek notu eşiği (backend'in döndüğü puanlara göre) */
export const SUPPORT_THRESHOLD = 3;
