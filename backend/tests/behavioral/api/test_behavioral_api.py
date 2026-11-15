"""Davranışsal modül HTTP testleri (TestClient, bellek içi, sabit saat 2026-11-14T09:00:00Z)."""
import uuid
from datetime import timedelta

import pytest

BASE = "/api/v1/behavioral"
A007 = {"Authorization": "Bearer A007"}
A008 = {"Authorization": "Bearer A008"}
TODAY = "2026-11-14"

CHECKIN = {"mood": 6, "energy": 5, "stress": 4, "loneliness": 1, "crew_relation": 3,
           "bed_time": "23:30", "wake_time": "06:45", "sleep_quality": 4}
WEEKLY_ANSWERS = {"who5_1": 3, "who5_2": 2, "who5_3": 3, "who5_4": 2, "who5_5": 2,
                  "phq2_1": 1, "phq2_2": 1, "gad2_1": 2, "gad2_2": 1}


def assert_error(resp, status: int, code: str, fields=None) -> dict:
    """Hata gövdesi tam olarak {"detail": {"code", "message", "fields"}} olmalı."""
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"detail"}
    assert set(body["detail"]) == {"code", "message", "fields"}
    assert body["detail"]["code"] == code
    assert isinstance(body["detail"]["message"], str) and body["detail"]["message"]
    assert isinstance(body["detail"]["fields"], list)
    if fields is not None:
        assert body["detail"]["fields"] == fields
    return body["detail"]


def put_checkin(client, day=TODAY, body=None, headers=A007, **extra_headers):
    return client.put(f"{BASE}/checkins/{day}", json=body or CHECKIN, headers={**headers, **extra_headers})


def create_checkin(client, day=TODAY, body=None, headers=A007):
    return put_checkin(client, day, body, headers, **{"If-None-Match": "*"})


def pvt_body(crid=None, n=40, started_at="2026-11-14T08:50:00Z", finished_at="2026-11-14T08:53:00Z"):
    return {"client_request_id": crid or str(uuid.uuid4()), "test_type": "pvt",
            "started_at": started_at, "finished_at": finished_at, "device": "tablet-1",
            "trials": [{"i": i, "delay_ms": 2000, "rt_ms": 300, "false_start": False} for i in range(1, n + 1)]}


def rotation_body(crid=None):
    trials = [{"i": i, "shape": "s1", "angle": 0, "mirror": i % 2 == 0,
               "answer": "mirror" if i % 2 == 0 else "same", "rt_ms": 1500} for i in range(1, 17)]
    return {"client_request_id": crid or str(uuid.uuid4()), "test_type": "rotation",
            "started_at": "2026-11-14T08:40:00Z", "finished_at": "2026-11-14T08:42:00Z", "trials": trials}


def weekly_body(crid=None, **changes):
    body = {"client_request_id": crid or str(uuid.uuid4()), "answers": dict(WEEKLY_ANSWERS)}
    body.update(changes)
    return body


# ================================================================ kimlik

@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer"}, {"Authorization": "Basic A007"},
                                     {"Authorization": "Bearer astronaut-7"}])
def test_missing_or_invalid_token_is_401(client, headers):
    resp = client.get(f"{BASE}/checkins/{TODAY}", headers=headers)
    assert_error(resp, 401, "unauthorized")
    assert resp.headers["WWW-Authenticate"] == "Bearer"


# ================================================================ check-in

def test_create_checkin(client):
    resp = create_checkin(client)
    assert resp.status_code == 201 and resp.headers["ETag"] == '"c-1-1"'
    body = resp.json()
    assert body["mission_day"] == 75 and body["mood_index"] == 56.7 and body["sleep_hours"] == 7.25
    assert body["symptoms"] == [] and body["date"] == TODAY


def test_get_checkin_same_etag(client):
    create_checkin(client)
    resp = client.get(f"{BASE}/checkins/{TODAY}", headers=A007)
    assert resp.status_code == 200 and resp.headers["ETag"] == '"c-1-1"'
    assert resp.json()["mood"] == 6


def test_update_with_if_match_and_stale_etag(client):
    create_checkin(client)
    updated = put_checkin(client, body={**CHECKIN, "mood": 8}, **{"If-Match": '"c-1-1"'})
    assert updated.status_code == 200 and updated.headers["ETag"] == '"c-1-2"'
    assert updated.json()["mood"] == 8
    stale = put_checkin(client, body={**CHECKIN, "mood": 3}, **{"If-Match": '"c-1-1"'})
    assert_error(stale, 412, "etag_mismatch")


def test_resubmit_same_body_returns_200(client):
    create_checkin(client)
    again = create_checkin(client)
    assert again.status_code == 200 and again.headers["ETag"] == '"c-1-1"'


