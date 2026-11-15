# AstraHealth — Davranış Modülü API Sözleşmesi

Nov 14, 2026 · @Şule · Sürüm 2

> **Bu belge koddan doğrulandı (commit `1e17099`).** Kaynaklar: `backend/app/schemas/behavioral.py`,
> `backend/app/routers/behavioral.py`, `backend/app/services/behavioral_*.py`,
> `backend/app/core/behavioral_settings.py`. Belge ile kod farklıysa kod geçerlidir.
> Backend ekibinin onayı beklenen noktalar en sondaki listede ve `open-questions.md` içinde.

## Genel kurallar

Davranış modülünün bütün uç noktaları `/api/v1/behavioral` altında; gövdeler JSON, tarih ve saatler UTC.

| Konu | Kural |
| --- | --- |
| Temel adres | `/api/v1/behavioral` |
| Kimlik | `Authorization: Bearer <token>`. `astronaut_id` gövdede gönderilmez; giriş yapan kullanıcıdan alınır. **Geçici:** gerçek auth gelene kadar token değeri astronot kimliğidir (`^A\d{3}$`, ör. `A007`) |
| Tarih | `YYYY-MM-DD` (UTC günü), örnek `2026-11-14` |
| Saat (uyku) | `HH:MM`, `00:00`–`23:59`. `24:00`, `7:30` ve saniyeli `23:30:00` reddedilir |
| Zaman damgası | ISO 8601, saat dilimi **zorunlu** (`Z` veya `+03:00`); saat dilimsiz değer 422. Cevaplarda UTC |
| Süreler | Milisaniye, sayı (`rt_ms: 287.4`) |
| Alan adları | `snake_case`, İngilizce. Şema v5.0 sütun adlarıyla karşılaştırma backend onayı bekliyor |
| Tip kuralları | Tam sayılar ve bool'lar **katı**: `true`, `"6"`, `6.0` tam sayı yerine; `1`, `"yes"` bool yerine kabul edilmez |
| Bilinmeyen alan | Gövdede tanımsız alan (ör. `astronaut_id`, `crew`) 422 `validation_error` |
| Puanlama | Frontend ham cevap ve ham deneme gönderir; bütün puanları backend hesaplar |
| Tekrar gönderim | Test ve haftalık kayıtlarda gövdede `client_request_id` (UUID v4). Aynı astronot + aynı kimlikle ikinci istek yeni kayıt açmaz; gövde farklı olsa bile **ilk kaydı** 200 ile döner |
| Başkasının kaydı | **404** döner (403 değil): başka bir astronotun kaydının var olduğu bilgisi sızdırılmaz |

### Takvim

| Kural | Değer |
| --- | --- |
| Görev başlangıcı | `2026-09-01` = görev günü **1** (`mission_day = (tarih − 2026-09-01) + 1`) |
| Test günleri | `mission_day % 7 ∈ {1, 4}` → görev Salı başladığı için **Salı ve Cuma** (takvim günü değil, görev gününe bağlı) |
| Haftalık ölçek | Son kayıttan **7 gün** sonra |
| Check-in eksik sinyali | **Dünden geriye** ardışık eksik gün ≥ **2** (bugün henüz bitmedi; görev öncesi günler sayılmaz) |

### Liste uç noktaları

Cevap her listede aynıdır; en yeni kayıt önce gelir:

```json
{ "items": [ ... ], "next_cursor": null }
```

| Parametre | Kural |
| --- | --- |
| `from`, `to` | Tarih; **ikisi de dahil**. `from > to` → 422 (`fields: ["from", "to"]`) |
| `limit` | 1–100, varsayılan 30. Dışındaysa 422 (`fields: ["limit"]`) |
| `cursor` | Önceki cevabın `next_cursor` değeri; **opak** metin, istemci içini okumaz. Bozuksa 422 (`fields: ["cursor"]`) |

Son sayfada `next_cursor: null`.

### Hata cevabı

Tüm hatalar aynı biçimdedir:

```json
{ "detail": { "code": "validation_error", "message": "Request validation failed", "fields": ["mood"] } }
```

