"""Analiz sonucu ve alarm uçları (Ömer'in kalan "ground/notifications" kısmı, Aybala).

Astronot (/me, salt okuma):
  GET  /me/anomaly-results?start&end      kendi sonuçları ([start, end), en fazla 120 gün)
  GET  /me/anomaly-results/{id}           tek sonuç (iş durumundaki anomaly_result_id ile)
  GET  /me/alerts?status=OPEN             kendi alarmları
Kule (/ground):
  GET  /ground/astronauts/{id}/anomaly-results?start&end
  GET  /ground/anomaly-results/{id}
  GET  /ground/alerts?status=OPEN&status=ACKNOWLEDGED&astronaut_id=A007
  POST /ground/alerts/{id}/acknowledge    "gördüm" (ilk onaylayan korunur)
  POST /ground/alerts/{id}/resolve        {"resolution_note": "..."} (yalnız ACKNOWLEDGED)
"""
import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import require_active_astronaut, require_ground_control
from app.schemas.common import AlertStatus, CurrentUser
from app.schemas.notifications import AlertOut, AnomalyResultOut, ResolveIn
from app.services import alerts as svc

me = APIRouter(prefix="/me", tags=["astronot sonuç/alarm"])
ground = APIRouter(prefix="/ground", tags=["kule sonuç/alarm"])

Astronaut = Depends(require_active_astronaut)
Ground = Depends(require_ground_control)
DB = Depends(get_db)
Start = Query(description="Başlangıç tarihi (dahil), YYYY-MM-DD")
End = Query(description="Bitiş tarihi (hariç), YYYY-MM-DD")
Statuses = Query(default=None, alias="status", description="Birden çok verilebilir")


@me.get("/anomaly-results", response_model=list[AnomalyResultOut])
def my_results(start: dt.date = Start, end: dt.date = End,
               user: CurrentUser = Astronaut, db: Session = DB):
    return svc.results(db, user.astronaut_id, start, end)


@me.get("/anomaly-results/{result_id}", response_model=AnomalyResultOut)
def my_result(result_id: uuid.UUID, user: CurrentUser = Astronaut, db: Session = DB):
    return svc.result(db, result_id, astronaut_id=user.astronaut_id)


@me.get("/alerts", response_model=list[AlertOut])
def my_alerts(status: list[AlertStatus] | None = Statuses,
              user: CurrentUser = Astronaut, db: Session = DB):
    return svc.alerts(db, status, astronaut_id=user.astronaut_id)


@ground.get("/astronauts/{astronaut_id}/anomaly-results", response_model=list[AnomalyResultOut])
def astronaut_results(astronaut_id: str, start: dt.date = Start, end: dt.date = End,
                      user: CurrentUser = Ground, db: Session = DB):
    return svc.results(db, astronaut_id, start, end)


@ground.get("/anomaly-results/{result_id}", response_model=AnomalyResultOut)
def any_result(result_id: uuid.UUID, user: CurrentUser = Ground, db: Session = DB):
    return svc.result(db, result_id)


@ground.get("/alerts", response_model=list[AlertOut])
def list_alerts(status: list[AlertStatus] | None = Statuses, astronaut_id: str | None = None,
                user: CurrentUser = Ground, db: Session = DB):
    return svc.alerts(db, status, astronaut_id)


@ground.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: uuid.UUID, user: CurrentUser = Ground, db: Session = DB):
    return svc.acknowledge(db, alert_id, user.user_id)


@ground.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: uuid.UUID, body: ResolveIn, user: CurrentUser = Ground, db: Session = DB):
    return svc.resolve(db, alert_id, user.user_id, body.resolution_note)
