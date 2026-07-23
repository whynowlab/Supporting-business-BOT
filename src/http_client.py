import logging
import socket
import time
from collections.abc import Mapping
from typing import Final

import httpx2

logger = logging.getLogger(__name__)

_LIMITS: Final = httpx2.Limits(
    max_connections=200,
    max_keepalive_connections=40,
    keepalive_expiry=30.0,
)
_TIMEOUT: Final = httpx2.Timeout(
    connect=5.0,
    read=30.0,
    write=10.0,
    pool=10.0,
)
_SOCKET_OPTIONS: Final[list[tuple[int, int, int]]] = [
    (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
]


def _log_request(request: httpx2.Request) -> None:
    request.extensions["request_started_at"] = time.perf_counter()


def _log_response(response: httpx2.Response) -> None:
    started_at = float(response.request.extensions["request_started_at"])
    logger.debug(
        "HTTP response method=%s url=%s status=%s elapsed=%.3f version=%s",
        response.request.method,
        response.request.url.copy_with(query=None),
        response.status_code,
        time.perf_counter() - started_at,
        response.http_version,
    )

def create_client(
    base_url: str = "",
    headers: Mapping[str, str] | None = None,
) -> httpx2.Client:
    transport = httpx2.HTTPTransport(
        http2=True,
        retries=3,
        limits=_LIMITS,
        socket_options=_SOCKET_OPTIONS,
    )
    return httpx2.Client(
        transport=transport,
        timeout=_TIMEOUT,
        base_url=base_url,
        headers=headers,
        event_hooks={"request": [_log_request], "response": [_log_response]},
        follow_redirects=True,
    )
