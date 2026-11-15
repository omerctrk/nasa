# Davranışsal ve Refleks Modülü – Teknik Tasarım Belgesi

Nov 14, 2026 · @Şule

> **Güncel olmayan kısımlar** (Adım 6, koddan doğrulandı). Aşağıdaki maddeler belgenin ilgili bölümlerinden önce gelir:
>
> - **Modül renk üretmez.** `evaluate`, `GET /summary`, `behavior_summary` ve "Temel değer ve durum kuralları" bölümündeki renk kuralları geçersiz. İnsan modelindeki "zihin" rengi anomali modülünden gelir.
> - **DSST yok.** Sembol-rakam testi kapsamdan çıkarıldı; `dsst` test türü, `score_dsst` ve tablolardaki DSST sütunu geçersiz.
> - **API öneki ve uç noktalar için `api-contract.md` geçerli** (`/api/v1/behavioral/...`). Bu belgedeki `POST /checkin`, `POST /tests`, `GET /history`, `GET /summary`, `GET /questions` geçersiz.
> - **Isolation Forest kullanılmıyor.** Anomali tarafı kurallar + yerel dil modeli + RAG ile çalışır. Davranış modülü anomaliye `daily_metrics()` ile günlük satırlar verir (alan adları `api-contract.md` → "Anomali modülüne veri"); `daily_series()` ve `pvt_mean_ms` geçersiz.
> - **Senaryo 74 gün:** görev günü 1–74 (`2026-09-01`..`2026-11-13`), demo günü 75.
> - **Haftalık puanlar dil modeline gitmez** (anomali modeline ve uyarı sistemine de gitmez).
> - **Ölçekler resmi İngilizce** metinlerle; tüm ekran metinleri İngilizce. Soru dosyası `contracts/behavioral/questions.json` (`data/behavior/questions.json` değil).
> - **Tablolar `astronaut_id` içerir;** alan adı `crew` değil `crew_relation`, belirti kodları İngilizce (`headache`, `fatigue`, …).
>
> Bilimsel temel ve test protokolleri bölümleri geçerlidir.

## Özet

Modül, astronotun **ruh halini, uykusunu ve bilişsel performansını** kısa ve tekrarlanabilir testlerle izler; sonucu yeşil, sarı veya kırmızı olarak insan modelinin “zihin” bölgesine aktarır. Modülde yapay zekâ yok: puanlar ve durum kural tabanlı hesaplanır.

| Başlık | İçerik |
| --- | --- |
| Sahibi | Davranışsal ve refleks modülü sorumlusu (arayüz + backend) |
| Karşılık geldiği NASA riskleri | Davranışsal değişiklikler ve psikiyatrik bozukluklar · Yetersiz uyku ve düzensiz programlar · Duyusal-motor ve denge değişiklikleri (dolaylı) · Yetersiz takım çalışması (dolaylı) |
| Bağlı olduğu tehlike | İzolasyon ve kapalı alan |
| Parçalar | Günlük check-in · Haftalık ölçekler · Reaksiyon testi (PVT benzeri) · Zihinsel döndürme testi · Opsiyonel sembol-rakam testi |
| Çıktılar | Modül ekranı (bugünkü durum, trendler) · Kural motoruna özet · Anomali modeline günlük özellikler |
| Astronotun günlük süresi | Check-in 1 dk + reaksiyon testi 3 dk; döndürme testi 2–3 günde bir, haftalık ölçekler haftada bir |

**Önceki planda düzeltilen bir nokta:** WHO-5, PHQ-2 ve GAD-2 ölçekleri “son iki hafta” için sorulur; bunları her gün sormak ölçeğin amacına aykırı olur. Bu belgede **günlük kısa check-in** ile **haftalık ölçekler** ayrıldı (aşağıdaki check-in bölümü).

## Bilimsel temel

Testlerimiz NASA'nın ISS astronotlarında rutin olarak kullandığı ölçümlerin sadeleştirilmiş sürümleri; jüriye “bu testleri biz uydurmadık” diyebilmemizin dayanağı bu bölüm.