def test_put_without_precondition_is_428(client):
    assert_error(put_checkin(client), 428, "precondition_required")


def test_future_date_is_422(client):
    assert_error(create_checkin(client, day="2026-11-15"), 422, "future_date", ["date"])


def test_mood_out_of_range(client):
    assert_error(create_checkin(client, body={**CHECKIN, "mood": 11}), 422, "validation_error", ["mood"])


def test_astronaut_id_in_body_rejected(client):
    resp = create_checkin(client, body={**CHECKIN, "astronaut_id": "A008"})
    assert_error(resp, 422, "validation_error", ["astronaut_id"])


def test_invalid_path_date(client):
    assert_error(create_checkin(client, day="2026-13-01"), 422, "validation_error", ["date"])


def test_missing_day_is_404(client):
    assert_error(client.get(f"{BASE}/checkins/{TODAY}", headers=A007), 404, "checkin_not_found")


def test_other_astronaut_cannot_get_checkin(client):
    create_checkin(client)
    assert_error(client.get(f"{BASE}/checkins/{TODAY}", headers=A008), 404, "checkin_not_found")


def test_list_checkins_pagination(client):
    for day in ("2026-11-12", "2026-11-13", TODAY):
        assert create_checkin(client, day=day).status_code == 201
    first = client.get(f"{BASE}/checkins", params={"limit": 2}, headers=A007).json()
    assert [i["date"] for i in first["items"]] == [TODAY, "2026-11-13"] and first["next_cursor"]
    rest = client.get(f"{BASE}/checkins", params={"limit": 2, "cursor": first["next_cursor"]},
                      headers=A007).json()
    assert [i["date"] for i in rest["items"]] == ["2026-11-12"] and rest["next_cursor"] is None


def test_list_checkins_from_to_aliases(client):
    for day in ("2026-11-12", "2026-11-13", TODAY):
        create_checkin(client, day=day)
    resp = client.get(f"{BASE}/checkins", params={"from": "2026-11-13", "to": "2026-11-13"}, headers=A007)
    assert [i["date"] for i in resp.json()["items"]] == ["2026-11-13"]


@pytest.mark.parametrize("params,fields", [({"limit": 101}, ["limit"]), ({"limit": "abc"}, ["limit"]),
                                           ({"from": "2026-11-14", "to": "2026-11-10"}, ["from", "to"])])
def test_list_checkins_invalid_params(client, params, fields):
    resp = client.get(f"{BASE}/checkins", params=params, headers=A007)
    assert_error(resp, 422, "validation_error", fields)


# ================================================================ bilişsel testler

def test_submit_pvt_and_resubmit(client):
    crid = str(uuid.uuid4())
    first = client.post(f"{BASE}/cognitive-tests", json=pvt_body(crid), headers=A007)
    assert first.status_code == 201
    body = first.json()
    assert body["valid"] is True and body["accuracy"] is None and body["mission_day"] == 75
    again = client.post(f"{BASE}/cognitive-tests", json=pvt_body(crid, n=5), headers=A007)
    assert again.status_code == 200 and again.json()["id"] == body["id"]


def test_get_test_has_trials_and_list_does_not(client):
    pvt_id = client.post(f"{BASE}/cognitive-tests", json=pvt_body(), headers=A007).json()["id"]
    client.post(f"{BASE}/cognitive-tests", json=rotation_body(), headers=A007)
    detail = client.get(f"{BASE}/cognitive-tests/{pvt_id}", headers=A007).json()
    assert len(detail["trials"]) == 40
    listing = client.get(f"{BASE}/cognitive-tests", headers=A007).json()
    assert len(listing["items"]) == 2 and all("trials" not in i for i in listing["items"])
    rotation = client.get(f"{BASE}/cognitive-tests", params={"test_type": "rotation"}, headers=A007).json()
    assert [i["test_type"] for i in rotation["items"]] == ["rotation"]


def test_other_astronaut_test_is_404(client):
    test_id = client.post(f"{BASE}/cognitive-tests", json=pvt_body(), headers=A007).json()["id"]
    assert_error(client.get(f"{BASE}/cognitive-tests/{test_id}", headers=A008), 404, "not_found")


def test_unknown_test_type_body_is_422(client):
    resp = client.post(f"{BASE}/cognitive-tests", json={**pvt_body(), "test_type": "dsst"}, headers=A007)
    assert_error(resp, 422, "validation_error", ["test_type"])


def test_unknown_test_type_filter_is_422(client):
    resp = client.get(f"{BASE}/cognitive-tests", params={"test_type": "dsst"}, headers=A007)
    assert_error(resp, 422, "validation_error", ["test_type"])


