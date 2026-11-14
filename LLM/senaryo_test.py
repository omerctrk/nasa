"""Senaryo testleri: her senaryoyu kart seçiminden ve modelden geçirir.

Kullanım:
  python senaryo_test.py            -> tüm senaryolar, model dahil
  python senaryo_test.py --kuru     -> yalnız kart seçimi (model çağrılmaz, saniyeler sürer)
  python senaryo_test.py uyku goz   -> yalnız adı verilen senaryolar

Tam çıktılar senaryo_ciktilari.json dosyasına yazılır.
"beklenen" alanları kodun karar verdiği kısımları denetler: acil kart, doktora yükseltme,
öneri listesi. Öneri metinleri kartlardaki onaylı cümlelerdir (action_tr); model yalnız özet ve
açıklama yazar ve bunların doğruluğunu bir insanın okuması gerekir.
"""
import json
import sys
import time

import kart_onerici as k

SENARYOLAR = {
    "uyku": {
        "aciklama": "Uyku eksikliği, dikkat hataları ve stres",
        "sapmalar": {
            "sleep_hours": {"direction": "down", "value": 5.1, "baseline": 7.2, "unit": "saat"},
            "pvt_lapses": {"direction": "up", "value": 9, "baseline": 3},
            "stress": "up",
        },
        "beklenen": {"acil": None, "yukselt": False},
    },
    "goz": {
        "aciklama": "Görme değişiklikleri (SANS şüphesi)",
        "sapmalar": {
            "blurred_vision": "up",
            "visual_acuity": "down",
            "eye_pressure": "up",
            "headache": "up",
        },
        # göz içi basıncı için önlem kartı yok (vision-06 bir deney bulgusu) -> hekime
        "beklenen": {"acil": None, "yukselt": True, "onerisiz": ["eye_pressure"]},
    },
    "psikososyal": {
        "aciklama": "Ruh hali düşüşü, yalnızlık, ekip ilişkisi",
        "sapmalar": {"mood_index": "down", "loneliness": "up", "crew_relation": "down"},
        "beklenen": {"acil": None, "yukselt": False},
    },
    "kardiyo": {
        "aciklama": "İniş sonrası: düşük tansiyon, baş dönmesi, hızlı nabız",
        "baglam": ("general", "landing"),
        "sapmalar": {
            "systolic_bp": {"direction": "down", "value": 96, "baseline": 118, "unit": "mmHg"},
            "dizziness": "up",
            "heart_rate": {"direction": "up", "value": 98, "baseline": 62, "unit": "atım/dk"},
        },
        "beklenen": {"acil": None, "yukselt": False},
    },
    "enfeksiyon": {
        "aciklama": "Ateş, boğaz ağrısı, öksürük: akut önlem kartı yok -> hekime",
        "sapmalar": {
            "body_temp": {"direction": "up", "value": 38.2, "baseline": 36.7, "unit": "C"},
            "sore_throat": "up",
            "cough": "up",
        },
        "beklenen": {"acil": None, "yukselt": True,
                     "onerisiz": ["body_temp", "sore_throat", "cough"]},
    },
    "sirt": {
        "aciklama": "Tek bulgu: sırt ağrısı",
        "sapmalar": {"back_pain": "up"},
        "beklenen": {"acil": None, "yukselt": False},
    },
    "spo2": {
        "aciklama": "Düşük SpO2: maske önerisi (resp-11) çıkmalı VE doktora yükseltilmeli",
        "sapmalar": {
            "spo2": {"direction": "down", "value": 91, "baseline": 97, "unit": "%"},
            "heart_rate": "up",
            "respiratory_rate": "up",
        },
        "beklenen": {"acil": None, "yukselt": True, "onerisiz": ["respiratory_rate"],
                     "kart": "resp-11"},
    },
    "acil_solunum": {
        "aciklama": "Öksürük + nefes darlığı + hızlı solunum -> gaz embolisi acil kartı",
        "sapmalar": {"cough": "up", "shortness_of_breath": "up", "respiratory_rate": "up"},
        "beklenen": {"acil": "emerg-02", "yukselt": True},
    },
    "acil_radyasyon": {
        "aciklama": "Bulantı + yorgunluk + cilt lezyonu -> radyasyon acil kartı",
        "baglam": ("general", "spe"),
        "sapmalar": {"nausea": "up", "fatigue": "up", "skin_lesion": "up"},
        "beklenen": {"acil": "rad-01", "yukselt": True},
    },
    "tek_bulanti": {
        "aciklama": "Yalnız bulantı: acil kart TETİKLENMEMELİ",
        "sapmalar": {"nausea": "up"},
        "beklenen": {"acil": None, "yukselt": False},
    },
    "eslesmeyen": {
        "aciklama": "Kartı olmayan bulgular: model çağrılmaz, doktora yükseltilir",
        "sapmalar": {"diastolic_bp": "up", "glucose": "up"},
        "beklenen": {"acil": None, "yukselt": True},
    },
    "karisik": {
        "aciklama": "Biri kartlı, biri kartsız: öneri gelir VE doktora yükseltilir",
        "sapmalar": {"sleep_hours": "down", "diastolic_bp": "up"},
        "beklenen": {"acil": None, "yukselt": True},
    },
}


