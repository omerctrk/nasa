"""Bilgi kartı seçimi + Qwen çağrısı + çıktı doğrulaması (sürüm 4).

İş bölümü:
  KOD   : kart seçimi, acil durum eşleşmesi, ÖNERİLER (kartın onaylı Türkçe cümlesi
          `action_tr`), öncelik, ölçüm satırı, hekime yükseltme.
  MODEL : yalnız durum özeti ve risk/belirti kartlarının Türkçe açıklaması.
Model öneri yazmaz ve seçmez; `action_tr` alanı olmayan önlem kartı öneri olarak gösterilmez.

Akış:
  1. kartlari_yukle()  -> knowledge_cards.json bir kez okunur
  2. kart_sec()        -> sapan metriklere göre kartlar; acil durum kartları ayrı döner
  3. oneriler_kur()    -> önlem kartlarından öneri listesi (kod)
  4. modele_sor()      -> özet + açıklamalar (Ollama, JSON şemalı)
  5. dogrula()         -> açıklamaların denetimi, yükseltme kararı, çıktının birleştirilmesi
  oner() hepsini sırayla çalıştırır.

Sapma girdisi iki biçimde verilebilir:
  {"sleep_hours": "down", "pvt_lapses": "up"}
  {"sleep_hours": {"direction": "down", "value": 5.1, "baseline": 7.2, "unit": "saat"}}
"""
import json
import re

MODEL = "qwen3:14b"
SECENEKLER = {"num_ctx": 4096, "num_predict": 1000, "temperature": 0, "repeat_penalty": 1.1}
UYARI = "Bu araç teşhis koymaz; karar destek amaçlıdır."
ACIL_MESAJ = "Acil durum kartı eşleşti. Aşağıdaki kartı okuyun ve uçuş hekimine hemen bildirin."

# Bir acil durum kartının tetiklenmesi için eşleşmesi gereken en az metrik sayısı.
ACIL_ESIK = 2
AKSIYON_TURLERI = ("countermeasure", "emergency")
# Henüz kapsanmamış bir metriği getiren karta verilen ek puan (metrik başına).
KAPSAMA_AGIRLIGI = 3
# Bu metrikler saptığında, öneri çıksa bile uçuş hekimine yükseltilir: {metrik: yön}.
# Yön "any" ise her iki yönde de yükseltilir.
HER_ZAMAN_YUKSELT = {"spo2": "down"}
# Kartın "context" alanı bu listede yoksa kart seçilmez (alanı olmayan kart "general" sayılır).
# Örnek: iniş günü için ("general", "landing"). Acil durum kartları bağlama bakılmadan değerlendirilir.
AKTIF_BAGLAM = ("general",)


# ---------------------------------------------------------------- 1. yükleme
def kartlari_yukle(yol="backend/config/knowledge_cards.json"):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def _yon(deger):
    return deger["direction"] if isinstance(deger, dict) else deger


# ---------------------------------------------------------------- 2. seçim
def _eslesen_metrikler(kart, sapmalar):
    """Kartın metriklerinden, sapan ve yönü uyanlar."""
    return [
        m for m in kart["metrics"]
        if m in sapmalar and kart["direction"] in ("any", _yon(sapmalar[m]))
    ]


def _baglam_uygun(kart, baglam):
    if kart["type"] == "emergency":      # acil durum kaçırılmasın diye süzülmez
        return True
    return kart.get("context", "general") in (baglam or AKTIF_BAGLAM)


def _puan(kart, eslesen):
    n = len(eslesen)
    if n == 0:
        return 0.0
    oran = n / len(kart["metrics"])          # uzun kartları kayırmayı dengeler
    yon_bonusu = 0.25 if kart["direction"] != "any" else 0.0
    return n + oran + yon_bonusu


