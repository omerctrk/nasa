# Davranış ve Refleks Modülü (frontend)

"Davranışsal ve Refleks Modülü – Frontend Arayüz Belgesi"ne göre yazıldı.
Frontend puan hesaplamaz, renk üretmez, veri saklamaz. Ham sonuçları gönderir, backend'in döndürdüğünü gösterir.

## Sahte veri ↔ gerçek API

| Değişken | Varsayılan | Açıklama |
| --- | --- | --- |
| `VITE_USE_MOCK` | `true` | `false` olunca `/api/v1/behavioral/...` çağrılır |
| `VITE_API_BASE_URL` | `/api/v1` | API öneki |

Belgedeki `NEXT_PUBLIC_USE_MOCK`, bu proje Vite kullandığı için `VITE_USE_MOCK` adını taşıyor.
Örnek `.env.local`:

```
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8001/api/v1
```

## Dosyalar

| Dosya | İçerik |
| --- | --- |
| `questions.ts` | **Tüm metinler.** Resmi WHO-5 / PHQ-2 / GAD-2 maddeleri buraya eklenecek (şu an yer tutucu) |
| `api.ts` | Uç noktalar, başlıklar (`If-Match`, `If-None-Match`, `Idempotency-Key`), hata mesajları |
| `types.ts` | İstek/cevap tipleri (belgedeki önerilen şekiller) |
| `timing.ts` | PVT ve döndürmenin ortak zamanlama kuralları (`performance.now()`, `visibilitychange`) |
| `mock/mockServer.ts` | Sahte backend (yalnızca demo). Puan hesapları backend'i taklit eder |
| `../../data/fixtures/behavioral/*.json` | Sahte veri dosyaları |
| `../../components/ui` | Ortak `Card`, `Button`, `PageHeader`, `FormField`, `Skeleton` |

## Backend ile netleşmesi gerekenler

- Görev günü kaynağı: şu an `GET /dashboard/me` → `{ mission_day, date }` varsayılıyor.
- Paylaşım güncellemesi gövdesi: `PUT /weekly-assessments/{id}/sharing` → `{ "share_with_crew_medical": true }` varsayıldı.
- 422 cevabında `error.details` alan adı → mesaj eşlemesi (`{ "bed_time": "..." }`) varsayıldı.

## Geliştirici ipuçları

- PVT'yi kısa denemek için adrese `?pvt_s=30` ekleyin (yalnızca geliştirme; gerçek süre 180 sn).
- Ağ hatasını sahte veriyle denemek: konsolda `localStorage.setItem('ahms-mock-offline','1')`, geri almak için `removeItem`.
- Geliştirme modunda gönderilen ham denemeler ve PVT bekleme süreleri konsola yazılır.
- Sahte veri bellekte tutulur; sayfa yenilenince başa döner.
