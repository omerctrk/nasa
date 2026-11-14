/**
 * Ortak API istemcisi.
 *
 * Ortam değişkenleri (.env):
 *   VITE_API_BASE_URL  varsayılan "/api/v1"
 *   VITE_USE_MOCK      "false" olunca gerçek API kullanılır (varsayılan: sahte veri)
 *
 * Not: Belgedeki NEXT_PUBLIC_USE_MOCK, bu proje Vite kullandığı için VITE_USE_MOCK'tur.
 */

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
export const USE_MOCK: boolean = (import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false';

/** Backend hata biçimi: {"error": {code, message, details, trace_id}} */
export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;
  traceId?: string;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}, traceId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.traceId = traceId;
  }
}

/** Oturum belirteci. Giriş sistemi eklenince burası güncellenir. */
export const getAuthToken = (): string | null => {
  try {
    return localStorage.getItem('ahms-token');
  } catch {
    return null;
  }
};

export interface ApiResponse<T> {
  data: T;
  status: number;
  etag: string | null;
}

type FieldError = { field?: string; code?: string; message?: string };

/**
 * Backend hata zarfı: {"detail": {code, message, trace_id, fields: [{field, code, message}]}}.
 * Eski biçim {"error": {..., details}} ve FastAPI'nin kendi doğrulama listesi de okunur.
 */
const parseErrorBody = (
  json: unknown
): { code?: string; message?: string; details: Record<string, unknown>; traceId?: string } => {
  const body = (json ?? {}) as { detail?: unknown; error?: Record<string, unknown> };
  const d = body.detail ?? body.error;
  if (Array.isArray(d)) {
    // FastAPI varsayılanı: [{loc, msg, type}]
    const msgs = d.map((x: { msg?: string }) => x?.msg).filter(Boolean);
    return { code: 'VALIDATION_ERROR', message: msgs.join(' ') || undefined, details: { fields: d } };
  }
  if (typeof d === 'string') return { message: d, details: {} };
  if (d && typeof d === 'object') {
    const o = d as { code?: string; message?: string; trace_id?: string; fields?: FieldError[]; details?: Record<string, unknown> };
    const fields = Array.isArray(o.fields) ? o.fields : [];
    // 422'de alan mesajları ekranda gösterilir
    const fieldMsg = fields.map((f) => f.message).filter(Boolean).join(' ');
    return {
      code: o.code,
      message: fieldMsg || o.message,
      details: fields.length ? { fields } : (o.details ?? {}),
      traceId: o.trace_id,
    };
  }
  return { details: {} };
};

export const apiRequest = async <T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  opts: { body?: unknown; headers?: Record<string, string>; query?: Record<string, string | number | undefined | null> } = {}
): Promise<ApiResponse<T>> => {
  const qs = opts.query
    ? '?' +
      Object.entries(opts.query)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : '';

  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}${qs === '?' ? '' : qs}`, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Network error');
  }

  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }

  if (!res.ok) {
    const traceId = res.headers.get('X-Trace-Id') ?? undefined;
    const e = parseErrorBody(json);
    const id = e.traceId ?? traceId;
    if (id) console.error(`[api] ${method} ${path} → ${res.status} trace_id=${id}`);
    throw new ApiError(res.status, e.code ?? `HTTP_${res.status}`, e.message ?? res.statusText, e.details, id);
  }

  return { data: json as T, status: res.status, etag: res.headers.get('ETag') };
};

/** Ağ hatasında aynı anahtarla tekrar denemek için benzersiz anahtar */
export const newIdempotencyKey = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