def kart_sec(sapmalar, kartlar, k=5, en_cok_onlem=3, baglam=None):
    """(secilen, acil) döndürür; ikisi de [(kart, eşleşen_metrikler, puan), ...].

    acil    : eşiği geçen acil durum kartları. Modele gönderilmez, backend gösterir.
              Acil kart varsa secilen yalnız o kartın bağlamındaki kartlardan oluşur (ya da boştur).
    secilen : modele gidecek en çok k kart. Önce her sapan metriği bir önlem kartıyla
              kapsamaya çalışır, kalan yerleri risk/belirti kartlarıyla doldurur.
    """
    adaylar, acil = [], []
    for kart in kartlar:
        e = _eslesen_metrikler(kart, sapmalar)
        if not e:
            continue
        aday = (kart, e, _puan(kart, e))
        if kart["type"] != "emergency":
            adaylar.append(aday)
        elif len(e) >= ACIL_ESIK:
            acil.append(aday)
    acil.sort(key=lambda a: (-a[2], a[0]["id"]))

    if acil:
        # Acil durumda rutin öneri verilmez: yalnız acil kartla aynı bağlamdaki kartlar kalır.
        # Bunların arasında önlem kartı yoksa modele hiç kart gitmez.
        acil_baglam = {kart.get("context", "general") for kart, _, _ in acil} - {"general"}
        adaylar = [a for a in adaylar if a[0].get("context", "general") in acil_baglam]
        if not any(a[0]["type"] == "countermeasure" for a in adaylar):
            return [], acil
    else:
        adaylar = [a for a in adaylar if _baglam_uygun(a[0], baglam)]
    onlemler = [a for a in adaylar if a[0]["type"] == "countermeasure"]
    digerleri = [a for a in adaylar if a[0]["type"] != "countermeasure"]

    def ac_gozlu(havuz, adet, kapsanan):
        """Puan + yeni kapsanan metrik sayısına göre sırayla seç."""
        havuz, alinan = list(havuz), []
        while havuz and len(alinan) < adet:
            en_iyi = max(havuz, key=lambda a: (a[2] + KAPSAMA_AGIRLIGI * len(set(a[1]) - kapsanan), a[0]["id"]))
            havuz.remove(en_iyi)
            alinan.append(en_iyi)
            kapsanan.update(en_iyi[1])
        return alinan, havuz

    diger_yeri = min(len(digerleri), k - min(en_cok_onlem, len(onlemler)))
    onlem_yeri = min(len(onlemler), k - diger_yeri)

    secilen_onlem, _ = ac_gozlu(onlemler, onlem_yeri, set())
    secilen_diger, _ = ac_gozlu(digerleri, k - len(secilen_onlem), set())
    secilen = secilen_onlem + secilen_diger
    secilen.sort(key=lambda a: (-a[2], a[0]["id"]))
    return secilen, acil


# ---------------------------------------------------------------- 3. kapsam
def eslesmeyenler(sapmalar, kartlar, baglam=None):
    """Geçerli bağlamda (acil kartlar hariç) hiçbir kartla eşleşmeyen sapan metrikler."""
    return [
        m for m in sapmalar
        if not any(
            _eslesen_metrikler(kart, {m: sapmalar[m]})
            for kart in kartlar
            if kart["type"] != "emergency" and _baglam_uygun(kart, baglam)
        )
    ]


def _onerilebilir(kart):
    return kart["type"] == "countermeasure" and bool(kart.get("action_tr"))


def aksiyonsuzlar(sapmalar, secilen):
    """Seçilen kartlar arasında gösterilebilir önlem kartı bulunmayan sapan metrikler."""
    kapsanan = {m for kart, e, _ in secilen if _onerilebilir(kart) for m in e}
    return [m for m in sapmalar if m not in kapsanan]


# ---------------------------------------------------------------- 4. öneriler (kod)
METRIK_AD = {
    "heart_rate": "Kalp atış hızı", "spo2": "SpO2", "body_temp": "Vücut sıcaklığı",
    "systolic_bp": "Sistolik tansiyon", "diastolic_bp": "Diyastolik tansiyon",
    "respiratory_rate": "Solunum hızı", "sleep_hours": "Uyku süresi",
    "sleep_quality": "Uyku kalitesi", "stress": "Stres", "fatigue": "Yorgunluk",
    "headache": "Baş ağrısı", "dizziness": "Baş dönmesi", "nausea": "Bulantı",
    "cough": "Öksürük", "sore_throat": "Boğaz ağrısı", "shortness_of_breath": "Nefes darlığı",
    "back_pain": "Sırt ağrısı", "skin_lesion": "Cilt lezyonu", "blurred_vision": "Bulanık görme",
    "visual_acuity": "Görme keskinliği", "eye_pressure": "Göz içi basıncı",
    "mood_index": "Ruh hali", "loneliness": "Yalnızlık", "crew_relation": "Ekip ilişkisi",
    "digestive_issue": "Sindirim sorunu", "pvt_lapses": "Dikkat kaçırma sayısı (PVT)",
    "pvt_mean_rt_ms": "Tepki süresi (PVT)", "pvt_false_starts": "Erken tepki sayısı (PVT)",
    "rotation_mean_rt_ms": "Zihinsel döndürme süresi", "rotation_accuracy": "Zihinsel döndürme doğruluğu",
}
YON_AD = {"up": "arttı", "down": "azaldı"}
ONCELIK_SIRASI = {"high": 0, "medium": 1, "low": 2}


