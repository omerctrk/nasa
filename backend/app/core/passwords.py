"""Parola hash'i (Argon2id) — ortak yardımcı.

core.Users.password_hash bu modülle üretilir (şema: "Argon2 hash; düz parola yok").
Seed (Aybala) hash üretir; giriş (Ömer, Ö1) aynı modülle doğrular. Parametreler
argon2-cffi'nin güncel varsayılanlarıdır; değiştirmek gerekirse yalnız burası değişir ve
eski hash'ler needs_rehash ile girişte yenilenebilir.
"""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Boş parola hash'lenmez")
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
