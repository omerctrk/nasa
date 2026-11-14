# ASTRA HEALTH — Ortak Backend Sözleşmesi

Sahipler: Aybala + Ömer (ortak). Durum: **taslak v1** — "Ek açıklama 1" seçimleri esas alındı.
Bu belgedeki bir değeri değiştirmek sözleşme değişikliğidir: ikinizin onayıyla, kod ve
`backend/tests/fixtures/contract/` ile birlikte aynı PR'da yapılır.

Kapsam dışı (bu sözleşme karar vermez): model sağlayıcısı, klinik eşikler, veri yeterlilik
şartları, SANS API'nin URL/auth/sözleşmesi.

## 1. Dosyalar ve sorumluluklar

| Dosya | İçerik | Sorumlu |
|---|---|---|
| `contracts/backend-contract.md` | Bu belge | Ortak |
| `backend/app/schemas/common.py` | Enum'lar, hata zarfı, `CurrentUser`, `MeasurementDTO` | Ortak |
| `backend/app/repositories/interfaces.py` | Repository `Protocol` imzaları | Ortak |
| `backend/app/repositories/records.py` | Repository girdi/çıktı veri modelleri | Ortak |
| `backend/app/repositories/errors.py` | Repository hataları | Ortak |
| `backend/app/core/errors.py` | Hata zarfı handler'ları, `trace_id` | Ortak |
| `backend/tests/fixtures/contract/` | Örnek istek/yanıt/olay JSON'ları | Ortak |
| `backend/app/repositories/sqlalchemy_*.py` | Gerçek uygulama (`SqlAlchemyRepository`) | Aybala |
| `backend/tests/fakes/` | Aynı arayüzlerin fake uygulaması | Ömer |
| `backend/app/schemas/{auth,analysis,notifications}.py` | Uca özel istek/yanıt modelleri | Ömer |

## 2. Enum değerleri

API, Python ve DB CHECK değerleri birebir aynıdır; büyük/küçük harf dönüşümü yapılmaz.

| Tür | Değerler |
|---|---|
| `Role` | `ASTRONAUT`, `GROUND_CONTROL` |
| `JobState` | `QUEUED`, `SYNCING`, `ANALYZING`, `COMPLETED`, `FAILED` |
| `AlertStatus` | `OPEN`, `ACKNOWLEDGED`, `RESOLVED` |
| `Severity` | `NORMAL`, `WARNING`, `CRITICAL` |
| `AnomalyLevel` | `normal`, `watch`, `review` |
| `SansLevel` | `green`, `yellow`, `red` |
| `SansState` | `normal`, `suspect`, `confirmed` |
| `AnalysisModule` | `anomaly`, `sans` — analizi **yapan** modül |
| `MeasurementModule` | `physiological`, `behavioral`, `sans` — ölçümün **geldiği** modül |
| `Source` | `manual`, `synthetic` |
| `Eye` | `OD` (sağ), `OS` (sol) |
| `TimePrecision` | `date`, `timestamp` |
| `EvaluationStatus` | `evaluated`, `insufficient_data`, `invalid_data` |

Şemadaki diğer CHECK değerleri de `common.py`'dedir: `ModuleScope`, `BaselineStatus`,
`DataQualityStatus`, `EventType`, `Audience`.

- `Severity.NORMAL` yalnız ekranda; `ops.Alerts`'e yalnız `WARNING`/`CRITICAL` yazılır.
- Kaynak tablodaki `seed` → `synthetic`, göz ekranındaki `test_screen` → `manual`.
  Orijinal değer `metadata_json.original_source` içinde korunur.

## 3. Ortak ölçüm formatı (`MeasurementDTO`)

Aybala üretir (tablolar + `anomaly.v_measurements`); Ömer geçmiş/snapshot/model hazırlığında
tüketir. Örnekler: `measurement_eye_daily.json`, `measurement_physio_timestamp.json`.