def olcum_satiri(metrik, deger):
    """'SpO2 azaldı: 91 % (taban 97)' biçiminde, modelsiz gerekçe satırı."""
    metin = f"{METRIK_AD.get(metrik, metrik)} {YON_AD.get(_yon(deger), _yon(deger))}"
    if isinstance(deger, dict) and "value" in deger:
        metin += f": {deger['value']}" + (f" {deger['unit']}" if deger.get("unit") else "")
        if "baseline" in deger:
            metin += f" (taban {deger['baseline']})"
    return metin


def oncelik(metrikler, sapmalar, acil):
    """Önerinin önceliğini kod belirler; aynı girdi her zaman aynı sonucu verir."""
    if acil or any(HER_ZAMAN_YUKSELT.get(m) in ("any", _yon(sapmalar[m])) for m in metrikler):
        return "high"
    return "medium" if len(metrikler) >= 2 else "low"


def oneriler_kur(sapmalar, secilen, acil):
    """Seçilen önlem kartlarından öneri listesi. Metin kartın onaylı cümlesidir."""
    oneriler, atlanan = [], []
    for kart, eslesen, _ in secilen:
        if kart["type"] != "countermeasure":
            continue
        if not kart.get("action_tr"):
            atlanan.append(kart["id"])          # onaylı Türkçe cümlesi yok: gösterilmez
            continue
        oneriler.append({
            "action": kart["action_tr"],
            "action_source": "card",
            "rationale": "; ".join(olcum_satiri(m, sapmalar[m]) for m in eslesen),
            "metrics": list(eslesen),
            "card_ids": [kart["id"]],
            "priority": oncelik(eslesen, sapmalar, acil),
            "sources": _kaynaklar([kart["id"]], {kart["id"]: kart}),
        })
    oneriler.sort(key=lambda o: ONCELIK_SIRASI[o["priority"]])   # kararlı: eşitlerde puan sırası
    return oneriler, atlanan


# ---------------------------------------------------------------- 5. model (özet + açıklama)
def sema_kur(sapmalar, aciklama_kartlari):
    """İsteğe özel şema: kart kimlikleri ve metrik adları yalnız gönderilenlerden seçilebilir."""
    kimlikler = [kart["id"] for kart, _, _ in aciklama_kartlari]
    metrikler = list(sapmalar)
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": 300},
            "explanations": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "maxLength": 350},
                        "card_ids": {
                            "type": "array", "minItems": 1, "maxItems": 1,
                            "items": {"type": "string", "enum": kimlikler},
                        },
                    },
                    "required": ["text", "card_ids"],
                },
            },
            "unmatched_findings": {
                "type": "array", "maxItems": len(metrikler),
                "items": {"type": "string", "enum": metrikler},
            },
        },
        "required": ["summary", "explanations", "unmatched_findings"],
    }


def _sade_sema(sema):
    """Uzunluk/adet sınırlarını çıkarır (Ollama sürümü bunları desteklemiyorsa yedek)."""
    if isinstance(sema, dict):
        return {a: _sade_sema(d) for a, d in sema.items()
                if a not in ("maxLength", "maxItems", "minItems")}
    if isinstance(sema, list):
        return [_sade_sema(d) for d in sema]
    return sema


SISTEM = """You are a decision-support assistant for a spaceflight crew health monitor. \
You do not diagnose and you do not recommend actions: recommended actions are selected by \
the system from approved sources and shown separately. Your job is to explain the findings \
using ONLY the knowledge cards provided in the user message.

Each card line looks like: [id] (TYPE; metrics: ...) card text.
The id, TYPE and metrics list are routing metadata. Only the card text after the parenthesis \
is evidence. Never present the metrics list as something the card states, and never mention \
card ids, the words RISK/SIGN or "the card" in your text.

Output fields:
- summary: two sentences at most, stating which measurements deviated and in which \
direction, using the given values when present. No diagnosis, no advice.
- explanations: for the most relevant cards (at most 3), restate in plain Turkish the fact \
given in that card's text. One card per explanation, one or two complete sentences. Keep the \
card's own conditions (who, when, which mission or study); do not generalise and do not add \
causes, symptoms or numbers that the text does not contain.
- unmatched_findings: deviating metrics that none of the provided cards mentions at all.

Rules:
1. Do not use outside medical knowledge. Do not invent numbers, thresholds, doses, drug \
names, equipment or treatments.
2. Do not give instructions or advice of any kind. Never turn a fact into a recommendation.
3. Translate meaning accurately. "Untreated" is "tedavi edilmeyen", "nausea" is "bulantı", \
"dizziness" is "baş dönmesi", "lapses" is "dikkat kaçırma", "hypoxia" is "hipoksi".
4. Language: Turkish, Latin Turkish alphabet only. Do not copy English sentences.
Return only the JSON object."""


