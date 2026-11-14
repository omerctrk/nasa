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
  iop: { mean: 13.9, sd: 0.8, basis: { tr: 'Uçuş öncesi 6 ölçüm + görevin ilk 30 günü', en: '6 pre-flight readings + first 30 mission days' } },
  pulse: { mean: 66, sd: 5, basis: { tr: 'Görevdeki dinlenme nabzı ortalaması', en: 'In-mission resting heart rate average' } },
  oxygen: { mean: 98.2, sd: 0.6, basis: { tr: 'Görevdeki SpO₂ ortalaması', en: 'In-mission SpO₂ average' } },
  glucose: { mean: 92, sd: 7, basis: { tr: 'Açlık ölçümleri ortalaması', en: 'Fasting reading average' } },
  temperature: { mean: 36.8, sd: 0.2, basis: { tr: 'Görevdeki vücut ısısı ortalaması', en: 'In-mission body temperature average' } },
};

export const AI_INSIGHTS: Record<string, AiInsight> = {
  iop: {
    metric: 'iop',
    interpretation: {
      tr: 'Göz içi basıncınız genel normal aralıkta olsa da kendi referansınızın belirgin biçimde üzerinde ve son ölçümlerde artış eğiliminde. Bu örüntü, ağırlıksız ortamda vücut sıvısının başa doğru kaymasıyla ilişkili SANS (uzay uçuşuna bağlı nöro-oküler sendrom) için erken bir işaret olabilir.',
      en: 'Your eye pressure is still within the general normal range, but clearly above your own baseline and trending up across recent readings. This pattern can be an early sign of SANS (spaceflight-associated neuro-ocular syndrome), linked to the headward fluid shift in microgravity.',
    },
    causes: [
      { text: { tr: 'Sıvının başa doğru kayması (mikro yerçekimi)', en: 'Headward fluid shift (microgravity)' }, likelihood: 0.72 },
      { text: { tr: 'Bugün düşük sıvı alımı (1.8 / 2.4 L)', en: 'Low fluid intake today (1.8 / 2.4 L)' }, likelihood: 0.46 },
      { text: { tr: 'Yüksek kabin CO₂ seviyesi', en: 'Elevated cabin CO₂' }, likelihood: 0.34 },
      { text: { tr: 'Ağır direnç egzersizi (ARED) sırasında nefes tutma', en: 'Breath-holding during heavy resistance exercise (ARED)' }, likelihood: 0.21 },
    ],
    recommendations: [
      { tr: 'Önümüzdeki 2 saatte 600 ml elektrolitli su için.', en: 'Drink 600 ml of electrolyte water over the next 2 hours.' },
      { tr: 'Bugünkü ağır ARED setlerini hafif aerobik egzersizle değiştirin.', en: 'Swap today’s heavy ARED sets for light aerobic exercise.' },
      { tr: '20 dakikalık alt vücut negatif basınç (LBNP) seansı yapın.', en: 'Do a 20-minute lower body negative pressure (LBNP) session.' },
      { tr: 'Akşam görme testini tekrarlayın.', en: 'Repeat the vision test this evening.' },
    ],
    followUpReadings: 3,
    sources: [
      { kind: 'nasa', title: 'Evidence Report: Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)', ref: 'NASA Human Research Program, 2017', relevance: 0.94 },
      { kind: 'paper', title: 'Optic disc edema, globe flattening, choroidal folds and hyperopic shifts observed in astronauts after long-duration space flight', ref: 'Mader TH et al., Ophthalmology, 2011', relevance: 0.88 },
      { kind: 'paper', title: 'Spaceflight associated neuro-ocular syndrome (SANS) and the neuro-ophthalmologic effects of microgravity', ref: 'Lee AG et al., npj Microgravity, 2020', relevance: 0.81 },
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
  oxygen: {
    metric: 'oxygen',
    interpretation: {
      tr: 'Oksijen doygunluğunuz kendi referansınızın altında. Tek ölçümlük düşüşlerde sensör yerleşimi sık bir nedendir; ancak bölgesel CO₂ birikimi de değerlendirilmeli. Ölçüm tekrarlanana kadar efor gerektiren işlerden kaçının.',
      en: 'Your oxygen saturation is below your own baseline. Sensor placement is a common cause of single-reading drops, but a local CO₂ pocket should also be considered. Avoid strenuous tasks until the reading is repeated.',
    },
    causes: [
      { text: { tr: 'Sensör yerleşimi / hareket', en: 'Sensor placement / motion' }, likelihood: 0.52 },
      { text: { tr: 'Bölgesel CO₂ birikimi (zayıf hava akışı)', en: 'Local CO₂ pocket (poor airflow)' }, likelihood: 0.41 },
      { text: { tr: 'Solunum yolu enfeksiyonu', en: 'Respiratory infection' }, likelihood: 0.15 },
    ],
    recommendations: [
      { tr: 'Sensörü yeniden takıp ölçümü tekrarlayın.', en: 'Refit the sensor and repeat the reading.' },
      { tr: 'Havalandırması iyi bir modüle geçin.', en: 'Move to a well-ventilated module.' },
      { tr: 'Nefes darlığı olursa hemen bildirin.', en: 'Report any shortness of breath right away.' },
    ],
    followUpReadings: 1,
    sources: [
      { kind: 'paper', title: 'Relationship between carbon dioxide levels and reported headaches on the International Space Station', ref: 'Law J et al., J Occup Environ Med, 2014', relevance: 0.83 },
      { kind: 'nasa', title: 'NASA-STD-3001 Space Flight Human-System Standard, Vol. 2', ref: 'NASA', relevance: 0.77 },
    ],
  },
};
