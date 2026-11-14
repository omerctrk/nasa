# Frontend ↔ Backend Entegrasyon Notu

"ASTRA HEALTH Sade Backend Tablo Şeması v5.0 MVP" ile frontend'in nasıl eşleştiğini anlatır.
Frontend şu an **sahte veriyle** çalışır; `.env.local` içinde `VITE_USE_MOCK=false` yapıldığında gerçek API'ye gider (`VITE_API_BASE_URL`, isteğe bağlı `VITE_WS_URL`).

Sahte modda ağ hatasını denemek için konsolda `localStorage.setItem('ahms-mock-offline','1')`.

## Genel ilke

Ekranlar kendi modelleriyle çalışmaya devam eder. Backend verisi tek bir katmanda ekranın modeline çevrilir:

| Dosya | Görev |
| --- | --- |
| `src/lib/backend/types.ts` | Tablo/DTO tipleri (sütun adları birebir, snake_case) |
| `src/lib/backend/adapters.ts` | DTO → ekran modeli dönüşümü ve seviye eşlemeleri |
| `src/lib/backend/measurementCodes.ts` | Gösterge ↔ `measurement_code` eşlemesi (**öneri, teyit bekliyor**) |
| `src/lib/apiClient.ts` | Ortak istemci: `/api/v1`, `Authorization: Bearer`, hata biçimi |
| `src/features/behavior/*` | Davranış modülü (behavioral.* tabloları); ayrıntı: `src/features/behavior/README.md` |

## Tablo → ekran eşlemesi

| Tablo | Ekranda | Durum |
| --- | --- | --- |
| `core.Missions` | Görev günü, görev ortamı seçici (`scenario` → ISS/Ay/Mars) | Tip + adapter hazır |
| `core.Astronauts` | Astronot seçici; `is_display_only` profilde test/veri girişi kapalı | **Uygulandı** (A007 aktif, A008 gösterim) |
| `core.Users` | Rol (ASTRONAUT / GROUND_CONTROL) | Tip hazır; giriş ekranı yok |
| `behavioral.checkins` | Davranış > Check-in, Bugün, Geçmiş | **Bağlı** (PUT + ETag) |
| `behavioral.cognitive_tests` | PVT ve zihinsel döndürme | **Bağlı** (`accuracy` 0–1, `client_request_id`) |
| `behavioral.weekly_assessments` | Haftalık ölçek (yalnız astronota görünür) | **Bağlı** |
| `anomaly.v_measurements` | Ana panel yaşamsal bulgu kartları ve grafikler | Adapter hazır (`vitalsFromMeasurements`) |
| `anomaly.anomaly_results` | Kart durumları (normal/watch/review) | Adapter hazır (`anomalyLevelToStatus`) |
| `sans.analiz` / `sans.test_kaydi` | Göz testi, SANS riski | Tip + logMAR çeviricisi hazır; SANS API sözleşmesi bekleniyor |
| `ops.Alerts` | Üst bant ve eylem planı penceresi (alarm durumu: Açık / Yer ekibi gördü / Kapatıldı) | Adapter hazır (`alertFromBackend`) |
| `ops.AnalysisJobs` | Sağlık Özeti > "Anomali analizi" (QUEUED → … → COMPLETED/FAILED, elle tekrar) | **Bağlı** (`src/lib/backend/analysisApi.ts`, sahte akış dahil) |
| `ops.NotificationEvents` | WebSocket bildirimleri (event_id ile tekrar ayıklama + receipt, yeniden bağlanma) | **İstemci hazır** (`src/lib/backend/notifications.ts`); sahte modda kapalı |

## Şemaya göre yapılan uyarlamalar

- **Ortak sağlık puanı kaldırıldı.** Ana paneldeki halka artık "normal aralıktaki gösterge sayısı / toplam" gösteriyor. Durum metni en yüksek uyarı seviyesinden geliyor.
- **Seviye eşlemesi:** anomali `normal` → normal, `watch`/`review` → dikkat (WARNING); SANS `green/yellow/red` → normal/dikkat/kritik.
- **Frontend eşik uygulamaz:** backend verisinde durum `anomaly_results.level` ile gelir; gelmezse kart "normal" kalır. (Demo modundaki eşikler yalnız simülasyon içindir.)
- **Davranış modülü:** `accuracy` 0–1 oran (ekranda %), `dsst` tanınır ama gösterilmez, `source` için `seed` ve `synthetic` "simüle veri" sayılır, `symptoms` NULL olabilir.
- **İki astronot:** A007 aktif, A008 yalnız gösterim. A008 seçilince testler/formlar yerine bilgi kutusu görünür, veriler karışmaz.

## Backend'den teyit beklenenler