def _sapma_satiri(metrik, deger):
    if isinstance(deger, dict):
        ek = ", ".join(f"{ad}={deger[ad]}" for ad in ("value", "baseline", "unit") if ad in deger)
        return f"- {metrik}: {deger['direction']}" + (f" ({ek})" if ek else "")
    return f"- {metrik}: {deger}"


def mesajlari_kur(sapmalar, aciklama_kartlari):
    bulgular = "\n".join(_sapma_satiri(m, d) for m, d in sapmalar.items())
    kartlar = "\n".join(
        f"[{kart['id']}] ({kart['type'].upper()}; metrics: {', '.join(e)}) {kart['text']}"
        for kart, e, _ in aciklama_kartlari
    )
    kullanici = (f"DEVIATING METRICS (metric: direction)\n{bulgular}\n\nKNOWLEDGE CARDS\n{kartlar}"
                 "\n\nYanıtı Türkçe yaz.")
    return [{"role": "system", "content": SISTEM}, {"role": "user", "content": kullanici}]


def modele_sor(mesajlar, sema, deneme=0):
    """deneme > 0 ise farklı tohum ve hafif sıcaklıkla yeniden dener."""
    import ollama

    secenekler = dict(SECENEKLER)
    if deneme:
        secenekler.update(temperature=0.3, seed=deneme)
    ortak = dict(model=MODEL, messages=mesajlar, options=secenekler, keep_alive="1h")

    def cagir(s):
        try:
            return ollama.chat(think=False, format=s, **ortak)
        except TypeError:  # eski ollama paketi think parametresini tanımıyorsa
            return ollama.chat(format=s, **ortak)

    try:
        yanit = cagir(sema)
    except ollama.ResponseError:  # şema reddedildiyse sınırlar olmadan dene
        yanit = cagir(_sade_sema(sema))
    return json.loads(yanit["message"]["content"])


# ---------------------------------------------------------------- 6. doğrulama
_YABANCI_YAZI = re.compile(r"[Ͱ-ϿЀ-ԯ֐-ۿऀ-෿぀-ヿ一-鿿가-힯]")
_INGILIZCE = re.compile(r"\b(the|and|should|with|during|to help|crew should|maintain|increase)\b", re.I)
_TURKCE_HARF = re.compile(r"[çğıöşüÇĞİÖŞÜ]")


def dil_hatasi(metin):
    """Türkçe olmayan çıktı için kaba denetim; sorun yoksa None."""
    if _YABANCI_YAZI.search(metin):
        return "Latin dışı karakter"
    if len(_INGILIZCE.findall(metin)) >= 2 and not _TURKCE_HARF.search(metin):
        return "İngilizce metin"
    return None


def _kaynaklar(kimlikler, gonderilen):
    return [
        {ad: gonderilen[k][ad] for ad in ("id", "type", "text", "source", "url", "locator")}
        for k in kimlikler
    ]


def _normal(metin):
    return re.sub(r"\W+", " ", metin.lower()).strip()


