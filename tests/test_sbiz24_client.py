from src.sbiz24_client import Sbiz24Client
from src.source_result import CollectionStatus


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, path, json):
        self.calls.append((path, json["startRow"], json["endRow"]))
        if path.endswith("sbiz24PbancList"):
            rows = (
                [{"pbancSn": 1}, {"pbancSn": 2}]
                if json["startRow"] == 0
                else [{"pbancSn": 3}]
            )
            return FakeResponse({"result": True, "data": {"default": {"total": 3, "list": rows}}})

        return FakeResponse({
            "result": True,
            "data": {"default": {
                "total": 2,
                "list": [{"pbancId": "PBLN_1"}, {"pbancId": "PBLN_1"}],
            }},
        })


def test_sbiz24_collects_both_lists_to_reported_total(monkeypatch):
    fake_client = FakeClient()
    factory_args = {}

    def fake_create_client(**kwargs):
        factory_args.update(kwargs)
        return fake_client

    monkeypatch.setenv("SBIZ24_PAGE_SIZE", "2")
    monkeypatch.setattr("src.sbiz24_client.create_client", fake_create_client)
    monkeypatch.setattr("src.sbiz24_client.time.sleep", lambda _seconds: None)

    own, combined = Sbiz24Client().collect_all()

    assert own.status is CollectionStatus.SUCCESS
    assert own.reported_count == 3
    assert own.fetched_count == 3
    assert len(own.items) == 3
    assert combined.status is CollectionStatus.SUCCESS
    assert combined.reported_count == 2
    assert combined.fetched_count == 2
    assert len(combined.items) == 1
    assert factory_args["headers"]["Origin-Method"] == "GET"
    assert fake_client.calls == [
        ("/api/pbanc/sbiz24PbancList", 0, 2),
        ("/api/pbanc/sbiz24PbancList", 2, 4),
        ("/api/combinePbanc/list", 0, 2),
    ]
