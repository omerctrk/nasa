import { Text } from '../types/telemetry';

/**
 * Yapay zekâ sağlık asistanı — ÖRNEK veri.
 *
 * Akış (backend tarafında):
 *   1) Her 30 dakikada bir ölçüm alınır.
 *   2) Ölçüm, astronotun KİŞİSEL referans bandıyla (uçuş öncesi + görevdeki kendi ortalaması) karşılaştırılır.
 *   3) Sapma varsa RAG ile NASA belgeleri ve hakemli yayınlardan ilgili pasajlar getirilir.
 *   4) LLM bu pasajlarla sapmayı yorumlar: olası nedenler, öneriler, aksiyon planı.
 *   5) Sonraki ölçümler izlenir; gerekirse sağlık ekibine bildirim yönlendirilir.
 *
 * Backend bağlandığında bu dosyadaki metinler LLM çıktısıyla değişecek; ekran aynı alanları bekler.
 */

/** Kişisel referans bandı (ortalama ± standart sapma) */
export interface PersonalBaseline {
  mean: number;
  sd: number;
  /** Bandın hangi verilerden hesaplandığı */
  basis: Text;
}

export interface AiSource {
  title: string;
  /** NASA belgesi mi, hakemli yayın mı */
  kind: 'nasa' | 'paper';
  ref: string;
  /** Getirilen pasajın sapmayla eşleşme oranı (0–1) */
  relevance: number;
}

export interface AiInsight {
  metric: string;
  /** LLM'in kısa yorumu */
  interpretation: Text;
  /** Olası nedenler, olasılık sırasına göre (0–1) */
  causes: { text: Text; likelihood: number }[];
  /** Kişiselleştirilmiş öneriler */
  recommendations: Text[];
  /** Kaç ölçüm sonra yeniden değerlendirilecek */
  followUpReadings: number;
  sources: AiSource[];
}

export const PERSONAL_BASELINES: Record<string, PersonalBaseline> = {
  bp_systolic: { mean: 114, sd: 5, basis: { tr: 'Uçuş öncesi 6 ölçüm + görevin ilk 30 günü', en: '6 pre-flight readings + first 30 mission days' } },
  bp_diastolic: { mean: 74, sd: 4, basis: { tr: 'Uçuş öncesi 6 ölçüm + görevin ilk 30 günü', en: '6 pre-flight readings + first 30 mission days' } },
  pulse: { mean: 66, sd: 5, basis: { tr: 'Görevdeki dinlenme nabzı ortalaması', en: 'In-mission resting heart rate average' } },
  glucose: { mean: 92, sd: 7, basis: { tr: 'Açlık ölçümleri ortalaması', en: 'Fasting reading average' } },
  temperature: { mean: 36.8, sd: 0.2, basis: { tr: 'Görevdeki vücut ısısı ortalaması', en: 'In-mission body temperature average' } },
};

