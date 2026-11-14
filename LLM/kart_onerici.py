"""Bilgi kartı seçimi + Qwen çağrısı + çıktı doğrulaması (sürüm 3).

Akış:
  1. kartlari_yukle()  -> knowledge_cards.json bir kez okunur
  2. kart_sec()        -> sapan metriklere göre kartlar; acil durum kartları ayrı döner
  3. eslesmeyenler() / aksiyonsuzlar() -> kartı ya da önlem kartı olmayan metrikler
  4. modele_sor()      -> Ollama, isteğe özel JSON şeması (kart kimlikleri sabitlenmiş)
  5. dogrula()         -> kimlik, tür, metrik kapsamı, dil ve tekrar kontrolleri
  oner() hepsini sırayla çalıştırır.

Kod ile modelin iş bölümü:
  - Acil durum kartı eşleşmesi, doktora yükseltme, hangi metriğin kartı olmadığı: KOD karar verir.
  - Kartların Türkçe açıklaması ve önlem kartlarından öneri yazımı: MODEL yapar, kod denetler.

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


def _puan(kart, eslesen):
    n = len(eslesen)
    if n == 0:
        return 0.0
    oran = n / len(kart["metrics"])          # uzun kartları kayırmayı dengeler
    yon_bonusu = 0.25 if kart["direction"] != "any" else 0.0
    return n + oran + yon_bonusu


def kart_sec(sapmalar, kartlar, k=5, en_cok_onlem=3):
    """(secilen, acil) döndürür; ikisi de [(kart, eşleşen_metrikler, puan), ...].

    acil    : eşiği geçen acil durum kartları. Modele gönderilmez, backend gösterir.
    secilen : modele gidecek en çok k kart. Önce her sapan metriği bir önlem kartıyla
              kapsamaya çalışır, kalan yerleri risk/belirti kartlarıyla doldurur.
    """
    acil, onlemler, digerleri = [], [], []
    for kart in kartlar:
        e = _eslesen_metrikler(kart, sapmalar)
        if not e:
            continue
        aday = (kart, e, _puan(kart, e))
        if kart["type"] == "emergency":
            if len(e) >= ACIL_ESIK:
                acil.append(aday)
        elif kart["type"] == "countermeasure":
            onlemler.append(aday)
        else:
            digerleri.append(aday)
    acil.sort(key=lambda a: (-a[2], a[0]["id"]))

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
def eslesmeyenler(sapmalar, kartlar):
    """Destede (acil kartlar hariç) hiçbir kartla eşleşmeyen sapan metrikler."""
    return [
        m for m in sapmalar
        if not any(
            _eslesen_metrikler(kart, {m: sapmalar[m]})
            for kart in kartlar if kart["type"] != "emergency"
        )
    ]


def aksiyonsuzlar(sapmalar, secilen):
    """Seçilen kartlar arasında önlem kartı bulunmayan sapan metrikler."""
    kapsanan = {m for kart, e, _ in secilen if kart["type"] == "countermeasure" for m in e}
    return [m for m in sapmalar if m not in kapsanan]


# ---------------------------------------------------------------- 4. model
def sema_kur(sapmalar, secilen):
    """İsteğe özel şema: kart kimlikleri ve metrik adları yalnız gönderilenlerden seçilebilir."""
    tum_kimlikler = [kart["id"] for kart, _, _ in secilen]
    onlem_kimlikleri = [kart["id"] for kart, _, _ in secilen if kart["type"] == "countermeasure"]
    metrikler = list(sapmalar)
    sema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": 300},
            "explanations": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "maxLength": 300},
                        "card_ids": {
                            "type": "array", "minItems": 1, "maxItems": 2,
                            "items": {"type": "string", "enum": tum_kimlikler},
                        },
                    },
                    "required": ["text", "card_ids"],
                },
            },
            "recommendations": {
                "type": "array",
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "maxLength": 220},
                        "rationale": {"type": "string", "maxLength": 300},
                        "metrics": {
                            "type": "array", "minItems": 1, "maxItems": 3,
                            "items": {"type": "string", "enum": metrikler},
                        },
                        "card_ids": {
                            "type": "array", "minItems": 1, "maxItems": 2,
                            "items": {"type": "string", "enum": onlem_kimlikleri},
                        },
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["action", "rationale", "metrics", "card_ids", "priority"],
                },
            },
            "unmatched_findings": {
                "type": "array", "maxItems": len(metrikler),
                "items": {"type": "string", "enum": metrikler},
            },
        },
        "required": ["summary", "explanations", "recommendations", "unmatched_findings"],
    }
    if not onlem_kimlikleri:  # önerilecek kart yok: alanı modele hiç sorma
        del sema["properties"]["recommendations"]
        sema["required"].remove("recommendations")
    return sema


def _sade_sema(sema):
    """Uzunluk/adet sınırlarını çıkarır (Ollama sürümü bunları desteklemiyorsa yedek)."""
    if isinstance(sema, dict):
        return {a: _sade_sema(d) for a, d in sema.items()
                if a not in ("maxLength", "maxItems", "minItems")}
    if isinstance(sema, list):
        return [_sade_sema(d) for d in sema]
    return sema


SISTEM = """You are a decision-support assistant for a spaceflight crew health monitor. \
You do not diagnose. You explain findings and suggest follow-up actions using ONLY the \
knowledge cards provided in the user message.

