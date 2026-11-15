# Davranışsal modül — ilerleme kaydı

## Özet durum (Adım 6 itibarıyla)

**Biten (bellek içi, 260 test):** puanlama · soru dosyası (`questions.json`, İngilizce) · seed (74 gün) ·
Pydantic şemaları · check-in / test / haftalık servisleri · `GET /today` ve eksik veri sinyalleri ·
anomali için `daily_metrics` · FastAPI router + hata işleyicileri · geliştirme sunucusu (seed yüklemeli) ·
belgeler koddan güncellendi.

**Dış bağımlılık bekleyen:**
- Gerçek (SQL) repository'ler ve `get_db` — backend şeması v5.0 bekleniyor
- Gerçek kimlik doğrulama ve ekip doktoru rolü — backend auth bekleniyor
- Şema v5.0 sütun adlarıyla karşılaştırma (`taken_at`, `duration_s`, `correct_count`, ETag sütunu)
- Fixture dosyaları — şema netleşince
- Ayrıntı: `open-questions.md`

## Adım 1 — Şemalar (2026-11-14)

### Ne yapıldı
- Pydantic v2 (2.14.3) ile istek ve cevap şemaları yazıldı. Veritabanı, FastAPI uygulaması ve router yok.
- Şemalar yalnız doğrular; puan hesaplama `behavioral_scoring.py` içinde kalır.
- Ön temizlik: seed'de belirti yoksa `symptoms` artık `"[]"` (null değil), kullanım notu düzeltildi,
  `questions.json` sürüm 2 ve paylaşım etiketi "crew medical officer" oldu.

### Dosyalar
- `backend/app/schemas/__init__.py`, `backend/app/schemas/behavioral.py` (yeni)
- `backend/tests/unit/test_behavioral_schemas.py` (yeni, 39 test)
- `backend/requirements.txt` (yeni: `pydantic>=2,<3`)
- `backend/scripts/seed_behavioral.py`, `backend/tests/unit/test_seed_behavioral.py`,
  `contracts/behavioral/questions.json` (temizlik)

### Verilen kararlar
- Deneme (trial) anahtarları `i` ve `delay_ms` korundu.
- `correct_count` cevaplardan kaldırıldı (`CognitiveTestOut` içinde yok).
- `mission_day` ve `source` cevaplara eklendi.
- Tam sayı alanları `StrictInt`: `true`, `"6"`, `6.0` kabul edilmez.
- Giriş modellerinde `extra="forbid"`: gövdede `astronaut_id`, `crew` gibi bilinmeyen alan hatadır.
- Belirti kodları `SYMPTOM_CODES` sabitinden doğrulanır; liste şemada tekrar yazılmadı.
- 100 ms altı `rt_ms` şemada reddedilmez; erken basma ve geçersizlik kararını puanlama verir.
- Şemaya eklenen ek kurallar: bool alanlar `StrictBool`; denemelerde `rt_ms` (ve döndürmede `answer`)
  anahtarı zorunlu, cevapsız deneme için açıkça `null` gönderilir.

### API sözleşmesinde güncellenecekler
- Check-in gövdesi: `crew` yerine `crew_relation`; saatler `HH:MM`; `symptoms` her zaman liste.
- Belirti kodları: 12 İngilizce kod (`questions.json` ile aynı sıra).
- Test gövdesi: `test_type` ayrımı (`pvt` / `rotation`), `started_at` + `finished_at` (saat dilimli),
  `client_request_id` UUID4, deneme sınırları (PVT 200, döndürme 16).
- Cevaplar: `correct_count` yok; `mission_day`, `source` var; haftalık cevapta `support_note` (bool).
- Hata biçimi: `{"detail": {"code", "message", "fields"}}`.
- Not: depoda henüz bir API sözleşmesi dosyası yok; testlerdeki örnek gövdeler bu adımın tarifinden kuruldu.

### Açık sorular
- Şema v5.0 sütun adları: bilişsel testte `taken_at` mı, `started_at` / `finished_at` / `date` mi?
  Seed şu an `taken_at` + `duration_s` üretiyor; şemalar `started_at` / `finished_at` / `date` bekliyor.
