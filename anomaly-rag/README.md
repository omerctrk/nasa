# anomaly-rag (Aynur)

`anomaly` dalından gelen, ana sistemden **ayrı** duran deneysel çalışma: bilgi kartları için
gömme (embedding) ve vektör veritabanı (Qdrant) altyapısı.

- Ana backend `backend/` klasöründedir; bu klasör onun parçası değildir ve Docker'daki
  ana servisler bunu çalıştırmaz.
- Klasör yapısı dalın kökündeki hâliyle korunur; çalıştırmak için bu klasörün içinden
  komut verin (ör. `cd anomaly-rag && pytest`).
- Ana sisteme alınıp alınmayacağı ekip kararıdır.