Each card line looks like: [id] (TYPE; metrics: ...) card text.
The id, TYPE and metrics list are routing metadata. Only the card text after the parenthesis \
is evidence. Never present the metrics list as something the card states, and never mention \
card ids, the words RISK/SIGN/COUNTERMEASURE or "the card" in summary, text, action or rationale.

Output fields:
- summary: two sentences at most, describing what deviated. No diagnosis.
- explanations: restate, in plain Turkish, the fact given in the text of a RISK or SIGN card. \
Keep the card's own conditions (who, when, in which situation); do not generalise it and do \
not add causes or symptoms that the text does not name. One or two sentences each.
- recommendations: concrete things the crew can DO. Each one restates an action from ONE \
COUNTERMEASURE card. In "metrics" list which deviating metric(s) that card's action addresses. \
In "card_ids" list only the COUNTERMEASURE card(s) the action comes from.
- unmatched_findings: deviating metrics that none of the provided cards mentions at all.

Rules:
1. Stay strictly within what the card says. Do not use outside medical knowledge. Do not \
invent actions, equipment, treatments, numbers, thresholds, doses or drug names.
2. If the user message lists metrics under NO COUNTERMEASURE CARD, do not recommend anything \
for those metrics. They are handled by the flight surgeon.
3. Only recommend a card's action if it plausibly applies to the deviating metrics. If a card \
is about a different situation (for example lunar dust or landing day), skip it.
4. Never turn an observation or statistic into an instruction.
5. When a card gives a number, keep what the number refers to (for example work hours versus \
sleep hours).
6. Each recommendation must be a different action. Each action is one sentence; each \
rationale is one or two sentences.
7. Language: write summary, text, action and rationale in Turkish, using only the Latin \
Turkish alphabet. Translate the card's meaning; do not copy English sentences.
Return only the JSON object."""


def _sapma_satiri(metrik, deger):
    if isinstance(deger, dict):
        ek = ", ".join(f"{ad}={deger[ad]}" for ad in ("value", "baseline", "unit") if ad in deger)
        return f"- {metrik}: {deger['direction']}" + (f" ({ek})" if ek else "")
    return f"- {metrik}: {deger}"


def mesajlari_kur(sapmalar, secilen, aksiyonsuz=()):
    bulgular = "\n".join(_sapma_satiri(m, d) for m, d in sapmalar.items())
    kartlar = "\n".join(
        f"[{kart['id']}] ({kart['type'].upper()}; metrics: {', '.join(e)}) {kart['text']}"
        for kart, e, _ in secilen
    )
    kullanici = f"DEVIATING METRICS (metric: direction)\n{bulgular}\n\nKNOWLEDGE CARDS\n{kartlar}"
    if aksiyonsuz:
        kullanici += "\n\nNO COUNTERMEASURE CARD FOR: " + ", ".join(aksiyonsuz)
    kullanici += "\n\nYanıtı Türkçe yaz."
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


# ---------------------------------------------------------------- 5. doğrulama
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


def dogrula(model_cikti, sapmalar, secilen, acil, backend_eslesmeyen, aksiyonsuz):
    gonderilen = {kart["id"]: kart for kart, _, _ in secilen}
    eslesen = {kart["id"]: set(e) for kart, e, _ in secilen}
    oneriler, aciklamalar, atilan = [], [], []
    gorulen = set()

    def at(madde, neden):
        atilan.append({**madde, "reason": neden})

    for a in model_cikti.get("explanations", []):
        kimlikler = [k for k in a.get("card_ids") or [] if k in gonderilen]
        hata = dil_hatasi(a.get("text", "")) or (None if kimlikler else "geçerli kart kimliği yok")
        if not hata and _normal(a["text"]) in gorulen:
            hata = "tekrar"
        if hata:
            at(a, hata)
            continue
        gorulen.add(_normal(a["text"]))
        aciklamalar.append({**a, "card_ids": kimlikler, "sources": _kaynaklar(kimlikler, gonderilen)})

    for o in model_cikti.get("recommendations", []):
        hata = dil_hatasi(o.get("action", "") + " " + o.get("rationale", ""))
        # yalnız önlem kartları dayanak sayılır
        kimlikler = [
            k for k in o.get("card_ids") or []
            if k in gonderilen and gonderilen[k]["type"] == "countermeasure"
        ]
        if not hata and not kimlikler:
            hata = "önlem kartına dayanmıyor"
        # önerinin hedeflediği metrikler, gösterilen kartların kapsadığı metrikler olmalı
        kapsanan = set().union(*(eslesen[k] for k in kimlikler)) if kimlikler else set()
        metrikler = [m for m in o.get("metrics") or [] if m in sapmalar and m in kapsanan]
        if not hata and not metrikler:
            hata = "gösterilen kart bu metriği kapsamıyor"
        if not hata and _normal(o["action"]) in gorulen:
            hata = "tekrar"
        if hata:
            at(o, hata)
            continue
        gorulen.add(_normal(o["action"]))
        oneriler.append({**o, "card_ids": kimlikler, "metrics": metrikler,
                         "sources": _kaynaklar(kimlikler, gonderilen)})

    # Doktora yükseltme: kod karar verir
    # Modelin "eşleşmedi" dediği metrik ancak seçilen hiçbir kart onu kapsamıyorsa kabul edilir.
    kartli = set().union(*eslesen.values()) if eslesen else set()
    eslesmeyen = list(backend_eslesmeyen)
    for m in model_cikti.get("unmatched_findings", []):
        if m in sapmalar and m not in kartli and m not in eslesmeyen:
            eslesmeyen.append(m)
    onerisiz = [m for m in sapmalar
                if m not in eslesmeyen and not any(m in o["metrics"] for o in oneriler)]

    nedenler = []
    if acil:
        nedenler.append("acil durum kartı eşleşti")
    if eslesmeyen:
        nedenler.append("bilinen bir riskle eşleşmeyen bulgu var")
    if any(m in aksiyonsuz for m in onerisiz):
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
        "disclaimer": UYARI,
    }


# ---------------------------------------------------------------- hepsi
def oner(sapmalar, kartlar, k=5, sor=None, en_cok_deneme=2):
    sor = sor or modele_sor
    eslesmeyen = eslesmeyenler(sapmalar, kartlar)
    secilen, acil = kart_sec(sapmalar, kartlar, k=k)
    aksiyonsuz = aksiyonsuzlar(sapmalar, secilen)
    bos = {"summary": "", "explanations": [], "recommendations": [], "unmatched_findings": []}

    if not secilen:  # hiçbir kart yok: modele hiç sorma
        return dogrula(bos, sapmalar, [], acil, eslesmeyen, aksiyonsuz)

    mesajlar = mesajlari_kur(sapmalar, secilen, aksiyonsuz)
    sema = sema_kur(sapmalar, secilen)
    en_iyi, hatalar = None, []

    for deneme in range(en_cok_deneme):
        try:
            cikti = sor(mesajlar, sema, deneme)
        except (json.JSONDecodeError, KeyError) as hata:
            hatalar.append(f"deneme {deneme + 1}: model çıktısı okunamadı ({hata})")
            continue
        sonuc = dogrula(cikti, sapmalar, secilen, acil, eslesmeyen, aksiyonsuz)
        sonuc["attempts"] = deneme + 1
        if en_iyi is None or len(sonuc["dropped"]) < len(en_iyi["dropped"]):
            en_iyi = sonuc
        if not sonuc["dropped"]:
            break

    if en_iyi is None:  # iki deneme de bozuk JSON
        en_iyi = dogrula(bos, sapmalar, secilen, acil, eslesmeyen, aksiyonsuz)
        en_iyi["error"] = "; ".join(hatalar)
        en_iyi["escalate_to_physician"] = True
        en_iyi["escalation_reasons"].append("model çıktısı üretilemedi")
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
