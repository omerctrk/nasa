import React from 'react';
import { Brain, Heart, Activity, Bone, Eye, Zap, LineChart } from 'lucide-react';
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

export const getZoneContent = (zone: AnatomyZoneId, vitals: Record<string, VitalMetric>, t: T): ZoneContent => {
  const reports = { label: t('Trend raporunu aç', 'Open trend report'), tab: 'reports' as const, icon: <LineChart className="w-4 h-4" /> };
  const measured = (label: string, metric: VitalMetric): ZoneMetric => ({
    label,
    value: Number.isFinite(metric.value) ? `${metric.value} ${metric.unit}` : t('Kayıt yok', 'No record'),
    normal: t('Eşik tanımlanmadı', 'No threshold configured'),
    status: metric.status,
  });
  const unavailable = (label: string): ZoneMetric => ({ label, value: t('Kayıt yok', 'No record'), normal: t('Veri kaynağı bağlı değil', 'Data source not connected'), status: 'normal' });

  switch (zone) {
    case 'head':
      return {
        id: zone,
        title: t('Baş & Gözler', 'Head & Eyes'),
        subtitle: t('Göz sağlığı, beyin ve dikkat', 'Eye health, brain and alertness'),
        icon: <Brain className="w-6 h-6 text-indigo-600" />,
        status: vitals.iop.status,
        metrics: [
          measured(t('Göz içi basıncı', 'Eye pressure (IOP)'), vitals.iop),
          unavailable(t('Optik sinir kılıfı', 'Optic nerve sheath')),
          unavailable(t('Tepki süresi', 'Reaction time')),
          measured(t('Uyku', 'Sleep'), vitals.sleep),
        ],
        spaceEffect: t(
          'Ağırlıksız ortamda yaklaşık 2 litre vücut sıvısı kafaya doğru kayar. Bu, göz arkasındaki basıncı artırıp görmeyi bulanıklaştırabilir. Buna SANS (uzay uçuşuna bağlı nöro-oküler sendrom) denir.',
          'In weightlessness about 2 liters of body fluid shift toward the head. This can raise pressure behind the eyes and blur vision, a condition called SANS (Spaceflight-Associated Neuro-ocular Syndrome).'
        ),
        actions: [
          t('Haftada en az bir kez görme testi yapın.', 'Take a vision test at least once a week.'),
          t('Baş aşağı pozisyonda uzun süre çalışmaktan kaçının.', 'Avoid long periods working head-down.'),
          t('Göz basıncı yükselirse LBNP (alt vücut negatif basınç) seansı uygulayın.', 'If eye pressure rises, do an LBNP (lower body negative pressure) session.'),
          t('Düzenli uyku saatlerine uyun; yorgunluk dikkati düşürür.', 'Keep regular sleep hours; fatigue lowers alertness.'),
        ],
        links: [
          { label: t('Görme testi', 'Vision test'), tab: 'vision-test', icon: <Eye className="w-4 h-4" /> },
          { label: t('Refleks testi', 'Reflex test'), tab: 'cognitive-test', icon: <Zap className="w-4 h-4" /> },
        ],
      };
    case 'chest':
      return {
        id: zone,
        title: t('Kalp & Akciğerler', 'Heart & Lungs'),
        subtitle: t('Kalp ritmi, oksijen ve tansiyon', 'Heart rhythm, oxygen and blood pressure'),
        icon: <Heart className="w-6 h-6 text-rose-500" />,
        status: worst(vitals.pulse.status, vitals.oxygen.status),
        metrics: [
          measured(t('Nabız', 'Heart rate'), vitals.pulse),
          measured(t('Oksijen (SpO₂)', 'Oxygen (SpO₂)'), vitals.oxygen),
          unavailable(t('Tansiyon', 'Blood pressure')),
          unavailable(t('Kalp debisi', 'Cardiac output')),
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
          measured(t('Kan şekeri', 'Blood glucose'), vitals.glucose),
          measured(t('Vücut ısısı', 'Body temperature'), vitals.temperature),
          unavailable(t('Elektrolit (Na/K)', 'Electrolytes (Na/K)')),
          unavailable(t('Günlük sıvı', 'Daily fluid')),
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
          unavailable(t('Kemik kaybı', 'Bone loss')),
          unavailable(t('Bacak kas gücü', 'Leg muscle strength')),
          unavailable(t('Egzersiz uyumu', 'Exercise adherence')),
          unavailable(t('Omurga uzaması', 'Spine lengthening')),
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
