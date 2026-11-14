/**
 * Ortak arayüz bileşenleri (Card, Button, PageHeader, FormField, Skeleton).
 * Modüller bu bileşenleri kullanır; kendi içlerinde yeniden yazmaz.
 */
import React from 'react';

export const Card: React.FC<React.HTMLAttributes<HTMLElement> & { as?: 'section' | 'div' | 'article' }> = ({
  as: Tag = 'section',
  className = '',
  children,
  ...rest
}) => (
  <Tag className={`bg-white rounded-2xl border border-slate-200 shadow-sm ${className}`} {...rest}>
    {children}
  </Tag>
);

type ButtonVariant = 'primary' | 'secondary' | 'ghost';

export const Button = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'md' | 'lg' }
>(({ variant = 'primary', size = 'md', className = '', type = 'button', ...rest }, ref) => {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 disabled:opacity-45 disabled:cursor-not-allowed';
  const sizes = { md: 'min-h-11 px-4 text-sm', lg: 'min-h-12 px-6 text-base' };
  const variants: Record<ButtonVariant, string> = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm',
    secondary: 'bg-white hover:bg-slate-50 text-slate-800 border border-slate-300',
    ghost: 'text-slate-600 hover:text-slate-900 hover:bg-slate-100',
  };
  return <button ref={ref} type={type} className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...rest} />;
});
Button.displayName = 'Button';

export const PageHeader: React.FC<{ title: string; subtitle?: React.ReactNode; actions?: React.ReactNode }> = ({
  title,
  subtitle,
  actions,
}) => (
  <div className="flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
      {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
    </div>
    {actions}
  </div>
);

/** Etiket + kontrol + yardım/hata metni. `as="fieldset"` buton grupları için. */
export const FormField: React.FC<{
  label: string;
  htmlFor?: string;
  as?: 'div' | 'fieldset';
  hint?: React.ReactNode;
  error?: string | null;
  missing?: boolean;
  children: React.ReactNode;
}> = ({ label, htmlFor, as = 'div', hint, error, missing, children }) => {
  const Tag = as;
  const labelEl =
    as === 'fieldset' ? (
      <legend className="text-sm font-semibold text-slate-800 mb-2">{label}</legend>
    ) : (
      <label htmlFor={htmlFor} className="block text-sm font-semibold text-slate-800 mb-2">
        {label}
      </label>
    );
  return (
    <Tag className={`min-w-0 ${missing ? 'pl-3 border-l-2 border-slate-400' : ''}`}>
      {labelEl}
      {children}
      {hint && !error && <p className="text-xs text-slate-500 mt-1.5">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs font-medium text-slate-900 mt-1.5 underline decoration-dotted">
          {error}
        </p>
      )}
    </Tag>
  );
};

/** Yükleniyor durumunda gri iskelet blok */
export const Skeleton: React.FC<{ className?: string }> = ({ className = 'h-4 w-full' }) => (
  <div className={`animate-pulse rounded-lg bg-slate-200 ${className}`} aria-hidden />
);

/** Sakin bilgi kutusu (alarm görünümü yok) */
export const InfoBox: React.FC<{ children: React.ReactNode; icon?: React.ReactNode }> = ({ children, icon }) => (
  <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-700 leading-relaxed">
    {icon && <span className="shrink-0 mt-0.5 text-slate-500">{icon}</span>}
    <div>{children}</div>
  </div>
);