export const AI_INSIGHTS: Record<string, AiInsight> = {
  bp_systolic: {
    metric: 'bp_systolic',
    interpretation: {
      tr: 'Büyük tansiyonunuz genel normal aralıkta olsa da kendi referansınızın belirgin biçimde üzerinde ve son ölçümlerde artış eğiliminde. Ağırlıksız ortamda vücut sıvısının üst vücuda kayması ve bugünkü düşük sıvı alımı bu örüntüyle uyumlu. Tek başına acil bir durum değil; sonraki ölçümlerde sürüp sürmediği izlenecek.',
      en: 'Your systolic pressure is still within the general normal range, but clearly above your own baseline and trending up across recent readings. The headward fluid shift in microgravity and today’s low fluid intake fit this pattern. It is not an emergency on its own; the next readings will show whether it persists.',
    },
    causes: [
      { text: { tr: 'Sıvının üst vücuda kayması (mikro yerçekimi)', en: 'Headward fluid shift (microgravity)' }, likelihood: 0.72 },
      { text: { tr: 'Bugün düşük sıvı alımı (1.8 / 2.4 L)', en: 'Low fluid intake today (1.8 / 2.4 L)' }, likelihood: 0.46 },
      { text: { tr: 'İş yükü ve stres', en: 'Workload and stress' }, likelihood: 0.34 },
      { text: { tr: 'Ağır direnç egzersizi (ARED) sonrası', en: 'After heavy resistance exercise (ARED)' }, likelihood: 0.21 },
    ],
    recommendations: [
      { tr: 'Önümüzdeki 2 saatte 600 ml elektrolitli su için.', en: 'Drink 600 ml of electrolyte water over the next 2 hours.' },
      { tr: '10 dakika oturarak dinlenip tansiyonu tekrar ölçün.', en: 'Rest seated for 10 minutes and re-measure.' },
      { tr: 'Bugünkü ağır ARED setlerini hafif aerobik egzersizle değiştirin.', en: 'Swap today’s heavy ARED sets for light aerobic exercise.' },
      { tr: 'Akşam yemeğinde tuzu azaltın.', en: 'Cut down on salt at dinner.' },
    ],
    followUpReadings: 3,
    sources: [
      { kind: 'nasa', title: 'Evidence Report: Risk of Cardiovascular Adaptations Contributing to Adverse Mission Performance and Health Outcomes', ref: 'NASA Human Research Program', relevance: 0.91 },
      { kind: 'paper', title: 'Heart in space: effect of the extraterrestrial environment on the cardiovascular system', ref: 'Hughson RL et al., Nature Reviews Cardiology, 2018', relevance: 0.87 },
      { kind: 'nasa', title: 'NASA-STD-3001 Space Flight Human-System Standard, Vol. 1', ref: 'NASA', relevance: 0.74 },
    ],
  },
  pulse: {
    metric: 'pulse',
    interpretation: {
      tr: 'Dinlenme nabzınız kendi referansınızın üzerinde. Egzersiz sonrası toparlanma, uyku açığı ya da sıvı kaybı en olası açıklamalar. Kalp ritmi düzenli görünüyor; durumun birkaç ölçüm boyunca sürüp sürmediği izlenecek.',
      en: 'Your resting heart rate is above your own baseline. Post-exercise recovery, sleep debt or fluid loss are the most likely explanations. The rhythm looks regular; the next readings will show whether it persists.',
    },
    causes: [
      { text: { tr: 'Egzersiz sonrası toparlanma', en: 'Post-exercise recovery' }, likelihood: 0.58 },
      { text: { tr: 'Sıvı kaybı ve kan hacminde azalma', en: 'Fluid loss and reduced blood volume' }, likelihood: 0.44 },
      { text: { tr: 'Uyku açığı / iş yükü stresi', en: 'Sleep debt / workload stress' }, likelihood: 0.37 },
    ],
    recommendations: [
      { tr: '15 dakika sakin dinlenin, sonra nabzı tekrar ölçün.', en: 'Rest quietly for 15 minutes, then re-measure.' },
      { tr: '500 ml sıvı alın.', en: 'Drink 500 ml of fluid.' },
      { tr: 'Bu akşam uyku penceresini koruyun.', en: 'Protect tonight’s sleep window.' },
    ],
    followUpReadings: 2,
    sources: [
      { kind: 'paper', title: 'Heart in space: effect of the extraterrestrial environment on the cardiovascular system', ref: 'Hughson RL et al., Nature Reviews Cardiology, 2018', relevance: 0.86 },
      { kind: 'nasa', title: 'NASA-STD-3001 Space Flight Human-System Standard, Vol. 1', ref: 'NASA', relevance: 0.74 },
    ],
  },
  temperature: {
    metric: 'temperature',
    interpretation: {
      tr: 'Vücut ısınız kendi referansınızın çok üzerinde. Uzun görevlerde astronotların çekirdek vücut ısısının Dünya’ya göre biraz daha yüksek seyrettiği bilinse de bu değer ateş düzeyinde. En olası açıklama bir enfeksiyon; ısı stresi de değerlendirilmeli.',
      en: 'Your body temperature is far above your own baseline. Astronauts’ core temperature is known to run slightly higher on long missions, but this value is at fever level. Infection is the most likely explanation; heat stress should also be considered.',
    },
    causes: [
      { text: { tr: 'Enfeksiyon (bağışıklık sistemi zayıflaması)', en: 'Infection (weakened immunity)' }, likelihood: 0.64 },
      { text: { tr: 'Isı stresi / egzersiz sonrası', en: 'Heat stress / after exercise' }, likelihood: 0.38 },
      { text: { tr: 'Sensör yerleşimi', en: 'Sensor placement' }, likelihood: 0.15 },
    ],
    recommendations: [
      { tr: 'Efor gerektiren işleri bırakın ve dinlenin.', en: 'Stop strenuous tasks and rest.' },
      { tr: 'Bol sıvı alın.', en: 'Drink plenty of fluids.' },
      { tr: '30 dakika sonra ısıyı tekrar ölçün.', en: 'Re-measure in 30 minutes.' },
      { tr: 'Mürettebatla yakın teması azaltın.', en: 'Reduce close contact with the crew.' },
    ],
    followUpReadings: 1,
    sources: [
      { kind: 'paper', title: 'Increased core body temperature in astronauts during long-duration space missions', ref: 'Stahn AC et al., Scientific Reports, 2017', relevance: 0.88 },
      { kind: 'nasa', title: 'NASA-STD-3001 Space Flight Human-System Standard, Vol. 1', ref: 'NASA', relevance: 0.72 },
    ],
  },
};
