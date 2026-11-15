"""MeasurementRepository'nin gerçek uygulaması (A5, sahip: Aybala).

get_measurements  → anomaly.v_measurements'tan ortak ölçüm DTO'su
get_sans_context  → SANS API paketi için profil, oturumlar, göz geçmişi, CO₂, semptom, durum

SANS bağlamında "gelecek" görev gününe göre kesilir: analiz edilen oturumun flight_day'inden
sonraki hiçbir oturum/test/CO₂/semptom pakete girmez. Demo görev takvimi simüle edildiği
(M01 gün 0 = 2027-01-05) ve sans tablolarında kayıt zamanı olmadığı için gerçek saat
(data_cutoff_at) ile takvim tarihi karşılaştırılmaz; data_cutoff_at denetim için pakette kalır.
evaluation şemasına dokunulmaz.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.identity import Astronaut
from app.models.sans import Durum, Ortam, Oturum, Semptom
from app.repositories.errors import RepositoryError
from app.repositories.records import (
    Co2Day,
    SansContext,
    SansSessionRecord,
    SansStateRecord,
    SymptomDay,
)
from app.repositories.sqlalchemy_identity import _astronaut
from app.schemas.common import MeasurementDTO, SansState

COLUMNS = (
    "record_id, astronaut_id, mission_id, module, measurement, value_num, value_text, unit, "
    "protocol_version, measured_date, measured_at, time_precision, mission_day, eye, source, "
    "valid, quality_score, session_id, metadata_json"
)


class MissingDefinition(RepositoryError):
    """VIEW'daki bir ölçüm kodunun anomaly.MeasurementDefinitions'ta tanımı yok (seed eksik)."""


def _dto(row: Any) -> MeasurementDTO:
    m = row._mapping
    measured_at = m["measured_at"]
    if measured_at is not None and measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=dt.UTC)  # DB'de saat dilimsiz UTC
    return MeasurementDTO(
        record_id=m["record_id"],
        astronaut_id=m["astronaut_id"],
        mission_id=m["mission_id"],
        module=m["module"],
        measurement=m["measurement"],
        value_num=m["value_num"],
        value_text=m["value_text"],
        unit=m["unit"],
        protocol_version=m["protocol_version"],
        measured_date=m["measured_date"],
        measured_at=measured_at,
        time_precision=m["time_precision"],
        mission_day=m["mission_day"],
        eye=m["eye"].strip() if m["eye"] else None,
        source=m["source"],
        valid=bool(m["valid"]),
        quality_score=m["quality_score"],
        session_id=m["session_id"],
        metadata_json=json.loads(m["metadata_json"]) if m["metadata_json"] else None,
    )


def _rows_to_dtos(rows: list[Any]) -> list[MeasurementDTO]:
    missing = sorted({r._mapping["measurement"] for r in rows
                      if r._mapping["protocol_version"] is None or r._mapping["unit"] is None})
    if missing:
        raise MissingDefinition(
            "Ölçüm sözlüğünde tanımı olmayan kod(lar): " + ", ".join(missing)
            + " — anomaly.MeasurementDefinitions seed'ini kontrol edin (A6)."
        )
    return [_dto(r) for r in rows]


def _session(row: Oturum) -> SansSessionRecord:
    return SansSessionRecord(
        session_id=row.session_id,
        flight_day=row.flight_day,
        date=row.date,
        is_retest=row.is_retest,
        retest_of=row.retest_of,
        quality_score=row.quality_score,
        source=row.source,
    )


class SqlAlchemyMeasurementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_measurements(self, astronaut_id: str, start_date: dt.date,
                         end_date: dt.date) -> list[MeasurementDTO]:
        rows = self.session.execute(
            text(
                f"SELECT {COLUMNS} FROM anomaly.v_measurements "
                "WHERE astronaut_id = :a AND measured_date >= :s AND measured_date < :e "
                "ORDER BY measured_date, measured_at, record_id"
            ),
            {"a": astronaut_id, "s": start_date, "e": end_date},
        ).all()
        return _rows_to_dtos(rows)

    def get_sans_context(self, astronaut_id: str, session_id: str,
                         data_cutoff_at: dt.datetime) -> SansContext | None:
        astro = self.session.get(Astronaut, astronaut_id)
        current = self.session.scalars(
            select(Oturum).where(Oturum.session_id == session_id,
                                 Oturum.astronaut_id == astronaut_id)
        ).one_or_none()
        if astro is None or current is None:
            return None

        last_day = current.flight_day

        sessions = self.session.scalars(
            select(Oturum)
            .where(Oturum.astronaut_id == astronaut_id, Oturum.flight_day <= last_day)
            .order_by(Oturum.flight_day, Oturum.session_id)
        ).all()
        eye_rows = self.session.execute(
            text(
                f"SELECT {COLUMNS} FROM anomaly.v_measurements "
                "WHERE astronaut_id = :a AND module = 'sans' AND mission_day <= :d "
                "ORDER BY mission_day, record_id"
            ),
            {"a": astronaut_id, "d": last_day},
        ).all()
        co2 = self.session.scalars(
            select(Ortam).where(Ortam.mission_id == astro.mission_id, Ortam.day <= last_day)
            .order_by(Ortam.day)
        ).all()
        symptoms = self.session.scalars(
            select(Semptom).where(Semptom.astronaut_id == astronaut_id,
                                  Semptom.flight_day <= last_day)
            .order_by(Semptom.flight_day)
        ).all()
        state = self.session.get(Durum, astronaut_id)

        return SansContext(
            profile=_astronaut(astro),
            session=_session(current),
            baseline_sessions=[_session(s) for s in sessions if s.flight_day < 0],
            eye_history=_rows_to_dtos(eye_rows),
            co2=[Co2Day(day=r.day, co2_mmhg=r.co2_mmhg, source=r.source) for r in co2],
            symptoms=[SymptomDay(flight_day=r.flight_day, headache=r.headache) for r in symptoms],
            state=SansStateRecord(
                astronaut_id=state.astronaut_id, state=SansState(state.state),
                since_flight_day=state.since_flight_day, retest_due_day=state.retest_due_day,
                last_analysis_id=state.last_analysis_id,
            ) if state else None,
            data_cutoff_at=data_cutoff_at,
        )
