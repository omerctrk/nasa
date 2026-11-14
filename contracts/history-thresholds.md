# Ö4 — A5 geçmiş okuma, eşik karşılaştırması ve snapshot

A5 teslimi `bc78c35`, bu feature branch'e birleştirildi. Ö4 gerçek
`SqlAlchemyRepository.get_astronaut/get_measurements` arayüzüne bağlıdır.
Yeni SQL tablo/VIEW/migration oluşturulmadı. Yeni Python bağımlılığı yoktur.
SANS API paketi ayrı Ö9 akışıdır; SANS uçuş öncesi temel oturumları bu anomali
penceresiyle kesilmez.

## Kod ve bağlantı

- `app/schemas/history.py`: sürümlü HistoryPolicy/ThresholdPolicy ve kesin bağlamlar.
- `app/services/thresholds.py`: Decimal karşılaştırma ve eşik sapması.
- `app/services/history.py`: HistoryPreparer.prepare(job), 74/7 gün ve model girdisi.
- `app/core/history_runtime.py`: A5 repository factory'si ve uygulama kaydı.
- `app/core/snapshots.py`: Ö3 ve Ö4'ün kullandığı ortak canonical JSON hash'i.
- `config/history-policy.json`, `config/thresholds.json`: secret içermeyen ayarlar.

main.py `app.state.history_preparer` oluşturur. Gelecek anomali pipeline'ı async
prepare adımında `await app.state.history_preparer.prepare(job)` çağırır.
Ö3 bu dict'i kalıcı snapshot/hash olarak kaydeder. Ö5 evaluate adımı yalnız
snapshot["model_input"] kısmını modele gönderir. Persist/result/alarm Ö6'dadır.
Bu nedenle iki model pipeline'ı tamamlanmadan üretim worker'ı hâlâ başlamaz.

Kaynaklar aynı worker thread'de açılan kısa read transaction içinde okunup kopyalanır;
Session kapanınca özet hesaplanır. Özetleme veya model beklerken açık Session taşınmaz.
A5 get_measurements yalnız tanımlı DTO döndürür; eksik A6 sözlük kaydı MissingDefinition
hatasıdır, sahte boş ölçüm veya sıfır üretilmez.

## Takvim ve veri kesimi

Varsayılan referans gerçek UTC günüdür. 74 gün: [referans-73 gün, referans+1 gün).
Son 7 gün: [referans-6 gün, referans+1 gün). Referans gününe ait timestamp kayıtları
okuma başlangıcından sonraysa dışlanır. Gün hassasiyetli kayıtların saati null kalır.

Demo görev takvimi gelecekte olabilir. `ANOMALY_REFERENCE_DATE=YYYY-MM-DD` açıkça
verilirse gün penceresi bu tarihe göre seçilir; sahte 00:00/23:59 timestamp üretilmez.
Bu modda measurement_timestamp_cutoff null ve reference_mode explicit_date olur.
data_cutoff_at yine gerçek okuma başlangıcıdır. Varsayılan boş ayar demo tarihini
kendiliğinden seçmez. Bu ayar göz dışı sentetik senaryonun başlangıç/bitiş kararı
veya klinik veri yeterlilik şartı değildir.

source_read.started_at/completed_at saklanır. READ COMMITTED okuması global atomik
snapshot gibi sunulmaz; kayıtların gerçek okunmuş değerleri sonradan dondurulur.
Gerçek timestamp ile simüle takvim günü arasındaki ayrım snapshot'ta açıkça belirtilir.

## Özellik ve kalite politikası

Policy sürümü ve tam kullanılan kurallar snapshot'a kopyalanır; semantic JSON hash'i
de saklanır. Aynı version metniyle dosya değişse bile içerik hash'i farkı görünür.
Her yeni hazırlık dosyaları yeniden okur; retry mevcut kalıcı snapshot'ı kullanır.

Başlangıç policy'si tanımları teyitli beş fizyolojik ve üç göz ölçümünü içerir.
Birim/protokol eşleşmesi tamdır (ör. BPM ile bpm otomatik eşlenmez). Diğer özellikler
tanım ve kalite kararı verilene kadar definition_not_configured olarak dışlanır.
Davranış ölçeklerinin yönü/formülü ve PVT speed bu çalışmada uydurulmadı.
Policy'ye yeni özellik eklenmesi açık definition_confirmed=true beyanı gerektirir.

valid=false kayıtlar dışlanır. Sayısal quality_score taşıyan kaynak için
minimum_quality_score onaylanmamışsa quality_policy_not_configured olur; veri modele
girmez. Onaylı minimum verilmiş ama puan yoksa quality_score_missing, altındaysa
low_quality olur. Default dosyada kalite sınırı uydurulmadı. A5 göz kayıtlarında
valid=true sabit olduğu için, göz kalite kuralı gelene kadar bu kayıtlar anomali
girdisinde bekler; ham göz verisi ve ayrı SANS API akışı bundan etkilenmez.

