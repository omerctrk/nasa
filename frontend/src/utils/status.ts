import { MetricStatus } from '../types/telemetry';

type T = (tr: string, en: string) => string;

/**
 * Durum renkleri tek yerden yönetilir. Renk + yazı birlikte kullanılır,
 * böylece renk körlüğü olan kullanıcılar da durumu okuyabilir.
 */
export const statusMeta = (status: MetricStatus, t: T) => {
  switch (status) {
    case 'critical':
      return {
        label: t('Kritik', 'Critical'),
        hex: '#EF4444',
        dot: 'bg-red-500',
        text: 'text-red-700',
        badge: 'bg-red-100 text-red-800 border-red-300',
        card: 'bg-red-50/60 border-red-300 ring-1 ring-red-200',
      };
    case 'warning':
      return {
        label: t('Dikkat', 'Caution'),
        hex: '#F59E0B',
        dot: 'bg-amber-500',
        text: 'text-amber-700',
        badge: 'bg-amber-100 text-amber-800 border-amber-300',
        card: 'bg-amber-50/60 border-amber-300 ring-1 ring-amber-200',
      };
    default:
      return {
        label: t('Normal', 'Normal'),
        hex: '#10B981',
        dot: 'bg-emerald-500',
        text: 'text-slate-900',
        badge: 'bg-emerald-100 text-emerald-800 border-emerald-200',
        card: 'bg-white border-slate-200 hover:border-sky-300',
      };
  }
};

/** Göstergelerin ekranda görünen kısa adları */
export const vitalLabel = (id: string, t: T) => {
  switch (id) {
    case 'pulse':
      return t('Nabız', 'Heart rate');
    case 'glucose':
      return t('Kan şekeri', 'Blood glucose');
    case 'oxygen':
      return t('Oksijen (SpO₂)', 'Oxygen (SpO₂)');
    case 'temperature':
      return t('Vücut ısısı', 'Body temp.');
    case 'iop':
      return t('Göz içi basıncı', 'Eye pressure');
    case 'sleep':
      return t('Uyku', 'Sleep');
    case 'bp':
      return t('Tansiyon', 'Blood pressure');
    case 'bp_systolic':
      return t('Büyük tansiyon', 'Systolic BP');
    case 'bp_diastolic':
      return t('Küçük tansiyon', 'Diastolic BP');
    default:
      return id;
  }
};

/** Birimlerin dile göre gösterimi */
export const unitLabel = (unit: string, t: T) => (unit === 'h' ? t('saat', 'h') : unit);
