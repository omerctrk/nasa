"""Ö5 model adaptörü: Yusuf'un kart önericisine (kart_onerici.oner) Ollama çağrısı enjekte eder.

- `ollama` paketi yerine düz HTTP (urllib) kullanılır; ek bağımlılık yok.
- Bağlantı/zaman aşımı → TransientModelError (işçi bir kez otomatik tekrar dener).
- 4xx → PermanentModelError (tekrar düzeltmez). Model yanıtı/hata metni loglanmaz.
- Senkron çalışır; işçi bunu thread'de çağırır, açık DB transaction'ı yoktur.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable

from app.providers import kart_onerici
from app.workers.analysis import PermanentModelError, TransientModelError

Sor = Callable[[list, dict, int], dict]


def ollama_sor(base_url: str, model: str, connect_timeout: float, total_timeout: float) -> Sor:
    url = base_url.rstrip("/") + "/api/chat"
    timeout = max(connect_timeout, total_timeout)

    def post(body: dict) -> dict:
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (ayarlı adres)
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raise PermanentModelError() from None
            raise TransientModelError() from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError):
            raise TransientModelError() from None

    def sor(mesajlar: list, sema: dict, deneme: int = 0) -> dict:
        secenekler = dict(kart_onerici.SECENEKLER)
        if deneme:
            secenekler.update(temperature=0.3, seed=deneme)
        body = {"model": model, "messages": mesajlar, "options": secenekler,
                "stream": False, "think": False, "keep_alive": "1h", "format": sema}
        try:
            yanit = post(body)
        except PermanentModelError:
            # Eski Ollama sürümü şema sınırlarını reddederse sınırsız şemayla bir kez dene.
            yanit = post(body | {"format": kart_onerici._sade_sema(sema)})
        # Bozuk içerik json.JSONDecodeError/KeyError verir; oner() bunu deneme hatası sayar.
        return json.loads(yanit["message"]["content"])

    return sor