WHO-5/PHQ-2/GAD-2, PVT speed doğrudan engellenir. Arbitrary metadata, genetik profil,
evaluation etiketleri ve serbest metinler model girdisine taşınmaz. Metadata'dan yalnız
bilinen original_source kodu korunur. weekly/private ölçümlerin değerleri veya
referansları model girdisine/özete/ayrıntıya eklenmez.

## Özet, güncel değer ve eksikler

Gruplar: module + measurement + unit + protocol_version + eye. OD/OS ayrı tutulur.
Özet count, gözlem olan gün sayısı, ilk/son tarih, min/max/ortalama/medyan,
population stddev ve ilk/son gözlem günü ortalamaları arasındaki farkı içerir.
Bu fark kötüleşme yorumu veya anomali puanı değildir. Tek gözlem gününde trend null;
tek kayıtta stddev null kalır. Eksik ölçüm sıfır yapılmaz.

days_without_observations, takvimde kayıt olmayan günleri sayar; haftalık testi günlük
zorunlu ölçüm gibi eksik saymaz. Beklenen sıklık/yeterlilik politikası seçilmedi.
Her grubun en son gözlem günündeki tüm kayıtlar current_measurements olur;
latest_age_days güncelliği açıklar. Aynı gün birden çok gerçek ölçüm sessizce ezilmez.
Aynı record_id aynı içerikte tek sayılır, çelişkili içerikte hazırlık durur.

Son 7 gün ayrıntısı ve güncel kayıtlar özetin alt kümesidir. overlap alanında bu açıkça
yazılır; independent_sample_sets=false ve kayıt referansları bulunur. Model yalnız
eşik aşanları değil, normal aralıktaki güncel ölçümleri de görür.

## Eşikler

thresholds.json başlangıçta version ve boş rules içerir; klinik sayılar yoktur.
Her kural module/measurement/unit/protocol_version/eye bağlamına aittir. En az bir
alt/üst sınır gerekir; ters aralık, duplicate kural, NaN/Infinity ve duplicate JSON
anahtarları reddedilir. Göz kuralları OD ve OS için ayrı tanımlanır; wildcard yoktur.

Kapalı aralık: alt/üst sınıra eşitlik within_range. Sapmada signed value_minus_bound
ve absolute_deviation hesaplanır. Limit/sapma kanıtları Decimal metniyle korunur;
sayısal skor veya yüzde üretilmez. Eksik eşik not_configured, uyumsuz bağlam
eye/unit/protocol_mismatch olur; breached=null kalır. Bilinmeyen durum normal değildir.
Yalnız uygun kaliteli güncel girdiler karşılaştırılır; valid_threshold_breach_record_ids
Ö5'in minimum watch kuralında kullanılacak referansları verir. Ö4 alarm üretmez.

## Snapshot içeriği

history_records özetin dayandığı bütün uygun gerçek değerleri/kimlikleri dondurur.
Modelin alacağı model_input yalnız özet, güncel kayıtlar, 7 günlük ayrıntı,
eşik bulguları ve örtüşme bilgisidir; 74 günlük ham seri ayrıca gönderilmez.
JSON number alanlarına ek value_num_exact/statistics_exact, Decimal değerlerinin
float dönüşümünde denetim hassasiyetini korur. Synthetic kaynak açıkça belirtilir.
excluded_records kalite/tanım nedenleriyle yerel denetim içindir; model_input'a girmez.

sufficiency.status=not_configured, baseline_status=null kalır; 74 kayıt bulunması
otomatik ready kararı değildir. Veri yeterlilik politikası ayrıca uygulanmadan Ö5/Ö6
bu girdiye klinik başarı/ready statüsü atamamalıdır.

## Test ve kalan teslimler

Testler A5'in gerçek DTO mapper'ı ve get_measurements sorgu parametreleriyle
hazırlığı, pencereleri, Decimal eşikleri, kalite/mahremiyet filtrelerini ve Ö3 retry
boyunca kaynak/policy değişse de snapshot'ın korunmasını doğrular.
tests/integration/test_history_db.py gerçek SQL VIEW üzerinden okuma ve kaynak
güncellemesi sonrası eski snapshot'ın değişmemesini RUN_DB_TESTS=1 ile sınar.
Yerel ODBC/SQL engeli nedeniyle bu gerçek DB grubu henüz çalıştırılamadı.

A6 sözlük/seed, gerçek sayısal eşikler/kalite kuralları, asgari veri yeterlilik
politikası ve Ö5/Ö6/Ö9 adaptörleri ayrı teslimlerdir. Mevcut migration'lar değiştirilmedi.
