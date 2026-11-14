import colors from 'tailwindcss/colors';
import plugin from 'tailwindcss/plugin';

/**
 * Tema sistemi (açık / koyu)
 * ---------------------------------------------------------------
 * Bileşenlerde normal Tailwind sınıfları (bg-white, text-slate-800,
 * bg-sky-50 ...) kullanılmaya devam eder. Bu sınıflar CSS değişkenlerine
 * bağlanır ve <html class="dark"> olduğunda değişkenler koyu karşılıklarına
 * döner. Böylece her bileşene ayrı ayrı `dark:` sınıfı yazmak gerekmez.
 *
 * - Arka plan / kenarlık / gradyan: açık tonlar (50–300) koyu tonlara döner.
 * - Yazı / ikon (fill, stroke): koyu tonlar (500–950) açık tonlara döner.
 * - Doygun renkler (bg-blue-600 butonlar vb.) ve text-white aynı kalır.
 */

const PALETTES = ['slate', 'red', 'orange', 'amber', 'emerald', 'cyan', 'sky', 'blue', 'indigo', 'purple', 'rose'];
const SHADES = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900', '950'];

const hexToRgb = (hex) => {
  const h = hex.replace('#', '');
  return `${parseInt(h.slice(0, 2), 16)} ${parseInt(h.slice(2, 4), 16)} ${parseInt(h.slice(4, 6), 16)}`;
};

// Koyu modda hangi tonun kullanılacağı (kullanım türüne göre)
const DARK_MAP = {
  bg: { 50: '950', 100: '900', 200: '800', 300: '700' },
  border: { 50: '900', 100: '900', 200: '800', 300: '700' },
  text: { 500: '400', 600: '400', 700: '300', 800: '200', 900: '100', 950: '50' },
};

// Nötr (slate) yüzeyler koyu modda özel tonlar alır
const SLATE_DARK = {
  bg: { 50: '#151f32', 100: '#1e293b', 200: '#334155', 300: '#475569', 800: '#334155', 900: '#1e293b' },
  border: { 50: '#1e293b', 100: '#1e293b', 200: '#2b3a52', 300: '#3b4b63' },
  text: { 400: '#7889a3', 500: '#94a3b8', 600: '#aab8cc', 700: '#cbd5e1', 800: '#e2e8f0', 900: '#f1f5f9', 950: '#f8fafc' },
};

const lightVars = {};
const darkVars = {};
const themed = { bg: {}, border: {}, text: {} };

for (const kind of ['bg', 'border', 'text']) {
  for (const p of PALETTES) {
    themed[kind][p] = {};
    for (const s of SHADES) {
      const light = colors[p][s];
      const dark =
        p === 'slate'
          ? SLATE_DARK[kind][s] ?? light
          : DARK_MAP[kind][s]
            ? colors[p][DARK_MAP[kind][s]]
            : light;
      if (dark === light) {
        themed[kind][p][s] = light;
        continue;
      }
      const name = `--c-${kind}-${p}-${s}`;
      lightVars[name] = hexToRgb(light);
      darkVars[name] = hexToRgb(dark);
      themed[kind][p][s] = `rgb(var(${name}) / <alpha-value>)`;
    }
  }
}

// Kart yüzeyi (bg-white) ve beyaz kenarlıklar
lightVars['--c-surface'] = '255 255 255';
darkVars['--c-surface'] = '17 26 43';
themed.bg.white = 'rgb(var(--c-surface) / <alpha-value>)';
themed.border.white = 'rgb(var(--c-surface) / <alpha-value>)';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        space: {
          50: '#F5F9FF',
          100: '#EBF3FE',
          200: '#D6E7FD',
          300: '#B4D5FB',
          400: '#7CB5F8',
          500: '#3B8FF4',
          600: '#1D6CE7',
          700: '#1552C0',
          800: '#13429B',
          900: '#0E295E',
          950: '#081738',
        },
        ice: {
          50: '#F0F9FF',
          100: '#E0F2FE',
          200: '#BAE6FD',
          300: '#7DD3FC',
          400: '#38BDF8',
          500: '#0EA5E9',
          600: '#0284C7',
          700: '#0369A1',
        },
        cyanGlow: '#00F0FF',
        electric: '#2563EB',
        navy: {
          800: '#0F1E36',
          900: '#0B1528',
          950: '#060B16',
        },
      },
      backgroundColor: themed.bg,
      gradientColorStops: themed.bg,
      borderColor: themed.border,
      divideColor: themed.border,
      ringColor: themed.border,
      textColor: themed.text,
      fill: themed.text,
      stroke: themed.text,
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        soft: '0 4px 20px -2px rgba(15, 23, 42, 0.05), 0 2px 6px -1px rgba(15, 23, 42, 0.03)',
        card: '0 10px 30px -5px rgba(27, 85, 226, 0.08), 0 4px 12px -2px rgba(0, 0, 0, 0.04)',
        'glow-cyan': '0 0 20px rgba(0, 240, 255, 0.35)',
        'glow-blue': '0 0 20px rgba(37, 99, 235, 0.3)',
      },
    },
  },
  plugins: [
    plugin(({ addBase }) => {
      addBase({ ':root': lightVars, '.dark': darkVars });
    }),
  ],
};