- `fields`: hatalı alan adları (gövde, yol veya sorgu parametresi); alan yoksa `[]`.
- Doğrulama hatası **gönderilen değeri geri yansıtmaz**; yalnız alan adları döner (haftalık cevaplar sızmasın).
- Bu biçim yalnız `/api/v1/behavioral` yollarında uygulanır; diğer yollarda FastAPI'nin varsayılan 422 biçimi değişmez.
- 401 cevabında `WWW-Authenticate: Bearer` başlığı vardır.
- Mesajlar İngilizcedir. Örnekler: `"Check-in date cannot be in the future"`,
  `"Next weekly assessment is due on 2026-11-21"`, `"Missing or invalid bearer token"`.

## Bugün

`GET /today` — "Bugün" ekranı tek istekle neyin yapılması gerektiğini ve eksik veri sinyallerini öğrenir; kuralı backend hesaplar, frontend tarih hesabı yapmaz. **Uygulandı, backend onayı bekliyor.** Haftalık puan içermez.

```json
{
  "date": "2026-11-14",
  "mission_day": 75,
  "checkin": { "done": false, "etag": null },
  "tests_due": [],
  "tests_done": [],
  "weekly_due": false,
  "weekly_last_date": "2026-11-09",
  "weekly_next_date": "2026-11-16",
  "signals": {
    "checkin_missing": false,
    "consecutive_missed_checkin_days": 0,
    "missed_checkin_days_7d": 0,
    "last_checkin_date": "2026-11-13",
    "tests_missing": false,
    "last_test_date": "2026-11-13"
  }
}
```

| Alan | Kural |
| --- | --- |
| `checkin.etag` | Bugünün check-in'i varsa ETag'i (düzeltme için `If-Match`), yoksa `null` |
| `tests_due` | Test günlerinde `["pvt", "rotation"]`, diğer günlerde `[]` |
| `tests_done` | Bugün kaydedilmiş test türleri (geçerli **veya** geçersiz) |
| `weekly_due` | Son haftalık kayıttan ≥ 7 gün geçtiyse veya hiç kayıt yoksa `true` |
| `weekly_last_date` / `weekly_next_date` | Son kaydın tarihi / +7 gün; hiç kayıt yoksa ikisi de `null` |
| `signals.consecutive_missed_checkin_days` | Dünden geriye ardışık check-in'siz gün sayısı |
| `signals.checkin_missing` | `consecutive_missed_checkin_days ≥ 2` |
| `signals.missed_checkin_days_7d` | Son 7 günde (dün dahil, bugün hariç) check-in'siz gün sayısı |
| `signals.tests_missing` | Son 7 günde (dün dahil, bugün hariç) en az bir test günü var ve o günlerin hiçbirinde test kaydı yok |
| `signals.last_checkin_date` / `last_test_date` | Son kaydın tarihi veya `null` |

## Günlük check-in

Günde tek kayıt vardır ve tarih adresin içindedir; oluşturma ve düzeltme aynı `PUT` isteğiyle yapılır.

| Yöntem | Adres | Ne yapar | Başarılı cevap |
| --- | --- | --- | --- |
| GET | `/checkins?from=&to=&limit=&cursor=` | Geçmiş check-in'ler (grafikler) | 200, liste |
| GET | `/checkins/{date}` | Tek günün kaydı; başlıkta `ETag` | 200; yoksa 404 `checkin_not_found` |
| PUT | `/checkins/{date}` | Oluştur veya düzelt | 201 yeni; 200 güncelleme veya tekrar gönderim; başlıkta `ETag` |

### ETag kuralları

| Durum | Sonuç |
| --- | --- |
| ETag biçimi | `"c-{id}-{version}"`, ör. `"c-1042-3"` (tırnaklar dahil) |
| `If-None-Match: *`, kayıt yok | Oluşturur → **201**, `"c-{id}-1"` |
| `If-None-Match: *`, kayıt var | 412 `etag_mismatch` |
| `If-None-Match` `*` dışında bir değer | 422 `validation_error` (yalnız `*` desteklenir) |
| `If-Match: "<ETag>"`, eşleşiyor | Günceller → 200, version +1, `created_at` aynı |
| `If-Match: "<ETag>"`, eşleşmiyor veya kayıt yok | 412 `etag_mismatch` (ekran güncel kaydı yeniden çeker) |
| `If-Match: *` | Kayıt varsa günceller (200); yoksa 412 |
| İki başlık birden **veya** hiçbiri | 428 `precondition_required` |
| **Aynı gövde** tekrar gönderildi | Başlıklara bakılmadan **200** ve mevcut kayıt; version artmaz, `updated_at` değişmez |
| Gelecek tarih | 422 `future_date` (`fields: ["date"]`) |
| Görev başlangıcından önce | 422 `validation_error` (`fields: ["date"]`) |

