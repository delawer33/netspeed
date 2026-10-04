"""Один замер: скачать тело ответа целиком и засечь время до последнего байта."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

CHUNK_SIZE = 64 * 1024
MEGABYTE = 1_000_000  # десятичный мегабайт, как у провайдеров и speedtest-сервисов
USER_AGENT = "netspeed/0.1"


@dataclass(frozen=True)
class Sample:
    """Успешный запрос: сколько байт тела пришло и за сколько секунд."""

    body_bytes: int
    seconds: float

    @property
    def megabytes_per_second(self) -> float:
        return self.body_bytes / self.seconds / MEGABYTE


class FetchError(Exception):
    """Запрос не дал пригодного замера: сеть, HTTP-ошибка, таймаут или оборванное тело."""


def fetch(url: str, timeout: float) -> Sample:
    """Скачивает ``url`` и возвращает замер.

    Время считается от отправки запроса до последнего байта тела. Время до
    заголовков (``response.elapsed`` в requests) для скорости бесполезно:
    на тяжёлом файле почти всё время уходит на тело.

    ``timeout`` — предел на весь запрос, а не только на одну операцию сокета.
    """
    received = 0
    started = time.perf_counter()
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                # Сжатое тело исказило бы объём, кэш прокси/CDN — время.
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            expected = _content_length(response.headers.get("Content-Length"))
            while chunk := response.read(CHUNK_SIZE):
                received += len(chunk)
                if time.perf_counter() - started > timeout:
                    raise FetchError(f"не уложился в {timeout:g} с")
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"сеть: {exc.reason}") from exc
    except (http.client.HTTPException, OSError) as exc:
        raise FetchError(f"обрыв соединения: {exc!r}") from exc
    except ValueError as exc:  # кривой URL: битый IPv6, пустая метка домена
        raise FetchError(f"некорректный адрес: {exc}") from exc
    elapsed = time.perf_counter() - started

    if expected is not None and received != expected:
        raise FetchError(f"тело оборвано: получено {received} из {expected} байт")
    if received == 0:
        raise FetchError("пустое тело ответа")
    return Sample(body_bytes=received, seconds=elapsed)


def _content_length(header: str | None) -> int | None:
    if header is None:
        return None
    value = header.strip()
    return int(value) if value.isdigit() else None