- `duration_s` ve `device` sütunları tabloda var mı? (`CognitiveTestOut` içinde `duration_s` yok.)
- ~~Seed `client_request_id` değerleri UUID5 (deterministik); API UUID4 istiyor.~~
  **Kapandı:** seed API'den geçmiyor, değişiklik gerekmiyor.
- Seed `symptoms`, `raw`, `answers` alanlarını JSON metni olarak yazıyor; cevap şemaları liste / nesne bekliyor.
  Dönüşüm veritabanı katmanında mı yapılacak?
- Seed hâlâ `correct_count` üretiyor; tabloda kalacak mı, yalnız API'den mi çıkarıldı?

## Adım 2 — Check-in servisi (2026-11-14)

### Ne yapıldı
- Check-in için hata sınıfı, repository arayüzü, bellek içi repository ve servis yazıldı.
  FastAPI, router ve SQLAlchemy yok.
- Servis: tarih kuralları, ön koşul başlıkları (If-Match / If-None-Match), ETag, tekrar gönderim,
  sayfalı listeleme. Hesaplar `behavioral_scoring` fonksiyonlarıyla yapılır.
- Repository yalnız saklar ve okur; commit yapmaz, iş kuralı içermez.

### Dosyalar
- `backend/app/services/behavioral_errors.py` (yeni)
- `backend/app/repositories/__init__.py`, `behavioral.py`, `behavioral_memory.py` (yeni)
- `backend/app/services/behavioral_checkins.py` (yeni)
- `backend/tests/conftest.py`, `backend/tests/unit/test_behavioral_checkins.py` (yeni, 31 test)

### Kararlar
- Aynı gövde tekrar gönderilirse başlıklara bakılmadan mevcut kayıt döner (200 mantığı):
  `created=False`, version artmaz, `updated_at` değişmez.
- İki başlık birden gelirse veya hiçbiri gelmezse 428 (`precondition_required`).
- `If-Match: *` desteklenir (kayıt varsa günceller, yoksa 412).
- ETag biçimi `"c-{id}-{version}"`.
- `mission_day` = (tarih − görev başlangıcı) + 1.
- Saat (`now`) ve görev başlangıcı servise dışarıdan verilir; testlerde sabit saat kullanılır.
- Ek kurallar: `If-None-Match` yalnız `*` kabul eder (başka değer 422); listelemede
  `date_from` / `date_to` boş bırakılabilir; cursor, son kaydın tarihinin base64'üdür.

### Açık sorular
- ETag için `version` sütunu mu, SQL Server `rowversion` mı kullanılacak? Backend'e sorulacak.
- ~~Görev günü tutarsızlığı: belgeler 14 Kasım = 74. gün diyor, formülle 75 çıkıyor.~~
  **Kapandı (Adım 3):** 1 Eylül = 1. gün; seed düzeltildi, 14 Kasım = 75.
- Demo için sabit saat ayarı gerekiyor (bugünün tarihi senaryonun son günüyle eşleşmeli).
- `mission_start` sabit değil, mission tablosundan okunacak.

## Adım 3 — Test ve haftalık servisleri (2026-11-14)

### Ne yapıldı
- Seed görev günü düzeltildi: tarih = görev başlangıcı + (gün − 1). 74 gün artık
  2026-09-01..2026-11-13 aralığında. Sayısal değerler aynı; tarihler 1 gün geri kaydı.
- Bilişsel test servisi (PVT, döndürme): puanlama, tekrar gönderim, tarih kuralları, okuma, listeleme.
- Haftalık ölçek servisi: puanlama, destek notu, 7 gün kuralı, tekrar gönderim, paylaşım ayarı, listeleme.
- Listeleme kuralları (limit, tarih aralığı, cursor) ortak modüle alındı; check-in servisi de bunu kullanıyor.
- Yeni hata kodu: `weekly_not_due` (409).

