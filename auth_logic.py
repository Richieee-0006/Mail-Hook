import os
import time
import json
import logging
import secrets
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, Response, HTTPException

logger = logging.getLogger(__name__)

APP_SECRET = os.environ.get("APP_SECRET") or ""
if not APP_SECRET:
    logger.warning("APP_SECRET is not set; using ephemeral secret (sessions reset on restart)")
    APP_SECRET = secrets.token_hex(32)
HASHED_PASSWORD = os.environ.get("HASHED_PASSWORD", "").encode()
SESSION_COOKIE = "discord_admin_session"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 86400))
CSRF_COOKIE_NAME = "csrf_token"

serializer = URLSafeTimedSerializer(APP_SECRET)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AUDIT_LOG_FILE = DATA_DIR / "audit.jsonl"
DB_FILE = DATA_DIR / "failed_logins.db"

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 900


def _get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS failed_logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            attempt_time REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_failed_logins_ip_time ON failed_logins(ip, attempt_time)")
    return conn


def get_client_ip(request: Optional[Request]) -> str:
    if not request:
        return "system"
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    x_real = request.headers.get("x-real-ip")
    if x_real:
        return x_real.strip()
    return request.client.host if request.client else "unknown"


def _client_fingerprint(request: Optional[Request]) -> str:
    if not request:
        return ""
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    return hashlib.sha256(f"{ip}|{ua}".encode("utf-8")).hexdigest()[:16]


def check_rate_limit(request: Request) -> bool:
    ip = get_client_ip(request)
    cutoff = time.time() - LOCKOUT_WINDOW_SECONDS
    try:
        with _get_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM failed_logins WHERE attempt_time < ?", (cutoff,))
            cur.execute("SELECT COUNT(*) FROM failed_logins WHERE ip = ? AND attempt_time >= ?", (ip, cutoff))
            count = cur.fetchone()[0]
            return count < MAX_LOGIN_ATTEMPTS
    except Exception:
        return True


def record_login_failure(request: Request):
    ip = get_client_ip(request)
    now = time.time()
    try:
        with _get_db() as conn:
            conn.execute("INSERT INTO failed_logins (ip, attempt_time) VALUES (?, ?)", (ip, now))
    except Exception as exc:
        logger.warning("Failed to record login failure: %s", exc)


def reset_rate_limit(request: Request):
    ip = get_client_ip(request)
    try:
        with _get_db() as conn:
            conn.execute("DELETE FROM failed_logins WHERE ip = ?", (ip,))
    except Exception as exc:
        logger.warning("Failed to reset rate limit: %s", exc)


def audit_log(event: str, request: Optional[Request] = None, status: str = "SUCCESS", details: Optional[Dict[str, Any]] = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "status": status,
        "ip": get_client_ip(request),
        "user_agent": request.headers.get("user-agent", "") if request else "",
        "details": details or {}
    }
    try:
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to write audit log: %s", exc)


def verify_session(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        payload = serializer.loads(token, max_age=SESSION_MAX_AGE)
        if not isinstance(payload, dict) or not payload.get("auth"):
            return False
        expected_fp = _client_fingerprint(request)
        token_fp = payload.get("fp")
        if token_fp and token_fp != expected_fp:
            audit_log("SESSION_HIJACK_DETECTED", request, "FAILURE", {"reason": "Fingerprint mismatch"})
            return False
        return True
    except (BadSignature, SignatureExpired, Exception):
        return False


def create_session_token(request: Optional[Request] = None) -> str:
    payload = {
        "auth": True,
        "fp": _client_fingerprint(request) if request else "",
        "ts": int(time.time())
    }
    return serializer.dumps(payload)


def check_password(password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), HASHED_PASSWORD)
    except Exception:
        return False


def ensure_csrf_token(request: Request, response: Response) -> str:
    token = request.cookies.get(CSRF_COOKIE_NAME) or secrets.token_hex(32)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=False,
        samesite="lax",
        secure=True,
        path="/"
    )
    return token


def validate_csrf(request: Request):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        audit_log("CSRF_REJECTED", request, "FAILURE")
        raise HTTPException(status_code=403, detail="Neplatný nebo chybějící CSRF token.")


def require_auth(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        validate_csrf(request)
