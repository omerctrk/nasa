"""ASTRA HEALTH — uçtan uca senaryo testi (canlı API + gerçek MS SQL + işçi + WebSocket).

Ayrı, geçici bir Docker yığınında (proje adı astra-e2e) çalışır; asıl demo veritabanına dokunmaz.
Çalıştırma: tests/e2e/e2e_calistir.cmd (çift tık). Elle:
    docker compose -p astra-e2e -f docker-compose.yml -f tests/e2e/docker-compose.e2e.yml run --rm e2e

Hikâye (tek astronot A007, bugün = görev günü 74; demo verisi bugün biten 74 günlük davranış geçmişi):
  S0  Sistem ayakta mı, API sınırlı hesapla mı çalışıyor
  S1  Kimlik ve rol sınırları
  S2  Profil ve görev takvimi (demo hizalaması)
  S3  Sabah check-in'i: oluştur, ETag ile güncelle, eski ETag, hatalı alan
  S4  Bilişsel test (PVT) ve haftalık ölçek: tekrar güvenliği
  S5  Veri yokken analiz → insufficient_data (no_current_measurements)
  S6  Düşük kaliteli tek ölçüm → insufficient_data (all_records_excluded)
  S7  Davranış kapsamı → insufficient_data (thresholds_not_configured)
  S8  Normal fizyolojik değerler → normal, alarm yok
  S9  Eşik dışı nabız + ateş → riskli sonuç, alarm, bildirim olayları
  S10 Frontend'in kullandığı combined kapsam
  S11 Okuma tutarlılığı (astronot ↔ kule ↔ sonuç)
  S12 Bildirimler: REST + WebSocket teslimi, receipt, yeniden bağlanma
  S13 Alarm yaşam döngüsü: OPEN → ACKNOWLEDGED → RESOLVED
  S14 Bilgi kartı CRUD (kule)
Her adım PASS/FAIL olarak kaydedilir; rapor /e2e/rapor/ altına yazılır.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = os.environ.get("E2E_API_URL", "http://api:8000").rstrip("/")
WS = API.replace("http", "ws", 1) + "/ws/v1/notifications"
P = API + "/api/v1"
RAPOR = Path(os.environ.get("E2E_RAPOR_DIR", "/e2e/rapor"))
ASTRO_EMAIL, GROUND_EMAIL = "astronaut@astra.local", "kule@astra.local"
ASTRO_PW = os.environ.get("SEED_ASTRONAUT_PASSWORD", "")
GROUND_PW = os.environ.get("SEED_GROUND_PASSWORD", "")
JOB_TIMEOUT = float(os.environ.get("E2E_JOB_TIMEOUT", "90"))
PHASE = os.environ.get("E2E_PHASE", "ana")  # ana | llm_yok | llm_gercek

NOW = dt.datetime.now(dt.UTC)
TODAY = NOW.date()
TOMORROW = TODAY + dt.timedelta(days=1)


def num(v) -> float:
    return float(v)  # DB Numeric(18,6) → "96.000000"

# Eşikler (config/thresholds.json, demo-thresholds-v1): HR≤80, SYS≤130, DIA≤86, GLU≤111, TEMP≤37.10
NORMAL = {"heart_rate": ("72", "BPM"), "systolic_bp": ("118", "mmHg"), "diastolic_bp": ("76", "mmHg"),
          "blood_glucose": ("94", "mg/dL"), "body_temperature": ("36.7", "°C")}
RISK = {"heart_rate": ("96", "BPM"), "body_temperature": ("37.8", "°C")}

results: list[dict] = []
ctx: dict = {}


# ------------------------------------------------------------------ altyapı
class Fail(AssertionError):
    pass


class Skip(Exception):
    pass


class CIDict(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())


def check(cond, beklenen, gercek=None):
    if not cond:
        raise Fail(f"beklenen: {beklenen} | gerçek: {gercek!r}"[:1500])


def http(method, path, token=None, body=None, headers=None, raw_url=False):
    url = path if raw_url else P + path
    data = None if body is None else json.dumps(body).encode()
    h = {"Accept": "application/json"}
    if body is not None:
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = f"Bearer {token}"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, hdrs, text = r.status, r.headers, r.read().decode()
    except urllib.error.HTTPError as e:
        status, hdrs, text = e.code, e.headers, e.read().decode()
    # HTTP başlık adları büyük/küçük harf duyarsızdır (uvicorn "etag" gönderir)
    hdrs = CIDict({k.lower(): v for k, v in hdrs.items()})
    try:
        payload = json.loads(text) if text else None
    except json.JSONDecodeError:
        payload = text
    return status, hdrs, payload


def err_code(payload):
    return (payload or {}).get("detail", {}).get("code") if isinstance(payload, dict) else None


def step(senaryo, ad):
    def deco(fn):
        t0 = time.monotonic()
        try:
            note = fn()
            results.append({"senaryo": senaryo, "adim": ad, "sonuc": "PASS", "not": note or "",
                            "sure_s": round(time.monotonic() - t0, 2)})
            print(f"  PASS  {senaryo} · {ad}" + (f"  ({note})" if note else ""), flush=True)
        except Skip as e:
            results.append({"senaryo": senaryo, "adim": ad, "sonuc": "SKIP", "not": str(e),
                            "sure_s": round(time.monotonic() - t0, 2)})
            print(f"  SKIP  {senaryo} · {ad}  ({e})", flush=True)
        except Fail as e:
            results.append({"senaryo": senaryo, "adim": ad, "sonuc": "FAIL", "not": str(e),
                            "sure_s": round(time.monotonic() - t0, 2)})
            print(f"  FAIL  {senaryo} · {ad}\n        {e}", flush=True)
        except Exception as e:  # noqa: BLE001
            results.append({"senaryo": senaryo, "adim": ad, "sonuc": "ERROR",
                            "not": f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}",
                            "sure_s": round(time.monotonic() - t0, 2)})
            print(f"  ERROR {senaryo} · {ad}: {type(e).__name__}: {e}", flush=True)
        return fn
    return deco


def login(email, pw):
    s, _, b = http("POST", "/auth/login", body={"email": email, "password": pw})
    check(s == 200 and b.get("token_type") == "bearer", "200 + bearer token", (s, b))
    return b["access_token"]


def ts(minutes_ago: float) -> dt.datetime:
    return NOW - dt.timedelta(minutes=minutes_ago)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")


def physio(token, code, value, unit, at: dt.datetime, quality="0.97"):
    body = {"client_request_id": str(uuid.uuid4()), "measurement": code, "value_num": value,
            "unit": unit, "measured_date": at.date().isoformat(), "measured_at": iso(at),
            "quality_score": quality, "valid": True}
    s, _, b = http("POST", "/me/physiological", ctx["astro"], body)
    check(s == 201 and b["created"] is True, f"{code}: 201 created", (s, b))
    return b


def run_job(scope: str, key: str | None = None) -> dict:
    key = key or str(uuid.uuid4())
    s, h, b = http("POST", "/analysis/jobs", ctx["astro"],
                   {"module": "anomaly", "idempotency_key": key, "module_scope": scope})
    check(s == 202 and b["state"] == "QUEUED", "202 QUEUED", (s, b))
    job_id, deadline = b["job_id"], time.monotonic() + JOB_TIMEOUT
    seen = ["QUEUED"]
    while time.monotonic() < deadline:
        s, _, st = http("GET", f"/analysis/jobs/{job_id}", ctx["astro"])
        check(s == 200, "iş durumu 200", (s, st))
        if st["state"] != seen[-1]:
            seen.append(st["state"])
        if st["state"] in ("COMPLETED", "FAILED"):
            st["_states"], st["_key"] = seen, key
            return st
        time.sleep(0.5)
    raise Fail(f"iş {JOB_TIMEOUT}s içinde bitmedi; görülen durumlar {seen}")


# ------------------------------------------------------------------ senaryolar
def main() -> int:
    if not ASTRO_PW or not GROUND_PW:
        print("SEED_ASTRONAUT_PASSWORD / SEED_GROUND_PASSWORD yok."); return 2
    for _ in range(120):  # API ayağa kalkana kadar
        try:
            if http("GET", "/health/live")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(1)
    print(f"ASTRA HEALTH e2e [{PHASE}] — {iso(NOW)}  API={API}\n", flush=True)
    if PHASE != "ana":
        ctx["astro"], ctx["ground"] = login(ASTRO_EMAIL, ASTRO_PW), login(GROUND_EMAIL, GROUND_PW)
        {"llm_yok": phase_llm_yok, "llm_gercek": phase_llm_gercek}[PHASE]()
        return report()

    # ---------------- S0
    @step("S0 Sistem", "health/live ve health/ready; API astra_app hesabıyla")
    def _():
        s, _, b = http("GET", "/health/ready")
        check(s == 200 and b.get("db_user") == "astra_app", "200, db_user=astra_app (sa değil)", (s, b))

    # ---------------- S1
    @step("S1 Kimlik", "astronot ve kule girişi, /auth/me rolleri")
    def _():
        ctx["astro"], ctx["ground"] = login(ASTRO_EMAIL, ASTRO_PW), login(GROUND_EMAIL, GROUND_PW)
        s, _, me = http("GET", "/auth/me", ctx["astro"])
        check(s == 200 and me["role"] == "ASTRONAUT" and me["astronaut_id"] == "A007", "ASTRONAUT/A007", me)
        s, _, g = http("GET", "/auth/me", ctx["ground"])
        check(s == 200 and g["role"] == "GROUND_CONTROL" and not g.get("astronaut_id"), "GROUND_CONTROL", g)
        ctx["astro_user"], ctx["ground_user"] = me["user_id"], g["user_id"]

    @step("S1 Kimlik", "yanlış parola 401, token'sız 401, bozuk token 401")
    def _():
        s, _, b = http("POST", "/auth/login", body={"email": ASTRO_EMAIL, "password": "yanlis-parola-123"})
        check(s == 401 and err_code(b) == "UNAUTHORIZED", "401 UNAUTHORIZED", (s, b))
        s, _, b = http("GET", "/me/profile")
        check(s == 401, "401", (s, b))
        s, _, b = http("GET", "/me/profile", "abc.def.ghi")
        check(s == 401, "401", (s, b))

    @step("S1 Kimlik", "rol sınırı: astronot kule ucuna, kule astronot ucuna giremez (403)")
    def _():
        for tok, method, path, body in [
            (ctx["astro"], "GET", "/ground/alerts", None),
            (ctx["astro"], "GET", "/ground/astronauts", None),
            (ctx["astro"], "GET", "/knowledge-cards", None),
            (ctx["ground"], "POST", "/me/physiological", {"client_request_id": str(uuid.uuid4()),
             "measurement": "heart_rate", "value_num": "70", "unit": "BPM",
             "measured_date": TODAY.isoformat()}),
            (ctx["ground"], "POST", "/analysis/jobs", {"module": "anomaly",
             "idempotency_key": str(uuid.uuid4()), "module_scope": "physiological"}),
        ]:
            s, _, b = http(method, path, tok, body)
            check(s == 403 and err_code(b) == "FORBIDDEN", f"{method} {path} → 403 FORBIDDEN", (s, b))

    # ---------------- S2
    @step("S2 Profil", "takvim hizalı: bugün = görev günü 74 (realign_demo, 2027 şema tarihinden kaydırıldı)")
    def _():
        s, _, p = http("GET", "/me/profile", ctx["astro"])
        check(s == 200 and p["astronaut_id"] == "A007" and not p["is_display_only"], "A007 aktif", p)
        start = dt.date.fromisoformat(p["mission_start_date"])
        ctx["day0"] = start
        check((TODAY - start).days == 74, "bugün = görev günü 74", (start.isoformat(), (TODAY - start).days))
        s, _, rows = http("GET", f"/me/checkins?start={(TODAY - dt.timedelta(days=80)).isoformat()}"
                                 f"&end={TOMORROW.isoformat()}", ctx["astro"])
        check(s == 200 and len(rows) == 74, "74 günlük demo check-in", (s, len(rows) if isinstance(rows, list) else rows))
        check(all((dt.date.fromisoformat(r["date"]) - start).days == r["mission_day"] for r in rows),
              "her kayıtta tarih − gün 0 = mission_day (kaydırma ilişkiyi korudu)", rows[:2])
        last = max(rows, key=lambda r: r["date"])
        check(last["date"] == TODAY.isoformat() and last["mission_day"] == 74,
              "son demo günü = bugün, mission_day 74", last)
        return f"görev günü 0 = {start}, {len(rows)} demo check-in"

    @step("S2 Profil", "kule profil listesi: A007 aktif, A008 yalnız gösterim")
    def _():
        s, _, rows = http("GET", "/ground/astronauts", ctx["ground"])
        ids = {r["astronaut_id"]: r["is_display_only"] for r in rows}
        check(s == 200 and ids.get("A007") is False and ids.get("A008") is True, "A007=False, A008=True", ids)

    # ---------------- S3
    checkin = {"mood": 7, "energy": 6, "stress": 3, "loneliness": 1, "crew": 3, "mood_index": 68.5,
               "bed_time": "23:10:00", "wake_time": "06:40:00", "sleep_quality": 4, "symptoms": []}

    @step("S3 Check-in", "bugünün (74) demo check-in'i hazır: GET 200 + ETag")
    def _():
        s, h, b = http("GET", f"/me/checkins/{TODAY}", ctx["astro"])
        check(s == 200 and h.get("ETag") and b["mission_day"] == 74 and b["source"] == "seed",
              "200 + ETag, mission_day 74, kaynak seed", (s, h.get("ETag"), b))
        ctx["etag"] = h["ETag"]

    @step("S3 Check-in", "If-Match'siz PUT 412, doğru ETag ile güncelleme 200 (manual), eski ETag 412")
    def _():
        s, _, b = http("PUT", f"/me/checkins/{TODAY}", ctx["astro"], checkin)
        check(s == 412 and err_code(b) == "PRECONDITION_FAILED", "412", (s, b))
        upd = checkin | {"stress": 5, "mood": 6}
        s, h, b = http("PUT", f"/me/checkins/{TODAY}", ctx["astro"], upd, {"If-Match": ctx["etag"]})
        check(s == 200 and b["stress"] == 5 and b["source"] == "manual" and b["sleep_hours"] == 7.5
              and h.get("ETag") != ctx["etag"], "200, stress=5, manual, uyku 7.5 sa, yeni ETag", (s, b))
        s, _, b = http("PUT", f"/me/checkins/{TODAY}", ctx["astro"], checkin, {"If-Match": ctx["etag"]})
        check(s == 412, "eski ETag → 412", (s, b))
        s, h2, b = http("GET", f"/me/checkins/{TODAY}", ctx["astro"])
        check(s == 200 and b["stress"] == 5 and h2.get("ETag") == h.get("ETag"), "GET son hâli + aynı ETag", (s, b))

    @step("S3 Check-in", "boş gün (75 = yarın): GET 404, If-Match'siz PUT 201, mission_day 75")
    def _():
        s, _, b = http("GET", f"/me/checkins/{TOMORROW}", ctx["astro"])
        check(s == 404 and err_code(b) == "NOT_FOUND", "404", (s, b))
        s, h, b = http("PUT", f"/me/checkins/{TOMORROW}", ctx["astro"], checkin)
        check(s == 201 and h.get("ETag") and b["mission_day"] == 75, "201 + ETag, mission_day 75", (s, b))

    @step("S3 Check-in", "kural dışı değer (mood=11) → 422 VALIDATION_ERROR zarfı, alan adı ile")
    def _():
        s, _, b = http("PUT", f"/me/checkins/{TODAY - dt.timedelta(days=200)}", ctx["astro"], checkin | {"mood": 11})
        fields = [f.get("field", "") for f in (b or {}).get("detail", {}).get("fields", [])]
        check(s == 422 and err_code(b) == "VALIDATION_ERROR" and any("mood" in f for f in fields)
              and b["detail"].get("trace_id"), "422 + fields[mood] + trace_id", (s, b))

    # ---------------- S4
    pvt = {"client_request_id": str(uuid.uuid4()), "taken_at": iso(ts(60)), "test_type": "pvt",
           "duration_s": 180, "n_trials": 60, "mean_rt_ms": 286.4, "median_rt_ms": 271.0,
           "lapses": 1, "false_starts": 0, "device": "e2e-tablet", "raw": {"trials": 60}}

    @step("S4 Bilişsel/haftalık", "PVT 201; aynı istek tekrarı 200 aynı id; aynı anahtar farklı içerik 409")
    def _():
        s, _, a = http("POST", "/me/cognitive-tests", ctx["astro"], pvt)
        check(s == 201 and a["mission_day"] == 74, "201, mission_day 74", (s, a))
        s, _, b = http("POST", "/me/cognitive-tests", ctx["astro"], pvt)
        check(s == 200 and b["id"] == a["id"], "200 aynı id", (s, b))
        s, _, c = http("POST", "/me/cognitive-tests", ctx["astro"], pvt | {"lapses": 4})
        check(s == 409 and err_code(c) == "IDEMPOTENCY_CONFLICT", "409", (s, c))

    @step("S4 Bilişsel/haftalık", "rotasyon testinde PVT metriği (lapses) → 422")
    def _():
        bad = {"client_request_id": str(uuid.uuid4()), "taken_at": iso(ts(50)), "test_type": "rotation",
               "duration_s": 120, "n_trials": 20, "mean_rt_ms": 900, "accuracy": 0.9, "lapses": 2,
               "device": "e2e-tablet", "raw": []}
        s, _, b = http("POST", "/me/cognitive-tests", ctx["astro"], bad)
        check(s == 422 and err_code(b) == "VALIDATION_ERROR", "422", (s, b))

    @step("S4 Bilişsel/haftalık", "haftalık ölçek 201, tekrar 200")
    def _():
        w = {"client_request_id": str(uuid.uuid4()), "taken_at": iso(ts(40)),
             "answers": {"who5": [3, 3, 4, 3, 3], "phq2": [0, 1], "gad2": [1, 0]},
             "who5_score": 64, "phq2_score": 1, "gad2_score": 1, "share_with_crew_medical": True}
        s, _, a = http("POST", "/me/weekly-assessments", ctx["astro"], w)
        check(s == 201, "201", (s, a))
        s, _, b = http("POST", "/me/weekly-assessments", ctx["astro"], w)
        check(s == 200 and b["id"] == a["id"], "200 aynı id", (s, b))

    # ---------------- S5–S7: sonuç üretmeyen analizler
    def insufficient(reason_hint):
        def inner(scope):
            st = run_job(scope)
            check(st["state"] == "COMPLETED" and st["evaluation_status"] == "insufficient_data"
                  and st["anomaly_result_id"] is None, "COMPLETED / insufficient_data / sonuç yok", st)
            ctx.setdefault("completed_jobs", []).append(st["job_id"])
            return f"durumlar {'→'.join(st['_states'])} ({reason_hint})"
        return inner

    @step("S5 Veri yok", "fizyolojik kapsam, hiç fizyolojik ölçüm yok → insufficient_data")
    def _():
        note = insufficient("no_current_measurements")("physiological")
        ctx["first_job"] = ctx["completed_jobs"][-1]
        return note

    @step("S5 Veri yok", "aynı idempotency_key → 200 aynı iş; COMPLETED iş retry → 409")
    def _():
        key = str(uuid.uuid4())
        st = run_job("physiological", key)
        s, _, b = http("POST", "/analysis/jobs", ctx["astro"],
                       {"module": "anomaly", "idempotency_key": key, "module_scope": "physiological"})
        check(s == 200 and b["job_id"] == st["job_id"], "200 aynı job_id", (s, b))
        s, _, b = http("POST", "/analysis/jobs", ctx["astro"],
                       {"module": "anomaly", "idempotency_key": key, "module_scope": "behavioral"})
        check(s == 409 and err_code(b) == "IDEMPOTENCY_CONFLICT", "aynı anahtar farklı kapsam → 409", (s, b))
        s, _, b = http("POST", f"/analysis/jobs/{st['job_id']}/retry", ctx["astro"])
        check(s == 409 and err_code(b) == "INVALID_STATE_TRANSITION", "409", (s, b))
        s, _, b = http("GET", f"/analysis/jobs/{uuid.uuid4()}", ctx["astro"])
        check(s == 404, "bilinmeyen iş 404", (s, b))
        ctx["completed_jobs"].append(st["job_id"])

    @step("S5 Veri yok", "SANS kapsamı kapalı → 422")
    def _():
        s, _, b = http("POST", "/analysis/jobs", ctx["astro"],
                       {"module": "anomaly", "idempotency_key": str(uuid.uuid4()), "module_scope": "sans"})
        check(s == 422, "422", (s, b))

    @step("S6 Düşük kalite", "kalite 0.50 nabız (politika ≥0.90) dışlanır → insufficient_data")
    def _():
        physio(ctx["astro"], "heart_rate", "71", "BPM", ts(30), quality="0.50")
        return insufficient("all_records_excluded")("physiological")

    @step("S6 Düşük kalite", "birim sözlükle uyuşmazsa (bpm küçük harf) → 422, kayıt yok")
    def _():
        s, _, b = http("POST", "/me/physiological", ctx["astro"], {
            "client_request_id": str(uuid.uuid4()), "measurement": "heart_rate", "value_num": "70",
            "unit": "bpm", "measured_date": TODAY.isoformat()})
        check(s == 422, "422", (s, b))

    @step("S7 Davranış", "davranış kapsamı: eşik tanımı yok → insufficient_data (bilinmeyen ≠ normal)")
    def _():
        return insufficient("thresholds_not_configured")("behavioral")

    # ---------------- S8 normal gün
    @step("S8 Normal gün", "5 fizyolojik ölçüm eşik içinde → normal sonuç, alarm yok")
    def _():
        for code, (v, unit) in NORMAL.items():
            physio(ctx["astro"], code, v, unit, ts(20))
        st = run_job("physiological")
        check(st["state"] == "COMPLETED" and st["evaluation_status"] == "evaluated"
              and st["anomaly_result_id"], "COMPLETED / evaluated / sonuç var", st)
        s, _, r = http("GET", f"/me/anomaly-results/{st['anomaly_result_id']}", ctx["astro"])
        check(s == 200 and r["level"] == "normal" and r["is_anomaly"] is False and r["drivers"] == [],
              "level normal, sürücü yok", r)
        check(r["baseline_status"] == "provisional", "baseline provisional (yeterlilik politikası yok)", r)
        s, _, al = http("GET", "/ground/alerts?astronaut_id=A007", ctx["ground"])
        check(s == 200 and not any(a["anomaly_result_id"] == r["id"] for a in al), "bu sonuca alarm yok", al)
        ctx["normal_result"] = r["id"]
        ctx["completed_jobs"].append(st["job_id"])
        return r["summary"]

    # ---------------- S9 riskli gün
    @step("S9 Risk", "nabız 96 BPM + ateş 37.8 °C → riskli sonuç, sürücüler eşikle tutarlı")
    def _():
        for code, (v, unit) in RISK.items():
            physio(ctx["astro"], code, v, unit, ts(10))
        st = run_job("physiological")
        check(st["evaluation_status"] == "evaluated" and st["anomaly_result_id"], "evaluated", st)
        s, _, r = http("GET", f"/me/anomaly-results/{st['anomaly_result_id']}", ctx["astro"])
        check(s == 200 and r["is_anomaly"] is True and r["level"] in ("watch", "review"), "watch/review", r)
        breaches = {d["measurement"]: d for d in r["drivers"] if d.get("type") != "advice"}
        check(set(breaches) == {"heart_rate", "body_temperature"}, "yalnız HR + ateş ihlal", list(breaches))
        hr, tp = breaches["heart_rate"], breaches["body_temperature"]
        check(num(hr["upper"]) == 80 and num(hr["value"]) == 96 and num(tp["upper"]) == 37.1
              and num(tp["value"]) == 37.8 and hr["direction"] == tp["direction"] == "up",
              "sınırlar thresholds.json ile aynı, yön up", breaches)
        check(num(hr["value_minus_bound"]) == 16, "nabız sınır farkı 16", hr)
        advice = [d for d in r["drivers"] if d.get("type") == "advice"]
        check(len(advice) == 1, "tek advice sürücüsü", r["drivers"])
        esc = r["recommendation"].startswith("Uçuş hekimine bildirin")
        check((r["level"] == "review") == esc, "review ⇔ öneri 'Uçuş hekimine bildirin' ile başlar",
              (r["level"], r["recommendation"]))
        check(advice[0]["disclaimer"], "teşhis uyarısı var", advice[0])
        ctx["risk_job"], ctx["risk_result"], ctx["risk_level"] = st["job_id"], r["id"], r["level"]
        ctx["risk_advice"] = advice[0]
        return (f"level={r['level']}, öneri sayısı={len(advice[0]['recommendations'])}, "
                f"yükseltme={advice[0]['escalation_reasons']}")

    @step("S9 Risk", "alarm OPEN/WARNING oluştu ve sonuca bağlı")
    def _():
        s, _, al = http("GET", "/ground/alerts?status=OPEN&astronaut_id=A007", ctx["ground"])
        mine = [a for a in al if a["anomaly_result_id"] == ctx["risk_result"]]
        check(s == 200 and len(mine) == 1 and mine[0]["severity"] == "WARNING"
              and mine[0]["module"] == "anomaly", "tek OPEN WARNING alarm", al)
        ctx["alert1"] = mine[0]["alert_id"]

    # ---------------- S10 combined
    @step("S10 Combined", "frontend'in kapsamı (combined): fizyolojik ihlal + davranış eşiksiz → riskli")
    def _():
        st = run_job("combined")
        check(st["evaluation_status"] == "evaluated", "evaluated", st)
        s, _, r = http("GET", f"/me/anomaly-results/{st['anomaly_result_id']}", ctx["astro"])
        check(r["module_scope"] == "combined" and r["level"] == ctx["risk_level"], "aynı seviye", r)
        names = {d["measurement"] for d in r["drivers"] if d.get("type") != "advice"}
        check(names == {"heart_rate", "body_temperature"}, "davranış ölçümleri ihlal sayılmaz", names)
        s, _, al = http("GET", "/ground/alerts?status=OPEN&astronaut_id=A007", ctx["ground"])
        mine = [a for a in al if a["anomaly_result_id"] == r["id"]]
        check(len(mine) == 1, "ikinci alarm", al)
        ctx["alert2"], ctx["combined_result"], ctx["combined_job"] = mine[0]["alert_id"], r["id"], st["job_id"]

    # ---------------- S11 okuma tutarlılığı
    @step("S11 Tutarlılık", "astronot ve kule bugünün ölçümlerini aynı görür; mission_day 74")
    def _():
        q = f"?start={TODAY}&end={TOMORROW}"  # end hariç
        s1, _, mine = http("GET", "/me/measurements" + q, ctx["astro"])
        s2, _, theirs = http("GET", "/ground/astronauts/A007/measurements" + q, ctx["ground"])
        check(s1 == 200 and s2 == 200, "200/200", (s1, s2))
        key = lambda m: (m["record_id"], str(m["value_num"]))
        check(sorted(map(key, mine)) == sorted(map(key, theirs)), "iki görünüm aynı", (len(mine), len(theirs)))
        phys = [m for m in mine if m["module"] == "physiological"]
        check(len(phys) == 1 + len(NORMAL) + len(RISK), "8 fizyolojik kayıt (1 düşük kalite + 5 + 2)", len(phys))
        check(all(m["mission_day"] == 74 for m in mine if m.get("mission_day") is not None), "mission_day 74",
              {m["mission_day"] for m in mine})
        beh = {m["measurement"] for m in mine if m["module"] == "behavioral"}
        check({"stress", "sleep_hours", "pvt_mean_rt"} <= beh, "check-in + PVT görünümde", beh)
        return f"{len(phys)} fizyolojik + {len(mine) - len(phys)} davranış kaydı"

    @step("S11 Tutarlılık", "sonuç listeleri: astronot = kule, normal + 2 riskli sonuç")
    def _():
        q = f"?start={TODAY}&end={TOMORROW}"
        s1, _, a = http("GET", "/me/anomaly-results" + q, ctx["astro"])
        s2, _, g = http("GET", "/ground/astronauts/A007/anomaly-results" + q, ctx["ground"])
        ids_a, ids_g = {r["id"] for r in a}, {r["id"] for r in g}
        want = {ctx["normal_result"], ctx["risk_result"], ctx["combined_result"]}
        check(s1 == 200 and ids_a == ids_g == want, "aynı 3 sonuç", (ids_a, ids_g, want))
        s, _, r = http("GET", f"/ground/anomaly-results/{ctx['risk_result']}", ctx["ground"])
        check(s == 200 and r["id"] == ctx["risk_result"], "kule tekil okuma", (s, r))
        s, _, r = http("GET", f"/me/anomaly-results/{uuid.uuid4()}", ctx["astro"])
        check(s == 404, "bilinmeyen sonuç 404", s)

    # ---------------- S12 bildirimler
    @step("S12 Bildirim", "REST pending: astronotta 5 tamamlanma + 2 risk olayı, kulede 2 risk olayı")
    def _():
        s, _, ev = http("GET", "/notifications/pending", ctx["astro"])
        check(s == 200, "200", (s, ev))
        types = [e["event_type"] for e in ev]
        n_done = len(ctx["completed_jobs"])
        check(types.count("analysis.completed") == n_done and types.count("risk.alert.created") == 2,
              f"{n_done} analysis.completed + 2 risk.alert.created", types)
        done_jobs = {e["payload"]["job_id"] for e in ev if e["event_type"] == "analysis.completed"}
        check(done_jobs == set(ctx["completed_jobs"]), "her tamamlanan işe bir olay", (done_jobs, ctx["completed_jobs"]))
        risk_alerts = {e["payload"]["alert_id"] for e in ev if e["event_type"] == "risk.alert.created"}
        check(risk_alerts == {ctx["alert1"], ctx["alert2"]}, "risk olayları alarmlarla aynı", risk_alerts)
        ctx["astro_events"] = {e["event_id"] for e in ev}
        s, _, gev = http("GET", "/notifications/pending", ctx["ground"])
        gtypes = [e["event_type"] for e in gev]
        check(gtypes.count("risk.alert.created") == 2 and "analysis.completed" not in gtypes,
              "kule yalnız 2 risk olayı", gtypes)
        ctx["ground_events"] = [e["event_id"] for e in gev]

    @step("S12 Bildirim", "kule REST receipt → recorded, pending'den düşer; başka kullanıcının olayı 404/403")
    def _():
        eid = ctx["ground_events"][0]
        s, _, b = http("POST", f"/notifications/{eid}/receipt", ctx["ground"])
        check(s == 200 and b["recorded"] is True, "recorded", (s, b))
        s, _, gev = http("GET", "/notifications/pending", ctx["ground"])
        check(eid not in {e["event_id"] for e in gev}, "pending'den düştü", gev)
        other = next(iter(ctx["astro_events"]))
        s, _, b = http("POST", f"/notifications/{other}/receipt", ctx["ground"])
        check(s in (403, 404), "astronotun olayına kule receipt veremez", (s, b))

    @step("S12 Bildirim", "WebSocket: geçersiz token 4401, geçerli token → tüm bekleyen olaylar")
    def _():
        from websockets.exceptions import ConnectionClosed
        from websockets.sync.client import connect
        with connect(WS, open_timeout=10) as ws:
            ws.send(json.dumps({"type": "authenticate", "access_token": "gecersiz"}))
            try:
                ws.recv(timeout=10)
                raise Fail("geçersiz token kabul edildi")
            except ConnectionClosed as e:
                check(e.rcvd and e.rcvd.code == 4401, "4401", e.rcvd)
        got = {}
        with connect(WS, open_timeout=10) as ws:
            ws.send(json.dumps({"type": "authenticate", "access_token": ctx["astro"]}))
            hello = json.loads(ws.recv(timeout=10))
            check(hello["type"] == "authenticated" and hello["role"] == "ASTRONAUT", "authenticated", hello)
            end = time.monotonic() + 8
            while time.monotonic() < end and len(got) < len(ctx["astro_events"]):
                try:
                    m = json.loads(ws.recv(timeout=1))
                except TimeoutError:
                    continue
                got[m["event_id"]] = m
            check(set(got) == ctx["astro_events"], "WS olayları = REST pending",
                  (len(got), len(ctx["astro_events"])))
            for eid in got:
                ws.send(json.dumps({"type": "receipt", "event_id": eid}))
            time.sleep(1.5)
        return f"{len(got)} olay teslim edildi"

    @step("S12 Bildirim", "receipt sonrası yeniden bağlanma: olay tekrar gelmez, REST pending boş")
    def _():
        from websockets.sync.client import connect
        with connect(WS, open_timeout=10) as ws:
            ws.send(json.dumps({"type": "authenticate", "access_token": ctx["astro"]}))
            json.loads(ws.recv(timeout=10))
            extra = []
            end = time.monotonic() + 5
            while time.monotonic() < end:
                try:
                    extra.append(json.loads(ws.recv(timeout=1)))
                except TimeoutError:
                    pass
        check(extra == [], "yeni olay yok", extra)
        s, _, ev = http("GET", "/notifications/pending", ctx["astro"])
        check(s == 200 and ev == [], "pending boş", ev)

    # ---------------- S13 alarm yaşam döngüsü
    @step("S13 Alarm", "OPEN alarm doğrudan kapatılamaz (409); astronot onaylayamaz (403)")
    def _():
        s, _, b = http("POST", f"/ground/alerts/{ctx['alert1']}/resolve", ctx["ground"], {"resolution_note": "erken"})
        check(s == 409 and err_code(b) == "INVALID_STATE_TRANSITION", "409", (s, b))
        s, _, b = http("POST", f"/ground/alerts/{ctx['alert1']}/acknowledge", ctx["astro"])
        check(s == 403, "403", (s, b))

    @step("S13 Alarm", "kule onaylar → ACKNOWLEDGED; tekrar onay idempotent (ilk onaylayan/zaman korunur)")
    def _():
        s, _, a = http("POST", f"/ground/alerts/{ctx['alert1']}/acknowledge", ctx["ground"])
        check(s == 200 and a["status"] == "ACKNOWLEDGED" and a["acknowledged_by"] == ctx["ground_user"]
              and a["acknowledged_at"], "ACKNOWLEDGED", (s, a))
        time.sleep(0.05)
        s, _, b = http("POST", f"/ground/alerts/{ctx['alert1']}/acknowledge", ctx["ground"])
        # Sözleşme (backend-contract.md §acknowledge_alert): "İlk onaylayan/zaman korunur" → 200, değişiklik yok
        check(s == 200 and b["acknowledged_at"] == a["acknowledged_at"]
              and b["acknowledged_by"] == a["acknowledged_by"], "200, aynı onaylayan ve zaman", (s, b))

    @step("S13 Alarm", "boş not 422; notla kapatma → RESOLVED; astronot kendi alarmını RESOLVED görür")
    def _():
        s, _, b = http("POST", f"/ground/alerts/{ctx['alert1']}/resolve", ctx["ground"], {"resolution_note": ""})
        check(s == 422, "422", (s, b))
        note = "Uçuş hekimi bilgilendirildi; ölçüm 1 saat sonra tekrarlanacak."
        s, _, a = http("POST", f"/ground/alerts/{ctx['alert1']}/resolve", ctx["ground"], {"resolution_note": note})
        check(s == 200 and a["status"] == "RESOLVED" and a["resolution_note"] == note
              and a["resolved_by"] == ctx["ground_user"], "RESOLVED", (s, a))
        s, _, mine = http("GET", "/me/alerts", ctx["astro"])
        st = {x["alert_id"]: x["status"] for x in mine}
        check(st.get(ctx["alert1"]) == "RESOLVED" and st.get(ctx["alert2"]) == "OPEN", "RESOLVED + OPEN", st)
        s, _, open_ = http("GET", "/ground/alerts?status=OPEN&astronaut_id=A007", ctx["ground"])
        check({x["alert_id"] for x in open_} == {ctx["alert2"]}, "yalnız ikinci alarm açık", open_)

    # ---------------- S14 bilgi kartları
    card_id = f"e2e-{uuid.uuid4().hex[:8]}"
    card = {"card_id": card_id, "type": "countermeasure", "system": "cardiovascular",
            "metrics": ["heart_rate"], "direction": "up", "text": "E2E test kartı.",
            "source": "e2e", "url": "https://example.org/e2e", "locator": "s.1"}

    @step("S14 Bilgi kartı", "oluştur 201, oku, tekrar oluştur 409, PUT → content_hash değişir, sil 204, sonra 404")
    def _():
        s, _, c = http("POST", "/knowledge-cards", ctx["ground"], card)
        check(s == 201 and c["card_id"] == card_id and len(c["content_hash"]) == 64, "201 + sha256", (s, c))
        s, _, c2 = http("GET", f"/knowledge-cards/{card_id}", ctx["ground"])
        check(s == 200 and c2["content_hash"] == c["content_hash"], "aynı hash", (s, c2))
        s, _, b = http("POST", "/knowledge-cards", ctx["ground"], card)
        check(s == 409, "409", (s, b))
        content = {k: v for k, v in card.items() if k != "card_id"} | {"text": "E2E test kartı (güncel)."}
        s, _, c3 = http("PUT", f"/knowledge-cards/{card_id}", ctx["ground"], content)
        check(s == 200 and c3["content_hash"] != c["content_hash"], "hash değişti", (s, c3))
        s, _, lst = http("GET", "/knowledge-cards?limit=100", ctx["ground"])
        check(s == 200 and isinstance(lst, list), "liste 200", (s, lst))
        s, _, _b = http("DELETE", f"/knowledge-cards/{card_id}", ctx["ground"])
        check(s == 204, "204", s)
        s, _, b = http("GET", f"/knowledge-cards/{card_id}", ctx["ground"])
        check(s == 404, "404", (s, b))

    return report()


# ------------------------------------------------------------------ model (Ollama) aşamaları
def _open_alerts() -> set:
    s, _, al = http("GET", "/ground/alerts?status=OPEN&astronaut_id=A007", ctx["ground"])
    check(s == 200, "alarm listesi 200", (s, al))
    return {a["alert_id"] for a in al}


def _risk_job(value: str, minutes_ago: float):
    before = _open_alerts()
    physio(ctx["astro"], "heart_rate", value, "BPM", ts(minutes_ago))
    st = run_job("physiological")
    return st, _open_alerts() - before


def phase_llm_yok():
    """API LLM_BASE_URL erişilemeyen bir adrese ayarlı: eşik aşımı varken model çağrılır ve düşer."""
    @step("S15 Model erişilemez", "eşik aşımı (nabız 99) + Ollama kapalı → iş yine sonuç üretmeli")
    def _():
        st, new = _risk_job("99", 3)
        ctx["llm_yok"] = (st, new)
        check(st["state"] == "COMPLETED" and st["evaluation_status"] == "evaluated",
              "COMPLETED/evaluated (model yalnız açıklama yazar; kararı kod verir)",
              {k: st[k] for k in ("state", "error_code", "attempts", "evaluation_status")})
        s, _, r = http("GET", f"/me/anomaly-results/{st['anomaly_result_id']}", ctx["astro"])
        check(r["algorithm"] == "threshold_rules" and r["model_version"] is None and r["level"] == "review"
              and "heart_rate 99" in r["summary"], "kural tabanlı sonuç, kodla yazılmış özet",
              (r["algorithm"], r["model_version"], r["level"], r["summary"]))
        return f"{'→'.join(st['_states'])}, deneme={st['attempts']}"

    @step("S15 Model erişilemez", "eşik aşımının alarmı kaybolmamalı")
    def _():
        st, new = ctx["llm_yok"]
        check(len(new) == 1, "1 yeni OPEN alarm", {"yeni_alarm": len(new), "is": st["state"],
                                                   "error_code": st["error_code"], "attempts": st["attempts"]})


def phase_llm_gercek():
    """API gerçek Ollama'ya bağlı (.env LLM_BASE_URL). Ollama veya model yoksa SKIP."""
    probe = os.environ.get("E2E_LLM_PROBE", "").rstrip("/")

    @step("S16 Gerçek model", "Ollama erişilebilir ve model yüklü")
    def _():
        if not probe:
            raise Skip("LLM_BASE_URL tanımlı değil")
        try:
            with urllib.request.urlopen(probe + "/api/tags", timeout=5) as r:
                tags = json.loads(r.read().decode())
        except OSError as e:
            raise Skip(f"Ollama'ya ulaşılamadı ({probe}): {e}") from None
        names = [m.get("name") for m in tags.get("models", [])]
        want = os.environ.get("E2E_LLM_MODEL", "qwen3:14b")
        if want not in names:
            raise Skip(f"{want} yüklü değil; mevcut: {names}")
        ctx["llm_ok"] = want
        return f"{want} hazır"

    @step("S16 Gerçek model", "eşik aşımı → model açıklamalı sonuç, karar yine kodda (review), alarm")
    def _():
        if "llm_ok" not in ctx:
            raise Skip("model hazır değil")
        t0 = time.monotonic()
        st, new = _risk_job("101", 2)
        check(st["state"] == "COMPLETED" and st["evaluation_status"] == "evaluated",
              "COMPLETED/evaluated", {k: st[k] for k in ("state", "error_code", "attempts")})
        s, _, r = http("GET", f"/me/anomaly-results/{st['anomaly_result_id']}", ctx["astro"])
        check(r["level"] == "review" and r["recommendation"].startswith("Uçuş hekimine"),
              "seviye kodla aynı (review)", (r["level"], r["recommendation"][:120]))
        check(len(new) == 1, "1 yeni alarm", len(new))
        check(r["summary"].strip(), "özet boş değil", r["summary"])
        sure = time.monotonic() - t0
        if r["algorithm"] != "threshold_rules_plus_llm":
            raise Skip(f"model süre bütçesinde cevap vermedi ({sure:.0f} sn); kural tabanlı geri dönüş "
                       "devreye girdi, alarm oluştu. Modeli ısıtıp tekrar deneyin.")
        check(r["model_version"] == ctx["llm_ok"], "model sürümü kayıtlı", r["model_version"])
        return f"{sure:.0f} sn; model özeti: {r['summary'][:160]}"