Kontrol sırası: gelecek tarih → görev öncesi → başlık sayısı → aynı gövde → `If-None-Match` / `If-Match`.

**İstek gövdesi** (`PUT /checkins/2026-11-14`):

```json
{
  "mood": 6,
  "energy": 5,
  "stress": 4,
  "loneliness": 1,
  "crew_relation": 3,
  "bed_time": "23:30",
  "wake_time": "06:45",
  "sleep_quality": 3,
  "symptoms": ["headache", "fatigue"]
}
```

| Alan | Tip | Aralık |
| --- | --- | --- |
| `mood`, `energy`, `stress` | tam sayı | 0–10 |
| `loneliness`, `crew_relation` | tam sayı | 0–4 |
| `bed_time`, `wake_time` | `HH:MM` | `00:00`–`23:59` |
| `sleep_quality` | tam sayı | 1–5 |
| `symptoms` | metin listesi | Aşağıdaki 12 koddan; boş liste olabilir, alan gönderilmezse `[]`; tekrar eden kod 422 |

**Belirti kodları** (sıra ve etiketler `contracts/behavioral/questions.json` ile aynı; kodda tek kaynak `SYMPTOM_CODES`):

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

**Cevap** (200/201):

```json
{
  "id": 1042,
  "date": "2026-11-14",
  "mission_day": 75,
  "mood": 6, "energy": 5, "stress": 4,
  "loneliness": 1, "crew_relation": 3,
  "bed_time": "23:30", "wake_time": "06:45", "sleep_quality": 3,
  "symptoms": ["headache", "fatigue"],
  "mood_index": 56.7,
  "sleep_hours": 7.25,
  "source": "manual",
  "created_at": "2026-11-14T09:00:00Z",
  "updated_at": "2026-11-14T09:00:00Z"
}
```

`mood_index` = (mood + energy + (10 − stress)) / 3 × 10, 1 ondalık; `sleep_hours` = uyanış − yatış (gece yarısını geçerse +24 sa), 2 ondalık. `source`: `"manual"` (API) veya `"seed"` (senaryo verisi).

## Bilişsel testler (PVT ve döndürme)

Frontend test bitince tüm ham denemeleri tek istekte gönderir; backend puanlar ve sonucu aynı cevapta döner. **Geçersiz oturum da kaydedilir**, `valid: false` ve nedeniyle döner.

| Yöntem | Adres | Ne yapar | Başarılı cevap |
| --- | --- | --- | --- |
| POST | `/cognitive-tests` | Bir test oturumu gönder | 201 yeni; aynı `client_request_id` ile 200 ve ilk kayıt |
| GET | `/cognitive-tests?test_type=&from=&to=&limit=&cursor=` | Geçmiş sonuçlar (ham denemeler **hariç**) | 200, liste |
| GET | `/cognitive-tests/{id}` | Tek oturum, ham denemelerle (`trials`) | 200; yoksa veya başkasınınsa 404 `not_found` |

`test_type` filtresi `pvt` veya `rotation`; başka değer 422 (`fields: ["test_type"]`). Listede `from` / `to`, testin `date` alanına uygulanır; sıralama `started_at` (eşitse `id`) yeniden eskiye.

### Ortak gövde alanları

| Alan | Kural |
| --- | --- |
| `client_request_id` | UUID v4, zorunlu |
| `test_type` | `"pvt"` veya `"rotation"`; başka değer (ör. `"dsst"`) 422 (`fields: ["test_type"]`) |
| `started_at`, `finished_at` | Saat dilimli zaman damgası, zorunlu; `finished_at ≥ started_at` |
| `device` | İsteğe bağlı metin, en çok 64 karakter |
| `trials` | Liste; **boş olabilir** (puanlama `no_trials` ile geçersiz sayar). PVT en çok 200, döndürme en çok 16 deneme. `i` değerleri benzersiz |

- `started_at`, sunucu saatinden **5 dakikadan** fazla ilerideyse 422 `future_date` (`fields: ["started_at"]`) — cihaz saati farkı için tolerans.
- Kaydın `date` alanı = `started_at`'in **UTC günü**; görev başlangıcından önceyse 422 `validation_error`.