def dogrula(model_cikti, sapmalar, secilen, acil, backend_eslesmeyen, oneriler, atlanan):
    """Modelin açıklamalarını denetler, kodun önerileriyle birleştirir, yükseltmeye karar verir."""
    gonderilen = {kart["id"]: kart for kart, _, _ in secilen if kart["type"] != "countermeasure"}
    kartli = {m for _, e, _ in secilen for m in e}
    aciklamalar, atilan, gorulen = [], [], set()

    for a in model_cikti.get("explanations", []):
        kimlikler = list(dict.fromkeys(k for k in a.get("card_ids") or [] if k in gonderilen))
        metin = a.get("text", "")
        hata = dil_hatasi(metin) or (None if kimlikler else "geçerli kart kimliği yok")
        if not hata and (_normal(metin) in gorulen or not metin.strip()):
            hata = "tekrar ya da boş"
        if hata:
            atilan.append({**a, "reason": hata})
            continue
        gorulen.add(_normal(metin))
        aciklamalar.append({"text": metin, "card_ids": kimlikler,
                            "sources": _kaynaklar(kimlikler, gonderilen)})

    # Modelin "eşleşmedi" dediği metrik ancak seçilen hiçbir kart onu kapsamıyorsa kabul edilir.
    eslesmeyen = list(backend_eslesmeyen)
    for m in model_cikti.get("unmatched_findings", []):
        if m in sapmalar and m not in kartli and m not in eslesmeyen:
            eslesmeyen.append(m)
    onerili = {m for o in oneriler for m in o["metrics"]}
    onerisiz = [m for m in sapmalar if m not in eslesmeyen and m not in onerili]

    nedenler = []
    if acil:
        nedenler.append("acil durum kartı eşleşti")
    if eslesmeyen:
        nedenler.append("bilinen bir riskle eşleşmeyen bulgu var")
    if onerisiz:
        nedenler.append("önlem kartı olmayan bulgu var")
    kritik = [m for m in sapmalar
              if HER_ZAMAN_YUKSELT.get(m) in ("any", _yon(sapmalar[m]))]
    if kritik:
        nedenler.append("her zaman hekime bildirilen bulgu: " + ", ".join(kritik))

    return {
        "emergency": [
            {"message": ACIL_MESAJ, "matched_metrics": e,
             **{ad: kart[ad] for ad in ("id", "text", "source", "url", "locator")}}
            for kart, e, _ in acil
        ],
        "summary": model_cikti.get("summary", ""),
        "explanations": aciklamalar,
        "recommendations": oneriler,
        "unmatched_findings": eslesmeyen,
        "no_recommendation_for": onerisiz,
        "escalate_to_physician": bool(nedenler),
        "escalation_reasons": nedenler,
        "dropped": atilan,
        "cards_without_action_tr": atlanan,
        "disclaimer": UYARI,
    }


# ---------------------------------------------------------------- hepsi
def oner(sapmalar, kartlar, k=5, sor=None, en_cok_deneme=2, baglam=None):
    sor = sor or modele_sor
    eslesmeyen = eslesmeyenler(sapmalar, kartlar, baglam)
    secilen, acil = kart_sec(sapmalar, kartlar, k=k, baglam=baglam)
    oneriler, atlanan = oneriler_kur(sapmalar, secilen, acil)       # model beklenmez
    aciklama_kartlari = [a for a in secilen if a[0]["type"] != "countermeasure"]
    bos = {"summary": "", "explanations": [], "unmatched_findings": []}

    def bitir(cikti):
        return dogrula(cikti, sapmalar, secilen, acil, eslesmeyen, oneriler, atlanan)

    if not aciklama_kartlari:      # açıklanacak kart yok: modele hiç sorma
        sonuc = bitir(bos)
        sonuc["attempts"] = 0
        return sonuc

    mesajlar = mesajlari_kur(sapmalar, aciklama_kartlari)
    sema = sema_kur(sapmalar, aciklama_kartlari)
    en_iyi, hatalar = None, []
    for deneme in range(en_cok_deneme):
        try:
            cikti = sor(mesajlar, sema, deneme)
        except (json.JSONDecodeError, KeyError) as hata:
            hatalar.append(f"deneme {deneme + 1}: model çıktısı okunamadı ({hata})")
            continue
        sonuc = bitir(cikti)
        sonuc["attempts"] = deneme + 1
        if en_iyi is None or len(sonuc["dropped"]) < len(en_iyi["dropped"]):
            en_iyi = sonuc
        if not sonuc["dropped"]:
            break

    if en_iyi is None:  # model hiç geçerli çıktı vermedi: öneriler ve yükseltme yine gösterilir
        en_iyi = bitir(bos)
        en_iyi["attempts"] = en_cok_deneme
        en_iyi["error"] = "; ".join(hatalar)
    en_iyi["attempt_errors"] = hatalar
    return en_iyi


if __name__ == "__main__":
    import sys

    kartlar = kartlari_yukle(sys.argv[1] if len(sys.argv) > 1 else "knowledge_cards.json")
    ornek = {
        "sleep_hours": {"direction": "down", "value": 5.1, "baseline": 7.2, "unit": "saat"},
        "pvt_lapses": {"direction": "up", "value": 9, "baseline": 3},
        "stress": "up",
    }
    secilen, acil = kart_sec(ornek, kartlar)
    print("Seçilen kartlar:")
    for kart, e, p in secilen:
        print(f"  {kart['id']:12} {kart['type']:14} puan={p:.2f} eşleşen={e}")
    print(json.dumps(oner(ornek, kartlar), ensure_ascii=False, indent=2))