def calistir(ad, senaryo, kartlar, kuru):
    sapmalar, beklenen = senaryo["sapmalar"], senaryo["beklenen"]
    baglam = senaryo.get("baglam")      # None -> kart_onerici.AKTIF_BAGLAM
    secilen, acil_kartlar = k.kart_sec(sapmalar, kartlar, baglam=baglam)
    eslesmeyen = k.eslesmeyenler(sapmalar, kartlar, baglam)
    aksiyonsuz = k.aksiyonsuzlar(sapmalar, secilen)
    acil = [kart["id"] for kart, _, _ in acil_kartlar]

    print(f"\n=== {ad}: {senaryo['aciklama']}" + (f"  [bağlam: {', '.join(baglam)}]" if baglam else ""))
    for kart, e, p in acil_kartlar:
        print(f"    ACİL  {kart['id']:10} {e}")
    for kart, e, p in secilen:
        print(f"    {kart['id']:12} {kart['type']:14} puan={p:.2f} {e}")
    if eslesmeyen:
        print(f"    eşleşmeyen: {eslesmeyen}")
    if aksiyonsuz:
        print(f"    önlem kartı yok: {aksiyonsuz}")

    sorunlar = []
    if beklenen["acil"] and beklenen["acil"] not in acil:
        sorunlar.append(f"beklenen acil kart yok: {beklenen['acil']}")
    if not beklenen["acil"] and acil:
        sorunlar.append(f"beklenmeyen acil kart: {acil}")

    sonuc = None
    if not kuru:
        t = time.time()
        sonuc = k.oner(sapmalar, kartlar, baglam=baglam)
        sure = time.time() - t
        print(f"    model: {sure:.1f} sn, {sonuc.get('attempts', 0)} deneme | "
              f"açıklama={len(sonuc['explanations'])} öneri={len(sonuc['recommendations'])} "
              f"atılan={len(sonuc['dropped'])} yükselt={sonuc['escalate_to_physician']} "
              f"{sonuc['escalation_reasons']}")
        for a in sonuc["explanations"]:
            print(f"      (açıklama) {a['text']}  <- {a['card_ids']}")
        for o in sonuc["recommendations"]:
            print(f"      [{o['priority']}] {o['action']}  <- {o['card_ids']}")
            print(f"          ölçüm: {o['rationale']}")
        if sonuc["dropped"]:
            print("    atılanlar:")
            for a in sonuc["dropped"]:
                print(f"      ({a['reason']}) {a.get('action') or a.get('text')}")

        if sonuc.get("error"):
            sorunlar.append(sonuc["error"])
        if sonuc["escalate_to_physician"] != beklenen["yukselt"]:
            sorunlar.append(f"yükseltme beklenen={beklenen['yukselt']} "
                            f"gerçek={sonuc['escalate_to_physician']}")
        beklenen_oneri = [kart["id"] for kart, _, _ in secilen if k._onerilebilir(kart)]
        gosterilen = [o["card_ids"][0] for o in sonuc["recommendations"]]
        if sorted(beklenen_oneri) != sorted(gosterilen):
            sorunlar.append(f"öneri listesi beklenenden farklı: {gosterilen} / {beklenen_oneri}")
        if sonuc["cards_without_action_tr"]:
            print(f"    action_tr alanı olmadığı için gösterilmeyen önlem kartları: {sonuc['cards_without_action_tr']}")
        if not sonuc["summary"] and sonuc.get("attempts"):
            sorunlar.append("model özeti boş")
        for m in beklenen.get("onerisiz", []):
            if any(m in o["metrics"] for o in sonuc["recommendations"]):
                sorunlar.append(f"önlem kartı olmayan metrik için öneri çıktı: {m}")
        if beklenen.get("kart") and beklenen["kart"] not in [kart["id"] for kart, _, _ in secilen]:
            sorunlar.append(f"beklenen kart seçilmedi: {beklenen['kart']}")
        if beklenen["acil"] and not sonuc["emergency"]:
            sorunlar.append("acil durum bloğu boş")

    print("    SONUÇ:", "GEÇTİ" if not sorunlar else "SORUN -> " + "; ".join(sorunlar))
    return {"senaryo": ad, "sorunlar": sorunlar, "cikti": sonuc}


if __name__ == "__main__":
    argumanlar = sys.argv[1:]
    kuru = "--kuru" in argumanlar
    istenen = [a for a in argumanlar if not a.startswith("--")] or list(SENARYOLAR)
    bilinmeyen = [a for a in istenen if a not in SENARYOLAR]
    if bilinmeyen:
        sys.exit(f"Bilinmeyen senaryo: {bilinmeyen}. Seçenekler: {list(SENARYOLAR)}")

    kartlar = k.kartlari_yukle("knowledge_cards.json")
    sonuclar = [calistir(ad, SENARYOLAR[ad], kartlar, kuru) for ad in istenen]

    sorunlu = [s["senaryo"] for s in sonuclar if s["sorunlar"]]
    print(f"\n{len(sonuclar) - len(sorunlu)}/{len(sonuclar)} senaryo geçti."
          + (f" Sorunlu: {sorunlu}" if sorunlu else ""))
    if not kuru:
        with open("senaryo_ciktilari.json", "w", encoding="utf-8") as f:
            json.dump(sonuclar, f, ensure_ascii=False, indent=2)
        print("Tam çıktılar: senaryo_ciktilari.json")
