from src.run_once import _apply_hard_filter, _ingest_all
from src.source_result import CollectionStatus, SourceBatch


class FakeBizinfoClient:
    def fetch_support_programs(self):
        return [{
            "pblancId": "PBLN_B1",
            "pblancNm": "기업마당 지원사업",
            "pblancSumry": "요약",
        }]

    def fetch_events(self):
        return [{
            "eventInfoId": "E1",
            "nttNm": "기업마당 행사",
            "nttCn": "행사 내용",
        }]


class FakeFanfandaeroClient:
    def fetch_support_programs(self):
        return [{
            "sprtBizCd": "F1",
            "sprtBizNm": "판판대로 지원사업",
            "txtDc": "판로 지원",
        }]


class FakeSbiz24Client:
    def collect_all(self):
        return (
            SourceBatch(
                source="sbiz24",
                items=({
                    "pbancSn": 10,
                    "pbancNm": "소진공 직접 공고",
                    "aplyPsbltySe": "Y",
                },),
                status=CollectionStatus.SUCCESS,
                reported_count=1,
                fetched_count=1,
            ),
            SourceBatch(
                source="sbiz24_combine",
                items=({
                    "pbancId": "PBLN_B1",
                    "pbancNm": "기업마당 지원사업",
                    "aplyPsbltySe": "신청가능",
                },),
                status=CollectionStatus.SUCCESS,
                reported_count=1,
                fetched_count=1,
            ),
        )


def test_ingest_all_includes_sbiz24_and_deduplicates_cross_source(monkeypatch):
    saved = []
    logs = []

    monkeypatch.setattr("src.source_ingestion.upsert_program", lambda item: saved.append(item))
    monkeypatch.setattr("src.source_ingestion.log_ingestion_run", lambda item: logs.append(item))

    outcome = _ingest_all(
        FakeBizinfoClient(),
        FakeFanfandaeroClient(),
        FakeSbiz24Client(),
    )

    assert [item["source"] for item in outcome.items] == [
        "bizinfo",
        "bizinfo",
        "fanfandaero",
        "sbiz24",
    ]
    assert len(saved) == 5
    assert [item["kind"] for item in logs] == [
        "support",
        "event",
        "fanfandaero_support",
        "sbiz24",
        "sbiz24_combine",
    ]
    assert [entry.source for entry in outcome.coverage] == [
        "bizinfo_support",
        "bizinfo_event",
        "fanfandaero",
        "sbiz24",
        "sbiz24_combine",
    ]


def test_ingest_all_marks_zero_required_source_as_failed(monkeypatch):
    class EmptyBizinfoClient:
        def fetch_support_programs(self):
            return []

        def fetch_events(self):
            return []

    monkeypatch.setattr("src.source_ingestion.upsert_program", lambda _item: None)
    monkeypatch.setattr("src.source_ingestion.log_ingestion_run", lambda _item: None)

    outcome = _ingest_all(
        EmptyBizinfoClient(),
        FakeFanfandaeroClient(),
        FakeSbiz24Client(),
    )

    assert outcome.coverage[0].status is CollectionStatus.FAILED
    assert outcome.coverage[1].status is CollectionStatus.FAILED


def test_hard_filter_splits_clear_noise_from_candidates():
    items = [
        {"title": "TV홈쇼핑 입점지원", "summary_raw": "온라인쇼핑몰"},
        {"title": "MRO 공공조달 컨설팅", "summary_raw": "입찰 성공률 제고"},
    ]

    candidates, rejected = _apply_hard_filter(items)

    assert [item["title"] for item in candidates] == ["MRO 공공조달 컨설팅"]
    assert rejected[0][0]["title"] == "TV홈쇼핑 입점지원"
