# Davranış Modülü — Açık Sorular

Nov 14, 2026 · @Şule

Tek liste; kime sorulacağına göre gruplu. Her madde: **soru · şu anki varsayımımız · etkilenen dosya**.
Varsayımlar kodda uygulanmış durumda; cevap farklı gelirse kod ve `api-contract.md` birlikte güncellenir.
Kaynak: `progress.md` Adım 1–5 açık soruları + belge senkronizasyonu (Adım 6).

## Ömer & Aybala (backend)

| # | Soru | Şu anki varsayımımız | Etkilenen dosya |
| --- | --- | --- | --- |
| B1 | Tekrar gönderim kimliği gövdede `client_request_id` mi, `Idempotency-Key` başlığı mı? | Gövdede `client_request_id` (UUID v4); aynı astronot + kimlik → ilk kayıt 200 | `app/schemas/behavioral.py`, `app/services/behavioral_tests.py`, `behavioral_weekly.py` |
| B2 | Şema v5.0'da bilişsel test zaman sütunları: `taken_at` mı, `started_at` / `finished_at` / `date` mi? | API ve repository `started_at` / `finished_at` / `date`; seed hâlâ `taken_at` + `duration_s` üretiyor, yükleyici çeviriyor | `app/repositories/behavioral.py`, `scripts/seed_behavioral.py`, `app/repositories/behavioral_seed_loader.py` |
| B3 | `duration_s` ve `device` sütunları tabloda var mı? | `device` var (isteğe bağlı, ≤ 64); `duration_s` yok (`finished_at − started_at`) | `app/repositories/behavioral.py`, `app/schemas/behavioral.py` |
| B4 | `correct_count` sütunu kalacak mı? | API'de yok; puanlama hep `null` döndürüyor; seed hâlâ yazıyor | `app/services/behavioral_scoring.py`, `scripts/seed_behavioral.py` |
| B5 | Check-in ETag'i için `version` sütunu mu, SQL Server `rowversion` mı? | `version` tam sayı sütunu; ETag `"c-{id}-{version}"` | `app/repositories/behavioral.py` (`CheckinRecord`), `app/services/behavioral_checkins.py` (`etag`) |
| B6 | `symptoms`, ham denemeler ve `answers` tabloda JSON metni mi, JSON sütunu mu? Dönüşüm nerede? | Seed JSON metni yazıyor; repository kayıtlarında liste / sözlük; dönüşüm SQL repository'de yapılacak | `app/repositories/behavioral.py`, `scripts/seed_behavioral.py` |
| B7 | Hata gövdesi tüm uygulamada `{"detail": {"code", "message", "fields"}}` mi olacak? | Yalnız `/api/v1/behavioral` yollarında; diğer yollarda FastAPI varsayılanı | `app/api/behavioral_errors_http.py` |
| B8 | Kimlik doğrulama yöntemi ne (JWT, oturum)? `astronaut_id` token'dan nasıl okunacak? | Geçici: `Bearer <id>`, token = astronot kimliği (`^A\d{3}$`) | `app/api/deps_behavioral.py` (`get_current_astronaut_id`) |
| B9 | Ekip doktoru rolü: yalnız `share_with_crew_medical = true` kayıtları görme kuralı nasıl uygulanacak? | Henüz yok; herkes yalnız kendi kayıtlarını görür | `app/services/behavioral_weekly.py`, `app/routers/behavioral.py` |
| B10 | Başkasının kaydına 404 (403 değil) kabul mü? | 404 `not_found` / `checkin_not_found` (varlık sızdırılmaz) | Tüm servisler, `api-contract.md` |
| B11 | `mission_start` mission tablosundan mı okunacak (astronot / görev başına)? | Sabit `2026-09-01` | `app/core/behavioral_settings.py` (`MISSION_START`) |
| B12 | Paket sürümleri: fastapi 0.163.0, pydantic 2.14.3, uvicorn 0.54.0, httpx 0.28.1 ortak backend'le uyumlu mu? Starlette 1.10, TestClient için `httpx` yerine `httpx2` öneriyor (test çıktısında uyarı) | Bu sürümler sabitlendi; uyarı gizlenmedi | `backend/requirements.txt` |
| B13 | Haftalık erken gönderimde 409 `weekly_not_due` uygun mu, yoksa kabul edip uyarı mı? | 409, mesajda sonraki tarih | `app/services/behavioral_weekly.py` |
| B14 | `GET /today` ve `PUT /weekly-assessments/{id}/sharing` uç noktaları kabul mü? | Uygulandı, onay bekliyor | `app/routers/behavioral.py` |
| B15 | `get_db` kalıbı: SQL repository'ler oturumu nasıl alacak, commit nerede yapılacak? | Repository commit yapmaz; commit istek sonunda (`get_db`) yapılır; servis fabrikaları `deps_behavioral.py`'de | `app/api/deps_behavioral.py` |
| B16 | Ortak `main.py` ne zaman hazır? Router ve hata işleyicisi oraya nasıl eklenecek? | Şimdilik ayrı `behavioral_dev_app.py`; `include_router(router)` + `register_behavioral_error_handlers(app)` yeterli | `app/behavioral_dev_app.py` |