- **NASA'nın Cognition bataryası.** NASA için geliştirilmiş 10 kısa bilişsel testten oluşur, 2017'de operasyonel kullanıma geçmiştir ve NASA'nın “Standart Ölçümler”inin parçasıdır; ISS astronotları bataryanın tamamını ortalama 16 dakikada bitirmiştir ([Penn Medicine](https://www.med.upenn.edu/uep/cognition.html)). Bataryada PVT-B ve Sembol-Rakam Eşleştirme (DSST) testleri de vardır.
- **PVT-B (3 dakikalık uyanıklık testi).** Standart 10 dakikalık PVT'nin kısaltılmış sürümüdür: süre 3 dakikaya, uyarıcılar arası bekleme 2–10 sn'den 1–4 sn'ye indirilmiş; dikkat kaybı eşiği 500 ms'den 355 ms'ye düşürüldüğünde uykusuzluğa duyarlılığı standart PVT'den farklı bulunmamıştır ([Basner ve ark., 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3197786)). 24 astronotla yapılan 6 aylık ISS çalışmasında kullanılmıştır ([Penn Medicine](https://www.med.upenn.edu/uep/astronaut.html)).
- **Uyku sorunu gerçek.** Mekik ve ISS görevlerinde astronotlar 24 saatte ortalama 6,1 saatten az uyumuştur ([Basner ve ark., 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4691281)). Uyku ve düzensiz program, NASA'nın 17 sağlık riskinden biridir.
- **Zihinsel döndürme.** Şekillerin yalnızca döndürülmüş mü yoksa ters çevrilmiş mi olduğunu ayırt etme becerisidir; NASA destekli MiniCog (MRAB) bataryasında yer alır ([NASA Spinoff](https://spinoff.nasa.gov/node/10598)). Cognition bataryasında zihinsel döndürme yok; uzamsal algıyı farklı bir testle ölçer. Jüriye anlatırken bu ayrımı doğru yapın.
- **Analog çalışmalar.** NASA'nın yer tabanlı HERA tesisinde kapalı kalan gönüllülerde, bir gece tam uykusuzluk sonrası uyanıklık testinde belirgin yavaşlama ve doğruluk kaybı görülmüştür ([Frontiers in Physiology, 2020](https://www.frontiersin.org/article/10.3389/fphys.2020.00394)).

**Ruh hali ölçekleri** (WHO-5, PHQ-2, GAD-2) uzaya özgü değil; yaygın kullanılan kısa tarama ölçekleri. Doğrulanmış Türkçe çevirileri kullanılmalı; kullanım koşulları ve eşik değerleri resmi kaynaktan kontrol edilmeli.

## Modülün parçaları ve veri akışı

Astronot üç tür girdi verir; backend ham veriyi puanlar, saklar ve tek bir özet (`behavior_summary`) üretir. Dışarıya giden her şey bu özetten ve günlük seriden geçer.

&#91;embedded content: Davranışsal modül veri akışı · 3 girdi, 3 backend adımı, 4 çıktı\]

Arayüz hiçbir puanı kendisi hesaplamaz; aynı hesap yolu canlı testlerde ve senaryo verisinde kullanılır.

## Günlük check-in ve haftalık ölçekler

Ruh hali iki hızda ölçülür: **her gün 1 dakikalık kısa check-in**, **haftada bir doğrulanmış tarama ölçekleri**. Soru metinleri ve seçenekler tek bir dosyada (`data/behavior/questions.json`) durur; arayüz formu bu dosyadan çizer, backend puanlamayı aynı dosyaya göre yapar.

### Günlük check-in (her sabah, \~1 dk)

Bu soruları biz tasarlıyoruz; doğrulanmış bir ölçek değil, günlük takip için tek maddelik sorular.

| Kod | Soru (özet) | Cevap | Not |
| --- | --- | --- | --- |
| `mood` | Bugün genel olarak kendini nasıl hissediyorsun? | 0–10 kaydırıcı | Yüksek = iyi |
| `energy` | Enerji düzeyin nasıl? | 0–10 | Yüksek = iyi |
| `stress` | Ne kadar stresli hissediyorsun? | 0–10 | Yüksek = kötü |
| `loneliness` | Kendini yalnız hissettin mi? | 0–4 | Yüksek = kötü |
| `crew` | Mürettebatla ilişkin nasıl? | 0–4 | Yüksek = iyi |
| `bed_time` / `wake_time` | Kaçta yattın, kaçta kalktın? | Saat seçici | Uyku süresi hesaplanır |
| `sleep_quality` | Uykunun kalitesi? | 1–5 |  |
| `symptoms` | Bugün bunlardan biri var mı? | Çoklu seçim | Kod listesi aşağıda |

**Günlük ruh hali indeksi (0–100)** = (`mood` + `energy` + (10 − `stress`)) / 3 × 10. Bu bizim tanımladığımız basit bir bileşik puan; trend izlemek için kullanılır, klinik anlamı yoktur. Anomali modeline giden “iyi oluş” özelliği budur.

**Belirti kodları** (sabit liste; diğer sistemler de kullanır): `bas_agrisi`, `halsizlik`, `bulanti`, `bas_donmesi`, `bulanik_gorme`, `goz_baskisi`, `sirt_agrisi`, `oksuruk`, `nefes_darligi`, `bogaz_agrisi`, `doku_lezyon` (döküntü/uçuk), `sindirim`.

### Haftalık ölçekler (haftada bir, \~2 dk)

Bu üç ölçek “son iki hafta” için sorulur; bu yüzden günlük değil haftalık uygulanır. Madde metinleri buraya kopyalanmadı; resmi Türkçe sürümlerinden alınıp `questions.json`'a konacak.

| Ölçek | Neyi tarar | Madde | Cevap | Puanlama | Yaygın kullanılan eşik (doğrulanacak) |
| --- | --- | --- | --- | --- | --- |
| WHO-5 | Genel iyi oluş | 5 | 0–5 | Ham toplam (0–25) × 4 → 0–100 | < 50 düşük iyi oluş · ≤ 28 olası depresyon |
| PHQ-2 | Depresif belirtiler | 2 | 0–3 | Toplam 0–6 | ≥ 3 pozitif tarama |
| GAD-2 | Kaygı belirtileri | 2 | 0–3 | Toplam 0–6 | ≥ 3 pozitif tarama |

Pozitif tarama teşhis değildir; ekranda “psikolojik destek ekibiyle görüşmeyi düşün” önerisi olarak gösterilir. Ruh hali verisi varsayılan olarak yalnızca astronotta kalır.

### Check-in kuralları

- Günde en fazla bir check-in; aynı gün tekrar gönderilirse güncellenir.
- Uyku süresi gece yarısını geçebilir (23:30 → 06:45 = 7,25 sa); 2 saatten kısa veya 14 saatten uzun süre kaydedilmeden önce onay sorulur.
- Haftalık ölçekler son uygulamadan 7 gün geçince “bugün haftalık değerlendirme günü” olarak gösterilir.

## Reaksiyon testi (PVT benzeri)

Test, PVT-B parametrelerini izler: **3 dakika, 1–4 sn rastgele bekleme, 355 ms üstü dikkat kaybı, 100 ms altı erken basma**. Uykusuzluğa en duyarlı test bu; günlük yapılır.

### Protokol

1. **Talimat ekranı:** “Ekranın ortasında sayı belirdiğinde olabildiğince hızlı dokun. Sayı görünmeden dokunma.” Tam ekran önerilir.
2. **Alıştırma:** 3 deneme; kaydedilmez.
3. **Test:** 180 saniye boyunca döngü:
   1. Boş ekran, rastgele 1.000–4.000 ms bekleme (tekdüze dağılım).
   2. Uyarıcı: ortada milisaniye sayacı akmaya başlar.
   3. Dokunma anında sayaç durur ve tepki süresi 1 sn gösterilir; sonra yeni bekleme başlar.
   4. Dokunma olmazsa uyarıcı en fazla 30 sn ekranda kalır; sonra “cevapsız” sayılır.
4. **Sonuç ekranı:** ortalama, dikkat kaybı sayısı, temel değerle kıyas.

3 dakikada yaklaşık 60 deneme oluşur.

### Ölçümler

| Ölçüm | Tanım | Neden |
| --- | --- | --- |
| `mean_rt_ms` | Geçerli tepkilerin (≥ 100 ms) ortalaması | Genel hız |
| `median_rt_ms` | Geçerli tepkilerin medyanı | Uç değerlere dayanıklı |
| `speed` | Ortalama (1000 / tepki ms) | Literatürde uykusuzluğa en duyarlı çıktı |
| `lapses` | 355 ms ve üstü tepki + cevapsız deneme sayısı | Dikkat kaybı |
| `false_starts` | Uyarıcıdan önce veya 100 ms'den kısa sürede dokunma | Afallama, dürtüsellik |
| `n_trials` | Toplam deneme | Geçerlilik kontrolü |

### Kenar durumlar ve teknik dikkat

- **Zaman ölçümü:** `performance.now()` kullanın; `Date.now()` yeterince hassas değil. Uyarıcı zamanını `requestAnimationFrame` içinde, ekrana çizildiği kareyle alın.
- **Dokunma ve fare gecikmesi** cihazdan cihaza değişir. Bu yüzden mutlak değer değil, **aynı cihazdaki temel değere göre fark** yorumlanır.
- **Sekme değişimi:** test sırasında sayfa görünürlüğü kaybolursa (`visibilitychange`) test geçersiz sayılır ve tekrar istenir.
- **Geçerlilik:** 30'dan az geçerli deneme veya %20'den fazla erken basma varsa sonuç “geçersiz” işaretlenir, duruma katılmaz.
- **Günün saati** sonucu etkiler; demoda testin her gün aynı zaman diliminde (sabah check-in'den sonra) yapılması önerilir.
- Ham denemelerin tamamı backend'e gönderilir; **ölçümleri backend hesaplar**.

## Zihinsel döndürme testi

Yan yana iki şekilden ikincisinin birincinin **döndürülmüş hali mi yoksa ayna görüntüsü mü** olduğu sorulur. Uzamsal algıyı ve yön duygusunu ölçer; ayakta denge testinin yerçekimsiz ortamda yapılabilecek dolaylı karşılığıdır. 2–3 günde bir yapılır.

### Uyarıcılar

- **Şekiller:** simetrisi olmayan 4 farklı 2B çokgen (örneğin “F”, “R”, “L” benzeri bloklar). SVG olarak çizilir; harf kullanılmaz ki okuma becerisi karışmasın.
- **Açılar:** 0°, 60°, 120°, 180°.
- **Koşullar:** her açıda yarı yarıya “aynı” ve “ayna”.
- **Deneme listesi:** 4 açı × 2 koşul × 2 tekrar = **16 deneme**, karışık sırada. Her oturumda şekiller rastgele seçilir ama açı ve koşul dağılımı sabit kalır, böylece oturumlar kıyaslanabilir.

### Protokol

1. Talimat + 2 alıştırma denemesi (geri bildirimli).
2. 16 deneme: iki şekil görünür, astronot **Aynı** veya **Ayna** butonuna basar. Zaman sınırı deneme başına 7 sn; aşılırsa “cevapsız”.
3. Denemeler arası 500 ms boş ekran. Test sırasında doğru/yanlış gösterilmez.
4. Sonuç: doğruluk ve ortalama süre, temel değerle kıyas.

### Ölçümler

| Ölçüm | Tanım |
| --- | --- |
| `accuracy` | Doğru cevap / toplam deneme (cevapsız = yanlış) |
| `mean_rt_ms` | Yalnızca doğru cevapların ortalama süresi |
| `rt_slope_ms_per_deg` | Doğru cevaplarda sürenin açıyla artış eğimi (opsiyonel) |

Klasik bulgu, açı büyüdükçe cevap süresinin uzamasıdır. Eğim, “zihinde çevirme hızını” gösterir ve sunumda görsel olarak etkileyicidir; ancak 16 denemeyle gürültülü olacağı için duruma katılmaz, sadece gösterilir.

### Dikkat

- İlk birkaç oturumda öğrenme etkisi olur (performans artışı). Temel dönemde en az 2 oturum olmalı.
- Doğruluğu şans düzeyine (%50) yakın çıkan oturum geçersiz sayılır: muhtemelen talimat anlaşılmamış veya rastgele basılmıştır.

## Opsiyonel: sembol-rakam eşleştirme testi

Check-in, reaksiyon ve döndürme testleri bittikten sonra eklenir; yarım günden az sürer. NASA'nın Cognition bataryasındaki DSST'nin sadeleştirilmiş sürümü; bilişsel işlem hızını ölçer.

- **Ekran:** üstte 9 sembol–rakam eşleşmesinden oluşan anahtar; ortada tek bir sembol; altta 1–9 rakam tuşları.
- **Görev:** ortadaki sembolün rakamına bas; doğru ya da yanlış, hemen yeni sembol gelir.
- **Süre:** 90 saniye.
- **Anahtar her oturumda karıştırılır**, böylece ezber etkisi azalır.
- **Ölçümler:** `correct_count` (90 sn'de doğru sayısı), `accuracy`.
- **Semboller** basit SVG şekiller olmalı; emoji kullanılmamalı (cihazdan cihaza farklı görünür).

## Temel değer ve durum kuralları

Durum, sabit eşikler ile **astronotun kendi temel değerine göre sapmanın** birleşimidir. Kural tetiklenirse gerekçe listesine eklenir; en kötü renk kazanır (kırmızı > sarı > yeşil).

### Temel değer

- **Dönem:** görevin 1–7. günleri.
- **Hesaplanan:** günlük ruh hali indeksi, uyku süresi, PVT ortalaması, PVT dikkat kaybı, döndürme doğruluğu; her biri için ortalama ve standart sapma.
- **Yeterli veri yoksa** (temel dönemde 3'ten az gün veya 2'den az test) yalnızca sabit eşikler uygulanır ve gerekçeye “temel değer henüz oluşmadı” yazılır.

### Kurallar (başlangıç değerleri — eşik tablosunda doğrulanacak)

| Renk | Koşul | Gerekçe metni örneği |
| --- | --- | --- |
| Kırmızı | Son haftalık PHQ-2 ≥ 3 | “Depresif belirti taraması pozitif” |
| Kırmızı | Son haftalık GAD-2 ≥ 3 | “Kaygı taraması pozitif” |
| Kırmızı | Son WHO-5 ≤ 28 | “İyi oluş puanı çok düşük” |
| Kırmızı | Günlük ruh hali indeksi 3 gün üst üste ≤ 30 | “3 gündür çok düşük ruh hali” |
| Sarı | Son WHO-5 < 50 | “İyi oluş puanı düşük” |
| Sarı | 7 günlük ruh hali indeksi ortalaması temel değerin %15'ten fazla altında | “Ruh hali son haftada %22 düştü” |
| Sarı | Uyku borcu (son 7 gün, hedef 8 sa) > 5 sa | “Uyku borcu 6,2 saat” |
| Sarı | PVT ortalaması temel değerin %15'ten fazla üstünde | “Reaksiyon süresi %18 yavaşladı” |
| Sarı | PVT dikkat kaybı ≥ temel ortalama + 3 | “Dikkat kaybı 6 (temel: 2)” |
| Sarı | Döndürme doğruluğu temel değerin 15 puandan fazla altında | “Uzamsal test doğruluğu %71 (temel: %90)” |
| Yeşil | Hiçbir kural tetiklenmedi | “Değerler temel aralıkta” |

**Veri eksikliği** renk değildir: son 3 günde check-in veya son 2 günde PVT yoksa özette `data_missing: true` döner, ekranda “bugün check-in / test yapılmadı” hatırlatması çıkar.

Tüm eşikler `service.py` dosyasının başında tek bir sözlükte (`THRESHOLDS`) tutulur; kodun içine dağıtılmaz. 8 saatlik uyku hedefi yetişkinler için yaygın önerilen aralığın ortası olarak seçildi.

## Veritabanı tabloları

Modül üç tablo kullanır. Tablolar `core/models.py` dosyasına Ömer & Aybala tarafından eklenir; alanları bu bölüm belirler. Tek astronotla çalışıldığı için `astronaut_id` yok; tüm zamanlar UTC.

### `checkins` — günlük check-in (günde en fazla bir)

| Alan | Tip | Zorunlu | Not |
| --- | --- | --- | --- |
| id | int, birincil anahtar | evet |  |
| date | date, **benzersiz** | evet | Aynı gün tekrar = güncelleme |
| mission\_day | int | evet |  |
| mood | int 0–10 | evet |  |
| energy | int 0–10 | evet |  |
| stress | int 0–10 | evet |  |
| loneliness | int 0–4 | evet |  |
| crew | int 0–4 | evet |  |
| mood\_index | float 0–100 | evet | Backend hesaplar |
| bed\_time / wake\_time | time | evet |  |
| sleep\_hours | float | evet | Backend hesaplar |
| sleep\_quality | int 1–5 | evet |  |
| symptoms | JSON (kod listesi) | hayır | `["bas_agrisi","halsizlik"]` |
| source | str | evet | `manual` veya `seed` |
| created\_at / updated\_at | datetime | evet |  |

### `weekly_assessments` — haftalık ölçekler

| Alan | Tip | Not |
| --- | --- | --- |
| id | int |  |
| taken\_at | datetime |  |
| mission\_day | int |  |
| answers | JSON | `{"who5_1":4,…,"phq2_1":1,"phq2_2":0,"gad2_1":1,"gad2_2":1}` |
| who5\_score | int 0–100 | Ham toplam × 4 |
| phq2\_score | int 0–6 |  |
| gad2\_score | int 0–6 |  |
| share\_with\_crew\_medical | bool | Varsayılan `false`; paylaşım izni |
| source | str |  |

### `cognitive_tests` — her test oturumu bir satır

| Alan | Tip | PVT | Döndürme | DSST |
| --- | --- | --- | --- | --- |
| id | int | ✓ | ✓ | ✓ |
| taken\_at | datetime | ✓ | ✓ | ✓ |
| mission\_day | int | ✓ | ✓ | ✓ |
| test\_type | str: `pvt` / `rotation` / `dsst` | ✓ | ✓ | ✓ |
| duration\_s | int | ✓ | ✓ | ✓ |
| n\_trials | int | ✓ | ✓ | ✓ |
| mean\_rt\_ms | float | ✓ | ✓ (doğrular) |  |
| median\_rt\_ms | float | ✓ |  |  |
| speed | float | ✓ |  |  |
| lapses | int | ✓ |  |  |
| false\_starts | int | ✓ |  |  |
| accuracy | float 0–1 |  | ✓ | ✓ |
| correct\_count | int |  |  | ✓ |
| valid | bool | ✓ | ✓ | ✓ |
| invalid\_reason | str | ✓ | ✓ | ✓ |
| device | str | ✓ | ✓ | ✓ |
| raw | JSON | ✓ | ✓ | ✓ |
| source | str | ✓ | ✓ | ✓ |

`raw` örnekleri:

```json
{"pvt": [{"i": 1, "delay_ms": 2340, "rt_ms": 287, "false_start": false}],
 "rotation": [{"i": 1, "shape": "s3", "angle": 120, "mirror": true, "answer": "mirror", "rt_ms": 1840}],
 "dsst": [{"i": 1, "symbol": "k4", "expected": 7, "answer": 7, "rt_ms": 950}]}
```

Neden denemeler ayrı bir tabloda değil? Denemeler yalnızca ayrıntı ekranı ve yeniden hesaplama için gerekiyor; JSON olarak saklamak hackathon için daha hızlı. `device` alanı, PVT sonuçlarının aynı cihazdaki temel değerle kıyaslanması için tutulur.

## API sözleşmesi

Tüm uç noktalar `/api/behavior` altında. Ölçümleri ve durumu **backend hesaplar**; arayüz ham cevapları ve ham denemeleri gönderir. Hatalar `{"detail": "açıklama"}` biçiminde döner (422: geçersiz girdi).

| Uç nokta | Ne yapar |
| --- | --- |
| `GET /questions` | `questions.json` içeriğini döner (günlük ve haftalık sorular) |
| `GET /today` | Bugün check-in yapıldı mı, PVT yapıldı mı, haftalık ölçek günü mü |
| `POST /checkin` | Günlük check-in kaydeder veya günceller; puanları ve güncel durumu döner |
| `POST /weekly` | Haftalık ölçekleri kaydeder; puanları ve durumu döner |
| `POST /tests` | Test oturumunu (ham denemeler) alır; ölçümleri hesaplayıp kaydeder |
| `GET /history?days=30` | Grafikler için günlük seriler |
| `GET /summary` | Bugünkü durum, gerekçeler ve özet değerler (ekran + kural motoru) |

### `POST /checkin`

İstek:

```json
{"mood": 6, "energy": 5, "stress": 6, "loneliness": 2, "crew": 3,
 "bed_time": "23:40", "wake_time": "06:10", "sleep_quality": 3,
 "symptoms": ["bas_agrisi"]}
```

Cevap:

```json
{"date": "2026-11-14", "mission_day": 87, "mood_index": 50.0, "sleep_hours": 6.5,
 "status": "yellow", "reasons": ["Uyku borcu 6,2 saat"]}
```

### `POST /tests`

İstek (PVT örneği):

```json
{"test_type": "pvt", "duration_s": 180, "device": "laptop-chrome",
 "trials": [{"i": 1, "delay_ms": 2340, "rt_ms": 287, "false_start": false},
            {"i": 2, "delay_ms": 1180, "rt_ms": null, "false_start": true}]}
```

Cevap:

```json
{"id": 412, "test_type": "pvt", "valid": true, "n_trials": 61,
 "mean_rt_ms": 318.4, "median_rt_ms": 301.0, "speed": 3.21, "lapses": 4, "false_starts": 2,
 "vs_baseline": {"mean_rt_pct": 6.1, "lapses_delta": 2}}
```

### `GET /history?days=30`

```json
{"days": [
  {"mission_day": 86, "mood_index": 44.0, "sleep_hours": 5.5, "pvt_mean_ms": 371.0,
   "pvt_lapses": 6, "rotation_acc": null},
  {"mission_day": 87, "mood_index": 50.0, "sleep_hours": 6.5, "pvt_mean_ms": 352.0,
   "pvt_lapses": 5, "rotation_acc": 0.81}],
 "weekly": [{"mission_day": 84, "who5": 48, "phq2": 2, "gad2": 3}],
 "baseline": {"mood_index": 72.0, "sleep_hours": 7.2, "pvt_mean_ms": 320.0,
              "pvt_lapses": 1.4, "rotation_acc": 0.9}}
```

### `GET /summary`

```json
{"status": "red", "reasons": ["Kaygı taraması pozitif", "Uyku borcu 6,2 saat",
  "Reaksiyon süresi %10 yavaşladı"],
 "mood_index_7d": 49.6, "sleep_debt_h": 6.2, "pvt_mean_ms": 352.0, "pvt_lapses": 5,
 "rotation_acc": 0.81, "last_who5": 48, "last_phq2": 2, "last_gad2": 3,
 "data_missing": false, "baseline_ready": true}
```

Ruh hali ölçek puanları (`last_who5`, `last_phq2`, `last_gad2`) yalnızca astronotun kendi ekranında gösterilir; kural motoruna yalnızca renk ve genel gerekçe gider.

## Backend fonksiyonları

Kod `backend/app/modules/behavior/` altında üç dosyaya bölünür. Puanlama fonksiyonları **saf fonksiyon** (veritabanı yok, girdi → çıktı); böylece birim testi kolay ve senaryo verisi üreticisi de aynı fonksiyonları kullanır.

### `scoring.py` — saf fonksiyonlar

```python
THRESHOLDS = {
    "pvt_lapse_ms": 355, "pvt_false_start_ms": 100, "pvt_min_valid_trials": 30,
    "sleep_target_h": 8, "sleep_debt_yellow_h": 5,
    "mood_drop_pct_yellow": 15, "mood_index_red": 30, "mood_red_days": 3,
    "pvt_slow_pct_yellow": 15, "pvt_lapse_delta_yellow": 3,
    "rotation_drop_pts_yellow": 15,
    "who5_yellow": 50, "who5_red": 28, "phq2_red": 3, "gad2_red": 3,
}

def mood_index(mood: int, energy: int, stress: int) -> float          # 0–100
def sleep_hours(bed: time, wake: time) -> float                         # gece yarısını geçen uyku
def score_who5(answers: dict) -> int                                    # 0–100
def score_phq2(answers: dict) -> int                                    # 0–6
def score_gad2(answers: dict) -> int                                    # 0–6
def score_pvt(trials: list[dict]) -> dict        # mean, median, speed, lapses, false_starts, valid, reason
def score_rotation(trials: list[dict]) -> dict   # accuracy, mean_rt_ms (doğrular), slope, valid
def score_dsst(trials: list[dict]) -> dict       # correct_count, accuracy
```

### `service.py` — veritabanı ve kurallar

```python
# Kayıt
def upsert_checkin(db, data: CheckinIn) -> CheckinOut
def create_weekly(db, data: WeeklyIn) -> WeeklyOut
def create_test(db, data: TestIn) -> TestOut

# Okuma ve türetilmiş değerler
def today_state(db) -> TodayState                # check-in / PVT yapıldı mı, haftalık günü mü
def baseline(db) -> Baseline                     # görev 1–7. gün ortalama ve std; baseline_ready
def sleep_debt(db, days: int = 7) -> float       # Σ max(0, hedef − gerçek)
def mood_index_avg(db, days: int = 7) -> float
def daily_series(db, days: int = 30) -> list[DayRow]   # gün başına tek satır (grafik + anomali)

# Durum
def evaluate(db) -> tuple[str, list[str]]        # THRESHOLDS ile renk + gerekçeler
def behavior_summary(db) -> Summary              # /summary ve kural motoru için tek giriş noktası
```

### `router.py`

Her uç nokta yalnızca isteği doğrular ve `service` fonksiyonunu çağırır; iş mantığı burada yazılmaz.

### Pydantic modelleri (`schemas.py`)

| Model | Alanlar (özet) |
| --- | --- |
| `CheckinIn` | mood, energy, stress (0–10) · loneliness, crew (0–4) · bed\_time, wake\_time · sleep\_quality (1–5) · symptoms (kod listesi) |
| `WeeklyIn` | answers (who5\_1–5, phq2\_1–2, gad2\_1–2) · share\_with\_crew\_medical |
| `TestIn` | test\_type · duration\_s · device · trials (liste) |
| `CheckinOut`, `WeeklyOut`, `TestOut` | Kaydedilen satır + hesaplanan puanlar + güncel durum |
| `Summary` | API sözleşmesindeki `/summary` alanları |

Aralık dışı değerler (örneğin `mood: 14`) Pydantic tarafından 422 ile reddedilir; bu yüzden aralıklar `Field(ge=0, le=10)` gibi modelde tanımlanır.

## Frontend ekranları ve bileşenleri

Modül tek sayfada dört sekmeden oluşur: **Bugün · Check-in · Testler · Geçmiş**. Kod `frontend/src/features/behavior/` altında; ortak bileşenler (`Card`, `Button`, `StatusBadge`) Yusuf & Sude'nin `components/ui/` klasöründen gelir.

| Bileşen | Görev | Veri |
| --- | --- | --- |
| `BehaviorPage` | Sekmeler ve sayfa düzeni | – |
| `TodayCard` | Durum rengi, gerekçeler, “check-in yapılmadı” / “test zamanı” / “haftalık değerlendirme günü” uyarıları | `GET /summary`, `GET /today` |
| `CheckinForm` | Günlük sorular; kaydırıcılar ve saat seçici; tek sayfa | `GET /questions`, `POST /checkin` |
| `WeeklyForm` | Haftalık ölçekler; “son iki haftayı düşün” notu; paylaşım izni kutusu | `GET /questions`, `POST /weekly` |
| `PvtTest` | Talimat → alıştırma → 3 dk test → sonuç | `POST /tests` |
| `RotationTest` | Talimat → 2 alıştırma → 16 deneme → sonuç | `POST /tests` |
| `DsstTest` (opsiyonel) | 90 sn sembol-rakam | `POST /tests` |
| `TestResult` | Test sonuç kartı; temel değerle kıyas | `POST /tests` cevabı |
| `BehaviorTrends` | Ruh hali indeksi, uyku, PVT ortalaması ve dikkat kaybı grafikleri; temel değer kesikli çizgi | `GET /history` |

### Arayüz kuralları

- **Test ekranları sade olur:** test sırasında menü, bildirim veya animasyon yok; dikkat dağıtan her şey sonucu bozar.
- **Tam ekran** butonu test başlangıcında sunulur.
- **Zaman ölçümü** test bileşeninin içinde, `performance.now()` ile; React yeniden çizimleri zamanlamayı etkilemesin diye uyarıcı gösterimi ve dokunma yakalama hafif tutulur (`ref` + doğrudan DOM olayı).
- **Klavye desteği:** PVT'de boşluk tuşu, döndürmede ← Aynı / → Ayna.
- **Grafiklerde** “simüle veri” etiketi görünür.
- **Gizlilik:** haftalık ölçek puanları yalnızca bu sayfada gösterilir; genel panoya yalnızca renk gider.

## Diğer modüllerle bağlantı

Modülün dışarıya verdiği her şey iki fonksiyondan geçer: `behavior_summary()` ve `daily_series()`. Bu iki fonksiyonun çıktı biçimi değişirse ilgili sahiplere haber verilir.

| Kim kullanır | Ne alır | Nasıl kullanır |
| --- | --- | --- |
| Kural motoru (`core/rules.py`, Ömer & Aybala) | `behavior_summary()` → renk + gerekçeler | İnsan modelinde **zihin** sisteminin rengi |
| Kural motoru | Check-in `symptoms` kodları | `oksuruk`, `nefes_darligi` → solunum · `bulanti`, `sindirim` → sindirim · `halsizlik`, `doku_lezyon`, `bogaz_agrisi` → bağışıklık · `sirt_agrisi` → iskelet |
| Kural motoru | `sleep_debt_h` | Bağışıklık sisteminde risk çarpanı |
| Göz modülü (Yusuf & Sude) | `bulanik_gorme`, `goz_baskisi` belirtileri | Göz belirtilerini ayrıca sormak yerine check-in'den okuyabilir (karar verilecek) |
| Anomali tespiti | `daily_series()` → gün başına `mood_index`, `sleep_hours`, `pvt_mean_ms` | Isolation Forest'ın özelliklerinden üçü |
| Chatbot (2. gün) | `behavior_summary()` | “Neden yorgunum?” sorusunda uyku ve dikkat verisini kullanır; ruh hali puanları yalnızca paylaşım izni varsa |

**Anomali modeline not:** Önceki planda “iyi oluş” özelliği için WHO-5 düşünülmüştü. WHO-5 artık haftalık olduğu için günlük özellik olarak **`mood_index`** kullanılmalı.

**Bağımlılık yönü:** bu modül başka hiçbir modülü çağırmaz; yalnızca kendi tablolarına yazar ve okunur. `mission_day` değerini `mission` tablosundan (Ömer & Aybala) okur.

## Senaryo verisinin davranış kısmı

Demo “Mars yolculuğu, 87. gün” senaryosuna göre **görevin 1–87. günleri** için sentetik veri üretilir. Değerler demo için uydurulmuştur; ekranda “simüle veri” olarak etiketlenir. Üretici sabit tohumla çalışır, her seferinde aynı veriyi verir.

| Dönem | Günlük check-in | Haftalık ölçek | PVT | Döndürme |
| --- | --- | --- | --- | --- |
| 1–7. gün (temel) | mood\_index \~72 ± 6 · uyku \~7,2 ± 0,5 sa | WHO-5 \~72 · PHQ-2 0–1 · GAD-2 0–1 | Ortalama \~320 ± 15 ms · dikkat kaybı 0–2 | Doğruluk \~%90 (2 oturum) |
| 8–79. gün | Hafif dalgalanma; uyku yavaşça 6,8 sa'ya iner | Benzer | Benzer, küçük gürültü | 2–3 günde bir; \~%88–92 |
| 80–85. gün (gömülü örüntü) | mood\_index \~42 · uyku \~5,2 sa · stres yüksek · belirtiler: `halsizlik`, `bas_agrisi` | 84. gün: WHO-5 48 · PHQ-2 2 · GAD-2 3 | \~380 ms · dikkat kaybı 5–6 | \~%75 |
| 86–87. gün (bugün) | Kısmi toparlanma: mood\_index \~50, uyku \~6,5 sa | – | \~350 ms · 4–5 | \~%81 |

**Beklenen demo sonucu:** 87. gün zihin sistemi **kırmızı** (84. günkü GAD-2 = 3), gerekçelerde uyku borcu ve reaksiyon yavaşlaması. Anomali modeli 80–85. günleri işaretler. Demoda kırmızı yerine sarı istenirse 84. gün GAD-2 değeri 2 yapılır; bu karar sunum hikayesine göre verilmeli.

**Üretim kuralı:** PVT için yalnızca özet değil, **ham denemeler** üretilir ve `score_pvt` ile puanlanır. Böylece seed verisi ile canlı test aynı hesap yolundan geçer.

## Test ve doğrulama kontrol listesi

Modül ancak aşağıdaki maddeler geçince “bitti” sayılır.

### Birim testleri (`scoring.py`, pytest)

- [ ] `sleep_hours(23:30, 06:45)` = 7,25 · `sleep_hours(01:00, 08:00)` = 7,0
- [ ] `mood_index(10, 10, 0)` = 100 · `mood_index(0, 0, 10)` = 0
- [ ] `score_who5` tüm cevaplar 5 → 100; tüm cevaplar 0 → 0
- [ ] `score_pvt`: 99 ms'lik tepki erken basma sayılır; 355 ms dikkat kaybı sayılır; cevapsız deneme dikkat kaybı sayılır
- [ ] `score_pvt`: 30'dan az geçerli deneme → `valid=false`
- [ ] `score_rotation`: cevapsız = yanlış; süre yalnızca doğrulardan
- [ ] `evaluate`: her kırmızı ve sarı kuralı için en az bir örnek veri seti, beklenen renk ve gerekçe

### Uç nokta testleri (`/docs` üzerinden elle)

- [ ] Aynı gün iki check-in → tek satır, ikinci değerlerle güncellenmiş
- [ ] `mood: 14` → 422
- [ ] Seed verisiyle `/summary` → 87. gün beklenen renk ve gerekçeler
- [ ] `/history?days=30` → 30 günlük seri, eksik günler `null`

### Arayüz testleri

- [ ] PVT'yi kendiniz 3 kez yapın: ortalama makul aralıkta (yaklaşık 250–400 ms) mı?
- [ ] PVT sırasında sekme değiştirince test geçersiz sayılıyor mu?
- [ ] Bilerek sürekli basınca erken basma sayısı artıyor ve test geçersiz sayılıyor mu?
- [ ] Döndürme testinde “ayna” ve “aynı” şekiller gerçekten doğru çiziliyor mu? (Bir ekip arkadaşına kontrol ettirin.)
- [ ] Telefon genişliğinde check-in formu kullanılabiliyor mu?

### Demo provası

- [ ] Canlı PVT 3 dakika sürer; sunumda zaman sıkışırsa 30 saniyelik “demo modu” (sonucu kaydetmez) hazır
- [ ] Check-in gönderilince insan modelinde zihin bölgesinin rengi değişiyor

## En baştan karar verilmesi gerekenler

Bu maddeler kod yazılmadan netleşmeli; sonradan değiştirmek tabloları, API'yi ve seed verisini birlikte etkiler. Her birinin yanındaki öneri bu belgede varsayılan olarak kullanıldı.

| # | Karar | Seçenekler | Bu belgedeki öneri | Kimle |
| --- | --- | --- | --- | --- |
| 1 | WHO-5, PHQ-2, GAD-2 ne sıklıkla? | Günlük / haftalık | **Haftalık** (ölçekler son iki haftayı sorar); günlük kısa check-in ayrı | Ekip |
| 2 | Anomali modeline hangi ruh hali özelliği gider? | WHO-5 / günlük indeks | **`mood_index`** (günlük) | Anomali sorumlusu |
| 3 | Senaryo kaç günlük? | 30 / 87 gün | **87 gün** (temel dönem 1–7. gün verinin içinde olsun) | Ömer & Aybala |
| 4 | 87. gün demo rengi | Kırmızı / sarı | **Kırmızı** (GAD-2 = 3); hikaye için sarı istenirse GAD-2 = 2 | Sunum sorumlusu |
| 5 | PVT dikkat kaybı eşiği | 500 ms / 355 ms | **355 ms** (3 dakikalık sürüm için literatürdeki eşik) | – |
| 6 | Denemeler nasıl saklanır? | JSON / ayrı tablo | **JSON** (`raw` alanı) | Ömer & Aybala |
| 7 | Göz belirtileri nereden sorulur? | Check-in / göz modülü | **Check-in** (tek form); göz modülü okur | Yusuf & Sude |
| 8 | Ölçek metinleri | Resmi Türkçe / kendi çevirimiz | **Resmi Türkçe sürüm** | – |
| 9 | Sembol-rakam testi | Yapılır / yapılmaz | **Opsiyonel** (üç ana parça bitince) | – |

### Açık sorular

- [ ] WHO-5, PHQ-2 ve GAD-2'nin resmi Türkçe sürümleri ve kullanım koşulları nereden alınacak?
- [ ] Kural eşikleri (%15 sapma, 5 saat uyku borcu vb.) kimin onayıyla kesinleşecek? (Plan belgesindeki eşik tablosu sorumlusu)
- [ ] Plan belgesinde davranışsal modülün sahibi güncellenecek mi?
- [ ] Ekip arkadaşları kendi PVT temel değerlerini oluşturmak için test edecek mi? (Canlı demoda gerçekçi kıyas sağlar)

## Kaynaklar

- [Cognition Test Battery – Penn Medicine](https://www.med.upenn.edu/uep/cognition.html)
- [Astronaut Behavioral Health – Penn Medicine](https://www.med.upenn.edu/uep/astronaut.html)
- [Basner ve ark. (2011), Validity and Sensitivity of a Brief Psychomotor Vigilance Test (PVT-B)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3197786)
- [Basner ve ark. (2015), Development and Validation of the Cognition Test Battery for Spaceflight](https://pmc.ncbi.nlm.nih.gov/articles/PMC4691281)
- [MiniCog Rapid Assessment Battery – NASA Spinoff](https://spinoff.nasa.gov/node/10598)
- [Cognitive performance in HERA – Frontiers in Physiology (2020)](https://www.frontiersin.org/article/10.3389/fphys.2020.00394)
- [NASA HRP – Risks of Human Spaceflight](https://www.nasa.gov/hrp/risks/)

WHO-5, PHQ-2 ve GAD-2 eşikleri bu belgede yaygın kullanılan değerler olarak verildi; resmi kaynaklarından doğrulanmalı.