def report() -> int:
    RAPOR.mkdir(parents=True, exist_ok=True)
    ok = sum(r["sonuc"] == "PASS" for r in results)
    skip = sum(r["sonuc"] == "SKIP" for r in results)
    bad = [r for r in results if r["sonuc"] in ("FAIL", "ERROR")]
    summary = {"asama": PHASE, "zaman_utc": iso(NOW), "toplam": len(results), "pass": ok,
               "skip": skip, "fail": len(bad), "risk_seviyesi": ctx.get("risk_level"),
               "risk_oneri": ctx.get("risk_advice"), "adimlar": results}
    name = "e2e_sonuc" if PHASE == "ana" else f"e2e_sonuc_{PHASE}"
    (RAPOR / f"{name}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# ASTRA HEALTH e2e [{PHASE}] — {iso(NOW)}", "",
             f"**{ok}/{len(results)} geçti, {skip} atlandı, {len(bad)} başarısız.**", "",
             "| Senaryo | Adım | Sonuç | Not |", "|---|---|---|---|"]
    for r in results:
        first = r["not"].splitlines()[0][:220] if r["not"] else ""
        lines.append(f"| {r['senaryo']} | {r['adim']} | {r['sonuc']} | {first.replace('|', '/')} |")
    (RAPOR / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSONUÇ [{PHASE}]: {ok}/{len(results)} geçti, {skip} atlandı. Rapor: tests/e2e/rapor/{name}.md", flush=True)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