| Alan | Tip | Kural |
|---|---|---|
| `record_id` | metin | Kaynak türüyle tekil: `checkin:12:stress`, `eye:42` |
| `astronaut_id`, `mission_id` | metin | `A007`, `M01` |
| `module` | `MeasurementModule` | |
| `measurement` | metin | Sözlük kodu (`near_acuity`) |
| `value_num` / `value_text` | number / metin | İkisi birden dolu olamaz; geçerli ölçümde biri zorunlu; eksik değer `null`, 0 değil |
| `unit` | metin | `logMAR`, `bpm`… |
| `protocol_version` | metin | **Zorunlu** |
| `measured_date` | `YYYY-MM-DD` | **Her zaman** dolu |
| `measured_at` | ISO-8601 UTC `…Z` | Yalnız gerçek saat biliniyorsa; yapay saat eklenmez |
| `time_precision` | `date`/`timestamp` | `date` ⇒ `measured_at=null`; `timestamp` ⇒ `measured_date` = `measured_at`'in UTC tarihi |
| `mission_day` | tam sayı / `null` | Negatif olabilir (uçuş öncesi) |
| `eye` | `OD`/`OS`/`null` | Göz dışı ölçümde `null`; API'de `NA` yok |
| `source` | `Source` | |
| `valid` | bool | `false` kayıt modele doğrudan girmez |
| `quality_score` | 0–1 / `null` | |
| `session_id` | metin / `null` | |
| `metadata_json` | JSON **nesnesi** / `null` | JSON içeren metin değil |

Sayılar API'de JSON number, Python/DB tarafında `Decimal`. Saat dilimli zaman UTC'ye çevrilir.

## 4. İstek ve hata formatı

- İstek/yanıt modelleri Pydantic, `ContractModel` tabanından: **bilinmeyen alan reddedilir**.
- Başarılı yanıtta zarf yok (`success/data/message` kullanılmaz); nesne doğrudan döner.
- Her yanıtta `X-Trace-Id` başlığı vardır; hatada aynı değer gövdededir ve loga yazılır.

```json
{ "detail": { "code": "VALIDATION_ERROR", "message": "İstek alanlarını kontrol edin.",
  "trace_id": "b6bc5389-179b-4b66-8103-ab430713cbcb",
  "fields": [ { "field": "eye", "code": "INVALID_VALUE", "message": "OD veya OS olmalıdır." } ] } }
```

| HTTP | `code` | Kullanım |
|---|---|---|
| 401 | `UNAUTHORIZED` | Token yok/geçersiz/süresi dolmuş |
| 403 | `FORBIDDEN` | Rol yetkisiz, hesap pasif, gösterim profiline yazma |
| 404 | `NOT_FOUND` | Kayıt yok veya erişim kapsamı dışında |
| 409 | `IDEMPOTENCY_CONFLICT` / `INVALID_STATE_TRANSITION` | Aynı anahtar farklı içerik / geçersiz durum geçişi |
| 412 | `PRECONDITION_FAILED` | Check-in sürümü/ETag eskimiş |
| 422 | `VALIDATION_ERROR` | Alan/veri kuralı geçersiz |
| 500 | `INTERNAL_ERROR` | Beklenmeyen hata |

`fields[].code`: `REQUIRED`, `UNKNOWN_FIELD`, `INVALID_VALUE`. Hata yanıtında SQL, token,
parola, ham model cevabı veya sağlık girdisinin tamamı bulunmaz. Kod `ApiError(status, code)`
fırlatır; repository hataları otomatik çevrilir.

## 5. Kimlik ve yetki (uygulayan: Ömer)

- `POST /api/v1/auth/login` `{email, password}` → `{access_token, token_type:"bearer", expires_in}`.
- JWT HS256, secret `JWT_SECRET` ortam değişkeninden. Claim'ler: `sub`(=`core.Users.user_id`),
  `iat`, `exp`, `iss`, `aud`, `jti`. Refresh token yok; süre bitince yeniden giriş.
- Rol, aktiflik ve astronot bağlantısı her istekte DB'den doğrulanır.
- Dependency'ler `CurrentUser {user_id, role, astronaut_id}` döndürür:
  - `current_user()` — token + aktif hesap
  - `require_active_astronaut()` — ASTRONAUT, kendi profili, `is_display_only=0`
  - `require_ground_control()` — GROUND_CONTROL
- Astronotun veri girişinde `astronaut_id` istemciden **alınmaz**; `CurrentUser`'dan atanır.

## 6. Repository sözleşmesi

Kaynak: `app/repositories/interfaces.py` (imzalar) ve `records.py` (veri modelleri).
Servisler tek nesne alır: `repo = SqlAlchemyRepository(session)`.

