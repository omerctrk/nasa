# ASTRA HEALTH Backend

FastAPI + SQLAlchemy 2.0 + Alembic + MS SQL Server 2022. Kaynaklar: `BACKEND_TABLO_SEMASI.md` v5.0 (SANS API/veri akışı rev.3) ve iş bölümü PDF'si.

## İlk kurulum (proje kökü `astra-health/` içinden)

```bash
cp backend/.env.example .env       # değerleri doldur; .env git'e girmez
docker compose run --rm migrate    # db → bootstrap → migration (sa)
docker compose run --rm seed       # sözlük, M01, A007 + gösterim profili, 2 giriş hesabı (astra_app)
docker compose up api              # API, astra_app hesabıyla açılır
```

Kontrol: http://localhost:8000/api/v1/health/ready adresi `"db_user": "astra_app"` döndürmeli. `sa` değil `astra_app` yazması, API'nin sınırlı hesapla çalıştığını kanıtlar. Swagger: http://localhost:8000/docs

## Kurulum sırası (şema §8)

| Adım | Hesap | Ne yapar |
|---|---|---|
| `db` | — | MS SQL açılır |
| `bootstrap` (`scripts/bootstrap.py`) | sa | AstraHealth veritabanı, `astra_app` ve `astra_eval` login + USER. Tekrar çalıştırılabilir |
| `migrate` (Alembic) | sa | Şemalar, roller, üyelik, GRANT/DENY, tablolar, VIEW'lar |
| `api` | **astra_app** | Uygulama + işçi. Migration çalıştırmaz, tablo oluşturamaz |

| SQL hesabı | Rol | Erişim |
|---|---|---|
| astra_app | astra_app_role | core, behavioral, sans, anomaly, ops: tablo oluştukça gereken veri işlemleri · evaluation: **DENY** |
| astra_eval | astra_eval_role | evaluation: A4'te verilir · operasyonel tablolar: yok |

SANS için SQL hesabı **yoktur** (rev.3). SANS veriyi backend'den yalnız API ile alır; `.env` içindeki `SANS_API_*` ayarları sadece `api` servisine gider.

## Tablo izinleri: nesne oluştukça (A1–A5)

A0 tablo izni vermez. Her migration, oluşturduğu tabloya gereken izni kendisi verir:

```python
from migrations.helpers import APP_ROLE, grant, revoke

def upgrade():
    ...  # tabloları oluştur
    grant("core.Missions", APP_ROLE, "SELECT")
    grant("core.Users", APP_ROLE, "SELECT, INSERT, UPDATE")

def downgrade():
    revoke("core.Users", APP_ROLE, "SELECT, INSERT, UPDATE")
    revoke("core.Missions", APP_ROLE, "SELECT")
    ...
```

`grant()` yalnız SELECT / INSERT / UPDATE / DELETE kabul eder; ALTER, CONTROL gibi yetkiler hata verir.

## Code-first iş akışı (yalnız Aybala)

1. `app/models/` altına modeli yaz (dosya adları `app/models/__init__.py` içinde listeli) ve import et.
2. Migration üret:
   ```bash
   docker compose run --rm migrate alembic revision --autogenerate --rev-id 0003 -m "sans ve anomaly tabloları"
   ```
3. Üretilen dosyayı **oku**. Filtreli UQ'lar, CHECK'ler, VIEW'lar ve `grant()` satırları elle tamamlanır.
4. Uygula: `docker compose run --rm migrate`
5. Sadece incelemek için: `docker compose run --rm migrate alembic upgrade head --sql` (veritabanına dokunmaz).
6. Model ile veritabanı aynı mı: `docker compose run --rm migrate alembic check` → "No new upgrade operations detected." beklenir.

Merge edilmiş migration değiştirilmez; düzeltme için yeni migration açılır. Sıfırdan kurulum: `docker compose down -v`.

## Yetki kabul testi (gerçek sınırlı hesapla, sa ile değil)

