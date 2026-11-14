"""Okuma uçları (Aybala): astronotun kendi geçmişi (/me) ve kule profil/ölçüm özetleri (/ground).

Tarih aralıkları [start, end) — start dahil, end hariç; en fazla 120 gün.
Kule alarm uçları Ömer'in ground router'ındadır; burada yalnız profil ve ölçüm okuması var.
"""
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import require_active_astronaut, require_ground_control
from app.schemas.behavioral import CheckinOut, WeeklyOut
from app.schemas.common import CurrentUser, MeasurementDTO, MeasurementModule
from app.schemas.readings import CognitiveDetailOut, ProfileOut
from app.services import readings

me = APIRouter(prefix="/me", tags=["astronot okuma"])
ground = APIRouter(prefix="/ground/astronauts", tags=["kule okuma"])

Astronaut = Depends(require_active_astronaut)
Ground = Depends(require_ground_control)
DB = Depends(get_db)
Start = Query(description="Başlangıç tarihi (dahil), YYYY-MM-DD")
End = Query(description="Bitiş tarihi (hariç), YYYY-MM-DD")


@me.get("/profile", response_model=ProfileOut)
def get_my_profile(user: CurrentUser = Astronaut, db: Session = DB):
    return readings.my_profile(db, user.astronaut_id)


@me.get("/checkins", response_model=list[CheckinOut])
def list_my_checkins(start: dt.date = Start, end: dt.date = End,
                     user: CurrentUser = Astronaut, db: Session = DB):
    return readings.my_checkins(db, user.astronaut_id, start, end)


@me.get("/weekly-assessments", response_model=list[WeeklyOut])
def list_my_weekly(start: dt.date = Start, end: dt.date = End,
                   user: CurrentUser = Astronaut, db: Session = DB):
    return readings.my_weekly(db, user.astronaut_id, start, end)


@me.get("/cognitive-tests", response_model=list[CognitiveDetailOut])
def list_my_cognitive(start: dt.date = Start, end: dt.date = End,
                      test_type: Literal["pvt", "rotation", "dsst"] | None = None,
                      user: CurrentUser = Astronaut, db: Session = DB):
    return readings.my_cognitive(db, user.astronaut_id, start, end, test_type)


@me.get("/measurements", response_model=list[MeasurementDTO])
def list_my_measurements(start: dt.date = Start, end: dt.date = End,
                         module: MeasurementModule | None = None,
                         user: CurrentUser = Astronaut, db: Session = DB):
    """Grafikler için: fizyolojik + davranış + göz ölçümleri tek formatta."""
    return readings.measurements(db, user.astronaut_id, start, end, module)


@ground.get("", response_model=list[ProfileOut])
def list_profiles(user: CurrentUser = Ground, db: Session = DB):
    return readings.all_profiles(db)


@ground.get("/{astronaut_id}/measurements", response_model=list[MeasurementDTO])
def list_astronaut_measurements(astronaut_id: str, start: dt.date = Start, end: dt.date = End,
                                module: MeasurementModule | None = None,
                                user: CurrentUser = Ground, db: Session = DB):
    """Kulenin paylaşılabilir özet görünümü: haftalık ölçekler dahil değildir."""
    return readings.measurements(db, astronaut_id, start, end, module)
