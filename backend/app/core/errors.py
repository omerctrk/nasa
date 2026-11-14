"""Ortak hata zarfı (sözleşme §4): her hata {"detail": {code, message, trace_id, fields}}.

- Her isteğe trace_id verilir (X-Trace-Id başlığı + hata gövdesi + log).
- Router/servis kodu hata için ApiError fırlatır; repository hataları burada çevrilir.
- Yanıta SQL, token, parola, ham model çıktısı veya sağlık girdisi konmaz.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.repositories import errors as repo_errors
from app.schemas.common import ErrorBody, ErrorCode, ErrorField, ErrorResponse

log = logging.getLogger("astra.errors")

TRACE_HEADER = "X-Trace-Id"

_STATUS_CODES = {
    503: ErrorCode.SERVICE_UNAVAILABLE,
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.VALIDATION_ERROR,
    409: ErrorCode.INVALID_STATE_TRANSITION,
    412: ErrorCode.PRECONDITION_FAILED,
    422: ErrorCode.VALIDATION_ERROR,
}

_DEFAULT_MESSAGES = {
    ErrorCode.SERVICE_UNAVAILABLE: "Servis henüz hazır değil.",
    ErrorCode.UNAUTHORIZED: "Oturum geçersiz veya süresi dolmuş.",
    ErrorCode.FORBIDDEN: "Bu işlem için yetkiniz yok.",
    ErrorCode.NOT_FOUND: "Kayıt bulunamadı.",
    ErrorCode.IDEMPOTENCY_CONFLICT: "Aynı istek anahtarı farklı içerikle kullanıldı.",
    ErrorCode.INVALID_STATE_TRANSITION: "Kayıt bu işlem için uygun durumda değil.",
    ErrorCode.PRECONDITION_FAILED: "Kayıt siz okuduktan sonra değişti; yeniden yükleyin.",
    ErrorCode.VALIDATION_ERROR: "İstek alanlarını kontrol edin.",
    ErrorCode.INTERNAL_ERROR: "Beklenmeyen bir sunucu hatası oluştu.",
}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str | None = None,
        fields: list[ErrorField] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message or _DEFAULT_MESSAGES[code]
        self.fields = fields or []
        self.headers = headers or {}


_REPO_ERRORS: dict[type[repo_errors.RepositoryError], tuple[int, ErrorCode]] = {
    repo_errors.IdempotencyConflict: (409, ErrorCode.IDEMPOTENCY_CONFLICT),
    repo_errors.InvalidStateTransition: (409, ErrorCode.INVALID_STATE_TRANSITION),
    repo_errors.NotFound: (404, ErrorCode.NOT_FOUND),
    repo_errors.ValidationFailed: (422, ErrorCode.VALIDATION_ERROR),
}


def trace_id_of(request: Request) -> uuid.UUID:
    tid = getattr(request.state, "trace_id", None)
    if tid is None:
        tid = request.state.trace_id = uuid.uuid4()
    return tid


def _response(request: Request, status: int, code: ErrorCode, message: str | None = None,
              fields: list[ErrorField] | None = None,
              headers: dict[str, str] | None = None) -> JSONResponse:
    body = ErrorResponse(
        detail=ErrorBody(
            code=code,
            message=message or _DEFAULT_MESSAGES[code],
            trace_id=trace_id_of(request),
            fields=fields or [],
        )
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={**(headers or {}), TRACE_HEADER: str(body.detail.trace_id), "Cache-Control": "no-store"},
    )


def _field_path(loc: tuple) -> str:
    # ("body", "eye") -> "eye";  ("query", "start") -> "start"
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


_PYDANTIC_CODES = {"missing": "REQUIRED", "extra_forbidden": "UNKNOWN_FIELD"}


async def _on_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return _response(request, exc.status_code, exc.code, exc.message, exc.fields, exc.headers)


async def _on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [
        ErrorField(
            field=_field_path(tuple(e.get("loc", ()))),
            code=_PYDANTIC_CODES.get(e.get("type", ""), "INVALID_VALUE"),
            message="Alan değeri geçersiz.",
        )
        for e in exc.errors()
    ]
    return _response(request, 422, ErrorCode.VALIDATION_ERROR, fields=fields)


async def _on_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    status = exc.status_code if exc.status_code in _STATUS_CODES else 500
    return _response(request, status, code)


async def _on_repository(request: Request, exc: repo_errors.RepositoryError) -> JSONResponse:
    for cls, (status, code) in _REPO_ERRORS.items():
        if isinstance(exc, cls):
            return _response(request, status, code)
    return await _on_unexpected(request, exc)


async def _on_unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.error("code=INTERNAL_ERROR trace_id=%s", trace_id_of(request))
    return _response(request, 500, ErrorCode.INTERNAL_ERROR)


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def _trace(request: Request, call_next):
        tid = trace_id_of(request)
        response = await call_next(request)
        response.headers.setdefault(TRACE_HEADER, str(tid))
        return response

    app.add_exception_handler(ApiError, _on_api_error)
    app.add_exception_handler(RequestValidationError, _on_validation)
    app.add_exception_handler(StarletteHTTPException, _on_http)
    app.add_exception_handler(repo_errors.RepositoryError, _on_repository)
    app.add_exception_handler(Exception, _on_unexpected)