### PVT gövdesi

```json
{
  "client_request_id": "3b8f6c0e-2a1d-4c7e-9f10-5e6a7b8c9d01",
  "test_type": "pvt",
  "started_at": "2026-11-14T08:50:00.000Z",
  "finished_at": "2026-11-14T08:53:02.400Z",
  "device": "chrome-desktop-keyboard",
  "trials": [
    { "i": 1, "delay_ms": 2310, "rt_ms": 287.4, "false_start": false },
    { "i": 2, "delay_ms": 1480, "rt_ms": null, "false_start": false },
    { "i": 3, "delay_ms": 3720, "rt_ms": null, "false_start": true }
  ]
}
```

| PVT deneme alanı | Kural |
| --- | --- |
| `i` | Tam sayı ≥ 0, oturum içinde benzersiz |
| `delay_ms` | Uyarıdan önceki bekleme, 1000–4000 |
| `rt_ms` | Uyarıdan basışa süre (≥ 0). **Anahtar zorunlu**; basılmadıysa `null` |
| `false_start` | Uyarıdan önce basıldıysa `true`; bu durumda `rt_ms` **`null` olmalı** |

100 ms altındaki `rt_ms` reddedilmez; erken basma kararını puanlama verir (`< 100 ms` erken basma, `≥ 355 ms` veya cevapsız dikkat kaybı).

### Döndürme gövdesi

Aynı çatı, `test_type: "rotation"`, en çok 16 deneme:

```json
{ "i": 1, "shape": "s3", "angle": 120, "mirror": true, "answer": "mirror", "rt_ms": 1620.5 }
```

| Döndürme deneme alanı | Kural |
| --- | --- |
| `i` | Tam sayı ≥ 0, oturum içinde benzersiz |
| `shape` | `"s1"`–`"s4"` |
| `angle` | 0, 60, 120 veya 180 (tam sayı) |
| `mirror` | Gösterilen şekil ayna görüntüsü mü |
| `answer` | `"same"`, `"mirror"` veya `null` (7 sn içinde cevap yok). **Anahtar zorunlu** |
| `rt_ms` | 0–7000. `answer` `null` ise `rt_ms` de `null`; `answer` doluysa `rt_ms` dolu |

### Cevap

