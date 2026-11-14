# Ö3 — Kalıcı analiz işçisi

14 Kasım 2026. Bu feature branch `feat/auth` commit ceeacea üzerine kuruludur.
Auth/Ö2 önce GitHub'a gönderildi. Ö3, aynı A3 sözleşmesini kullanan işçi çekirdeğini
ve testlerini ekler; ORM/migration/gerçek SQL repository sahibi Aybala'dır.

Güncelleme: bachand A3/A4 (3da69ef) birleştirildi. Dört uyumluluk noktası gerçek
repository'de düzeltildi: recovery imzası, reschedule_job, tüm lease yazımlarında
süre kontrolü ve aynı astronot SANS claim sıralaması. Bu düzeltmeler kullanıcı
isteğiyle yapıldı; merge edilmiş migration'lar değiştirilmedi.

## Uygulanan akış

Her tur önce süresi dolmuş işleri kurtarır, sonra zamanı gelmiş bir işi atomik
sahiplenir. Claim: QUEUED → SYNCING, attempts+1, yeni lease token ve DB saatine
dayalı lease_until. Tek işçi döngüsü işleri sırayla işler; birden çok işçi çalışsa
da tekillik/sahiplik SQL repository tarafından korunmalıdır.

1. Yeni işte pipeline.prepare gerçek girdiyi hazırlar (Ö4/Ö9).
2. JSON-ready girdi/hash kısa transaction'da dondurulur; durum ANALYZING olur.
3. Model değerlendirmesi DB transaction dışında ve toplam timeout ile yürür.
4. Sonuç kaydından önce lease yeniden doğrulanır/yenilenir.
5. Pipeline.persist sonuç/durum/alarm/olayları yazar (Ö6). Worker aynı transaction
   içinde job'ı finalize eder. Hata halinde tüm yazılar rollback edilir.

Her DB işlemi kendi worker thread'inde Session açar/kapatır. Session, canlı ORM
nesnesi veya açık transaction model bekleme süresine taşınmaz.
Snapshot provider'a deepcopy ile verilir; adapter değişikliği kalıcı girdiyi ezmez.
Retry/restart snapshot'ı yeniden hazırlamaz; kayıtlı hash yeniden doğrulanır.

## Lease ve kesinti

- Varsayılan lease 120 sn, yenileme 30 sn, model timeout 60 sn, boş kuyruk yoklama 1 sn.
- Lease yenileme/finalizasyon token, aktif durum ve süreyi DB saatiyle kontrol eder.
- Yenileme başarısızsa bekleyen çağrı iptal edilmeye çalışılır; geç yanıt yazılmaz.
- Cancellation dış API'nin isteği almadığını kanıtlamaz.
- Uygulama kapanınca yeni claim durur ve aktif coroutine iptal edilir; kayıtlı iş
  lease'iyle kalır. Sonraki başlangıç/döngüde süre dolunca kurtarılır.
- DB kesintisinde log yalnız güvenli kod/job_id içerir; kalıcı iş kaybolmaz. Commit
  sonucu belirsizse ikinci bir korumasız sonuç yazılmaz; lease kurtarması beklenir.

## Retry kuralları

Anomali için yalnız evaluate aşamasındaki TransientModelError/timeout tekrar edilir.
Bir otomatik tekrar, toplam en fazla iki claim/deneme vardır. Retry aynı işte,
aynı snapshot/hash ile QUEUED olur; next_attempt_at DB saati+gecikme (varsayılan 2 sn).
Bekleme bellekte uyuyan bir job olarak tutulmaz; sonraki tur zamanı gelince sahiplenir.
Geçici hata iki kez sürerse FAILED; elle retry Ö2 endpoint'inden aynı girdiyi kullanır.
automatic_retries yalnız 0 veya 1 olabilir; üst limit repository kurtarmasına da verilir.

PermanentModelError, InvalidModelOutput, hazırlık/snapshot hatası ve persistence
hatası otomatik model tekrarına dönüşmez. Teknik hata NORMAL/sağlık alarmı üretmez.
Yetersiz/geçersiz veri sonucu COMPLETED olabilir; pipeline bu durumda sonuç FK'sı
olmayan, açıklamalı outcome döndürmelidir. Veri yeterlilik eşiğini worker uydurmaz.

SANS için:

- İlk snapshot henüz yokken prepare → evaluate yapılabilir.
- Timeout/geçici bağlantı hatasında otomatik POST retry yapılmaz;
  FAILED/SANS_RECONCILIATION_REQUIRED kaydedilir.
- ANALYZING aşamasında lease süresi dolarsa recovery de aynı güvenli sonucu üretir.
- Elle retry attempts/error_code'u sıfırlayabildiğinden, işçi **kayıtlı SANS snapshot'ı
  gördüğü her tekrar çağrısında** evaluate yerine reconcile kullanır.
- reconcile adaptörü yoksa tekrar FAILED/SANS_RECONCILIATION_REQUIRED; yeni POST yok.
- reconcile mevcut request_id sonucunu sorgulamalı/uzlaştırmalı veya doğrulanmış
  idempotency sözleşmesine dayanmalıdır. Gerçek SANS sözleşmesi henüz teyit edilmedi.
- Aynı astronotun SANS işleri SQL claim katmanında sıralı tutulur.

## Pipeline bağlantısı (Ö4/Ö5/Ö6/Ö9)

