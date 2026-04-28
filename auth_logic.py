import os
import time
import bcrypt
from itsdangerous import URLSafeTimedSerializer
from fastapi import Request, HTTPException

APP_SECRET = os.environ.get("APP_SECRET", "secure-key")
HASHED_PASSWORD = os.environ.get("HASHED_PASSWORD", "").encode()
SESSION_COOKIE = "discord_admin_session"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 3600))

serializer = URLSafeTimedSerializer(APP_SECRET)

def verify_session(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if not token: return False
    try:
        serializer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except: return False

def require_auth(request: Request):
    if not verify_session(request): raise HTTPException(status_code=401)

def check_password(password: str) -> bool:
    return bcrypt.checkpw(password.encode(), HASHED_PASSWORD)

def create_session_token():
    return serializer.dumps({"auth": True, "ts": int(time.time())})