Puanlar her iki test için aynı alanlarda; teste uymayan alan `null` (PVT'de `accuracy`; döndürmede `median_rt_ms`, `speed`, `lapses`, `false_starts`). `correct_count` **yoktur**.

```json
{
  "id": 588,
  "client_request_id": "3b8f6c0e-2a1d-4c7e-9f10-5e6a7b8c9d01",
  "test_type": "pvt",
  "date": "2026-11-14",
  "mission_day": 75,
  "started_at": "2026-11-14T08:50:00Z",
  "finished_at": "2026-11-14T08:53:02.400000Z",
  "device": "chrome-desktop-keyboard",
  "n_trials": 52,
  "mean_rt_ms": 301.6,
  "median_rt_ms": 289.0,
  "speed": 3.412,
  "lapses": 4,
  "false_starts": 1,
  "accuracy": null,
  "valid": true,
  "invalid_reason": null,
  "source": "manual"
}
```

`GET /cognitive-tests/{id}` aynı alanlara ek olarak `trials` döner.

| Test | Geçerlilik kuralı | `invalid_reason` değerleri |
| --- | --- | --- |
| PVT | ≥ 30 geçerli tepki ve erken basma oranı ≤ %20 | `no_trials`, `too_few_responses`, `too_many_false_starts` |
| Döndürme | Doğruluk ≥ %55 | `no_trials`, `near_chance_accuracy` |

PVT'de önce tepki sayısına bakılır: hem az tepki hem çok erken basma varsa neden `too_few_responses` olur.

## Haftalık değerlendirme

Haftalık ölçekler gizlidir: puanlar anomali modeline, dil modeline ve uyarı sistemine gitmez, loglanmaz. Astronot kendi kayıtlarını görür; ekip doktoru yalnız `share_with_crew_medical: true` olanları görür (yetkilendirme gelince uygulanacak).

| Yöntem | Adres | Ne yapar | Başarılı cevap |
| --- | --- | --- | --- |
| POST | `/weekly-assessments` | Haftalık cevapları gönder | 201 yeni; aynı `client_request_id` ile 200 ve ilk kayıt |
| GET | `/weekly-assessments?from=&to=&limit=&cursor=` | Kendi geçmiş puanları (madde cevapları **hariç**) | 200, liste |
| PUT | `/weekly-assessments/{id}/sharing` | Paylaşım iznini değiştir. **Uygulandı, backend onayı bekliyor** | 200; yoksa veya başkasınınsa 404 `not_found` |

**İstek gövdesi:**

```json
{
  "client_request_id": "9a2e4f71-0c3b-4d5a-8e6f-1b2c3d4e5f60",
  "answers": {
    "who5_1": 3, "who5_2": 2, "who5_3": 3, "who5_4": 2, "who5_5": 2,
    "phq2_1": 1, "phq2_2": 1,
    "gad2_1": 2, "gad2_2": 1
  },
  "share_with_crew_medical": false
}
```

| Madde | Aralık | Zorunlu |
| --- | --- | --- |
| `who5_1` … `who5_5` | 0–5 | Evet, hepsi |
| `phq2_1`, `phq2_2` | 0–3 | Evet |
| `gad2_1`, `gad2_2` | 0–3 | Evet |
| `share_with_crew_medical` | true / false | Hayır, varsayılan `false` |

`answers` içinde fazladan anahtar (ör. `phq9_3`) 422.

**Kontrol sırası:** (1) aynı `client_request_id` varsa mevcut kayıt 200 ile döner — **7 gün kuralından önce**; (2) son kayıttan 7 gün geçmediyse 409 `weekly_not_due`, mesajda sonraki tarih: `"Next weekly assessment is due on 2026-11-21"`; (3) puanlanır ve kaydedilir (`date` = bugünün UTC günü).

**Cevap** (201):

```json
{
  "id": 77,
  "client_request_id": "9a2e4f71-0c3b-4d5a-8e6f-1b2c3d4e5f60",
  "date": "2026-11-14",
  "mission_day": 75,
  "who5_score": 48,
  "phq2_score": 2,
  "gad2_score": 3,
  "support_note": true,
  "share_with_crew_medical": false,
  "created_at": "2026-11-14T09:00:00Z"
}
```

`who5_score` = madde toplamı × 4 (0–100); `phq2_score` ve `gad2_score` = iki madde toplamı (0–6). `support_note` = `phq2_score ≥ 3` veya `gad2_score ≥ 3`; saklanmaz, her cevapta hesaplanır. `true` ise ekran `questions.json` içindeki `support_note` metnini gösterir.

**Paylaşım gövdesi** (`PUT /weekly-assessments/{id}/sharing`): `{"share_with_crew_medical": true}`. Alan zorunlu ve katı bool; fazladan alan 422. Yalnız paylaşım alanı değişir; cevap `WeeklyOut`.

## Durum kodları özeti

| Kod | `detail.code` | Ne zaman | Frontend ne yapar |
| --- | --- | --- | --- |
| 200 | — | Okuma, güncelleme, tekrar gönderim | Sonucu gösterir |
| 201 | — | Yeni kayıt | Sonucu gösterir |
| 401 | `unauthorized` | Token yok veya geçersiz (`WWW-Authenticate: Bearer`) | Giriş ekranına yönlendirir |
| 404 | `checkin_not_found`, `not_found` | Kayıt yok **veya başka bir astronotun** | Check-in'de boş form; diğerlerinde hata mesajı |
| 409 | `weekly_not_due` | Haftalık erken | Mesajdaki sonraki tarihi gösterir |
| 412 | `etag_mismatch` | Kayıt başka yerde değişti veya zaten var | Kaydı yeniden çeker, kullanıcıya sorar |
| 422 | `validation_error`, `future_date` | Hatalı gövde / parametre, gelecek tarih | `fields` içindeki alanların yanında hata gösterir |
| 428 | `precondition_required` | `If-Match` / `If-None-Match` ikisi birden veya hiçbiri | Geliştirme hatası; düzeltilir |
| 5xx | — | Sunucu hatası | Cevapları saklar, tekrar dener (aynı `client_request_id`) |

403 kullanılmaz.

## Anomali modülüne veri

HTTP uç noktası **değildir**; anomali modülü aynı backend içinde Python fonksiyonu olarak çağırır.

```python
from app.api.deps_behavioral import get_metrics_feed
rows = get_metrics_feed().daily_metrics(astronaut_id, date_from, date_to)   # list[DailyMetrics]
```

- Aralıktaki **her gün** için bir satır (veri olmayan günler dahil), eskiden yeniye. Veri yoksa `null`.
- `date_from > date_to` veya görev başlangıcından önce → `validation_error`; `date_to` gelecekte → `future_date`.
- Testlerde yalnız **geçerli** (`valid: true`) oturumlar; aynı gün aynı türden birden fazla varsa **en son** olanı (`started_at`, sonra `id`).
- **Haftalık veri yok:** WHO-5 / PHQ-2 / GAD-2 puanları, madde cevapları ve paylaşım alanı bu fonksiyonda bulunmaz; fonksiyon haftalık repository'yi parametre olarak bile almaz.

Satır alanları (**kesin adlar**; anomali modülü ve bilgi kartları kullanıyor, değiştirilmez):

| Alan | Tip | Kaynak |
| --- | --- | --- |
| `date` | tarih | — |
| `mission_day` | tam sayı | — |
| `checkin_done` | bool | O gün check-in var mı |
| `mood_index` | sayı / null | Check-in |
| `stress` | tam sayı / null | Check-in |
| `loneliness` | tam sayı / null | Check-in |
| `crew_relation` | tam sayı / null | Check-in |
| `sleep_hours` | sayı / null | Check-in |
| `sleep_quality` | tam sayı / null | Check-in |
| `symptoms` | metin listesi | Check-in; yoksa `[]` |
| `pvt_mean_rt_ms` | sayı / null | Geçerli PVT |
| `pvt_lapses` | tam sayı / null | Geçerli PVT |
| `pvt_false_starts` | tam sayı / null | Geçerli PVT |
| `rotation_accuracy` | sayı / null | Geçerli döndürme |
| `rotation_mean_rt_ms` | sayı / null | Geçerli döndürme |
| `checkin_missing` | bool | O güne kadar ardışık eksik gün ≥ 2 (bugünün satırında sayım dünden başlar) |

## Demo ve geliştirme sunucusu

Geliştirme sunucusu bellek içidir; ortak `main.py` değildir. `backend` klasöründen (PowerShell):

```powershell
$env:BEHAVIORAL_LOAD_SEED = "1"; $env:BEHAVIORAL_FIXED_NOW = "2026-11-14T09:00:00Z"
uvicorn app.behavioral_dev_app:app --reload
```

| Değişken | Etkisi |
| --- | --- |
| `BEHAVIORAL_FIXED_NOW` | Sunucu saatini sabitler (ISO 8601, saat dilimi zorunlu) |
| `BEHAVIORAL_LOAD_SEED=1` | Açılışta `seed_output/` içindeki 3 dosyayı A007 için yükler; dosya yoksa üretme komutunu söyleyen hata verir |

Seed verisi: görev günü **1–74** (`2026-09-01`..`2026-11-13`); demo günü **75** (`2026-11-14`). Üretmek için: `python -m scripts.seed_behavioral seed_output`. Belgeler: `http://127.0.0.1:8000/docs` ("Authorize" → `A007`).

## Backend'in onaylaması gereken noktalar

Aşağıdakiler kodda uygulandı; backend farklı karar verirse kod ve belge birlikte güncellenir. Ayrıntılar ve diğer sorular `open-questions.md` içinde.

- [ ] `client_request_id` gövdede (`Idempotency-Key` başlığı değil).
- [ ] Alan adları şema v5.0 ile aynı mı (`crew_relation`, `symptoms`, `bed_time` / `wake_time`, testlerde `started_at` / `finished_at` / `date`)?
- [ ] Hata gövdesi tüm uygulamada `detail.code` biçiminde mi olacak?
- [ ] `GET /today` ve `PUT /weekly-assessments/{id}/sharing` kabul mü?
- [ ] Haftalık erken gönderimde 409 uygun mu?
- [ ] Kimlik doğrulama yöntemi ve ekip doktoru rolü.
- [ ] Başkasının kaydına 404 (403 değil) kuralı.

Soru metinleri `contracts/behavioral/questions.json` içinde. Örnek cevap dosyaları (fixture) şema netleşince üretilecek; o zamana kadar geliştirme sunucusu ve `/docs` kullanılabilir.
