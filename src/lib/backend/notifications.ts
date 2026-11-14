/**
 * Bildirim akışı: /ws/v1/notifications (ops.NotificationEvents).
 *
 * Şema kuralları:
 * - Belirteç adres satırına (query string) yazılmaz; ilk mesajda gönderilir.
 * - Olaylar "en az bir kez" gelir; ekran event_id ile tekrarları ayıklar.
 * - Her olay için teslim alındısı (receipt) gönderilir. Bu insan onayı değildir.
 * - Bağlantı koparsa yeniden bağlanılır; bekleyen olaylar sunucudan tekrar gelir.
 *
 * MESAJ BİÇİMLERİ VARSAYIMDIR (şemada verilmedi):
 *   istemci → { "type": "auth", "token": "<JWT>" }
 *   sunucu  → { "type": "event", "event": NotificationEvent }
 *   istemci → { "type": "receipt", "event_id": "<uuid>" }
 */
import { useEffect, useRef } from 'react';
import { API_BASE_URL, USE_MOCK, getAuthToken } from '../apiClient';
import type { NotificationEvent } from './types';

type Handler = (e: NotificationEvent) => void;

const wsUrl = (): string => {
  const env = import.meta.env.VITE_WS_URL as string | undefined;
  if (env) return env;
  // API_BASE_URL "/api/v1" veya "http://host:8000/api/v1" olabilir
  const base = API_BASE_URL.startsWith('http') ? new URL(API_BASE_URL) : new URL(API_BASE_URL, window.location.origin);
  const proto = base.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${base.host}/ws/v1/notifications`;
};

export class NotificationClient {
  private ws: WebSocket | null = null;
  private handlers = new Set<Handler>();
  private seen = new Set<string>();
  private retry = 0;
  private closed = false;
  private timer: number | undefined;

  connect() {
    if (USE_MOCK || this.ws) return;
    this.closed = false;
    const token = getAuthToken();
    if (!token) return; // giriş yapılmadan bağlanılmaz
    const ws = new WebSocket(wsUrl());
    this.ws = ws;

    ws.onopen = () => {
      this.retry = 0;
      ws.send(JSON.stringify({ type: 'auth', token }));
    };
    ws.onmessage = (msg) => {
      let data: { type?: string; event?: NotificationEvent };
      try {
        data = JSON.parse(String(msg.data));
      } catch {
        return;
      }
      const ev = data.type === 'event' ? data.event : undefined;
      if (!ev?.event_id) return;
      // Teslim alındısı her durumda gönderilir (tekrar gelen olay için de)
      ws.send(JSON.stringify({ type: 'receipt', event_id: ev.event_id }));
      if (this.seen.has(ev.event_id)) return;
      this.seen.add(ev.event_id);
      this.handlers.forEach((h) => h(ev));
    };
    ws.onclose = () => {
      this.ws = null;
      if (this.closed) return;
      // Artan bekleme ile yeniden bağlan (en fazla 30 sn)
      const delay = Math.min(30_000, 1000 * 2 ** this.retry++);
      this.timer = window.setTimeout(() => this.connect(), delay);
    };
    ws.onerror = () => ws.close();
  }

  subscribe(h: Handler): () => void {
    this.handlers.add(h);
    return () => this.handlers.delete(h);
  }

  close() {
    this.closed = true;
    window.clearTimeout(this.timer);
    this.ws?.close();
    this.ws = null;
  }
}

/** Uygulama genelinde tek bağlantı */
export const notificationClient = new NotificationClient();

/** Bildirim olaylarını dinler. Sahte modda hiçbir şey yapmaz. */
export const useNotifications = (handler: Handler) => {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (USE_MOCK) return;
    notificationClient.connect();
    return notificationClient.subscribe((e) => ref.current(e));
  }, []);
};
