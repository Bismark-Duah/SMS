import os
import base64
import json
import hmac
import hashlib
import time

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

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
DEFAULT_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) * 60

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
        secret = os.getenv("SECRET_KEY", SECRET_KEY)
    if expires_in is None:
        expires_in = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) * 60

    payload = payload.copy()
    now = int(time.time())
    payload["iat"] = payload.get("iat", now)
    payload["exp"] = now + expires_in

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

def decode_jwt(token: str, secret: str = None) -> dict:
    """Decodes and validates a JWT token's signature and expiration."""
    if secret is None:
        secret = os.getenv("SECRET_KEY", SECRET_KEY)

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

