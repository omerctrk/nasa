# Davranışsal ve Refleks Modülü – Frontend Arayüz Belgesi

Nov 14, 2026 · @Şule · Sürüm 2

> Uç noktalar, alanlar ve hata kuralları için tek doğru kaynak **`api-contract.md`** (koddan doğrulandı).
> Soru ve seçenek metinleri için tek doğru kaynak **`contracts/behavioral/questions.json`**.
> Bu belge ikisiyle çelişirse onlar geçerlidir.

## Özet

Bu belge, davranışsal ve refleks modülünün ekranlarını yazacak frontend ekibi içindir. Backend uç noktaları bellek içi bir geliştirme sunucusunda çalışıyor; ekranlar şimdiden gerçek API şekilleriyle denenebilir (bkz. "API çağrıları").

**Frontend'in işi:** soruları göstermek, testleri oynatmak, ham sonuçları toplayıp backend'e göndermek, backend'in döndüğü puanları ve geçmişi göstermek.

**Frontend'in işi olmayan:** puan hesaplamak, "geç / erken" kararı vermek, yeşil/sarı/kırmızı renk üretmek, tarih veya görev günü hesaplamak, veri saklamak.

### Alınan kararlar

| Konu | Karar |
| --- | --- |
| Modülün rengi | Davranış modülü **renk üretmez**. İnsan modelindeki "zihin" rengi anomali modelinden gelir. Bu ekranlarda durum rozeti yok. |
| "Bugün" | **UTC** tarihine göre. Bugünün tarihi ve görev günü `GET /today` cevabından gelir. |
| Test gönderimi | Frontend **ham denemeleri** gönderir; ölçümleri backend hesaplar. |
| Görev günü | Demoda bugün **75. gün** (fırlatma 1 Eylül 2026 = 1. gün); backend'den gelir, frontend hesaplamaz. |
| API adresi | Tüm çağrılar `/api/v1/behavioral/...` altında. |
| Dil | Tüm ekran metinleri **İngilizce**. |

### Kapsam sırası

1. Check-in formu
2. Tepki testi (PVT)
3. Zihinsel döndürme testi
4. Haftalık ölçek formu
5. Bugün sekmesi ve geçmiş grafikleri

## Ekran haritası

Modül tek sayfada dört sekmeden oluşur. Astronot Bugün sekmesindeki görev butonlarıyla check-in ve testlere gider; her test aynı beş adımı izler.

&#91;embedded content: Ekran haritası · 4 sekme ve ortak test akışı\]

Haftalık form, Check-in sekmesinin altında ikinci bir bölüm olarak durur ve yalnızca `weekly_due: true` olduğunda Bugün sekmesinde hatırlatılır.

## Genel arayüz kuralları

- **Ortak bileşenler kullanılır:** `Card`, `Button`, `PageHeader`, `FormField` vb. `components/ui/` klasöründen gelir; modül içinde yeniden yazılmaz.
- **Puan hesaplanmaz:** ekranda gösterilen her sayı backend cevabından gelir. Tek istisna testin kendi içinde gösterdiği anlık süre ("287 ms").
- **Renk rozeti yok:** bu modülde yeşil/sarı/kırmızı durum gösterilmez. Grafiklerde nötr renkler kullanılır.
- **Tarih:** "bugün" UTC günüdür. Ekranda yerel saat değil, "Mission day 75 · 14 Nov (UTC)" biçimi kullanılır.
- **Simüle veri etiketi:** seed verisinden gelen kayıtlar (`source: "seed"`) grafiklerde küçük bir "Simulated data" etiketiyle gösterilir.
- **Gizlilik:** haftalık ölçek puanları (WHO-5, PHQ-2, GAD-2) yalnızca bu modülün ekranlarında, yalnızca astronota gösterilir. Genel panoya veya kule ekranına konmaz.
- **Dil:** tüm metinler İngilizce. Soru, seçenek ve ölçek metinleri `contracts/behavioral/questions.json` dosyasından okunur; ölçek maddeleri **resmi İngilizce** metinlerdir ve değiştirilmez, kısaltılmaz, yeniden çevrilmez.
- **Erişilebilirlik:** gerçek `<button>` ve `<label>` kullanılır; test butonları klavyeyle de kullanılabilir; dokunma alanları en az 44 px.
- **Test ekranları sadedir:** test sırasında menü, bildirim, animasyon veya başka bir şey ekranda olmaz. Tam ekran butonu sunulur.