1. **Fizyolojik ölçüm kodları:** `heart_rate`, `blood_pressure_systolic/diastolic`, `spo2`, `body_temperature`, `blood_glucose` önerildi. Sözlük gelince yalnız `measurementCodes.ts` değişir.
2. **Göz içi basıncı (IOP):** Şemadaki SANS testlerinde yok (near_acuity / contrast / amsler). Ekranda IOP kartı var; fizyolojik ölçüm olarak eklenecek mi, yoksa kaldırılacak mı?
3. **Görev günü uç noktası:** frontend `GET /api/v1/dashboard/me` → `{ mission_day, date, mission_id, start_date, length_days, scenario }` bekliyor.
4. **Liste/okuma uç noktaları:** `v_measurements`, `anomaly_results`, `sans.analiz`, `ops.Alerts` için yol ve sayfalama biçimi (`{ items, next_cursor }` varsayıldı).
5. **Alarm kapatma:** şemaya uygun olarak astronot ekranında düğme "Adımları tamamladım" oldu ve yalnız yerel olarak gizler; alarmı yer ekibi kapatır. Astronotun alarm üzerinde bir yetkisi (ör. "gördüm") olacak mı?
6. **WebSocket mesaj biçimi (varsayım):** istemci → `{"type":"auth","token":...}`, sunucu → `{"type":"event","event":NotificationEvent}`, istemci → `{"type":"receipt","event_id":...}`. Adres `VITE_WS_URL` ile değiştirilebilir.
9. **Analiz işi uç noktaları (varsayım):** `POST /analysis/jobs` (`Idempotency-Key`, gövde `{module:"anomaly"}`) → 202 + iş; `GET /analysis/jobs/{id}`; `POST /analysis/jobs/{id}/retry`; `GET /anomaly/results/{id}`.
7. **Hata biçimi:** `{"error": {code, message, details, trace_id}}` varsayıldı; 422'de `details` alan adı → mesaj eşlemesi.
8. **PVT kuralları:** geçersizlik eşikleri (erken basma, en az deneme sayısı) ve `lapses` eşiği backend'de; frontend yalnız ham denemeleri gönderir.

## Gönderim anahtarları

| İstek | Başlık | Gövde |
| --- | --- | --- |
| Check-in `PUT /behavioral/checkins/{date}` | `If-None-Match: *` (yeni) / `If-Match: <ETag>` (güncelleme) | — |
| Test `POST /behavioral/cognitive-tests` | `Idempotency-Key: <UUID>` | `client_request_id` (aynı UUID) |
| Haftalık `POST /behavioral/weekly-assessments` | `Idempotency-Key: <UUID>` | `client_request_id` (aynı UUID) |

Ağ hatasında aynı UUID ile tekrar gönderilir; şemadaki `UQ (astronaut_id, client_request_id)` çift kaydı önler.

## Acil durum bildirimi (kırmızı alarm)

Bir yaşamsal bulgu `critical` olduğunda ekran otomatik olarak Dünya'daki Görev Kontrol Merkezi'ne acil bildirim gönderir (`src/lib/backend/emergencyApi.ts`, ekran: `src/components/emergency/EmergencyAlarm.tsx`).

Uç noktalar **varsayımdır**, backend ile netleştirilecek:

- `POST /emergencies` + `Idempotency-Key` başlığı. Gövde: `client_request_id, astronaut_id, measurement_code, value, unit, detected_at, severity: "CRITICAL"`
- `GET /emergencies/{emergency_id}` → `status: SENT | RECEIVED | SURGEON_ASSIGNED | SURGEON_CONNECTED` ve her adımın zamanı (`sent_at, received_at, surgeon_assigned_at, surgeon_connected_at`)
- WebSocket olayı: `event_type: "emergency.updated"` (gelince ekran kaydı yeniden okur; yoksa 1 sn'de bir sorgular)

Kurallar: ağ hatasında aynı anahtarla otomatik tekrar denenir (aynı acil durum merkeze iki kez düşmez); "doktor yönlendirildi" bilgisi yalnız sunucudan gelir, ekran uydurmaz. Teyit beklenen: uç nokta yolları, uçuş cerrahı atamasının nasıl kaydedildiği, astronotun bu uca yazma yetkisi.

## ASTRA backend uyarlaması (bachand dalı, 15 Kasım)

Ekranlar değişmedi; uyarlama API katmanında. Sahte mod (`VITE_USE_MOCK`, varsayılan açık) eskisi gibi çalışır.

- **Bağlantı:** `vite.config.ts` → `/api` ve `/ws` istekleri `localhost:8000`'e aktarılır.
- **Adresler:** davranış uçları `/me/...` (`/me/checkins/{date}`, `/me/checkins`, `/me/cognitive-tests`, `/me/weekly-assessments`); görev günü `/me/profile`'daki `mission_start_date`'ten.
- **Listeler:** düz dizi, `?start=&end=` (son 120 gün). Ekrana yeniden eskiye sıralı verilir.
- **Hata biçimi:** `{"detail": {code, message, trace_id, fields}}` okunur; 422'de alan mesajları gösterilir; `X-Trace-Id` konsola yazılır.
- **Check-in:** yeni kayıtta başlık yok, güncellemede `If-Match`; `mood_index` istemciden gönderilir.
- **Test ve haftalık form:** hesaplanmış değerler gönderilir (ham denemeler `raw` alanında). Tüm formüller tek dosyada: `src/features/behavior/scoring.ts` (sahte backend de aynısını kullanır).
- **Ölçüm kodları:** `heart_rate (BPM)`, `systolic_bp`, `diastolic_bp`, `blood_glucose`, `body_temperature`. Arayüzdeki göstergeler de bunlara indirildi: SpO₂ ve göz içi basıncı kaldırıldı, tansiyon artık sabit değil, `bp_systolic` / `bp_diastolic` göstergelerinden gelir.
- **Analiz:** gövde `{module: "anomaly", idempotency_key, module_scope: "combined"}`. Sonuç ayrıntısı ucu olmadığından ekran yalnız "analiz tamamlandı" der.
- **Bildirimler (WS):** `{type: "authenticate", access_token}`; olay `{event_id, type, created_at, payload}`.
- **Backend'de olmayanlar:** `/emergencies` (gerçek modda istek gitmez, alarm sesli kanaldan haber verilmesini söyler) ve haftalık paylaşım ayarı (gerçek modda yalnız durum gösterilir).
- **Giriş:** ekran yok; deneme için token `localStorage`'a `ahms-token` olarak konur.
- **SANS/göz:** göz testi ekranı, SANS uyarısı ve göz basıncı kartları kaldırıldı. Varsayılan demo uyarısı ve yapay zekâ örneği tansiyon üzerine; demo düğmeleri: tansiyon, nabız, ateş.
