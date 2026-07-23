import json
import os
import time
from dataclasses import dataclass
from typing import Final

import httpx2
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from src.http_client import create_client
from src.source_result import CollectionStatus, RawItem, SourceBatch

_BASE_URL: Final = "https://www.sbiz24.kr"
_HEADERS: Final[dict[str, str]] = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin-Method": "GET",
    "User-Agent": "Supporting-business-BOT/2.0",
}
_EMPTY_SEARCH: Final[dict[str, JsonValue]] = {
    "searchValue": "",
    "rcrtTypeCdNmList": [],
    "rcrtTypeCdNmListDisplay": "",
    "regionNmList": [],
    "regionNmListDisplay": "",
    "tpbizCdList": [],
    "tpbizCdListDisplay": "",
    "bhis": {"from": None, "to": None},
    "wrkr": {"from": None, "to": None},
    "sls": {"from": None, "to": None},
    "aplySeYn": "N",
    "sbrPbancYn": "N",
    "itrstPbancYn": "N",
    "departNmList": None,
    "searchBox": None,
    "departNmListDisplay": "",
    "ptPbancSortBy": None,
    "pbancNm": None,
    "regionCdList": [],
}


class _ListBlock(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    total: int = Field(ge=0)
    items: tuple[RawItem, ...] = Field(alias="list")


class _ResponseData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    default: _ListBlock


class _ListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    result: bool
    data: _ResponseData


@dataclass(frozen=True, slots=True)
class _Endpoint:
    source: str
    path: str
    id_fields: tuple[str, ...]


_ENDPOINTS: Final = (
    _Endpoint("sbiz24", "/api/pbanc/sbiz24PbancList", ("pbancSn",)),
    _Endpoint("sbiz24_combine", "/api/combinePbanc/list", ("pbancId", "pbancSn")),
)


class Sbiz24Client:
    def _page_size(self) -> int:
        try:
            return max(1, min(200, int(os.getenv("SBIZ24_PAGE_SIZE", "100"))))
        except ValueError:
            return 100

    def _delay_seconds(self) -> float:
        try:
            return max(0.5, float(os.getenv("SBIZ24_REQUEST_DELAY", "0.5")))
        except ValueError:
            return 0.5

    def _collect(self, client: httpx2.Client, endpoint: _Endpoint) -> SourceBatch:
        page_size = self._page_size()
        delay_seconds = self._delay_seconds()
        reported_count: int | None = None
        fetched_count = 0
        start_row = 0
        rows: list[RawItem] = []
        seen: set[str] = set()

        while reported_count is None or start_row < reported_count:
            body: dict[str, JsonValue] = {
                "sortModel": [],
                "search": _EMPTY_SEARCH,
                "paging": True,
                "startRow": start_row,
                "endRow": start_row + page_size,
            }
            try:
                response = client.post(endpoint.path, json=body)
                response.raise_for_status()
                payload = _ListResponse.model_validate(response.json())
            except (httpx2.HTTPError, json.JSONDecodeError, ValidationError) as error:
                status = CollectionStatus.PARTIAL if fetched_count else CollectionStatus.FAILED
                return SourceBatch(
                    source=endpoint.source,
                    items=tuple(rows),
                    status=status,
                    reported_count=reported_count,
                    fetched_count=fetched_count,
                    note=f"{type(error).__name__}: 수집 중단",
                )

            if not payload.result:
                status = CollectionStatus.PARTIAL if fetched_count else CollectionStatus.FAILED
                return SourceBatch(
                    source=endpoint.source,
                    items=tuple(rows),
                    status=status,
                    reported_count=reported_count,
                    fetched_count=fetched_count,
                    note="API result=false",
                )

            block = payload.data.default
            reported_count = block.total
            if not block.items:
                break

            for item in block.items:
                fetched_count += 1
                stable_id = next(
                    (str(item[field]) for field in endpoint.id_fields if item.get(field)),
                    "",
                )
                if stable_id and stable_id not in seen:
                    seen.add(stable_id)
                    rows.append(item)

            start_row += page_size
            if start_row < reported_count:
                time.sleep(delay_seconds)

        status = (
            CollectionStatus.SUCCESS
            if reported_count is not None and fetched_count >= reported_count
            else CollectionStatus.PARTIAL
        )
        note = None if status is CollectionStatus.SUCCESS else "서버 고지 건수보다 적게 수집"
        return SourceBatch(
            source=endpoint.source,
            items=tuple(rows),
            status=status,
            reported_count=reported_count,
            fetched_count=fetched_count,
            note=note,
        )

    def collect_all(self) -> tuple[SourceBatch, SourceBatch]:
        enabled = os.getenv("SBIZ24_ENABLED", "true").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        if not enabled:
            disabled = tuple(
                SourceBatch(
                    source=endpoint.source,
                    items=(),
                    status=CollectionStatus.DISABLED,
                    reported_count=None,
                    fetched_count=0,
                    note="SBIZ24_ENABLED=false",
                )
                for endpoint in _ENDPOINTS
            )
            return disabled[0], disabled[1]

        with create_client(base_url=_BASE_URL, headers=_HEADERS) as client:
            batches = tuple(self._collect(client, endpoint) for endpoint in _ENDPOINTS)
        return batches[0], batches[1]
