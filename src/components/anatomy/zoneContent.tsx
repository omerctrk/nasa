import React from 'react';
import { Brain, Heart, Activity, Bone, Zap, LineChart } from 'lucide-react';
import { AnatomyZoneId, MetricStatus, VitalMetric } from '../../types/telemetry';
import type { NavigationTab } from '../../context/TelemetryContext';

type T = (tr: string, en: string) => string;

export interface ZoneMetric {
  label: string;
  value: string;
  normal: string;
  status: MetricStatus;
}

export interface ZoneContent {
  id: AnatomyZoneId;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  status: MetricStatus;
  metrics: ZoneMetric[];
  /** Uzayda bu bölgeye ne oluyor? (sade dil) */
  spaceEffect: string;
  /** Astronotun yapabileceği önleyici adımlar */
  actions: string[];
  links: { label: string; tab: NavigationTab; icon: React.ReactNode }[];
}

const worst = (...s: MetricStatus[]): MetricStatus =>
  s.includes('critical') ? 'critical' : s.includes('warning') ? 'warning' : 'normal';

/**
 * Vücut bölgeleri için içerik. Sabit değerler (tepki süresi, kemik kaybı vb.)
 * şimdilik örnek veridir; backend bağlandığında buradan beslenebilir.
 */
export const getZoneContent = (zone: AnatomyZoneId, vitals: Record<string, VitalMetric>, t: T): ZoneContent => {
  const reports = { label: t('Trend raporunu aç', 'Open trend report'), tab: 'reports' as const, icon: <LineChart className="w-4 h-4" /> };

  switch (zone) {
    case 'head':
      return {
        id: zone,
        title: t('Baş & Zihin', 'Head & Mind'),
        subtitle: t('Dikkat, uyku ve ruh hali', 'Alertness, sleep and mood'),
        icon: <Brain className="w-6 h-6 text-indigo-600" />,
        status: vitals.sleep.status,
        metrics: [
          { label: t('Uyku', 'Sleep'), value: `${vitals.sleep.value} ${t('saat', 'h')}`, normal: t('7–8.5 saat', '7–8.5 h'), status: vitals.sleep.status },
          { label: t('Tepki süresi (son PVT)', 'Reaction time (last PVT)'), value: '291 ms', normal: '250–400 ms', status: 'normal' },
        ],
        spaceEffect: t(
          'Düzensiz uyku, izolasyon, iş yükü ve radyasyon dikkat ile tepki süresini etkileyebilir. Yorgunluk, kritik görevlerde hata riskini artırır.',
          'Irregular sleep, isolation, workload and radiation can affect alertness and reaction time. Fatigue raises the risk of mistakes during critical tasks.'
        ),
        actions: [
          t('Her gün 3 dakikalık tepki testini (PVT) yapın.', 'Take the 3-minute reaction test (PVT) every day.'),
          t('Düzenli uyku saatlerine uyun; yorgunluk dikkati düşürür.', 'Keep regular sleep hours; fatigue lowers alertness.'),
          t('Günlük check-in ile ruh halinizi kaydedin.', 'Log your mood with the daily check-in.'),
        ],
        links: [
          { label: t('Refleks testi', 'Reflex test'), tab: 'cognitive-test', icon: <Zap className="w-4 h-4" /> },
          { label: t('Davranış modülü', 'Behavior module'), tab: 'behavior', icon: <Activity className="w-4 h-4" /> },
        ],
      };
    case 'chest':
      return {
        id: zone,
        title: t('Kalp & Akciğerler', 'Heart & Lungs'),
        subtitle: t('Kalp ritmi ve tansiyon', 'Heart rhythm and blood pressure'),
        icon: <Heart className="w-6 h-6 text-rose-500" />,
        status: worst(vitals.pulse.status, vitals.bp_systolic.status, vitals.bp_diastolic.status),
        metrics: [
          { label: t('Nabız', 'Heart rate'), value: `${vitals.pulse.value} bpm`, normal: '60–90 bpm', status: vitals.pulse.status },
          {
            label: t('Tansiyon', 'Blood pressure'),
            value: `${vitals.bp_systolic.value}/${vitals.bp_diastolic.value} mmHg`,
            normal: '90–130 / 60–85',
            status: worst(vitals.bp_systolic.status, vitals.bp_diastolic.status),
          },
          { label: t('Kalp debisi', 'Cardiac output'), value: t('5.4 L/dk', '5.4 L/min'), normal: t('4.8–6.2 L/dk', '4.8–6.2 L/min'), status: 'normal' },
        ],
        spaceEffect: t(
          'Yerçekimi olmadığında kalp kanı yukarı pompalamak için daha az çalışır ve zamanla zayıflayabilir. Dünyaya dönüşte ayağa kalkınca baş dönmesi yaşanabilir.',
          'Without gravity the heart works less to pump blood upward and can weaken over time. On return to Earth, astronauts may feel dizzy when standing up.'
        ),
        actions: [
          t('Günlük aerobik egzersizi (koşu bandı / bisiklet) aksatmayın.', "Don't skip daily aerobic exercise (treadmill / cycle)."),
          t('Yeterli sıvı ve tuz alarak kan hacmini koruyun.', 'Keep blood volume up with enough fluid and salt.'),
          t('Çarpıntı, göğüs ağrısı veya nefes darlığında hemen yer ekibine bildirin.', 'Report palpitations, chest pain or shortness of breath to the ground team right away.'),
        ],
        links: [reports],
      };
    case 'abdomen':
      return {
        id: zone,
        title: t('Metabolizma', 'Metabolism'),
        subtitle: t('Kan şekeri, vücut ısısı ve sıvı dengesi', 'Blood sugar, body temperature and fluid balance'),
        icon: <Activity className="w-6 h-6 text-emerald-600" />,
        status: worst(vitals.glucose.status, vitals.temperature.status),
        metrics: [
          { label: t('Kan şekeri', 'Blood glucose'), value: `${vitals.glucose.value} mg/dL`, normal: '70–110 mg/dL', status: vitals.glucose.status },
          { label: t('Vücut ısısı', 'Body temperature'), value: `${vitals.temperature.value} °C`, normal: '36.3–37.2 °C', status: vitals.temperature.status },
          { label: t('Elektrolit (Na/K)', 'Electrolytes (Na/K)'), value: '141 / 4.2', normal: '135–145 / 3.5–5.0', status: 'normal' },
          { label: t('Günlük sıvı', 'Daily fluid'), value: '1.8 L', normal: '≥ 2.4 L', status: 'warning' },
        ],
        spaceEffect: t(
          'Uzayda insülin duyarlılığı azalabilir ve kemiklerden çıkan kalsiyum böbrek taşı riskini artırır. Isınan kabin ve egzersiz vücut ısısını yükseltebilir.',
          'In space insulin sensitivity can drop, and calcium released from bones raises kidney-stone risk. A warm cabin and exercise can push body temperature up.'
        ),
        actions: [
          t('Günde en az 2.4 litre sıvı için.', 'Drink at least 2.4 liters of fluid per day.'),
          t('Öğünleri planlı yiyin; şekerli atıştırmalıkları sınırlayın.', 'Eat planned meals; limit sugary snacks.'),
          t('Egzersizden sonra vücut ısınızı kontrol edin.', 'Check your body temperature after exercise.'),
        ],
        links: [reports],
      };
    case 'musculoskeletal':
    default:
      return {
        id: 'musculoskeletal',
        title: t('Kas & Kemik', 'Muscle & Bone'),
        subtitle: t('Kemik yoğunluğu ve kas gücü', 'Bone density and muscle strength'),
        icon: <Bone className="w-6 h-6 text-indigo-600" />,
        status: 'normal',
        metrics: [
          { label: t('Kemik kaybı', 'Bone loss'), value: t('%0.4 / ay', '0.4% / mo'), normal: t('< %1 / ay', '< 1% / mo'), status: 'normal' },
          { label: t('Bacak kas gücü', 'Leg muscle strength'), value: '93%', normal: '> 88%', status: 'normal' },
          { label: t('Egzersiz uyumu', 'Exercise adherence'), value: '96%', normal: '> 90%', status: 'normal' },
          { label: t('Omurga uzaması', 'Spine lengthening'), value: '+3.4 cm', normal: '+2–5 cm', status: 'normal' },
        ],
        spaceEffect: t(
          'Ağırlık taşımayan kemikler ayda %1–1.5 oranında mineral kaybedebilir. Kaslar küçülür ve omurga diskleri genişleyerek bel ağrısına yol açabilir.',
          'Bones that carry no weight can lose 1–1.5% of their mineral per month. Muscles shrink, and spinal discs expand, which can cause back pain.'
        ),
        actions: [
          t('Her gün yaklaşık 2 saat direnç ve koşu egzersizi yapın.', 'Do about 2 hours of resistance and running exercise every day.'),
          t('Squat ve deadlift gibi ağırlık yükleyen hareketlere öncelik verin.', 'Prioritize load-bearing moves like squats and deadlifts.'),
          t('Yeterli kalsiyum ve D vitamini alın.', 'Get enough calcium and vitamin D.'),
        ],
        links: [reports],
      };
  }
};
