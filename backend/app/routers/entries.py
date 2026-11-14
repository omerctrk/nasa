"""Astronotun kendi veri girişi uçları (A7, sahip: Aybala) — önek /api/v1/me.

Yeni kayıt 201, aynı isteğin tekrarı 200 (aynı kayıt döner). Hatalar ortak zarfla:
403 gösterim profili/rol, 409 aynı anahtar farklı içerik, 412 eski ETag, 422 kural ihlali.
"""
import datetime as dt

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import require_active_astronaut
from app.schemas.behavioral import (
    CheckinIn,
    CheckinOut,
    CognitiveIn,
    CognitiveOut,
    WeeklyIn,
    WeeklyOut,
)
from app.schemas.common import CurrentUser
from app.schemas.measurements import PhysiologicalIn, PhysiologicalOut
from app.schemas.sans import EyeSessionIn, EyeSessionOut, HeadacheIn, HeadacheOut
from app.services import data_entry

router = APIRouter(prefix="/me", tags=["veri girişi"])

Astronaut = Depends(require_active_astronaut)
DB = Depends(get_db)


def _status(response: Response, created: bool) -> None:
    response.status_code = 201 if created else 200


@router.get("/checkins/{day}", response_model=CheckinOut)
def get_checkin(day: dt.date, response: Response, user: CurrentUser = Astronaut,
                db: Session = DB):
    out, etag = data_entry.get_checkin(db, user, day)
    response.headers["ETag"] = etag
    return out


@router.put("/checkins/{day}", response_model=CheckinOut,
            responses={201: {"description": "Yeni check-in"}, 412: {"description": "Eski ETag"}})
def put_checkin(day: dt.date, body: CheckinIn, response: Response,
                if_match: str | None = Header(default=None), user: CurrentUser = Astronaut,
                db: Session = DB):
    """Yeni gün: If-Match gönderme. Güncelleme: GET'ten aldığın ETag'i If-Match ile gönder."""
    out, etag, created = data_entry.put_checkin(db, user, day, body, if_match)
    response.headers["ETag"] = etag
    _status(response, created)
    return out


@router.post("/weekly-assessments", response_model=WeeklyOut, status_code=201)
def post_weekly(body: WeeklyIn, response: Response, user: CurrentUser = Astronaut,
                db: Session = DB):
    out, created = data_entry.create_weekly(db, user, body)
    _status(response, created)
    return out


@router.post("/cognitive-tests", response_model=CognitiveOut, status_code=201)
def post_cognitive(body: CognitiveIn, response: Response, user: CurrentUser = Astronaut,
                   db: Session = DB):
    out, created = data_entry.create_cognitive(db, user, body)
    _status(response, created)
    return out


@router.post("/physiological", response_model=PhysiologicalOut, status_code=201)
def post_physiological(body: PhysiologicalIn, response: Response,
                       user: CurrentUser = Astronaut, db: Session = DB):
    out = data_entry.create_physiological(db, user, body)
    _status(response, out.created)
    return out


@router.post("/eye-sessions", response_model=EyeSessionOut, status_code=201)
def post_eye_session(body: EyeSessionIn, response: Response, user: CurrentUser = Astronaut,
                     db: Session = DB):
    """Tam göz oturumu (3 test × OD/OS). Tekrar test için retest_of verilir."""
    out, created = data_entry.create_eye_session(db, user, body)
    _status(response, created)
    return out


@router.post("/symptoms/headache", response_model=HeadacheOut, status_code=201)
def post_headache(body: HeadacheIn, response: Response, user: CurrentUser = Astronaut,
                  db: Session = DB):
    out, created = data_entry.record_headache(db, user, body)
    _status(response, created)
    return out