| Fonksiyon | Dönüş / davranış |
|---|---|
| `get_user_by_email(email)` | `UserRecord \| None`; e-posta trim + küçük harf |
| `get_user_by_id(user_id)` | `UserRecord \| None` |
| `get_astronaut(astronaut_id)` | `AstronautRecord \| None` (görev başlangıcı dahil) |
| `get_measurements(astronaut_id, start_date, end_date)` | `list[MeasurementDTO]`, `[start, end)` |
| `get_sans_context(astronaut_id, session_id, data_cutoff_at)` | `SansContext \| None` |
| `create_or_get_job(scope, idempotency_key, request_hash, request)` | `CreateJobResult(job, created)`; farklı hash → `IdempotencyConflict` |
| `get_job(job_id, scope)` | `JobRecord \| None` |
| `claim_next_job(lease_seconds)` | `ClaimedJob \| None` (atomik) |
| `renew_job_lease(job_id, lease_token, lease_seconds)` | `bool` |
| `recover_expired_jobs()` | `list[RecoveredJob]` (DB saatine göre) |
| `reschedule_job(job_id, lease_token, delay_seconds, error_code, max_attempts=2)` | Ö3: geçerli lease ile yalnız anomaliyi gecikmeli QUEUED yapar; snapshot korunur |
| `save_input_snapshot(job_id, lease_token, snapshot, input_hash)` | ilk kayıt; aynı hash no-op; farklı → `SnapshotConflict` |
| `save_anomaly_result(result)` | `UUID` |
| `save_sans_analysis(result)` | `int` |
| `update_sans_state(new_state, expected_last_analysis_id)` | `bool` (iyimser eşzamanlılık) |
| `finalize_job(job_id, lease_token, outcome)` | `JobRecord`; sahiplik yoksa `LeaseLost` |
| `create_alert(alert)` | `AlertRecord`; sonuç başına tek alarm |
| `create_notification_event(event)` | `NotificationEventRecord`; konu+hedef başına tek olay |
| `acknowledge_alert(alert_id, user_id)` | İlk onaylayan/zaman korunur |
| `resolve_alert(alert_id, user_id, note)` | Yalnız ACKNOWLEDGED → RESOLVED |
| `record_receipt(event_id, user_id)` | `bool` (ilk kayıt True) |

### 6.1 Eklenen fonksiyonlar (ek açıklamanın tablosunda yoktu)

Ek açıklamadaki endpoint'ler ve akışlar bunlar olmadan yazılamıyor; Ömer onaylamalı:

| Fonksiyon | Neden |
|---|---|
| `request_retry(job_id, scope)` | `POST /analysis/jobs/{id}/retry`; yalnız FAILED iş |
| `list_alerts(statuses, astronaut_id)` | Kule paneli + yeniden bağlanmada aktif alarmlar |
| `list_pending_events(user_id)` | Yeniden bağlanmada alındısı olmayan olaylar |
| `mark_event_sent(event_id)` | `first_sent_at`/`attempts` (teslim kanıtı değil) |

### 6.2 Ek kurallar

- Senkron SQLAlchemy. Repository **commit yapmaz**.
- Listeler tarih/zaman + `record_id` ile kararlı sıralanır.
- Dışarı ORM nesnesi verilmez; `records.py` modelleri (frozen) döner.
- Tekillik ve eşzamanlılık DB UNIQUE/koşullu UPDATE ile sağlanır; "önce bak sonra ekle" yetmez.
- Hatalar: `IdempotencyConflict`, `InvalidStateTransition`, `LeaseLost`, `SnapshotConflict`,
  `NotFound`, `ValidationFailed` (→ 422).
- Süresi dolan lease: anomaly işi `attempts < min(max_attempts, anomaly_auto_retries+1)`
  ise QUEUED (gecikmeli), değilse FAILED (`LEASE_EXPIRED`). SANS işi otomatik tekrar
  edilmez → FAILED (`SANS_RECONCILIATION_REQUIRED`).

Ö3 ayrıntısı: `recover_expired_jobs(max_attempts=2)` opsiyonel limit alır; normal
çağrıdaki iki deneme davranışı korunur. Claim attempts+1 yapar. Lease yenileme ve
finalizasyon süre/token/aktif durum kontrolünü DB saatiyle yapar; süresi dolan lease
canlandırılmaz. Snapshot aynı hash'teyse içerik korunur ama retry'de ANALYZING
geçişi yapılır. SANS SYNCING/ANALYZING lease kurtarması kör POST yerine
FAILED/SANS_RECONCILIATION_REQUIRED üretir. Aynı astronotun SANS claim'leri atomik
olarak sıralanır. Tam teslim ve pipeline arayüzü: `contracts/analysis-worker.md`.

