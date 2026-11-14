"""WebSocket bildirimleri: /ws/v1/notifications (sözleşme §10; Ömer'in kalan kısmı, Aybala).

Protokol:
  1. İstemci bağlanır, 5 sn içinde {"type":"authenticate","access_token":"<jwt>"} gönderir.
     Gelmezse / token geçersizse bağlantı 4401 ile kapanır.
  2. Sunucu {"type":"authenticated"} der; ardından bekleyen olayları gönderir:
     {"event_id","type","created_at","payload"}. Olay önce DB'ye yazılmıştır (persist adımı).
  3. İstemci her olay için {"type":"receipt","event_id"} gönderir → EventReceipts.
     Teslim alınmayan olay yeniden bağlanınca tekrar gelir; frontend event_id ile ayıklar.
  4. Token süresi dolunca bağlantı 4401 ile kapanır (istemci yeni token'la yeniden bağlanır).

Yeni olaylar ws_poll_seconds aralığıyla DB'den okunur (tek API worker; ayrı mesaj kuyruğu yok).
Her DB işlemi kendi thread'inde kendi Session'ını açar/kapatır.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import contextmanager

import anyio
import jwt
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.errors import ApiError
from app.schemas.common import WS_NOTIFICATIONS_PATH

log = logging.getLogger("astra.ws")
router = APIRouter()

CLOSE_UNAUTHORIZED = 4401
CLOSE_BAD_MESSAGE = 4400


@contextmanager
def _repository():
    from app.db.session import SessionLocal
    from app.repositories.sqlalchemy_repository import SqlAlchemyRepository

    with SessionLocal.begin() as session:
        yield SqlAlchemyRepository(session)


def _pending(user_id: uuid.UUID, already_sent: set[uuid.UUID]) -> list[dict]:
    with _repository() as repo:
        events = [e for e in repo.list_pending_events(user_id) if e.event_id not in already_sent]
        for event in events:
            repo.mark_event_sent(event.event_id)
    return [{"event_id": str(e.event_id), "type": e.event_type.value,
             "created_at": e.created_at.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z",
             "payload": e.payload} for e in events]


def _receipt(event_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with _repository() as repo:
        repo.record_receipt(event_id, user_id)


def _token_expiry(token: str) -> float:
    # İmza resolve_user içinde zaten doğrulandı; burada yalnız exp okunur.
    return float(jwt.decode(token, options={"verify_signature": False})["exp"])


async def _authenticate(ws: WebSocket, timeout: float):
    try:
        message = await asyncio.wait_for(ws.receive_json(), timeout)
    except (TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        return None, None
    if not isinstance(message, dict) or message.get("type") != "authenticate" \
            or not isinstance(message.get("access_token"), str):
        return None, None
    service = getattr(ws.app.state, "auth_service", None)
    if service is None:
        return None, None
    token = message["access_token"]
    try:
        user = await run_in_threadpool(service.resolve_user, token)
        return user, _token_expiry(token)
    except (ApiError, jwt.InvalidTokenError, KeyError, ValueError):
        return None, None


@router.websocket(WS_NOTIFICATIONS_PATH)
async def notifications(ws: WebSocket):
    settings = get_settings()
    await ws.accept()
    user, expires_at = await _authenticate(ws, settings.ws_auth_timeout_seconds)
    if user is None:
        await ws.close(code=CLOSE_UNAUTHORIZED)
        return
    await ws.send_json({"type": "authenticated", "user_id": str(user.user_id), "role": user.role.value})
    sent: set[uuid.UUID] = set()

    async def sender():
        while True:
            for event in await run_in_threadpool(_pending, user.user_id, sent):
                await ws.send_json(event)
                sent.add(uuid.UUID(event["event_id"]))
            await asyncio.sleep(settings.ws_poll_seconds)

    async def receiver():
        while True:
            message = await ws.receive_json()
            if not isinstance(message, dict) or message.get("type") != "receipt":
                continue
            try:
                event_id = uuid.UUID(str(message.get("event_id")))
            except ValueError:
                continue
            if event_id in sent:  # yalnız bu bağlantıda bu kullanıcıya gönderilen olay
                await run_in_threadpool(_receipt, event_id, user.user_id)

    async def expiry():
        await asyncio.sleep(max(0.0, expires_at - time.time()))

    # anyio görev grubu: biri biterse (kopma, süre dolumu, hata) diğerleri düzgün iptal edilir;
    # sunucu kapanırken gelen iptal de doğru yayılır.
    expired = False
    async with anyio.create_task_group() as group:
        async def run(part):
            nonlocal expired
            try:
                await part()
                expired = part is expiry
            except WebSocketDisconnect:
                pass
            except Exception:  # noqa: BLE001 — bağlantı kapanır, içerik loglanmaz
                log.error("code=WS_FAILED user_id=%s", user.user_id)
            finally:
                group.cancel_scope.cancel()
        for part in (sender, receiver, expiry):
            group.start_soon(run, part)
    if expired:
        await ws.close(code=CLOSE_UNAUTHORIZED)


def install_notifications(app: FastAPI) -> None:
    app.include_router(router)
