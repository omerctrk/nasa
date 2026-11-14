# Ö1 auth entegrasyonu ve Aşama 3 kabul durumu

14 Kasım 2026. Kaynak repository: https://github.com/omerctrk/nasa.git
İncelenen uzak branch: `bachand`, başlangıç commit'i
`a4156cd323ec4c72b316e634095e05680968b2ad`. Yerel çalışma branch'i: `feat/auth`.

## Tamamlanan kod entegrasyonu

- Aşama 2 auth kodu mevcut ortak sözleşmeye uyarlandı; common.py ve repository
  arayüzleri ikinci kez oluşturulmadı.
- `IdentityRepository`, `UserRecord`, `AstronautRecord` ve ortak `CurrentUser`
  kullanılır. Auth UserResponse ortak kullanıcıyı ek doğrulamalarla genişletir.
- `auth_runtime.auth_repository` her çağrıda gerçek SessionLocal açar ve mevcut
  SqlAlchemyRepository döndürür. Factory'ye giriş, okuma ve kapanış aynı worker
  thread içinde gerçekleşir. Session başka request/thread'den devralınmaz.
- main.py auth'u `/api/v1/auth/login` ve `/api/v1/auth/me` yollarına kaydeder.
- Merkezi Settings içindeki JWT_SECRET/JWT_ISSUER/JWT_AUDIENCE/access_token_seconds
  kullanılır. Önceki bağımsız hazırlıktaki AUTH_ önekli ortam adları kullanılmaz.
- JWT secret en az 32 UTF-8 bayt olmalı; eksik/kısa secret ile API başlamaz.
  API runtime DB_USER değeri astra_app olmalıdır. Bu kontrol gerçek SQL yetki
  testlerinin yerine geçmez.
- Compose API servisine yalnız ilgili auth ayarları eklendi.
- Ortak ErrorCode korunur: auth 401 UNAUTHORIZED, auth 403 FORBIDDEN.
  Yanlış e-posta/parola aynı genel mesajı verir; hesap durumu parola doğrulandıktan
  sonra açıklanır. 401 WWW-Authenticate: Bearer taşır.
- Hata işleyicisi validator mesajından ham kullanıcı girdisi veya traceback/SQL
  exception ayrıntısı loglamaz. Her hata trace_id taşır. Login/me ve hata yanıtları
  Cache-Control: no-store taşır. Ortak handler tek kez merkezi main.py'de kurulur.
- UserRecord.password_hash repr ve genel model_dump çıktısından çıkarıldı.
- Argon2/PyJWT ortak pyproject ve lock'a eklendi. Windows'ta lock yeniden çözüldü;
  platforma özgü uvloop çıkarıldı ve pytest'in colorama bağımlılığı eklendi.
  Docker/Linux'ta uvicorn varsayılan asyncio event loop ile çalışabilir; Docker
  build'i bu makinede çalıştırılmadı.

## Aybala'nın kullanım biçimi

Veri yazma endpoint'lerinde `Depends(require_active_astronaut)` kullanılır;
astronaut_id dönen CurrentUser'dan türetilir. Kule endpoint'lerinde
`Depends(require_ground_control)` kullanılır. Genel korumalı okumalarda
`Depends(current_user)` kullanılabilir. Kayıt sahipliği ve paylaşım izni ayrıca
ilgili serviste kontrol edilir; dependency tek başına başka kişinin kaydını açmaz.

Seed parola hash'i için `PasswordManager().hash_password(password)` kullanılabilir.
Parola ortamdan veya kontrollü kurulum girdisinden alınmalı; kaynağa yazılmamalıdır.
Yeni seed scripti, ORM veya migration bu çalışmada oluşturulmadı.

## Testler

- Mevcut A0/A1/A2 ve ortak sözleşme testleri korundu.
- Parola/JWT, rol/profil/aktiflik, değişen kullanıcı, HTTP hata güvenliği,
  kaynak kapsamı kullanım örneği, factory kapanışı ve gerçek repository bağlantı
  yapısı için DB'siz testler eklendi.
- `tests/integration/test_auth_db.py`: gerçek MSSQL'de astra_app kontrolü, gerçek
  repository ile login, hesabı pasifleştirdikten sonra token reddi, gösterim profili
  yazım reddi ve evaluation/DDL izin kontrolü. Geçici kayıtlar mevcut rollback
  fixture'ıyla temizlenir. A6 seed veya gerçek demo kullanıcılarını değiştirmez.
- DB testleri mevcut RUN_DB_TESTS=1 kapısına tabidir; varsayılan test çalıştırması
  bunları atlar. Atlanmış DB testi başarılı gerçek SQL kabulü sayılmaz.

DB'siz doğrulama, backend içinden:

```text
python -B -m pytest tests/unit -q
```

DB hazır/migration uygulanmış ortamda:

```text
docker compose run --rm -e RUN_DB_TESTS=1 api pytest tests/integration -v
```

## Tamamlanması beklenen gerçek kabul

- İncelenen bachand commit'inde A0/A1/A2 var; A6 seed ve A7 veri API'leri yok.
- Bu checkout'ta gerçek DB bağlantı secret'ları/.env bulunmadı. Docker komutu da
  bu makinede mevcut değil. SQL Server kurulumu veya migration çalıştırılmadı.
- Windows Uygulama Denetimi, kurulan pyodbc native DLL'inin yüklenmesini engelledi.
  OS ilkesi aşılmadı; gerçek SQL kabul testleri bu makinede çalıştırılamadı.
- A6 hesaplarıyla HTTP login/me, A7 veri API'lerinde gerçek yetki kontrolleri ve
  sınırlı hesapla DB testleri uygun SQL ortamında çalıştırılmalıdır.

Bu nedenle Aşama 3'ün kod uyarlaması hazırdır; gerçek DB/seed kabulü tamamlanmadı.
Çalışma feat/auth feature branch'indedir; uzak bachand branch'ine doğrudan push veya
merge yapılmaz. İnceleme için feature branch → PR → Aybala incelemesi akışı
izlenmelidir.