`AnalysisPipeline` arayüzü:

| Metot | Tip | Sorumluluk |
|---|---|---|
| prepare(job) | async → JSON-ready dict | Gerçek girdi/snapshot hazırlama; dış model çağırmaz |
| evaluate(job, snapshot) | async → doğrulanmış sonuç nesnesi | Model/adaptör; açık DB transaction yok |
| persist(repo, job, result) | sync → JobOutcome | Aynı Session ile sonuç/durum/alarm/olay; commit yok |
| reconcile(job, snapshot) | async → doğrulanmış mevcut sonuç | SANS tekrarlarında güvenli kaynak sonucu uzlaştırma |

Persist yalnız COMPLETED outcome döndürür. evaluated sonucunda modüle uygun tek
sonuç FK'sı zorunludur. insufficient_data/invalid_data için iki sonuç FK'sı da null
ve outcome açıklaması zorunludur. Worker bu zarfı finalize öncesinde doğrular.
Klinik model çıktı şeması/ham yanıt metadata'sı Ö5/Ö9, atomik klinik yazım Ö6'dadır.

Uygulama başlangıcından önce `app.state.analysis_pipelines` içine anomaly ve sans
adaptörleri yerleştirilir. prepare/evaluate async, persist sync olmalıdır.
FastAPI lifespan A3 metotlarını ve iki pipeline'ı doğrular. Eksikse
app.state.analysis_worker=None kalır ve background task açılmaz. Test pipeline'ı
ve fake repository üretim başlangıcına bağlanmaz. Tek API worker ayarı korunur.

## Aybala'ya A3 ek teslimi

Yeni metot: reschedule_job(job_id, lease_token, delay_seconds, error_code,
max_attempts=2). Aynı transaction içinde geçerli lease, anomaly modülü ve kalan
deneme hakkı kontrol edilir; lease temizlenir, next_attempt_at ayarlanır. Snapshot,
input_hash ve orijinal istek korunur. Uygun değilse InvalidStateTransition;
sahiplik/süre yoksa LeaseLost. Repository commit yapmaz.

recover_expired_jobs artık opsiyonel max_attempts alır (varsayılan 2). Mevcut
çağrılarda en fazla iki deneme korunur; daha düşük konfigürasyon limiti aşılmaz.
SANS işi SYNCING veya ANALYZING aşamasında da otomatik kuyruğa alınmaz;
FAILED/SANS_RECONCILIATION_REQUIRED olur. Recovery süre sınırında <= kontrolü yapar.

Claim attempts+1 yapar ve tek işi iki işçiye vermez. Aynı astronotun SANS işleri
için yalnız ayrı satırlara UPDLOCK koymak yeterli olmayabilir; kontrol ve sahiplenme
aynı astronot kapsamında atomik/sıralı olmalıdır. Gerçek A3 claim artık kısa
transaction'a ait global bir sp_getapplock kilidi ve aktif SANS NOT EXISTS filtresi
kullanır. Böylece iki claim arasındaki kontrol/sahiplenme yarışı kapanır. Kilit yalnız
claim transaction'ı boyunca tutulur; provider bekleme süresinde tutulmaz. Çekişmede
beklemeden boş claim döner; beklenmeyen kilit hatası rollback için dışarı verilir.
DB public rolü kullanılır; yönetici veya yeni DDL yetkisi istenmez. Bağlantıda
NOCOUNT açılmaz, sonraki UPDATE rowcount kontrolleri korunur.
[SQL Server kilit sözleşmesi](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-getapplock-transact-sql).

save_input_snapshot aynı hash'te girdiyi ezmez ama retry SYNCING → ANALYZING geçişini
yapar. finalize_job son yazımda süre/token/aktif state kontrolünü yeniden uygular.
Ö2'de belgelenen request_json, A3 migration 0004 içinde mevcuttur ve kullanılır;
uyumluluk düzeltmesinde kolon veya migration eklenmedi.

## Doğrulama ve sınır

Testler: başarı, gecikmeli tek tekrar, retry tükenmesi, kalıcı/bozuk çıktı,
snapshot/hash koruması, provider mutasyonu, lease kaybı, heartbeat, restart,
shutdown, iki işçi tek claim, SANS sıralaması/uzlaştırması ve atomik rollback.
Python lock kullanan fake, gerçek SQL yarış/izin kabulünün yerine geçmez.
`tests/integration/test_worker_db.py` A3 + RUN_DB_TESTS=1 ile gerçek claim,
snapshot, yeniden kuyruğa alma, lease süresi ve kurtarma kontrollerini içerir.

Bu ortamda gerçek DB testleri atlanıyor: önceki pyodbc/SQL ortam engelleri sürüyor.
A3 kodu mevcut; pipeline adaptörleri henüz bağlı değil. Bu nedenle üretim worker'ı
kapalıdır. SQL guard/imza testleri gerçek repository metotlarını ODBC'siz kontrol
eder; canlı SQL kilit/yetki kabulünün yerine geçmez. Ek SQL kabul testleri iki ayrı
connection'da claim kilidi ve aynı astronot SANS sıralamasını doğrulamaya hazırdır.
Ö4 geçmiş/eşik hesabı, Ö5 sağlayıcı ve Ö6 klinik sonuç/alarm işlemleri bu çekirdeğin
üstüne bağlanacaktır; bunların yerine sahte klinik sonuç oluşturulmadı.