## Anomali sorumlusu

| # | Soru | Şu anki varsayımımız | Etkilenen dosya |
| --- | --- | --- | --- |
| A1 | `knowledge_cards.json` içindeki metrik adları ve belirti kodları İngilizce mi, `daily_metrics` adlarıyla birebir aynı mı (ör. `pvt_mean_rt_ms`, `rotation_accuracy`, `crew_relation`)? | Dosya bu depoda yok, kontrol edilemedi; adların `api-contract.md` → "Anomali modülüne veri" ile aynı olması gerekiyor | `knowledge_cards.json` (anomali tarafı), `app/services/behavioral_feed.py` |
| A2 | `daily_metrics(astronaut_id, date_from, date_to)` imzası ve kuralları uygun mu (her gün bir satır, veri yoksa `null`, gelecek / görev öncesi tarih hata)? | Uygun; `get_metrics_feed()` ile alınır, HTTP ucu yok | `app/services/behavioral_feed.py`, `app/api/deps_behavioral.py` |
| A3 | Check-in eksik eşiği 2 gün uygun mu? `checkin_missing` modelde ayrı bir özellik mi, uyarı kuralı mı? | 2 gün, dünden geriye; satırda bool alan olarak veriliyor | `app/core/behavioral_settings.py` (`CHECKIN_MISSING_DAYS`) |
| A4 | Testler: feed yalnız geçerli testleri kullanıyor, `/today` → `tests_missing` ise geçersiz testi "yapıldı" sayıyor. Anomali tarafı eksik test sinyalinde hangisini ister? | Feed: yalnız geçerli ve günün en sonu; `tests_missing`: geçersiz de sayılır | `app/services/behavioral_feed.py`, `app/services/behavioral_today.py` |

## Frontend

| # | Soru | Şu anki varsayımımız | Etkilenen dosya |
| --- | --- | --- | --- |
| F1 | Sahte veri (fixture) dosyaları şema netleşene kadar ertelendi; bu süre frontend için uygun mu? | Ertelendi; `contracts/behavioral/` altında yalnız `questions.json` var | `contracts/behavioral/`, `frontend.md` |
| F2 | Geliştirme sunucusu ve `/docs` ile deneme yeterli mi? Frontend başka porttan çağıracaksa CORS gerekecek (şu an CORS ayarı yok) | `/docs` ile deneme; CORS gerekirse geliştirme sunucusuna eklenir | `app/behavioral_dev_app.py` |

## Ekip / sunum

| # | Soru | Şu anki varsayımımız | Etkilenen dosya |
| --- | --- | --- | --- |
| E1 | Demo günü 75 (2026-11-14). Belgelerdeki "74. gün" düzeltildi; sunum metinleri ve ortak belgeler de güncellenmeli | Demo günü 75; seed 1–74. günleri kapsar | `frontend.md`, `api-contract.md`, sunum |
| E2 | Demo saati nasıl sabitlenecek? Ortak backend'de de `BEHAVIORAL_FIXED_NOW` benzeri bir ayar olacak mı? | Geliştirme sunucusunda `BEHAVIORAL_FIXED_NOW=2026-11-14T09:00:00Z` | `app/core/behavioral_settings.py` (`utc_now`) |
| E3 | Test günleri görev gününe bağlı (görev günü % 7 ∈ {1, 4} → Salı ve Cuma). Takvim günü (ör. Pazartesi / Perşembe) mi istenir? | Seed ile aynı kural; değişirse seed de değişmeli | `app/core/behavioral_settings.py` (`TEST_WEEKDAYS`), `scripts/seed_behavioral.py` |

## Kapandı

| Soru | Karar |
| --- | --- |
| Seed `client_request_id` UUID5, API UUID4 istiyor | Seed API'den geçmiyor; değişiklik gerekmiyor (Adım 2) |
| Görev günü tutarsızlığı (14 Kasım = 74 mü 75 mi) | 1 Eylül = 1. gün; seed düzeltildi, 14 Kasım = 75 (Adım 3) |
| `crew` mı `crew_relation` mı; belirti kodları Türkçe mi | `crew_relation`; 12 İngilizce kod, tek kaynak `SYMPTOM_CODES` (Adım 1) |
| Saat biçimi | `HH:MM`, saniyesiz (Adım 1) |
| `from` / `to` dahil mi | İkisi de dahil (Adım 2) |
| Check-in GET'te `ETag` dönüyor mu | Dönüyor (Adım 4) |
| Liste cevabının şekli | `{"items": [...], "next_cursor": ...}`, cursor opak (Adım 2) |
| Ölçek metinleri | Resmi İngilizce, `questions.json` içinde (Adım 0) |
| Sembol-rakam testi (DSST) | Kapsam dışı; şema `dsst` türünü reddeder |
| Demo saati mekanizması | `BEHAVIORAL_FIXED_NOW` eklendi (Adım 4); ortak backend'deki karşılığı E2'de |
