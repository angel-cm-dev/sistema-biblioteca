"""Hash de contraseñas y emisión/validación de JWT.

Se usa `bcrypt` directamente (no passlib): passlib está sin mantenimiento y falla con bcrypt>=4.1
y Python 3.13+. bcrypt solo considera los primeros 72 bytes de la contraseña, por eso los
schemas limitan la longitud y aquí rechazamos explícitamente entradas más largas.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import Settings

BCRYPT_MAX_BYTES = 72


def hash_password(password: str, rounds: int = 12) -> str:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError("La contraseña excede 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, subject: str, role: str, settings: Settings) -> str:
    # El token usa el reloj real (no el Clock inyectado del dominio): PyJWT valida `exp`
    # contra la hora real, y la expiración de sesiones no es una regla de negocio.
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "role": role, "iat": now, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    """Lanza `jwt.PyJWTError` si el token es inválido o expiró."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
