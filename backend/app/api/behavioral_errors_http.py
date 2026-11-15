"""Davranışsal modül hatalarını HTTP cevabına çevirir.

Gövde biçimi: {"detail": {"code": ..., "message": ..., "fields": [...]}}
Doğrulama hatası yalnız davranış yollarında bu biçime çevrilir; diğer yollarda FastAPI'nin
varsayılan işleyicisi çalışır. Hiçbir şey log'a yazılmaz; doğrulama cevabı gönderilen
değerleri geri yansıtmaz (haftalık cevaplar sızmasın diye yalnız alan adları döner).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.behavioral_module import ErrorDetail, ErrorResponse
from app.services.behavioral_errors import BehavioralError

BEHAVIORAL_PREFIX = "/api/v1/behavioral"
_LOC_SOURCES = {"body", "query", "path", "header", "cookie"}
_UNION_TAGS = {"pvt", "rotation"}      # ayrımlı birleşimde pydantic loc'a eklediği etiketler


def _error_response(status: int, code: str, message: str, fields: list[str]) -> JSONResponse:
    body = ErrorResponse(detail=ErrorDetail(code=code, message=message, fields=fields))
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content=body.model_dump(), headers=headers)


def _field_name(loc: tuple) -> str:
    """loc'un son anlamlı öğesi: ("body", "mood") -> "mood"; ("body", "pvt", "trials", 3, "rt_ms") -> "rt_ms"."""
    names = [p for p in loc if isinstance(p, str) and p not in _UNION_TAGS]
    meaningful = [p for p in names if p not in _LOC_SOURCES]
    if meaningful:
        return meaningful[-1]
    return names[0] if names else "body"


def validation_fields(errors: list[dict]) -> list[str]:
    fields: list[str] = []
    for err in errors:
        if err.get("type") in ("union_tag_invalid", "union_tag_not_found"):
            # ayrımlı birleşim: hatalı alan, ayrımcı alanın kendisi (ör. test_type)
            name = str(err.get("ctx", {}).get("discriminator", "body")).strip("'")
        else:
            name = _field_name(tuple(err.get("loc", ())))
        if name not in fields:
            fields.append(name)
    return fields


async def _behavioral_error_handler(request: Request, exc: BehavioralError) -> JSONResponse:
    return _error_response(exc.status, exc.code, exc.message, exc.fields)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    if not request.url.path.startswith(BEHAVIORAL_PREFIX):
        return await request_validation_exception_handler(request, exc)
    return _error_response(422, "validation_error", "Request validation failed",
                           validation_fields(list(exc.errors())))


def register_behavioral_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BehavioralError, _behavioral_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