## 7. Session ve transaction düzeni

```text
Transaction 1:  işi sahiplen → girdiyi oku → snapshot kaydet          → COMMIT
Transaction dışında:  model API çağrısı
Transaction 2:  lease'i yeniden doğrula → sonucu kaydet → (SANS) durumu güncelle
                → işi tamamla → alarm/olayları oluştur                → COMMIT
```

Hata olursa ilgili transaction tamamen geri alınır. Senkron DB bloğu kendi thread'inde
Session açıp kapatır; Session thread'ler veya paralel işler arasında paylaşılmaz.

## 8. Analiz API'si (uygulayan: Ömer)

- `POST /api/v1/analysis/jobs`, `module` ile ayrılan iki istek modeli:
  - anomaly: `{module, idempotency_key, module_scope}` — `session_id` gönderilirse 422
  - sans: `{module, idempotency_key, session_id}` — `module_scope` gönderilirse 422
- Yeni iş → `202 {job_id, module, state:"QUEUED", status_url}`. Aynı anahtar + aynı istek → mevcut iş.
- `GET /api/v1/analysis/jobs/{job_id}` · `POST /api/v1/analysis/jobs/{job_id}/retry`
- `request_hash` = normalize `JobRequestData`'nın SHA-256'sı; token ve anahtar hash'e girmez.
- Retry yalnız teknik FAILED işte; snapshot varsa korunur, yoksa hazırlık yeniden yapılır.

## 9. Başlangıç çalışma ayarları

Klinik karar değil; `app/core/config.py`'de ayardır, kodda sabit yazılmaz, `.env` ile değişir.

| Ayar (`config.py`) | Başlangıç |
|---|---:|
| `access_token_seconds` | 3600 |
| `job_lease_seconds` | 120 |
| `job_lease_renew_seconds` | 30 |
| `model_connect_timeout_seconds` | 5 |
| `model_total_timeout_seconds` | 60 |
| `anomaly_auto_retries` | 1 |
| `anomaly_retry_delay_seconds` | 2 |
| `ws_auth_timeout_seconds` | 5 |
| `worker_poll_seconds` | 1 |

**SANS POST'u için otomatik tekrar kapalıdır** ve ayar olarak sunulmaz (tekrar güvenliği teyit edilmedi).

## 10. WebSocket (`/ws/v1/notifications`, uygulayan: Ömer)

- İlk istemci mesajı `{type:"authenticate", access_token}`; 5 sn içinde gelmezse bağlantı kapanır.
- Olay: `{event_id, type, created_at, payload}` — örnek `ws_analysis_completed_sans.json`.
- İstemci teslim yanıtı: `{type:"receipt", event_id}` → `record_receipt`.
- Olay önce DB'ye yazılır, sonra gönderilir; frontend `event_id` ile tekrarları ayıklar.
- `retest_due_day` modelden gelir; backend süre üretmez. Token süresi dolunca bağlantı kapanır.

## 11. Açık konular

1. **`ops.AnalysisJobs.request_json` (A3'te eklendi, Ö2/Ö3 entegrasyonunda kullanılıyor).** Şemada
   `module_scope` / `session_id` için sütun yoktu; `input_snapshot_json` hazırlık bitene kadar
   NULL olduğundan işçi işi sahiplendiğinde neyi analiz edeceğini bilemiyordu. Sütun
   `NVARCHAR(MAX) NOT NULL` + ISJSON; içeriği normalize `JobRequestData`. Mevcut migration
   değiştirilmedi. Ayrıca `IX_AnalysisJobs_state_next_attempt_at` performans indeksi
   eklendi (veri kuralı değil).
2. `metadata_json` için izin verilen anahtar listesi henüz yok (şimdilik `original_source`).
3. `MeasurementDTO.eye` kuralı: göz dışı modülde `null` zorunlu; `sans` modülünde göz dışı
   kayıt (CO₂, baş ağrısı) DTO'ya girecekse `eye=null` olabilir — VIEW tasarımında (A5) netleşecek.
