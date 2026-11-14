# Ö2 — Analiz işi API teslimi

Durum: DTO, servis, router ve A3'e bağlanma noktası hazır. DB'siz HTTP ve servis
testleri test-only transaction repository'siyle çalışır. İncelenen `bachand`
başlangıcı a4156cd; A3 gerçek job repository'si henüz yoktur. Üretimde fake
repository veya bellek kuyruğu kullanılmaz. Bu teslim Ö2'dir; işçi/model çağrısı
Ö3/Ö5/Ö9 kapsamındadır.

## Kullanım

Bütün yollar `/api/v1` altında ve Bearer token gerektirir. Yalnız aktif, gösterim
olmayan astronot kendi işleri için kullanabilir. Kule bu endpoint'leri kullanmaz;
kuleye açılacak paylaşımlı sonuç/alarm akışı ayrı endpoint'lerdedir.
Astronaut_id kullanıcıdan türetilir; istemci role/user_id/astronaut_id gönderemez.

### Yeni iş

`POST /api/v1/analysis/jobs`

```json
{
  "module": "anomaly",
  "idempotency_key": "225dcecb-677f-4925-9570-f412943822bf",
  "module_scope": "combined"
}
```

Anomali kapsamları: physiological, behavioral, sans, combined.

SANS isteği:

```json
{
  "module": "sans",
  "idempotency_key": "225dcecb-677f-4925-9570-f412943822bf",
  "session_id": "S-A007-D074"
}
```

SANS session_id zorunlu metin, en fazla 64 karakter; çevre boşlukları temizlenir.
Anomali session_id, SANS module_scope kabul etmez; ilgisiz/bilinmeyen alanlar 422.
SANS oturumunun varlığı/sahipliği ve veri yeterliliği, SYNCING sırasında kaynak
okunurken ayrıca doğrulanmalıdır; Ö2 henüz A5 kaynak sorgusu/model çağrısı yapmaz.

Yeni iş transaction'ı başarıyla kapandıktan sonra 202:

```json
{
  "job_id": "9f18136c-626d-482e-ae40-d1b04d903be4",
  "module": "sans",
  "state": "QUEUED",
  "status_url": "/api/v1/analysis/jobs/9f18136c-626d-482e-ae40-d1b04d903be4"
}
```

Location başlığı status_url ile aynıdır. Yanıtlar Cache-Control: no-store taşır.
202 analiz tamamlandı anlamına gelmez; yalnız işin kabul edildiğini ifade eder.

### Tekrar anahtarı ve hash

- Tekillik kapsamı: astronaut_id + idempotency_key; module bu kapsamı ayırmaz.
- Aynı anahtar/aynı normalize istek: mevcut job ve güncel durumu, HTTP 200.
- Aynı anahtar/farklı istek: 409 IDEMPOTENCY_CONFLICT.
- Farklı anahtar yeni analizdir. Token/kullanıcı/anahtar canonical hash'e girmez;
  astronot ayrımı repository scope üzerinden yapılır.
- `canonical_request_hash`: JobRequestData.model_dump(mode="json", exclude_none=True),
  sıralı anahtarlar, boşluksuz JSON, ensure_ascii=False; UTF-8 üstünden SHA-256.
  Aybala hash'i yeniden farklı kuralla hesaplamamalı; servisin verdiğini saklamalıdır.
- FAILED işin orijinal POST'unu tekrarlamak işi yeniden çalıştırmaz. Retry ayrı uçtur.

### Durum

`GET /api/v1/analysis/jobs/{job_id}` → 200.

Alanlar: job_id, astronaut_id, module, state, attempts, retry_cycle,
evaluation_status, error_code, anomaly_result_id, sans_analysis_id, created_at,
updated_at. Snapshot, request hash, provider yanıtı veya lease token dışarı verilmez.
SQL UTC DATETIME2 zamanları UTC/Z olarak sunulur. error_code yalnız teknik kod
biçimindedir; ham exception/SQL metni yanıt olamaz.