### Dosyalar
- `backend/scripts/seed_behavioral.py`, `backend/tests/unit/test_seed_behavioral.py` (seed düzeltmesi)
- `backend/app/services/behavioral_errors.py` (`weekly_not_due`)
- `backend/app/repositories/behavioral.py`, `behavioral_memory.py` (test ve haftalık repository'leri)
- `backend/app/services/behavioral_paging.py` (yeni, ortak listeleme kuralları)
- `backend/app/services/behavioral_checkins.py` (ortak modülü kullanacak şekilde sadeleşti)
- `backend/app/services/behavioral_tests.py`, `behavioral_weekly.py` (yeni)
- `backend/tests/conftest.py`, `backend/tests/unit/test_behavioral_tests.py`,
  `backend/tests/unit/test_behavioral_weekly.py` (yeni testler)

### Kararlar
- Seed görev günü düzeltildi: 1 Eylül = 1. gün, 14 Kasım = 75.
- Haftalık ölçekte tekrar gönderim kontrolü (`client_request_id`), 7 gün kontrolünden önce yapılır.
- Başkasının kaydı 404 (`not_found`) döner; sözleşmedeki 403 güncellenecek.
- `PUT /weekly-assessments/{id}/sharing` eklendi; sözleşmeye eklenecek.
- `started_at` için 5 dakikalık saat toleransı (cihaz saati sunucudan biraz ileride olabilir).
- Geçersiz test oturumu da kaydedilir (`valid=false` + `invalid_reason`).
- `support_note` saklanmaz, her cevapta `phq2_score >= 3 or gad2_score >= 3` ile hesaplanır.
- Haftalık modül hiç log yazmaz; cevaplar ve puanlar log'a gitmez.

### Puanlama kontrolünün sonucu
- `score_pvt` / `score_rotation` anahtarları: `n_trials`, `mean_rt_ms`, `median_rt_ms`, `speed`,
  `lapses`, `false_starts`, `accuracy`, `correct_count`, `valid`, `invalid_reason`.
- PVT: geçerli = en az 30 geçerli tepki ve erken basma oranı en çok %20. Nedenler: `no_trials`,
  `too_few_responses`, `too_many_false_starts`. Sözleşmeyle aynı.
- Döndürme: geçerli = doğruluk en az %55. Nedenler: `no_trials`, `near_chance_accuracy`. Sözleşmeyle aynı.
- Fark yok; eşleme gerekmedi. `correct_count` puanlamada hep `None`, servis bunu kayda almıyor.
- Not: PVT'de önce tepki sayısına bakılır. Hem az tepki hem çok erken basma varsa neden `too_few_responses` olur.

### Açık sorular
- Ekip doktoru rolü: yalnız `share_with_crew_medical=true` kayıtları görme kuralı,
  yetkilendirme gelince yazılacak.

## Adım 4 — Router (2026-11-14)

### Ne yapıldı
- FastAPI router (9 uç nokta), hata işleyicileri, geçici kimlik ve servis bağımlılıkları,
  geliştirme sunucusu ve HTTP testleri yazıldı. SQLAlchemy ve gerçek auth yok.
- Kurulan paketler: fastapi 0.163.0, uvicorn 0.54.0, httpx 0.28.1 (`backend/requirements.txt`).
- Yeni hata kodu: `unauthorized` (401).

### Dosyalar
- `backend/app/core/behavioral_settings.py` (yeni: `MISSION_START`, `utc_now`)
- `backend/app/api/deps_behavioral.py` (yeni: kimlik ve servis bağımlılıkları)
- `backend/app/api/behavioral_errors_http.py` (yeni: hata işleyicileri)
- `backend/app/routers/behavioral.py` (yeni: router)
- `backend/app/behavioral_dev_app.py` (yeni: geliştirme sunucusu)
- `backend/app/schemas/behavioral.py` (`SharingIn` eklendi), `backend/app/services/behavioral_errors.py`
- `backend/tests/api/conftest.py`, `backend/tests/api/test_behavioral_api.py`,
  `backend/tests/unit/test_behavioral_settings.py` (yeni testler)

### /docs'u açma
PowerShell, `backend` klasöründen:

    .venv\Scripts\Activate.ps1
    $env:BEHAVIORAL_FIXED_NOW = "2026-11-14T09:00:00Z"
    uvicorn app.behavioral_dev_app:app --reload

Sonra tarayıcıda http://127.0.0.1:8000/docs . İsteklerde başlık: `Authorization: Bearer A007`.

### Geçici olanlar ve backend gelince değişecek yerler
| Geçici | Dosya | Değişecek yer |
|---|---|---|
| Bearer token = astronaut_id | `app/api/deps_behavioral.py` | `get_current_astronaut_id` |
| Bellek içi repository'ler (yeniden başlatınca boşalır) | `app/api/deps_behavioral.py` | `_checkin_repo`, `_test_repo`, `_weekly_repo` ve `get_checkin_service`, `get_test_service`, `get_weekly_service` |
| `MISSION_START` sabiti | `app/core/behavioral_settings.py` | `MISSION_START` (mission tablosundan okunacak) |
| Ayrı geliştirme uygulaması | `app/behavioral_dev_app.py` | Ortak `main.py` gelince `app.include_router(router)` ve `register_behavioral_error_handlers(app)` oraya eklenecek |

Router ve servisler bu değişikliklerden etkilenmez.

### Kararlar
- Doğrulama hatası işleyicisi yalnız `/api/v1/behavioral` yollarında çalışır; diğer yollarda
  FastAPI'nin varsayılan 422 biçimi aynen kalır.
- Doğrulama cevabı yalnız alan adlarını döner, gönderilen değeri geri yansıtmaz (haftalık cevaplar sızmasın).
- Demo saati `BEHAVIORAL_FIXED_NOW` ortam değişkeniyle sabitlenir; saat dilimi zorunludur.
- 401 cevabına `WWW-Authenticate: Bearer` başlığı eklenir.
- PUT check-in: yeni kayıt 201, güncelleme ve tekrar gönderim 200; her ikisinde `ETag` başlığı.

### Açık sorular
- Hata gövdesi tüm uygulamada `{"detail": {"code", "message", "fields"}}` biçiminde mi olacak,
  yoksa yalnız davranış modülünde mi?
- Backend'in auth yöntemi ne olacak (JWT mi, oturum mu)? `astronaut_id` token'dan nasıl okunacak?
- Starlette 1.10, `httpx` ile TestClient kullanımını eskimiş sayıyor (`httpx2` öneriyor). Uyarı test
  çıktısında görünüyor; ortak backend hangi sürümü seçecekse ona uyulacak.

## Adım 5 — Today, eksik veri sinyali, anomali verisi (2026-11-14)

### Ne yapıldı
- Kimlik `HTTPBearer(auto_error=False)` ile alınıyor; `/docs`'ta "Authorize" butonu var. 401 cevabı değişmedi.
- `GET /api/v1/behavioral/today`: bugünün check-in / test / haftalık durumu ve eksik veri sinyalleri.
- Anomali modülü için günlük metrik fonksiyonu (`DailyMetricsFeed.daily_metrics`, HTTP ucu yok).
- Geliştirme sunucusu `BEHAVIORAL_LOAD_SEED=1` ile `seed_output` verisini A007 için yükler.

### Dosyalar
- `backend/app/core/behavioral_settings.py` (`TEST_WEEKDAYS`, `CHECKIN_MISSING_DAYS`, `WEEKLY_INTERVAL_DAYS`)
- `backend/app/services/behavioral_calendar.py` (yeni: görev günü, test günü, ardışık eksik sayımı)
- `backend/app/services/behavioral_today.py`, `behavioral_feed.py` (yeni)
- `backend/app/repositories/behavioral_seed_loader.py` (yeni: seed -> bellek içi repository)
- `backend/app/schemas/behavioral.py` (`TodayOut`, `TodayCheckin`, `TodaySignals`)
- `backend/app/api/deps_behavioral.py`, `backend/app/routers/behavioral.py`, `backend/app/behavioral_dev_app.py`
- `backend/app/services/behavioral_weekly.py` (7 gün sabiti ayarlardan okunuyor)
- Testler: `tests/unit/test_behavioral_today.py`, `test_behavioral_feed.py`,
  `tests/api/test_behavioral_today_api.py` (yeni); `test_behavioral_settings.py`, `test_behavioral_api.py` güncellendi

### Kararlar
- `TEST_WEEKDAYS = {1, 4}`: seed ile aynı kural, **görev günü % 7** (takvim haftasının günü değil).
  Görev 1 Eylül Salı başladığı için Salı ve Cuma. Seed ile eşleştiği testle doğrulanıyor.
- Eksik check-in sayımı dünden geriye yapılır (bugün henüz bitmedi); görev başlangıcından önceki günler sayılmaz.
- Eşik 2 gün: `checkin_missing = consecutive_missed_checkin_days >= 2`.
- `tests_missing`: son 7 günde (dün dahil, bugün hariç) en az bir test günü var ve o günlerin hiçbirinde test kaydı yok.
  Geçersiz test de "yapıldı" sayılır.
- Feed'de yalnız geçerli (`valid=true`) testler; aynı gün aynı türden birden fazla varsa en son (`started_at`, sonra `id`).
- Feed'de haftalık veri yok; `DailyMetricsFeed` haftalık repository'yi parametre olarak bile almaz.
- `/today` haftalık puan içermez; yalnız son ve sonraki tarih.

### Anomali sorumlusuna not
```python
from app.api.deps_behavioral import get_metrics_feed
rows = get_metrics_feed().daily_metrics(astronaut_id, date_from, date_to)   # list[DailyMetrics]
```
- Aralıktaki her gün için bir satır (veri olmayan günler dahil), eskiden yeniye. Veri yoksa `null`.
- Satır alanları: `date`, `mission_day`, `checkin_done`, `mood_index`, `stress`, `loneliness`,
  `crew_relation`, `sleep_hours`, `sleep_quality`, `symptoms` (check-in yoksa `[]`), `pvt_mean_rt_ms`,
  `pvt_lapses`, `pvt_false_starts`, `rotation_accuracy`, `rotation_mean_rt_ms`, `checkin_missing`.
- Hatalar (`BehavioralError`): `date_from > date_to` veya görev başlangıcından önce -> `validation_error`;
  `date_to` gelecekte -> `future_date`.

### Açık sorular
- Test günleri görev gününe bağlı (Salı/Cuma). Takvim günü (ör. Pazartesi/Perşembe) mi istenir? Değişirse seed de değişmeli.
- `tests_missing` için "test kaydı" geçersiz oturumu da kapsıyor; anomali tarafı yalnız geçerli testleri mi saymalı?
- Eksik veri sinyali (`checkin_missing`) anomali modelinde ayrı bir özellik mi olacak, yoksa uyarı kuralı mı?
- Feed için `mission_start` astronot / görev başına mission tablosundan okunacak.

## Adım 6 — Belgeler (2026-11-14)

### Ne yapıldı
- `api-contract.md`, `frontend.md`, `technical-design.md` koddan güncellendi (kod esas alındı). Orijinaller ayrı commit'te.
- `api-contract.md`: belirti kodları, deneme alanları, katı tip kuralları, ETag kuralları, 404 kuralı,
  `GET /today` (signals dahil), sharing ucu, hata biçimi ve kodları, takvim, liste kuralları,
  "Anomali modülüne veri" bölümü, demo değişkenleri.
- `frontend.md`: İngilizce ekran metinleri ve `questions.json` kaynağı, `crew_relation`, `HH:MM`,
  gövdede `client_request_id`, yeni hata biçimi, `GET /today` ile Bugün sekmesi, DSST kaldırıldı, görev günü 75.
- `technical-design.md`: baştan yazılmadı; başa "Güncel olmayan kısımlar" kutusu eklendi, 27. satırdaki bozuk cümle düzeltildi.
- `open-questions.md` oluşturuldu: tüm açık sorular tek listede, kime sorulacağına göre gruplu.

### Dosyalar
- `docs/behavioral/api-contract.md`, `frontend.md`, `technical-design.md`, `open-questions.md` (yeni), `progress.md`

### Kod değişmedi
Testler aynı (260).
