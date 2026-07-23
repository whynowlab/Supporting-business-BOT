import importlib


def test_default_profile_min_score_is_60(tmp_path, monkeypatch):
    db = importlib.import_module("src.db")
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "bot.db"))
    monkeypatch.delenv("PROFILE_MIN_SCORE", raising=False)

    db.init_db()

    assert db.get_profile()["min_score"] == 60


def test_invalid_profile_min_score_falls_back_to_60(tmp_path, monkeypatch):
    db = importlib.import_module("src.db")
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "bot.db"))
    monkeypatch.setenv("PROFILE_MIN_SCORE", "not-a-number")

    db.init_db()

    assert db.get_profile()["min_score"] == 60


def test_program_status_is_persisted(tmp_path, monkeypatch):
    db = importlib.import_module("src.db")
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "bot.db"))
    db.init_db()

    db.upsert_program({
        "program_key": "sbiz24:1",
        "kind": "support",
        "source": "sbiz24",
        "seq": "1",
        "title": "소상공인 지원",
        "status": "접수중",
    })

    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT status FROM programs WHERE program_key = ?",
            ("sbiz24:1",),
        ).fetchone()
    finally:
        connection.close()

    assert row["status"] == "접수중"