```bash
# astra_app tablo oluşturamamalı → "CREATE TABLE permission denied" beklenir
docker compose exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -C -d AstraHealth \
  -U astra_app -P "<ASTRA_APP_DB_PASSWORD>" -Q "CREATE TABLE core.deneme (id INT)"

# A1'den sonra: astra_app core'u okuyabilmeli ama silememeli
docker compose exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -C -d AstraHealth \
  -U astra_app -P "<ASTRA_APP_DB_PASSWORD>" -Q "SELECT COUNT(*) FROM core.Missions"      # 0
docker compose exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -C -d AstraHealth \
  -U astra_app -P "<ASTRA_APP_DB_PASSWORD>" -Q "DELETE FROM core.Missions"               # DELETE permission denied

# A4'ten sonra: astra_app evaluation'ı okuyamamalı → "SELECT permission was denied"
docker compose exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -C -d AstraHealth \
  -U astra_app -P "<ASTRA_APP_DB_PASSWORD>" -Q "SELECT * FROM evaluation.gercek_durum"
```

## Gerçek DB testleri (migrate'ten sonra)

```bash
docker compose run --rm -e RUN_DB_TESTS=1 api pytest tests/integration -v
```
astra_app hesabıyla çalışır; her test ROLLBACK edilir, veritabanında iz bırakmaz.
`tests/unit/test_migrations.py` ise DB'siz olarak her migration'ın modellerle aynı DDL'i
ürettiğini ve her tablonun DELETE'siz izin aldığını denetler.

## Bağımlılıklar ve testler

`pyproject.toml` tanımdır, `requirements.lock.txt` doğrulanmış çözümdür. Yeni paket eklerken ikisi birlikte güncellenir:

```bash
pip install pip-tools
pip-compile --strip-extras --extra dev pyproject.toml -o requirements.lock.txt
pip install -r requirements.lock.txt && pytest
```

## Durum

- [x] A0: klasör yapısı, tek Base, 6 şema, 2 rol (SANS rolü yok), evaluation DENY, bootstrap, ayrı migrate, sınırlı API hesabı, `/api/v1/health/live|ready`
- [x] A1 core: Missions/Astronauts/Users, FK/UQ/CHECK, filtreli UQ, app izinleri (DELETE yok), flight_day eşlemesi, kimlik repository'si
- [x] Ortak sözleşme: common.py, interfaces.py, records.py, hata zarfı, ayarlar, fixture'lar (contracts/backend-contract.md)
- [x] A2 sans (6) + anomaly (3) tablo, migration 0003 + izinler, sonuç repository'si (save_anomaly_result, save_sans_analysis, update_sans_state)
- [x] A3 ops: AnalysisJobs (+request_json önerisi), Alerts, NotificationEvents, EventReceipts; migration 0004; iş ve alarm repository'leri (Ömer'e teslim)
- [x] A4 behavioral (3) + evaluation.gercek_durum; migration 0005; eval yalnız astra_eval_role'e açık
- [x] A5 sans.gorev, sans.profil, anomaly.v_measurements (migration 0006, SELECT izni); get_measurements, get_sans_context — Repository arayüzünün tamamı hazır
- [x] A6 seed: tekrar çalıştırılabilir; parolalar .env'den, Argon2 (app/core/passwords.py). Geçici değerler scripts/seed.py içinde TODO(ekip) ile işaretli
- [x] 0007: `dbo.knowledge_cards` ek tablosu. `astra_app_role` için SELECT/INSERT/UPDATE/DELETE; `astra_collaborator` üyelikten devralır. Diğer tablolarda DELETE izni yoktur.
- [x] A7 veri giriş API'leri (/api/v1/me/...): check-in PUT+ETag, haftalık, bilişsel, fizyolojik. Yetki: Ömer'in app/core/security.py dependency'leri (app/routers/deps.py yeniden dışa aktarır)
- [x] Okuma uçları: GET /me/profile, /me/checkins, /me/weekly-assessments, /me/cognitive-tests, /me/measurements; GET /ground/astronauts, /ground/astronauts/{id}/measurements
- [x] SANS/göz modülü kapsam dışı: göz oturumu, baş ağrısı ve göz okuma uçları kaldırıldı; eski DB tabloları korunuyor.
- [x] Seed: Ömer'in history-policy.json'undaki 5 fizyolojik ölçüm (heart_rate, systolic_bp, diastolic_bp, blood_glucose, body_temperature)
- [ ] A8 sentetik veri (fizyolojik + davranış) · ~~A9 a007_aktarim.json~~ (SANS kapsam dışı)
