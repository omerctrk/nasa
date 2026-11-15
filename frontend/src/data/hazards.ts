/**
 * NASA İnsan Araştırma Programı'nın (HRP) 5 uzay uçuşu tehlikesi.
 * Her gösterge, en çok ilişkili olduğu tehlikeye bağlanır.
 */
export type HazardId = 'radiation' | 'isolation' | 'distance' | 'gravity' | 'environment';

type L = { tr: string; en: string };

export const HAZARDS: Record<HazardId, { name: L; short: L; desc: L }> = {
  radiation: {
    name: { tr: 'Uzay radyasyonu', en: 'Space radiation' },
    short: { tr: 'Radyasyon', en: 'Radiation' },
    desc: {
      tr: 'Kozmik ışınlar ve güneş parçacıkları; kanser ve merkezi sinir sistemi riski.',
      en: 'Cosmic rays and solar particles; cancer and central nervous system risk.',
    },
  },
  isolation: {
    name: { tr: 'İzolasyon ve kapalı yaşam', en: 'Isolation & confinement' },
    short: { tr: 'İzolasyon', en: 'Isolation' },
    desc: {
      tr: 'Küçük ekip, dar alan, bozulan uyku; ruh hali ve dikkat etkilenir.',
      en: 'Small crew, tight space, disrupted sleep; mood and alertness suffer.',
    },
  },
  distance: {
    name: { tr: "Dünya'dan uzaklık", en: 'Distance from Earth' },
    short: { tr: 'Uzaklık', en: 'Distance' },
    desc: {
      tr: 'İletişim gecikir, tahliye zorlaşır; mürettebat kendi başına karar vermeli.',
      en: 'Communication is delayed and evacuation is hard; the crew must decide on its own.',
    },
  },
  gravity: {
    name: { tr: 'Değişen yerçekimi', en: 'Altered gravity' },
    short: { tr: 'Yerçekimi', en: 'Gravity' },
    desc: {
      tr: 'Kemik ve kas kaybı, sıvının kafaya kayması, kalp-damar sisteminde zayıflama.',
      en: 'Bone and muscle loss, fluid shift to the head, cardiovascular deconditioning.',
    },
  },
  environment: {
    name: { tr: 'Kapalı ve zorlu ortam', en: 'Hostile closed environment' },
    short: { tr: 'Kapalı ortam', en: 'Environment' },
    desc: {
      tr: 'Kabin havası (CO₂, O₂), sıcaklık, beslenme ve mikroplar sağlığı etkiler.',
      en: 'Cabin air (CO₂, O₂), temperature, nutrition and microbes affect health.',
    },
  },
};

/** Gösterge → ilişkili tehlike */
export const METRIC_HAZARD: Record<string, HazardId> = {
  pulse: 'gravity',
  bp: 'gravity',
  temperature: 'environment',
  glucose: 'environment',
  sleep: 'isolation',
};