QUEUED/SYNCING/ANALYZING değerlendirme sonucu değildir. Yetersiz/geçersiz veriyle
COMPLETED işte evaluation_status açıklayıcıdır ve sonuç kimlikleri null kalır.
Teknik hata FAILED'dır; bu API sahte NORMAL sonucu veya alarm üretmez.
Olmayan ve başka astronota ait job aynı 404 NOT_FOUND yanıtını verir.

### Elle retry

`POST /api/v1/analysis/jobs/{job_id}/retry` → 202, aynı job_id ve QUEUED.

Gövde verilmez veya `{}` gönderilir. Yeni snapshot, scope, session veya anahtar
gönderilemez. Yalnız FAILED iş kabul edilir; diğer durumlar 409
INVALID_STATE_TRANSITION. attempts=0, retry_cycle+1; dondurulmuş snapshot/hash ve
orijinal istek korunur. Snapshot henüz oluşmamışsa hazırlık yeniden yapılabilir.
Eşzamanlı retry'de yalnız bir FAILED → QUEUED geçişi başarılı olmalıdır.

SANS retry job'ı yeniden kuyruğa alır; bu endpoint dış POST çağırmaz. Ö3/Ö9 işçisi
SANS tekrar güvenliği teyit edilmeden timeout sonrası kör POST yapmamalı, önce
aynı dondurulmuş isteğin sonucunu uzlaştırmalıdır.

## A3 bağlantısı — Aybala'ya teslim

Ö2'nin ihtiyacı olan üç işlem `JobApiRepository` arayüzünde gruplandı:
create_or_get_job, get_job, request_retry. İmzalar değişmedi; JobRepository bu
arayüzü miras alıp işçi işlemlerini ekler. Fake yalnız Ö2 alt arayüzünü uygular.

Gerçek SqlAlchemyRepository bu üç metodu sağladığında uygulama başlangıcında
AnalysisService etkinleşir. `analysis_transaction` SessionLocal.begin() kullanır:
aynı worker'da Session açılır; başarılı çıkışta commit, hatada rollback ve kapanış.
Repository commit yapmaz. Transaction commit hatası 202'ye dönüşmez.

A3 şu an eksik olduğundan route'lar OpenAPI'de görünür, yetkili çağrı 503
SERVICE_UNAVAILABLE alır. Ortak ErrorCode'a yalnız bu teknik değer eklendi.
Fake üretim uygulamasına bağlanmaz. A3 teslimi/migration uygulaması sonrası
uygulama yeniden başlatılır. Metot varlığı, DB'nin migrate edildiğinin kanıtı değildir.

A3 kabul gereklilikleri:

- UNIQUE(astronaut_id, idempotency_key) ve eşzamanlı INSERT çakışmasını ele alma.
- get_job ve request_retry scope kontrolü; servis ayrıca astronaut_id doğrular.
- Atomik koşullu FAILED → QUEUED; ilk okuma tek başına yarış güvenliği sağlamaz.
- Retry'de snapshot/input_hash/orijinal istek değişmez; lease/eski hata/sonuç alanları
  yeni deneme için tutarlı temizlenir.
- JobRecord.request orijinal normalize isteği geri vermelidir. Ortak sözleşme §11'deki
  request_json saklama konusu hâlâ A3 şema kararıdır; bu teslimde kolon/migration
  eklenmedi ve iş isteği snapshot alanına gizlenmedi.

## Doğrulama

HTTP ve servis testleri: istek ayrımı, scope, 202/200/409/404/422/503, canonical hash,
snapshot koruma, tekrar isteği, transaction başarısızlığında rollback ve concurrent
create/retry. Python lock'lu fake testi gerçek MSSQL yarış kabulünün yerine geçmez.

`tests/integration/test_analysis_db.py` gerçek A3 repository'si ve RUN_DB_TESTS=1
ile aynı anahtar/çakışma/retry/snapshot kontrollerini çalıştırmaya hazırdır.
Mevcut rollback fixture'ını kullanır; migration veya seed oluşturmaz.
Gerçek SQL testleri mevcut ortamda çalıştırılmadı (A3 eksik, önceki pyodbc/SQL
ortam engelleri sürüyor). Ö3 işçi ve harici model entegrasyonu bu teslimde yoktur.