def test_future_started_at_is_422(client):
    body = pvt_body(started_at="2026-11-14T09:10:00Z", finished_at="2026-11-14T09:13:00Z")
    resp = client.post(f"{BASE}/cognitive-tests", json=body, headers=A007)
    assert_error(resp, 422, "future_date", ["started_at"])


def test_finished_before_started_is_422(client):
    body = pvt_body(started_at="2026-11-14T08:50:00Z", finished_at="2026-11-14T08:49:00Z")
    resp = client.post(f"{BASE}/cognitive-tests", json=body, headers=A007)
    assert_error(resp, 422, "validation_error")


# ================================================================ haftalık

def test_submit_weekly_contract_example(client):
    resp = client.post(f"{BASE}/weekly-assessments", json=weekly_body(), headers=A007)
    assert resp.status_code == 201
    body = resp.json()
    assert (body["who5_score"], body["phq2_score"], body["gad2_score"]) == (48, 2, 3)
    assert body["support_note"] is True and body["share_with_crew_medical"] is False
    assert "answers" not in body


def test_weekly_not_due_and_resubmit(client, clock):
    crid = str(uuid.uuid4())
    first = client.post(f"{BASE}/weekly-assessments", json=weekly_body(crid), headers=A007).json()
    clock.value = clock.value + timedelta(days=6)
    early = client.post(f"{BASE}/weekly-assessments", json=weekly_body(), headers=A007)
    detail = assert_error(early, 409, "weekly_not_due")
    assert "2026-11-21" in detail["message"]
    again = client.post(f"{BASE}/weekly-assessments", json=weekly_body(crid), headers=A007)
    assert again.status_code == 200 and again.json()["id"] == first["id"]


def test_weekly_sharing(client):
    weekly_id = client.post(f"{BASE}/weekly-assessments", json=weekly_body(), headers=A007).json()["id"]
    resp = client.put(f"{BASE}/weekly-assessments/{weekly_id}/sharing",
                      json={"share_with_crew_medical": True}, headers=A007)
    assert resp.status_code == 200 and resp.json()["share_with_crew_medical"] is True
    other = client.put(f"{BASE}/weekly-assessments/{weekly_id}/sharing",
                       json={"share_with_crew_medical": True}, headers=A008)
    assert_error(other, 404, "not_found")


@pytest.mark.parametrize("body,fields", [({"share_with_crew_medical": "yes"}, ["share_with_crew_medical"]),
                                         ({"share_with_crew_medical": True, "x": 1}, ["x"]),
                                         ({}, ["share_with_crew_medical"])])
def test_weekly_sharing_body_validation(client, body, fields):
    weekly_id = client.post(f"{BASE}/weekly-assessments", json=weekly_body(), headers=A007).json()["id"]
    resp = client.put(f"{BASE}/weekly-assessments/{weekly_id}/sharing", json=body, headers=A007)
    assert_error(resp, 422, "validation_error", fields)


def test_weekly_validation_error_does_not_echo_answers(client):
    body = weekly_body()
    body["answers"]["who5_1"] = 6
    resp = client.post(f"{BASE}/weekly-assessments", json=body, headers=A007)
    detail = assert_error(resp, 422, "validation_error", ["who5_1"])
    assert "6" not in resp.text.replace("who5_1", "") and "input" not in resp.text


def test_weekly_list_has_no_answers(client):
    client.post(f"{BASE}/weekly-assessments", json=weekly_body(), headers=A007)
    items = client.get(f"{BASE}/weekly-assessments", headers=A007).json()["items"]
    assert len(items) == 1 and "answers" not in items[0]


# ================================================================ genel

def test_other_route_keeps_default_422_format(client):
    resp = client.post("/other", json={"name": "x", "count": "many"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list) and detail[0]["loc"] == ["body", "count"]
    assert "type" in detail[0] and "msg" in detail[0]


def test_openapi_lists_all_operations(client):
    paths = client.get("/openapi.json").json()["paths"]
    operations = {(method.upper(), path.removeprefix(BASE)) for path, ops in paths.items()
                  for method in ops if path.startswith(BASE)}
    assert operations == {
        ("GET", "/checkins"), ("GET", "/checkins/{date}"), ("PUT", "/checkins/{date}"),
        ("POST", "/cognitive-tests"), ("GET", "/cognitive-tests"), ("GET", "/cognitive-tests/{id}"),
        ("POST", "/weekly-assessments"), ("GET", "/weekly-assessments"),
        ("PUT", "/weekly-assessments/{id}/sharing"), ("GET", "/today"),
    }
    params = {p["name"] for p in paths[f"{BASE}/checkins"]["get"]["parameters"]}
    assert {"from", "to", "limit", "cursor"} <= params
