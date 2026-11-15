"""Kişisel taban çizgisi: bugünün ölçümü, aynı astronotun önceki günleriyle karşılaştırılır.

Akış (anomali analizi Ö5'in ilk adımı):
  1. Snapshot'taki kabul edilmiş kayıtlar (history_records) ölçüm bağlamına göre gruplanır.
  2. Referans gün (= bugün, model_input.reference_date) "günün verisi"dir; günün birden çok
     kaydı varsa ortalaması alınır.
  3. Referans günden ÖNCEKİ günlerin günlük ortalamaları taban çizgisidir (gün başına bir
     değer: çok kayıtlı gün tabanı şişirmez). Ortalama + popülasyon standart sapması.
  4. z = (bugün − taban ortalaması) / taban std. |z| ≥ z_watch → sapma (izle),
     |z| ≥ z_review → güçlü sapma (hekime yükselt).
Kurallar: sayı uydurulmaz. Bugün kaydı yoksa o ölçüm değerlendirilmez (eski gün "bugün"
sayılmaz). Taban günü min_baseline_days'ten azsa veya std = 0 ise karar verilmez.
Hesap Decimal ile yapılır; z iki ondalığa yuvarlanır (gösterim/karar için yeterli).
"""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal, localcontext
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BaselinePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = Field(min_length=1)
    source_note: str | None = None
    min_baseline_days: int = Field(ge=2)
    z_watch: Decimal = Field(gt=0)
    z_review: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> BaselinePolicy:
        if self.z_review < self.z_watch:
            raise ValueError("z_review, z_watch'tan küçük olamaz.")
        return self


def load_baseline_policy(path: Path) -> BaselinePolicy:
    return BaselinePolicy.model_validate(
        json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal))


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / len(values)


def _fmt(value: Decimal, places: int = 2) -> str:
    """Gösterim için sabit ondalık (ör. '73.58'); bilimsel gösterim yok."""
    return format(value.quantize(Decimal(1).scaleb(-places)), "f")


def baseline_findings(snapshot: dict, policy: BaselinePolicy) -> list[dict]:
    """Her ölçüm için bugün ↔ önceki günler karşılaştırması (status: deviation | within |
    insufficient_baseline | no_variance). Bugün kaydı olmayan ölçüm listede yer almaz."""
    model_input = snapshot.get("model_input") or {}
    reference = model_input.get("reference_date")
    if not reference:
        return []
    groups: dict[tuple, dict[str, list[tuple[str, Decimal]]]] = defaultdict(lambda: defaultdict(list))
    for record in snapshot.get("history_records") or []:
        raw = record.get("value_num_exact")
        if raw in (None, "None") or not record.get("valid", True):
            continue
        value = Decimal(str(raw))
        if not value.is_finite():
            continue
        key = (record["module"], record["measurement"], record["unit"], record.get("protocol_version"))
        groups[key][record["measured_date"]].append((record["record_id"], value))

    findings = []
    for (module, measurement, unit, protocol), by_day in sorted(groups.items()):
        today = by_day.get(reference)
        if not today:
            continue
        with localcontext() as ctx:
            ctx.prec = 40
            today_value = _mean([v for _, v in today])
            prior = [_mean([v for _, v in vals]) for day, vals in sorted(by_day.items()) if day < reference]
            finding = {
                "kind": "baseline", "module": module, "measurement": measurement, "unit": unit,
                "protocol_version": protocol, "measured_date": reference,
                "record_ids": sorted(rid for rid, _ in today),
                "value": _fmt(today_value), "baseline_days": len(prior),
                "baseline_mean": None, "baseline_sd": None, "z": None,
                "direction": None, "severity": None, "policy_version": policy.version,
            }
            if len(prior) < policy.min_baseline_days:
                findings.append(finding | {"status": "insufficient_baseline"})
                continue
            mean = _mean(prior)
            sd = (sum(((v - mean) ** 2 for v in prior), Decimal(0)) / len(prior)).sqrt()
            finding |= {"baseline_mean": _fmt(mean), "baseline_sd": _fmt(sd)}
            if sd == 0:
                findings.append(finding | {"status": "no_variance"})
                continue
            z = ((today_value - mean) / sd).quantize(Decimal("0.01"))
        severity = ("review" if abs(z) >= policy.z_review else
                    "watch" if abs(z) >= policy.z_watch else None)
        findings.append(finding | {
            "z": str(z), "direction": "up" if z > 0 else "down" if z < 0 else None,
            "severity": severity, "status": "deviation" if severity else "within"})
    return findings
