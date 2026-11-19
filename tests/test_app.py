import importlib
import json
import sys
from pathlib import Path

import bcrypt
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_app(monkeypatch, tmp_path, webhook_secret="test-webhook-secret"):
    pwd_hash = bcrypt.hashpw(b"secret-pass", bcrypt.gensalt()).decode()
    monkeypatch.setenv("APP_SECRET", "test-app-secret-0123456789abcdef")
    monkeypatch.setenv("HASHED_PASSWORD", pwd_hash)
    monkeypatch.setenv("WEBHOOK_SECRET", webhook_secret)
    monkeypatch.setenv("PERSONAL_FILTER_TERMS", "alice@example.com")

    import auth_logic
    import mail_logic
    import app as app_mod

    importlib.reload(auth_logic)
    importlib.reload(mail_logic)
    importlib.reload(app_mod)

    data_dir = tmp_path / "data"
    auth_logic.DATA_DIR = data_dir
    auth_logic.DB_FILE = data_dir / "failed_logins.db"
    auth_logic.AUDIT_LOG_FILE = data_dir / "audit.jsonl"
    mail_logic.HISTORY_FILE = str(tmp_path / "history.json")
    mail_logic.FILTERS_FILE = str(tmp_path / "filters.json")
    app_mod.HISTORY_FILE = mail_logic.HISTORY_FILE
    app_mod.FILTERS_FILE = mail_logic.FILTERS_FILE
    return app_mod, mail_logic


def test_headers_auth_and_csrf(monkeypatch, tmp_path):
    app_mod, _ = _load_app(monkeypatch, tmp_path)
    client = TestClient(app_mod.app, base_url="https://testserver")

    root = client.get("/")
    assert root.status_code == 200
    assert root.headers["x-frame-options"] == "DENY"
    assert root.headers["x-content-type-options"] == "nosniff"
    assert "escHtml" in root.text
    assert "F00000" in root.text

    assert client.get("/api/settings").status_code == 401
    assert client.post("/auth/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"password": "secret-pass"}).status_code == 200

    assert client.post("/api/settings", json={"senders": []}).status_code == 403
    csrf = client.cookies.get("csrf_token")
    res = client.post("/api/settings", json={"senders": ["x@y.cz"]}, headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200


def test_webhook_rejects_unset_secret(monkeypatch, tmp_path):
    app_mod, _ = _load_app(monkeypatch, tmp_path, webhook_secret="")
    client = TestClient(app_mod.app, base_url="https://testserver")
    res = client.post("/api/webhook", json={"from": "a@b.cz", "subject": "hi", "body": "x"})
    assert res.status_code == 401


def test_personal_filter_and_obfuscation(monkeypatch, tmp_path):
    app_mod, mail_logic = _load_app(monkeypatch, tmp_path)
    monkeypatch.setitem(app_mod.DISCORD_CONFIG, "DISCORD_BOT_TOKEN", "dummy-token")
    monkeypatch.setitem(app_mod.DISCORD_CONFIG, "DISCORD_CHANNEL_ID", "12345")

    captured = {}

    class DummyResponse:
        is_success = True
        status_code = 200

    async def fake_post(self, url, headers=None, json=None, data=None, files=None):
        captured["payload"] = json
        return DummyResponse()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with open(mail_logic.FILTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "senders": [],
                "keywords": [],
                "obfuscations": [
                    {"pattern": "[invalid-regex", "replacement": "X", "is_regex": True},
                    {"pattern": r"https?://orsee\.example/\S*[?&]p=\w+", "replacement": "[MASKED]", "is_regex": True},
                ],
            },
            f,
        )

    client = TestClient(app_mod.app, base_url="https://testserver")
    skipped = client.post(
        "/api/webhook",
        headers={"X-Webhook-Secret": "test-webhook-secret"},
        json={"from": "alice@example.com", "subject": "Priv", "body": "hello"},
    )
    assert skipped.status_code == 200
    assert skipped.json()["skipped"] == "personal_email"

    sent = client.post(
        "/api/webhook",
        headers={"X-Webhook-Secret": "test-webhook-secret"},
        json={"from": "bot@ujep.cz", "subject": "Test", "body": "link https://orsee.example/x?p=tok123"},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "ok"
    desc = captured["payload"]["embeds"][0]["description"]
    assert "[MASKED]" in desc
    assert "tok123" not in desc
