# AstraHealth — yeni kurulumda veri aktarımı

Bu akış, bir kişi `version1` branch'ini klonlayıp kendi boş SQL Server
veritabanını oluşturduktan sonra, merkezî AstraHealth verisini o yeni
veritabanına yükler. Hedef DB backup restore ile ezilmez.

## Paketin kapsamı

`backend/scripts/export_database_transfer.py` uygulama tablolarındaki satırları
taşınabilir JSON'a aktarır. SQL Server login'leri, `.env` parolaları, SA
parolası ve JWT sırları aktarılmaz. `core.Users` içindeki parola hash'leri ise
uygulama verisi olduğundan pakete dahildir.

`0008_m01_mission_day_zero.py`, canlı merkezî DB ile karşılaştırılarak eklenmiş
uyumluluk revisionıdır. `0007` ve `0008` arasında tablo, kolon veya view farkı
bulunmamıştır; `0008` temiz kurulumun veri paketiyle aynı Alembic revizyonuna
ulaşmasını sağlar.

## Merkezî bilgisayarda export

Proje kökünde çalıştırın:

```powershell
$transferPath = (Resolve-Path transfer).Path
docker compose run --rm -v "${transferPath}:/transfer" -e PYTHONPATH=/app migrate `
  python scripts/export_database_transfer.py /transfer/AstraHealth-data.json
```

Oluşan `transfer/AstraHealth-data.json` dosyasını güvenli bir kanalla hedef
bilgisayara verin. Bu dosyayı Git'e eklemeyin veya herkese açık depoya koymayın.

## Hedef bilgisayarda kurulum ve import

1. `version1` branch'ini klonlayın ve proje kökünde güvenli bir `.env` oluşturun.
   Hedefin kendi `MSSQL_SA_PASSWORD`, `ASTRA_APP_DB_PASSWORD`,
   `ASTRA_EVAL_DB_PASSWORD` ve `JWT_SECRET` değerleri olmalı.
2. Boş DB ve şemayı oluşturun:

```powershell
docker compose up -d db bootstrap
docker compose run --rm migrate
```

3. Size verilen `AstraHealth-data.json` dosyasını proje kökündeki `transfer/`
   klasörüne koyun.
4. Hedef DB boşken ve yalnızca migrationlar uygulanmışken import edin:

```powershell
$transferPath = (Resolve-Path transfer).Path
docker compose run --rm -v "${transferPath}:/transfer" -e PYTHONPATH=/app migrate `
  python scripts/import_database_transfer.py /transfer/AstraHealth-data.json
```

5. Uygulamayı başlatın:

```powershell
docker compose up -d api
```

## Güvenlik ve korumalar

- Import yalnız boş uygulama tablolarına izin verir; dolu hedef DB'yi
  karıştırmaz veya üzerine yazmaz.
- Import kaynak ve hedef Alembic revizyonlarının eşit olmasını zorunlu tutar.
- Tablo/kolon farkı varsa işlem durur.
- FK sırası ve identity değerleri korunur.
- Paketi import etmek için `migrate` servisi kullanılır; bu servis hedefte SA
  hesabıyla yalnız tek seferlik aktarım yapar. Sonraki API çalışması `astra_app`
  hesabıyla devam eder.

## Doğrulanmış paket

Bu makinede üretilen `AstraHealth-data-2026-11-15.json` paketi, boş bir
`version1` DB'sine test edilmiştir: 530 satır başarıyla aktarılmış; 370 ölçüm,
2 astronot ve Alembic `0008` kaynakla eşit doğrulanmıştır.
