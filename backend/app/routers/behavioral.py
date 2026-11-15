"""Davranışsal modül HTTP uçları.

Router yalnız doğrular ve servisi çağırır; iş kuralı servislerdedir.
"""
from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Query, Response

from app.api.deps_behavioral import (
    get_checkin_service, get_current_astronaut_id, get_test_service, get_today_service,
    get_weekly_service,
)
from app.schemas.behavioral_module import (
    CheckinIn, CheckinOut, CognitiveTestDetail, CognitiveTestIn, CognitiveTestOut,
    ErrorResponse, Page, SharingIn, TodayOut, WeeklyIn, WeeklyOut,
)
from app.services.behavioral_checkins import CheckinService
from app.services.behavioral_paging import DEFAULT_LIMIT
from app.services.behavioral_tests import CognitiveTestService
from app.services.behavioral_today import TodayService
from app.services.behavioral_weekly import WeeklyService

router = APIRouter(prefix="/api/v1/behavioral", tags=["behavioral"])

AstronautId = Annotated[str, Depends(get_current_astronaut_id)]
Checkins = Annotated[CheckinService, Depends(get_checkin_service)]
Tests = Annotated[CognitiveTestService, Depends(get_test_service)]
Weekly = Annotated[WeeklyService, Depends(get_weekly_service)]
Today = Annotated[TodayService, Depends(get_today_service)]

DateFrom = Annotated[dt.date | None, Query(alias="from", description="Inclusive start date (YYYY-MM-DD)")]
DateTo = Annotated[dt.date | None, Query(alias="to", description="Inclusive end date (YYYY-MM-DD)")]
Limit = Annotated[int, Query(description="Page size, 1-100")]
Cursor = Annotated[str | None, Query(description="Opaque cursor from next_cursor")]

ETAG_HEADER = {"ETag": {"description": 'Record version, e.g. "c-1-2"', "schema": {"type": "string"}}}


def _errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    descriptions = {
        401: "Missing or invalid bearer token (unauthorized)",
        404: "Record not found or belongs to another astronaut",
        409: "Weekly assessment is not due yet (weekly_not_due)",
        412: "ETag does not match (etag_mismatch)",
        422: "Validation error, future date",
        428: "Exactly one of If-Match / If-None-Match is required (precondition_required)",
    }
    return {s: {"model": ErrorResponse, "description": descriptions[s]} for s in (401, 422, *statuses)}


# ---------------------------------------------------------------- bugün

@router.get("/today", response_model=TodayOut, responses=_errors(),
            summary="Today's tasks and missing-data signals (no weekly scores)")
def get_today(astronaut_id: AstronautId, service: Today):
    return service.today(astronaut_id)


# ---------------------------------------------------------------- check-in

@router.get("/checkins", response_model=Page[CheckinOut], responses=_errors(),
            summary="List daily check-ins (newest first)")
def list_checkins(astronaut_id: AstronautId, service: Checkins, date_from: DateFrom = None,
                  date_to: DateTo = None, limit: Limit = DEFAULT_LIMIT, cursor: Cursor = None):
    return service.list(astronaut_id, date_from, date_to, limit, cursor)


@router.get("/checkins/{date}", response_model=CheckinOut,
            responses={200: {"headers": ETAG_HEADER}, **_errors(404)},
            summary="Get the check-in for one day")
def get_checkin(date: dt.date, response: Response, astronaut_id: AstronautId, service: Checkins):
    out, etag = service.get(astronaut_id, date)
    response.headers["ETag"] = etag
    return out


@router.put("/checkins/{date}", response_model=CheckinOut,
            responses={200: {"description": "Updated, or same body resubmitted", "headers": ETAG_HEADER},
                       201: {"model": CheckinOut, "description": "Created", "headers": ETAG_HEADER},
                       **_errors(412, 428)},
            summary="Create (If-None-Match: *) or update (If-Match) the check-in for one day")
def put_checkin(date: dt.date, data: CheckinIn, response: Response, astronaut_id: AstronautId,
                service: Checkins,
                if_match: Annotated[str | None, Header(alias="If-Match")] = None,
                if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None):
    out, etag, created = service.put(astronaut_id, date, data, if_match, if_none_match)
    response.headers["ETag"] = etag
    response.status_code = 201 if created else 200
    return out


# ---------------------------------------------------------------- bilişsel testler

@router.post("/cognitive-tests", response_model=CognitiveTestOut,
             responses={200: {"description": "Same client_request_id already submitted; first record"},
                        201: {"model": CognitiveTestOut, "description": "Created"},
                        **_errors()},
             summary="Submit a PVT or mental rotation session")
def submit_test(data: Annotated[CognitiveTestIn, Body()], response: Response,
                astronaut_id: AstronautId, service: Tests):
    out, created = service.submit(astronaut_id, data)
    response.status_code = 201 if created else 200
    return out


@router.get("/cognitive-tests", response_model=Page[CognitiveTestOut], responses=_errors(),
            summary="List cognitive tests without trials (newest first)")
def list_tests(astronaut_id: AstronautId, service: Tests,
               test_type: Annotated[str | None, Query(description='"pvt" or "rotation"')] = None,
               date_from: DateFrom = None, date_to: DateTo = None,
               limit: Limit = DEFAULT_LIMIT, cursor: Cursor = None):
    return service.list(astronaut_id, date_from, date_to, test_type, limit, cursor)


@router.get("/cognitive-tests/{id}", response_model=CognitiveTestDetail, responses=_errors(404),
            summary="Get one cognitive test with its trials")
def get_test(id: int, astronaut_id: AstronautId, service: Tests):
    return service.get(astronaut_id, id)


# ---------------------------------------------------------------- haftalık ölçekler

@router.post("/weekly-assessments", response_model=WeeklyOut,
             responses={200: {"description": "Same client_request_id already submitted; first record"},
                        201: {"model": WeeklyOut, "description": "Created"},
                        **_errors(409)},
             summary="Submit the weekly WHO-5 / PHQ-2 / GAD-2 assessment")
def submit_weekly(data: WeeklyIn, response: Response, astronaut_id: AstronautId, service: Weekly):
    out, created = service.submit(astronaut_id, data)
    response.status_code = 201 if created else 200
    return out


@router.get("/weekly-assessments", response_model=Page[WeeklyOut], responses=_errors(),
            summary="List weekly assessment scores without item answers (newest first)")
def list_weekly(astronaut_id: AstronautId, service: Weekly, date_from: DateFrom = None,
                date_to: DateTo = None, limit: Limit = DEFAULT_LIMIT, cursor: Cursor = None):
    return service.list(astronaut_id, date_from, date_to, limit, cursor)


@router.put("/weekly-assessments/{id}/sharing", response_model=WeeklyOut, responses=_errors(404),
            summary="Share or unshare a weekly assessment with the crew medical officer")
def set_weekly_sharing(id: int, data: SharingIn, astronaut_id: AstronautId, service: Weekly):
    return service.set_sharing(astronaut_id, id, data.share_with_crew_medical)
