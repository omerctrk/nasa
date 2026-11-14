/**
 * Görev profilleri: aynı astronot verisi farklı ortamlarda nasıl yorumlanmalı?
 *
 * Değerler yaklaşık ve eğitim amaçlıdır (kaynaklar):
 * - ISS dozu ~0.3–0.8 mSv/gün (NASA HRP)
 * - Ay yüzeyi ~1.37 mSv/gün (Chang'e-4 LND ölçümü, 2020)
 * - Mars yolculuğu ~1.84 mSv/gün (Curiosity RAD, seyir evresi)
 * - Mars yüzeyi ~0.67 mSv/gün (Curiosity RAD, Gale Krateri)
 * - Kariyer limiti 600 mSv (NASA-STD-3001, 2022)
 * - Mars iletişim gecikmesi tek yön ~4–24 dk (Dünya–Mars konumuna göre)
 */
export type MissionProfileId = 'iss' | 'moon' | 'mars_transit' | 'mars_surface';

type L = { tr: string; en: string };

export interface MissionProfile {
  id: MissionProfileId;
  name: L;
  short: string;
  habitat: L;
  /** Dünya yerçekimine oranla */
  gravityG: number;
  /** Tek yön iletişim gecikmesi (saniye) */
  oneWayDelaySec: number;
  /** Ortalama günlük radyasyon dozu (mSv) */
  dailyDoseMSv: number;
  /** Acil durumda Dünya'ya dönüş süresi */
  returnTime: L;
  /** Bu ortamda astronotun ne kadar kendi başına olduğu */
  autonomy: L;
}

export const CAREER_LIMIT_MSV = 600;

export const MISSION_PROFILES: MissionProfile[] = [
  {
    id: 'iss',
    name: { tr: 'Uluslararası Uzay İstasyonu', en: 'International Space Station' },
    short: 'ISS',
    habitat: { tr: 'Alçak Dünya yörüngesi', en: 'Low Earth orbit' },
    gravityG: 0,
    oneWayDelaySec: 0.3,
    dailyDoseMSv: 0.5,
    returnTime: { tr: '~1 gün', en: '~1 day' },
    autonomy: {
      tr: 'Yer ekibi anında ulaşılabilir. Uçuş cerrahıyla canlı görüşme yapılabilir.',
      en: 'The ground team is reachable instantly. Live calls with the flight surgeon are possible.',
    },
  },
  {
    id: 'moon',
    name: { tr: 'Ay yüzeyi üssü', en: 'Lunar surface base' },
    short: 'MOON',
    habitat: { tr: 'Ay güney kutbu', en: 'Lunar south pole' },
    gravityG: 0.166,
    oneWayDelaySec: 1.3,
    dailyDoseMSv: 1.37,
    returnTime: { tr: '~3–5 gün', en: '~3–5 days' },
    autonomy: {
      tr: 'Kısa gecikme var; yer ekibi danışılabilir ama tahliye günler sürer.',
      en: 'Short delay; the ground team can advise, but evacuation takes days.',
    },
  },
  {
    id: 'mars_transit',
    name: { tr: 'Mars yolculuğu', en: 'Mars transit' },
    short: 'TRANSIT',
    habitat: { tr: 'Derin uzay aracı', en: 'Deep-space vehicle' },
    gravityG: 0,
    oneWayDelaySec: 8 * 60,
    dailyDoseMSv: 1.84,
    returnTime: { tr: 'Geri dönüş yok (aylar)', en: 'No return (months)' },
    autonomy: {
      tr: 'Mesajlar dakikalar sonra ulaşır. Önce ekip kendi başına müdahale eder.',
      en: 'Messages take minutes to arrive. The crew must act on its own first.',
    },
  },
  {
    id: 'mars_surface',
    name: { tr: 'Mars yüzeyi üssü', en: 'Mars surface base' },
    short: 'MARS',
    habitat: { tr: 'Mars, Jezero Krateri', en: 'Mars, Jezero Crater' },
    gravityG: 0.38,
    oneWayDelaySec: 14 * 60,
    dailyDoseMSv: 0.67,
    returnTime: { tr: 'En erken ~26 ay sonra', en: 'Earliest in ~26 months' },
    autonomy: {
      tr: 'Bir soru-cevap yarım saati bulabilir. Kararlar büyük ölçüde mürettebatındır.',
      en: 'One question-and-answer can take half an hour. Decisions are largely the crew’s.',
    },
  },
];

export const getProfile = (id: MissionProfileId): MissionProfile =>
  MISSION_PROFILES.find((p) => p.id === id) ?? MISSION_PROFILES[0];

/** "0.3 sn", "1.3 sn", "8 dk" */
export const formatDelay = (sec: number, lang: 'tr' | 'en'): string => {
  if (sec < 60) return lang === 'tr' ? `${sec} sn` : `${sec} s`;
  const m = Math.round(sec / 60);
  return lang === 'tr' ? `${m} dk` : `${m} min`;
};

/** Görev süresince birikmiş doz (mSv) */
export const cumulativeDose = (profile: MissionProfile, missionDay: number): number =>
  Math.round(profile.dailyDoseMSv * missionDay * 10) / 10;
