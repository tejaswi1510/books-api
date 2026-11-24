"""Password hashing with Argon2 (via pwdlib). We store hashes, never passwords."""
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()  # Argon2id with safe defaults


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _hasher.verify(password, hashed_password)
