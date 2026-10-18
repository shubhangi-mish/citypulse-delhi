"""Session handling.

Residents: passwordless "quick profile". A random token is set in a signed, HTTP-only cookie; only its
SHA-256 hash is stored. This is a browser-session convenience, NOT verified identity. Email is never used
to look up or recover a profile, so typing someone else's email grants nothing.

Operators (CityPulse Command): separate username/password accounts configured via OPERATOR_ACCOUNTS
(PBKDF2 hashes), separate cookie, short-lived sessions.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import OperatorSession, ResidentSession, utcnow
from app.db.session import get_db

RESIDENT_COOKIE = "cp_session"
OPERATOR_COOKIE = "cp_operator"
OPERATOR_TTL = timedelta(hours=12)


def _serializer(salt: str) -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().session_secret, salt=salt)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(name, value, max_age=max_age, httponly=True, samesite="lax",
                        secure=get_settings().cookie_secure, path="/")


# ---------- residents ----------

def start_resident_session(db: Session, response: Response, resident_id: str) -> None:
    token = secrets.token_urlsafe(32)
    db.add(ResidentSession(token_hash=_hash(token), resident_id=resident_id))
    db.commit()
    _set_cookie(response, RESIDENT_COOKIE, _serializer("resident").dumps(token), 60 * 60 * 24 * 180)


def _resident_token(request: Request) -> str | None:
    raw = request.cookies.get(RESIDENT_COOKIE)
    if not raw:
        return None
    try:
        return _serializer("resident").loads(raw)
    except BadSignature:
        return None


def optional_resident(request: Request, db: Session = Depends(get_db)) -> str | None:
    token = _resident_token(request)
    if not token:
        return None
    row = db.get(ResidentSession, _hash(token))
    if not row:
        return None
    row.last_seen_at = utcnow()
    db.commit()
    return row.resident_id


def require_resident(resident_id: str | None = Depends(optional_resident)) -> str:
    if not resident_id:
        raise HTTPException(401, detail={"error": "profile_required",
                                         "message": "Create a quick profile to do this."})
    return resident_id


def end_resident_sessions(db: Session, resident_id: str) -> None:
    db.query(ResidentSession).filter(ResidentSession.resident_id == resident_id).delete()
    db.commit()


# ---------- operators ----------

def hash_password(password: str, salt: str | None = None, iterations: int = 310_000) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def operator_login(db: Session, response: Response, username: str, password: str) -> bool:
    stored = get_settings().operators.get(username)
    if not stored or not verify_password(password, stored):
        return False
    token = secrets.token_urlsafe(32)
    db.add(OperatorSession(token_hash=_hash(token), username=username, expires_at=utcnow() + OPERATOR_TTL))
    db.commit()
    _set_cookie(response, OPERATOR_COOKIE, _serializer("operator").dumps(token), int(OPERATOR_TTL.total_seconds()))
    return True


def optional_operator(request: Request, db: Session = Depends(get_db)) -> str | None:
    raw = request.cookies.get(OPERATOR_COOKIE)
    if not raw:
        return None
    try:
        token = _serializer("operator").loads(raw)
    except BadSignature:
        return None
    row = db.get(OperatorSession, _hash(token))
    if not row:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    return row.username


def require_operator(username: str | None = Depends(optional_operator)) -> str:
    if not username:
        raise HTTPException(401, detail={"error": "operator_required",
                                         "message": "CityPulse Command sign-in required."})
    return username


def operator_logout(db: Session, request: Request, response: Response) -> None:
    raw = request.cookies.get(OPERATOR_COOKIE)
    if raw:
        try:
            db.query(OperatorSession).filter(
                OperatorSession.token_hash == _hash(_serializer("operator").loads(raw))).delete()
            db.commit()
        except BadSignature:
            pass
    response.delete_cookie(OPERATOR_COOKIE, path="/")