## Bugün sekmesi

Modül açıldığında ilk görülen sekme. Amacı: astronota **bugün ne yapması gerektiğini** ve son değerlerini göstermek.

### İçerik (yukarıdan aşağı)

1. **Başlık:** "Behavior & Reflexes · Mission day 75" (`mission_day` `GET /today`'den)
2. **Bugünkü görevler listesi** (her biri bir satır, sağında buton):

| Görev | Ne zaman görünür (`GET /today`) | Yapılmadıysa | Yapıldıysa |
| --- | --- | --- | --- |
| Daily check-in | Her gün | "Do check-in" butonu | ✓ ve "Edit" linki (`checkin.done: true`) |
| Reaction test (3 min) | `tests_due` içinde `"pvt"` | "Start test" butonu | ✓ (`tests_done` içinde `"pvt"`) |
| Mental rotation | `tests_due` içinde `"rotation"` | "Start test" butonu | ✓ (`tests_done` içinde `"rotation"`) |
| Weekly assessment | `weekly_due: true` | "Weekly assessment is due today" | `weekly_next_date` ile "Next: 16 Nov" |

Testler haftada iki gün yapılır (görev günü % 7 ∈ {1, 4} → Salı ve Cuma); hangi günün test günü olduğunu **frontend hesaplamaz**, `tests_due` alanına bakar.

3. **Hatırlatma** (yalnızca gerekiyorsa): `signals.checkin_missing: true` ise sakin bir bilgi satırı: "You haven't done a check-in for 2 days. A quick one takes about a minute." Sayı `signals.consecutive_missed_checkin_days` alanından gelir. `signals.tests_missing: true` ise benzer şekilde "No tests recorded on the last test days." Kırmızı veya alarm görünümü kullanılmaz.
4. **Son değerler kartı:** ruh hali indeksi, uyku süresi, son PVT ortalaması ve dikkat kaybı, son döndürme doğruluğu. Her birinin yanında son 7 günün küçük bir çizgi grafiği (sparkline). Renk yok.
5. **Destek notu** (yalnızca gerekiyorsa): son haftalık değerlendirmenin cevabında `support_note: true` ise sakin bir bilgi kutusu; metin `questions.json` → `weekly_assessment.support_note`:
   "Your latest weekly assessment suggests it may help to talk with the psychological support team. This is a screening result, not a diagnosis."
   Kırmızı veya alarm görünümü kullanılmaz.

### Veri

- Görevler, görev günü ve hatırlatmalar: **tek istek** `GET /behavioral/today`. Frontend tarih hesabı yapmaz.
- Son değerler ve sparkline: `GET /behavioral/checkins?limit=7` ve `GET /behavioral/cognitive-tests?limit=20`.
- Destek notu: `GET /behavioral/weekly-assessments?limit=1` → `items[0].support_note`.

## Günlük check-in formu

Tek sayfa, yaklaşık 1 dakikada doldurulur. Aynı gün tekrar açılırsa önceki cevaplarla dolu gelir ve güncellenir.

### Alanlar

Etiket ve seçenek metinleri `questions.json` → `daily_checkin.questions` dizisinden okunur; aşağıdaki tablo özet.

| Alan (API anahtarı) | Etiket | Kontrol | Değer | Varsayılan |
| --- | --- | --- | --- | --- |
| `mood` | Overall, how do you feel today? | Kaydırıcı, uçlarda "Very bad" – "Very good" | 0–10 tam sayı | Seçilmemiş |
| `energy` | How is your energy level today? | Kaydırıcı, "Very low" – "Very high" | 0–10 | Seçilmemiş |
| `stress` | How stressed do you feel today? | Kaydırıcı, "Not at all" – "Extremely" | 0–10 | Seçilmemiş |
| `loneliness` | Did you feel lonely? | 5 seçenekli buton grubu: Not at all · A little · Moderately · Quite a bit · Extremely | 0–4 | Seçilmemiş |
| `crew_relation` | How are your relations with the crew? | 5 seçenekli: Very poor · Poor · Neutral · Good · Very good | 0–4 | Seçilmemiş |
| `bed_time` | What time did you go to bed last night? | Saat seçici, `HH:MM` | `"23:40"` | – |
| `wake_time` | What time did you wake up this morning? | Saat seçici, `HH:MM` | `"06:10"` | – |
| `sleep_quality` | How would you rate the quality of your sleep? | 5 buton: Very poor · Poor · Fair · Good · Very good | 1–5 | Seçilmemiş |
| `symptoms` | Do you have any of the following today? | Çoklu seçim çipleri + "None" | Kod listesi | Boş liste |

**Kaydırıcılar başlangıçta seçilmemiş** görünür (ortada durmaz); astronot dokunmadan 5 kaydedilmesin diye.

Saatler **`HH:MM`** gönderilir (saniye yok, 24 saat biçimi, başta sıfır: `07:30`, `7:30` değil).

### Belirti çipleri

Kod ve etiketler `questions.json` → `symptom_codes` dizisinden, bu sırayla:

| Kod | Etiket |
| --- | --- |
| `headache` | Headache |
| `fatigue` | Fatigue |
| `nausea` | Nausea |
| `dizziness` | Dizziness |
| `blurred_vision` | Blurred vision |
| `eye_pressure` | Eye pressure |
| `back_pain` | Back pain |
| `cough` | Cough |
| `shortness_of_breath` | Shortness of breath |
| `sore_throat` | Sore throat |
| `skin_lesion` | Skin lesion (rash / cold sore) |
| `digestive_issue` | Digestive issue |

"None" (`questions.json` → `none_label`) seçilince diğer çipler temizlenir; başka bir çip seçilince "None" kalkar. "None" bir kod değildir: gönderimde `symptoms: []` olur. Aynı kod iki kez gönderilmez (backend 422 döner).

### Doğrulama (göndermeden önce)

- Tüm alanlar zorunlu (belirtiler hariç). Eksik alan varsa "Submit" pasif kalır ve eksik alan işaretlenir.
- Uyku süresi önizlemesi: yatış ve kalkış seçilince altında "About 6 h 30 min of sleep" yazılır. Bu yalnızca bilgi amaçlıdır; kaydedilen değer backend'in hesabıdır. Gece yarısını geçen uyku doğru gösterilmeli (23:30 → 06:45 = 7 h 15 min).
- 2 saatten kısa veya 14 saatten uzun uyku görünürse onay sorulur: "Your sleep looks like 15 hours. Is that right?"
- Gelecek bir tarihe check-in gönderilmez (backend 422 `future_date`).

### Gönderim sonrası

Başarılı kayıtta kısa bir onay ("Check-in saved") ve Bugün sekmesine dönüş. Backend'in döndüğü `mood_index` ve `sleep_hours` Bugün sekmesinde görünür.

## Tepki testi (PVT) ekranı

Modülün en hassas ekranı. Amaç: ekrana rastgele zamanlarda gelen uyarıcıya tepki süresini **milisaniye doğruluğunda** ölçmek. Frontend süreleri ölçer ve listeler; geri kalan her şeyi backend yapar.

### Ekran durumları

| Durum | Ekranda | Geçiş |
| --- | --- | --- |
| 1. Talimat | "When a number appears in the middle of the screen, tap or press the space bar as fast as you can. Don't press before the number appears. The test takes 3 minutes." + Full screen + Start | Start → 2 |
| 2. Alıştırma | 3 deneme; üstte "Practice" etiketi; kaydedilmez | 3 deneme bitince → 3 |
| 3. Hazır | "Test starting" + 3-2-1 geri sayım | → 4 |
| 4. Test | Sade, koyu zemin; ortada sayı alanı. Üstte küçük kalan süre çubuğu | 180 sn dolunca → 5 |
| 5. Gönderiliyor | "Saving results…" | Cevap gelince → 6 |
| 6. Sonuç | Backend'den gelen ortalama, medyan, dikkat kaybı, erken basma | Done → Bugün sekmesi |
| Yarıda kaldı | "The test was interrupted. Please try again." + Try again | → 1 |

### Bir denemenin döngüsü (durum 4 içinde)

1. **Bekleme:** boş ekran. Bekleme süresi **1.000–4.000 ms arası rastgele** (tekdüze dağılım).
2. **Uyarıcı:** ortada milisaniye sayacı 0'dan saymaya başlar (örn. büyük, sarı rakamlar). Göründüğü an `shownAt` kaydedilir.
3. **Tepki:** dokunma, tıklama veya boşluk tuşu. Sayaç durur, süre 1 saniye ekranda kalır.
4. Yeni bekleme başlar. 3 dakikada yaklaşık 60 deneme oluşur (backend en çok 200 deneme kabul eder).

| Olay | Kaydedilen deneme |
| --- | --- |
| Uyarıcıdan sonra basıldı | `{"i": n, "delay_ms": 2340, "rt_ms": 287, "false_start": false}` |
| Uyarıcıdan **önce** basıldı | `{"i": n, "delay_ms": 2340, "rt_ms": null, "false_start": true}`; ekranda kısa "Too early" yazısı, sonra yeni bekleme |
| 30 sn basılmadı | `{"i": n, "delay_ms": 2340, "rt_ms": null, "false_start": false}`; yeni bekleme |

- `rt_ms` anahtarı her denemede **bulunur**; değer yoksa `null` gönderilir (anahtar atlanmaz).
- `false_start: true` olan denemede `rt_ms` **her zaman `null`**.
- `i` her denemede benzersizdir (1, 2, 3, …).
- 100 ms altındaki tepkiler de **olduğu gibi** gönderilir; erken basma sayıp saymamak backend'in kararıdır.

### Zamanlama kuralları (çok önemli)

- Süre ölçümü **yalnızca `performance.now()`** ile; `Date.now()` kullanılmaz.
- `shownAt`, uyarıcının ekrana çizildiği karede alınır: uyarıcıyı görünür yapan `requestAnimationFrame` geri çağırmasının içinde.
- Basış, React state güncellemesini beklemeden **doğrudan DOM olayında** (`pointerdown` / `keydown`) yakalanır ve süre hemen hesaplanır. `click` yerine `pointerdown` kullanılır (daha az gecikme).
- Uyarıcı sayacının güncellenmesi ölçümü etkilememeli; sayaç görüntüsü için `ref` ile doğrudan metin güncellemesi tercih edilir.
- Test sırasında sayfa görünürlüğü kaybolursa (`visibilitychange`) test **yarıda kalmış** sayılır, hiçbir şey gönderilmez.
- Pencere boyutu değişimi veya tam ekrandan çıkma testi durdurmaz.

### Gönderim

180 sn dolunca tüm denemeler tek istekte gönderilir (aşağıda örnek). Gövdede `started_at` ve `finished_at` (saat dilimli ISO 8601, `new Date().toISOString()`) bulunur. `device` alanına tarayıcı ve giriş türü yazılır (en çok 64 karakter): örn. `"chrome-desktop-keyboard"` veya `"safari-tablet-touch"`.

## Zihinsel döndürme testi ekranı

Yan yana iki şekil gösterilir; astronot sağdakinin soldakinin **döndürülmüş hali mi (Same)** yoksa **ayna görüntüsü mü (Mirror)** olduğunu seçer. Yaklaşık 2 dakika.\
Frontendin çıktısına bakıp sonradan değiştirebiliriz bu bölümü

### Şekiller

- **4 farklı asimetrik 2B şekil**, SVG olarak çizilir. Simetri ekseni olmamalı (ayna görüntüsü döndürmeyle elde edilememeli). Öneri: 5–6 kareden oluşan "F", "R", "L" benzeri blok şekiller. Harf veya rakam kullanılmaz.
- Şekil kimlikleri: `s1`, `s2`, `s3`, `s4`.
- **Ayna:** şeklin yatay eksende yansıtılmışı (`scale(-1, 1)`), sonra döndürülmüşü.
- Sol şekil her zaman 0° ve düz. Sağ şekil 0°, 60°, 120° veya 180° döndürülür.
- İki şekil aynı boyutta, aralarında yeterli boşluk; döndürülünce kesilmemeli.

### Deneme listesi

4 açı × 2 koşul (aynı/ayna) × 2 tekrar = **16 deneme** (backend en çok 16 kabul eder), karışık sırada. Her denemede şekil rastgele seçilir; açı ve koşul dağılımı her oturumda aynı kalır.

### Ekran durumları

| Durum | Ekranda |
| --- | --- |
| 1. Talimat | Örnek görsel: bir "same" ve bir "mirror" çifti, açıklamalı |
| 2. Alıştırma | 2 deneme, **geri bildirimli** ("Correct" / "Not quite, this one was a mirror image"); kaydedilmez |
| 3. Test | 16 deneme. Altında iki büyük buton: **Same** (←) ve **Mirror** (→). Test sırasında doğru/yanlış gösterilmez |
| 4. Gönderiliyor / Sonuç | Backend'den gelen doğruluk ve ortalama süre |

- Deneme başına **en fazla 7 sn**; süre dolarsa cevapsız sayılır ve bir sonrakine geçilir.
- Denemeler arasında **500 ms** boş ekran.
- Süre, şekillerin ekrana çizildiği andan butona basışa kadar `performance.now()` ile ölçülür.
- Sekme değişimi testi yarıda bırakır (PVT ile aynı kural).

### Kaydedilen deneme

```json
{"i": 1, "shape": "s3", "angle": 120, "mirror": true, "answer": "mirror", "rt_ms": 1840}
```

- `answer`: `"same"`, `"mirror"` veya süre dolduysa `null`. Süre dolduysa `rt_ms` de `null`; cevap varsa `rt_ms` dolu.
- `answer` ve `rt_ms` anahtarları her denemede bulunur (değer yoksa `null`).
- Doğru/yanlışı frontend hesaplamaz; backend `mirror` ile `answer`'ı karşılaştırır.

## Haftalık ölçek formu

Haftada bir doldurulur; Bugün sekmesi `weekly_due: true` olunca hatırlatır. Yaklaşık 2 dakika.

### Yapı

1. **Açıklama:** her ölçeğin `instructions` metni ve `questions.json` → `weekly_assessment.privacy_note`:
   "Your answers stay with you by default. They are not used by the anomaly model, the language model or the alert system."
2. **WHO-5:** 5 madde, her biri 6 seçenekli (0–5). Anahtarlar `who5_1` … `who5_5`.
3. **PHQ-2:** 2 madde, her biri 4 seçenekli (0–3). Anahtarlar `phq2_1`, `phq2_2`.
4. **GAD-2:** 2 madde, her biri 4 seçenekli (0–3). Anahtarlar `gad2_1`, `gad2_2`.
5. **Paylaşım izni:** onay kutusu, **varsayılan kapalı**; etiket `share_label`: "Share this assessment with the crew medical officer".
6. **Submit** butonu.

Her ölçeğin altında küçük yazıyla `source` (lisans / kaynak) metni gösterilir.

### Metinler

Madde, seçenek ve talimat metinleri `contracts/behavioral/questions.json` → `weekly_assessment.scales` içindeki **resmi İngilizce** metinlerdir. Kelime, noktalama veya büyük/küçük harf değiştirilmez; kısaltılmaz, yeniden çevrilmez.

### Kurallar

- 9 maddenin hepsi zorunlu.
- Puan ekranda hesaplanmaz. Gönderimden sonra backend'in döndüğü `who5_score`, `phq2_score`, `gad2_score` sonuç ekranında sade biçimde gösterilir.
- Backend'in döndüğü `support_note: true` ise sonuç ekranında destek notu gösterilir (Bugün sekmesindeki ile aynı metin, "not a diagnosis" içerir). Alarm görünümü kullanılmaz.
- 7 gün dolmadan gönderilirse backend 409 `weekly_not_due` döner; mesajdaki sonraki tarih gösterilir.
- Geçmiş sekmesinde her değerlendirmenin yanında paylaşım anahtarı bulunur; değiştirilince `PUT /weekly-assessments/{id}/sharing` çağrılır (gövde `{"share_with_crew_medical": true}`).

## Geçmiş sekmesi ve grafikler

Son 30 günün trendleri. Recharts kullanılır; renkler nötr, durum rengi yok.

| Grafik | Veri | Biçim |
| --- | --- | --- |
| Mood index | Check-in `mood_index` (0–100), gün başına | Çizgi |
| Sleep | Check-in `sleep_hours`, gün başına | Çubuk |
| Reaction time | PVT `mean_rt_ms`, test başına | Çizgi |
| Lapses | PVT `lapses`, test başına | Çubuk |
| Rotation accuracy | Rotation `accuracy` (%), test başına | Nokta + çizgi |
| Weekly assessments | WHO-5, PHQ-2, GAD-2 | Küçük tablo (tarih, puanlar, paylaşım anahtarı) |

### Kurallar

- X ekseni **görev günü** (`mission_day`); ipucunda tarih de gösterilir.
- Eksik günler **boş** bırakılır; 0 olarak çizilmez, çizgi o günde kesilir.
- `valid: false` olan test kayıtları grafikte çizilmez; listede "invalid" etiketiyle görünür.
- `source: "seed"` kayıtları varsa grafiğin köşesinde "Simulated data" etiketi.
- Görev günü 1–7 arası (temel dönem) grafikte hafif bir arka plan bandıyla gösterilir; etiketi "First week".
- Liste uç noktaları sayfalıdır (`limit` en fazla 100, devamı için `cursor`); 30 günlük veri için gerekirse birden fazla sayfa çekilir. `from` ve `to` **ikisi de dahildir**.

## API çağrıları

Uç noktaların tamamı ve kuralları `api-contract.md` içinde. Sahte veri (fixture) dosyaları **şema netleşene kadar ertelendi**; o zamana kadar ekranlar geliştirme sunucusuna karşı denenebilir:

```powershell
# backend klasöründen
$env:BEHAVIORAL_LOAD_SEED = "1"; $env:BEHAVIORAL_FIXED_NOW = "2026-11-14T09:00:00Z"
uvicorn app.behavioral_dev_app:app --reload
```

`http://127.0.0.1:8000/docs` adresinde tüm uç noktalar denenebilir ("Authorize" → `A007`). Sunucu bellek içidir; yeniden başlatınca seed verisine döner.

### Uç noktalar (`/api/v1` öneki ile)

| Uç nokta | Ekran | Özel başlık / alan |
| --- | --- | --- |
| `GET /behavioral/today` | Bugün | – |
| `GET /behavioral/checkins/{date}` | Check-in formunu doldurma | Cevapta `ETag` |
| `PUT /behavioral/checkins/{date}` | Check-in | Yeni kayıt: `If-None-Match: *` · güncelleme: `If-Match: <ETag>` |
| `GET /behavioral/checkins?from=&to=&limit=&cursor=` | Bugün, Geçmiş | – |
| `POST /behavioral/cognitive-tests` | PVT, döndürme | Gövdede `client_request_id` |
| `GET /behavioral/cognitive-tests?test_type=&from=&to=&limit=&cursor=` | Bugün, Geçmiş | – |
| `GET /behavioral/cognitive-tests/{id}` | Test ayrıntısı (ham denemeler) | – |
| `POST /behavioral/weekly-assessments` | Haftalık form | Gövdede `client_request_id` |
| `GET /behavioral/weekly-assessments?from=&to=&limit=&cursor=` | Bugün, Geçmiş | – |
| `PUT /behavioral/weekly-assessments/{id}/sharing` | Geçmiş | – |

Tüm isteklerde `Authorization: Bearer <token>` (ortak API istemcisi ekler). `{date}` UTC tarihidir: `2026-11-14`.

### Başlık ve tekrar gönderim kuralları

- **Check-in:** form açılırken bugünün kaydı `GET /checkins/{date}` ile çekilir (veya `GET /today` → `checkin.etag`). Kayıt varsa `ETag` saklanır ve PUT'ta `If-Match` olarak gönderilir. Kayıt yoksa (404) `If-None-Match: *` gönderilir. İki başlık **asla birlikte** gönderilmez (428). Aynı gövde tekrar gönderilirse backend 200 ve mevcut kaydı döner; ağ hatasında güvenle tekrar denenebilir.
- **`client_request_id`:** her yeni test veya haftalık gönderimde **gövdeye** `crypto.randomUUID()` ile üretilip konur (`Idempotency-Key` başlığı kullanılmaz). Ağ hatasında **aynı `client_request_id` ile** tekrar denenir; backend ikinci kayıt açmaz, ilk kaydı 200 ile döner.

### Örnek: check-in

```json
PUT /api/v1/behavioral/checkins/2026-11-14
If-None-Match: *
{"mood": 6, "energy": 5, "stress": 6, "loneliness": 2, "crew_relation": 3,
 "bed_time": "23:40", "wake_time": "06:10", "sleep_quality": 3,
 "symptoms": ["headache"]}

→ 201, ETag: "c-74-1"
{"id": 74, "date": "2026-11-14", "mission_day": 75, "mood": 6, "energy": 5, "stress": 6,
 "loneliness": 2, "crew_relation": 3, "bed_time": "23:40", "wake_time": "06:10",
 "sleep_quality": 3, "symptoms": ["headache"], "mood_index": 50.0, "sleep_hours": 6.5,
 "source": "manual", "created_at": "2026-11-14T09:00:00Z", "updated_at": "2026-11-14T09:00:00Z"}
```

### Örnek: PVT

```json
POST /api/v1/behavioral/cognitive-tests
{"client_request_id": "3b8f6c0e-2a1d-4c7e-9f10-5e6a7b8c9d01", "test_type": "pvt",
 "started_at": "2026-11-14T08:50:00.000Z", "finished_at": "2026-11-14T08:53:00.000Z",
 "device": "chrome-desktop-keyboard",
 "trials": [{"i": 1, "delay_ms": 2340, "rt_ms": 287, "false_start": false},
            {"i": 2, "delay_ms": 1180, "rt_ms": null, "false_start": true}]}

→ 201
{"id": 412, "client_request_id": "3b8f6c0e-2a1d-4c7e-9f10-5e6a7b8c9d01", "test_type": "pvt",
 "date": "2026-11-14", "mission_day": 75,
 "started_at": "2026-11-14T08:50:00Z", "finished_at": "2026-11-14T08:53:00Z",
 "device": "chrome-desktop-keyboard", "n_trials": 61, "mean_rt_ms": 318.4, "median_rt_ms": 301.0,
 "speed": 3.21, "lapses": 4, "false_starts": 2, "accuracy": null,
 "valid": true, "invalid_reason": null, "source": "manual"}
```

Döndürme için aynı uç nokta: `test_type: "rotation"`, denemeler döndürme biçiminde; cevapta `accuracy` ve `mean_rt_ms` dolu, PVT'ye özgü alanlar (`median_rt_ms`, `speed`, `lapses`, `false_starts`) `null`.

### Örnek: haftalık

```json
POST /api/v1/behavioral/weekly-assessments
{"client_request_id": "9a2e4f71-0c3b-4d5a-8e6f-1b2c3d4e5f60",
 "answers": {"who5_1": 3, "who5_2": 2, "who5_3": 3, "who5_4": 2, "who5_5": 2,
             "phq2_1": 1, "phq2_2": 1, "gad2_1": 2, "gad2_2": 1},
 "share_with_crew_medical": false}

→ 201
{"id": 11, "client_request_id": "9a2e4f71-0c3b-4d5a-8e6f-1b2c3d4e5f60",
 "date": "2026-11-14", "mission_day": 75,
 "who5_score": 48, "phq2_score": 2, "gad2_score": 3, "support_note": true,
 "share_with_crew_medical": false, "created_at": "2026-11-14T09:00:00Z"}
```

## Hata, boş ve yükleniyor durumları

Backend hataları şu biçimde döner; ekranda kullanıcıya uygun mesaj gösterilir, `detail.code` ile hangi durumun olduğu anlaşılır, `detail.fields` ile hatalı alanlar işaretlenir:

```json
{"detail": {"code": "validation_error", "message": "Request validation failed", "fields": ["mood"]}}
```

| Durum | Kullanıcıya mesaj | Davranış |
| --- | --- | --- |
| Yükleniyor | İskelet kartlar (gri bloklar) | Spinner yerine iskelet tercih edilir |
| Henüz veri yok | "No check-ins yet. Start with your first check-in." | Grafik yerine bu mesaj + buton |
| 401 `unauthorized` | "Your session has expired. Please sign in again." | Giriş ekranına yönlendir |
| 404 `checkin_not_found` | – | Check-in formu boş açılır (`If-None-Match: *`) |
| 404 `not_found` | "This record could not be found." | Bugün sekmesine dön. Başka bir astronotun kaydı da 404 döner |
| 409 `weekly_not_due` | Backend `message` alanı: "Next weekly assessment is due on 2026-11-21" | Formu kapat; tekrar gönderme |
| 412 `etag_mismatch` (check-in) | "This check-in was updated elsewhere. Reload and try again." | Güncel kaydı yeniden çek, formu doldur |
| 422 `validation_error` | `detail.fields` içindeki alanların altında hata | Formu silme |
| 422 `future_date` | "You can't submit for a future date." | Formu silme |
| 428 `precondition_required` | – | Geliştirme hatası; başlık mantığı düzeltilir |
| 5xx / ağ hatası | "Can't save right now. Try again." | **Test sonuçları kaybolmaz:** ham denemeler bellekte tutulur, "Try again" aynı `client_request_id` ile gönderir |
| Test yarıda kaldı (sekme değişimi) | "The test was interrupted. Please try again." | Hiçbir şey gönderilmez |
| Backend `valid: false` döndü | "This test didn't count (too many early presses or too few responses). You can try again if you like." | Sonuç ekranında "Try again" butonu |

3 dakikalık bir test bittikten sonra ağ hatası yüzünden sonucun kaybolması en kötü kullanıcı deneyimidir. Bu yüzden gönderim başarısız olursa ham denemeler sayfa açık kaldıkça saklanır ve tekrar denenebilir.

## Yapı ve sahiplik

Bileşen ve klasör yapısı **frontend ekibinin kararıdır**; bu belge yalnızca modülün ihtiyaçlarını tanımlar. Modülün yapıdan tek beklentisi:

- **Metinler tek yerden okunsun:** günlük soru etiketleri, belirti kodları ve haftalık ölçek maddeleri `contracts/behavioral/questions.json` dosyasından okunur; ekranda elle yazılmaz.
- **Zamanlama kuralları ortak olsun:** PVT ve döndürme testi aynı zaman ölçümü ve sekme değişimi kurallarını kullansın (`performance.now()`, `visibilitychange`).

## Kabul kontrol listesi

Ekranlar ancak bu maddeler geçince "bitti" sayılır. Önce geliştirme sunucusuyla, ortak backend hazır olunca gerçek API ile denenir.

### Check-in

- [ ] Kaydırıcılar seçilmemiş başlıyor; tüm alanlar doldurulmadan Submit pasif
- [ ] 23:30 → 06:45 önizlemesi "7 h 15 min" gösteriyor
- [ ] Saatler `HH:MM` gidiyor (`07:30`, saniyesiz)
- [ ] Aynı gün ikinci açılışta form dolu geliyor ve güncelleme `If-Match` ile gidiyor
- [ ] "None" çipi diğerlerini temizliyor ve `symptoms: []` gönderiliyor
- [ ] Gövdede `crew_relation` var, `crew` yok

### Tepki testi

- [ ] Bekleme süreleri 1–4 sn arasında değişiyor (konsolda kontrol)
- [ ] Ekip üyeleri kendi testlerinde 250–400 ms civarı ortalama görüyor
- [ ] Uyarıcıdan önce basınca "Too early" çıkıyor ve `false_start: true`, `rt_ms: null` kaydediliyor
- [ ] Test sırasında sekme değiştirince test yarıda kalıyor, istek gitmiyor
- [ ] Ağı kapatıp test bitirince "Try again" çıkıyor; ağ açılınca aynı `client_request_id` ile tek kayıt oluşuyor
- [ ] Boşluk tuşu ve dokunma ikisi de çalışıyor

### Zihinsel döndürme

- [ ] Ayna şekiller gerçekten ayna; aynı şekiller sadece döndürülmüş (bir ekip arkadaşı kontrol etsin)
- [ ] 16 denemede her açı 4 kez, her koşul 8 kez
- [ ] 7 sn dolunca `answer: null`, `rt_ms: null` ile sonraki denemeye geçiliyor
- [ ] ← / → tuşları çalışıyor

### Bugün, haftalık ve geçmiş

- [ ] Bugün sekmesi tek istekle (`GET /today`) doluyor; görev günü 75 görünüyor
- [ ] Test günü olmayan günde test görevleri görünmüyor
- [ ] `checkin_missing: true` iken sakin hatırlatma görünüyor, alarm görünümü yok
- [ ] Paylaşım kutusu varsayılan kapalı
- [ ] GAD-2 = 3 olan kayıtta destek notu görünüyor ("not a diagnosis" metniyle), alarm görünümü yok
- [ ] 7 gün dolmadan gönderimde sonraki tarih gösteriliyor
- [ ] Grafiklerde eksik günler boş, 0 değil; geçersiz testler çizilmiyor
- [ ] "Simulated data" etiketi seed kayıtlarında görünüyor

### Genel

- [ ] Ekranlarda hiç yeşil/sarı/kırmızı durum rozeti yok
- [ ] Tüm ekran metinleri İngilizce; ölçek metinleri `questions.json` ile birebir aynı
- [ ] Telefon genişliğinde formlar kullanılabiliyor
- [ ] Konsolda hata yok

## Henüz netleşmeyen noktalar

Bu maddeler frontend'i durdurmaz; geliştirme sunucusuyla ilerlenir, karar gelince güncellenir. Tam liste `open-questions.md` içinde.

| Konu | Şu anki varsayım | Kimden beklenir |
| --- | --- | --- |
| Sahte veri (fixture) dosyaları | Şema netleşince üretilecek; şimdilik geliştirme sunucusu ve `/docs` | Modül sorumlusu, backend |
| Gerçek kimlik doğrulama | Geçici: Bearer token = astronot kimliği (`A007`) | Backend |
| Ortak backend'de uç noktaların son hali | `api-contract.md` (`GET /today` ve sharing ucu backend onayı bekliyor) | Backend |

Ayrıntılı bilimsel gerekçe için modülün teknik tasarım belgesine bakın.
