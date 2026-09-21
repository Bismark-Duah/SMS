import os
import base64
import json
import hmac
import hashlib
import time
import uuid

try:
    import jwt as pyjwt
except ImportError:
    pyjwt = None

try:
    import bcrypt
    if not hasattr(bcrypt, "__about__"):
        class About:
            __version__ = getattr(bcrypt, "__version__", "5.0.0")
        bcrypt.__about__ = About()
except ImportError:
    bcrypt = None

DEFAULT_INSECURE_SECRET = "your-secret-key-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_INSECURE_SECRET)
DEFAULT_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) * 60

def get_secret_key() -> str:
    """
    Returns the configured cryptographic secret key.
    In production mode, strictly refuses default or empty secret keys.
    """
    secret = os.getenv("SECRET_KEY", DEFAULT_INSECURE_SECRET).strip()
    env_mode = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    is_production = env_mode in ("production", "prod")

    if is_production and (not secret or secret == DEFAULT_INSECURE_SECRET):
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION: In production mode, SECRET_KEY must be set to "
            "a strong, unique cryptographic secret and cannot use the default placeholder."
        )
    return secret or DEFAULT_INSECURE_SECRET

def hash_password(password: str) -> str:
    """
    Hashes a password using modern bcrypt (with 72-byte truncation for safety).
    Strictly refuses to generate weak or unhashed passwords.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    if bcrypt:
        pwd_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    raise RuntimeError("Secure password hashing backend (bcrypt) is not available")

def verify_password(plain_password: str, hashed_password: str) -> tuple[bool, bool]:
    """
    Verifies plain password against stored hash.
    Supports both bcrypt and legacy SHA-256 hashes for transparent migration.
    Returns: (is_valid, needs_rehash)
    """
    if not plain_password or not hashed_password:
        return False, False

    # Legacy SHA-256 hash check (64 hex characters, not starting with $)
    if len(hashed_password) == 64 and not hashed_password.startswith("$"):
        expected = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(expected, hashed_password):
            return True, True  # Valid legacy hash, needs upgrade to bcrypt
        return False, False

    # Modern Bcrypt hash check ($2a$, $2b$, $2y$)
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        if not bcrypt:
            return False, False
        try:
            pwd_bytes = plain_password.encode("utf-8")[:72]
            hash_bytes = hashed_password.encode("utf-8")
            is_valid = bcrypt.checkpw(pwd_bytes, hash_bytes)
            return is_valid, False
        except Exception:
            return False, False

    return False, False

def base64url_encode(data: bytes) -> str:
    """Encodes bytes to base64url string."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data: str) -> bytes:
    """Decodes base64url string to bytes."""
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def create_jwt(payload: dict, secret: str = None, expires_in: int = None) -> str:
    """Generates a secure HMAC-SHA256 JWT token using PyJWT or built-in HMAC."""
    if secret is None:
        secret = get_secret_key()
    if expires_in is None:
        expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) * 60

    payload = payload.copy()
    now = int(time.time())
    payload["iat"] = payload.get("iat", now)
    payload["exp"] = now + expires_in
    if "jti" not in payload:
        payload["jti"] = uuid.uuid4().hex

    if pyjwt:
        token = pyjwt.encode(payload, secret, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token

    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
    
    signature_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), signature_input, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

create_access_token = create_jwt

def decode_jwt(token: str, secret: str = None) -> dict:
    """Decodes and validates a JWT token's signature and expiration."""
    if secret is None:
        secret = get_secret_key()

    if pyjwt:
        try:
            return pyjwt.decode(token, secret, algorithms=["HS256"])
        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except pyjwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")

    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid token format")
        
    header_b64, payload_b64, signature_b64 = parts
    signature_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    
    # Verify signature using timing-safe comparison
    expected_signature = hmac.new(secret.encode('utf-8'), signature_input, hashlib.sha256).digest()
    expected_signature_b64 = base64url_encode(expected_signature)
    
    if not hmac.compare_digest(signature_b64, expected_signature_b64):
        raise ValueError("Signature verification failed")
        
    payload = json.loads(base64url_decode(payload_b64).decode('utf-8'))
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")
        
    return payload


def is_legacy_sha256_hash(hash_str: str) -> bool:
    """Returns True if the hash string matches a raw 64-hex SHA-256 digest."""
    if not hash_str or not isinstance(hash_str, str):
        return False
    return len(hash_str) == 64 and not hash_str.startswith("$") and all(c in "0123456789abcdefABCDEF" for c in hash_str)


def audit_password_hashes(db) -> dict:
    """
    Audits the database for user password hash security posture.
    Categorizes accounts into modern bcrypt, legacy SHA-256, and other/invalid.
    """
    from ..models import User
    users = db.query(User).all()
    total_users = len(users)
    bcrypt_count = 0
    legacy_sha256_count = 0
    unrecognized_count = 0
    legacy_accounts = []

    for u in users:
        h = u.password_hash or ""
        if h.startswith(("$2a$", "$2b$", "$2y$")):
            bcrypt_count += 1
        elif is_legacy_sha256_hash(h):
            legacy_sha256_count += 1
            legacy_accounts.append({
                "user_id": u.id,
                "username": u.username,
                "school_id": getattr(u, "school_id", None),
                "is_active": getattr(u, "is_active", True),
                "is_first_login": getattr(u, "is_first_login", False)
            })
        else:
            unrecognized_count += 1

    return {
        "total_users": total_users,
        "bcrypt_secure": bcrypt_count,
        "legacy_sha256": legacy_sha256_count,
        "unrecognized": unrecognized_count,
        "legacy_accounts": legacy_accounts
    }


def remediate_legacy_sha256_accounts(db) -> dict:
    """
    Flags all accounts with legacy SHA-256 hashes for mandatory password rotation (is_first_login=True).
    When they log in, JIT migration upgrades them to bcrypt AND forces immediate password rotation.
    """
    from ..models import User
    users = db.query(User).all()
    remediated_count = 0
    remediated_users = []

    for u in users:
        h = u.password_hash or ""
        if is_legacy_sha256_hash(h):
            if not getattr(u, "is_first_login", False):
                u.is_first_login = True
                remediated_count += 1
                remediated_users.append(u.username)

    if remediated_count > 0:
        db.commit()

    return {
        "status": "success",
        "remediated_count": remediated_count,
        "remediated_users": remediated_users
    }


