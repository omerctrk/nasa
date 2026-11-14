/**
 * Acil durum bildirimi: kritik bir yaşamsal bulgu algılanınca Dünya'daki
 * Görev Kontrol Merkezi'ne (uçuş cerrahı nöbet hattı) anında haber verir.
 *
 * Kurallar:
 * - İstek Idempotency-Key ile yazılır; ağ hatasında AYNI anahtarla tekrar denenir,
 *   böylece aynı acil durum merkeze iki kez düşmez.
 * - Durum yalnız sunucudan okunur; ekran "doktor yönlendirildi" bilgisini kendisi uydurmaz.
 * - Yaşam döngüsü: SENT → RECEIVED (merkez aldı) → SURGEON_ASSIGNED (cerrah yönlendirildi)
 *   → SURGEON_CONNECTED (cerrahın yanıtı astronota ulaştı)
 *
 * UÇ NOKTALAR VARSAYIMDIR (backend ile netleştirilecek):
 *   POST /emergencies            + Idempotency-Key
 *        { client_request_id, astronaut_id, measurement_code, value, unit, detected_at, severity: 'CRITICAL' }
 *   GET  /emergencies/{emergency_id}
 *   WebSocket olayı: event_type 'emergency.updated' (emergency_id payload içinde)
 */
import { USE_MOCK, apiRequest, ApiError } from '../apiClient';

export type EmergencyStatus = 'SENT' | 'RECEIVED' | 'SURGEON_ASSIGNED' | 'SURGEON_CONNECTED';

export interface EmergencyNotification {
  emergency_id: string;
  astronaut_id: string;
  measurement_code: string;
  value: number;
  unit: string;
  severity: 'CRITICAL';
  status: EmergencyStatus;
  detected_at: string;
  sent_at: string;
  received_at: string | null;
  surgeon_assigned_at: string | null;
  surgeon_connected_at: string | null;
  /** Yönlendirilen ekip (ör. "Nöbetçi uçuş cerrahı") */
  assigned_team: string | null;
}

export interface EmergencyRequest {
  client_request_id: string;
  astronaut_id: string;
  measurement_code: string;
  value: number;
  unit: string;
  detected_at: string;
  severity: 'CRITICAL';
}

// ---------------------------------------------------------------- sahte akış (yalnız demo)

type MockEmergency = EmergencyNotification & { startedAt: number; delayMs: number };
const mockItems = new Map<string, MockEmergency>();
const mockByKey = new Map<string, string>();

const isMockOffline = () => {
  try {
    return localStorage.getItem('ahms-mock-offline') === '1' || navigator.onLine === false;
  } catch {
    return false;
  }
};

const uuid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;

/** Demo süreleri: gerçek gecikme uzunsa (Mars) sunum için kısaltılır */
export const demoDelayMs = (oneWayDelaySec: number) => Math.min(4000, Math.max(700, oneWayDelaySec * 1000));

const advance = (e: MockEmergency): MockEmergency => {
  const el = Date.now() - e.startedAt;
  const at = (ms: number) => new Date(e.startedAt + ms).toISOString();
  const recv = e.delayMs;
  const assigned = recv + 2500;
  const connected = assigned + e.delayMs + 1500;
  if (el >= recv && !e.received_at) {
    e.received_at = at(recv);
    e.status = 'RECEIVED';
  }
  if (el >= assigned && !e.surgeon_assigned_at) {
    e.surgeon_assigned_at = at(assigned);
    e.assigned_team = 'Flight Surgeon on duty · MCC';
    e.status = 'SURGEON_ASSIGNED';
  }
  if (el >= connected && !e.surgeon_connected_at) {
    e.surgeon_connected_at = at(connected);
    e.status = 'SURGEON_CONNECTED';
  }
  return e;
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const publicItem = ({ startedAt, delayMs, ...e }: MockEmergency): EmergencyNotification => ({ ...e });

const mock = {
  async create(key: string, req: EmergencyRequest, oneWayDelaySec: number): Promise<EmergencyNotification> {
    await new Promise((r) => setTimeout(r, 250));
    if (isMockOffline()) throw new ApiError(0, 'NETWORK_ERROR', 'Network error');
    const existing = mockByKey.get(key);
    if (existing) return publicItem(advance(mockItems.get(existing)!));
    const now = Date.now();
    const item: MockEmergency = {
      emergency_id: uuid(),
      astronaut_id: req.astronaut_id,
      measurement_code: req.measurement_code,
      value: req.value,
      unit: req.unit,
      severity: 'CRITICAL',
      status: 'SENT',
      detected_at: req.detected_at,
      sent_at: new Date(now).toISOString(),
      received_at: null,
      surgeon_assigned_at: null,
      surgeon_connected_at: null,
      assigned_team: null,
      startedAt: now,
      delayMs: demoDelayMs(oneWayDelaySec),
    };
    mockItems.set(item.emergency_id, item);
    mockByKey.set(key, item.emergency_id);
    return publicItem(item);
  },
  async get(id: string): Promise<EmergencyNotification> {
    const e = mockItems.get(id);
    if (!e) throw new ApiError(404, 'NOT_FOUND', 'Bu kayda erişemiyorsun.');
    return publicItem(advance(e));
  },
};

// ---------------------------------------------------------------- dışa açık API

export const emergencyApi = {
  /** oneWayDelaySec yalnız sahte modda süreleri canlandırmak için kullanılır */
  async create(idempotencyKey: string, req: EmergencyRequest, oneWayDelaySec: number): Promise<EmergencyNotification> {
    if (USE_MOCK) return mock.create(idempotencyKey, req, oneWayDelaySec);
    const r = await apiRequest<EmergencyNotification>('POST', '/emergencies', {
      body: req,
      headers: { 'Idempotency-Key': idempotencyKey },
    });
    return r.data;
  },
  async get(id: string): Promise<EmergencyNotification> {
    if (USE_MOCK) return mock.get(id);
    return (await apiRequest<EmergencyNotification>('GET', `/emergencies/${id}`)).data;
  },
};
