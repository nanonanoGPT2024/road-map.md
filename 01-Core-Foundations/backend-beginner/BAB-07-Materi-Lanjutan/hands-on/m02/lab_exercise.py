#!/usr/bin/env python3
"""
================================================================================
LAB HANDS-ON: CORE AUTHENTICATION, AUTHORIZATION & IDENTITY SECURITY
================================================================================
Modul: 07 - Deep Dive Mekanisme Autentikasi & Otorisasi Modern
Implementasi: PBKDF2 Password Hashing, Stateless HMAC Token (Zero-Dependency JWT),
              Timing-Safe String Verification, dan Dynamic RBAC Guard.
================================================================================
"""

import os
import sys
import time
import json
import base64
import hmac
import hashlib
import secrets
from typing import Dict, Any, List, Optional, Tuple

# --- ANSI Formatting Constants ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"


class SecurityLogger:
    """Utility logger untuk simulasi audit log keamanan sistem."""
    @staticmethod
    def info(msg: str):
        print(f"{CLR_BLUE}[INFO]{CLR_RESET} {msg}")

    @staticmethod
    def success(msg: str):
        print(f"{CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")

    @staticmethod
    def warning(msg: str):
        print(f"{CLR_YELLOW}[WARN]{CLR_RESET} {msg}")

    @staticmethod
    def alert(msg: str):
        print(f"{CLR_RED}[ALERT/SECURITY VIOLATION]{CLR_RESET} {msg}")

    @staticmethod
    def divider(title: str):
        line = "=" * 70
        print(f"\n{CLR_CYAN}{CLR_BOLD}{line}\n[*] {title}\n{line}{CLR_RESET}")


class CryptoEngine:
    """
    Sub-sistem Kriptografi Mandiri:
    - PBKDF2-HMAC-SHA256 untuk Hashing Password dengan Salt unik.
    - Timing-safe comparison untuk mitigasi side-channel timing attack.
    """
    ITERATIONS = 100_000
    SALT_SIZE = 16  # 128-bit salt

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Menghasilkan password hash berformat storage-safe:
        format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
        """
        salt = secrets.token_bytes(cls.SALT_SIZE)
        derived_key = hashlib.pbkdf2_hmac(
            hash_name='sha256',
            password=password.encode('utf-8'),
            salt=salt,
            iterations=cls.ITERATIONS
        )
        return f"pbkdf2_sha256${cls.ITERATIONS}${salt.hex()}${derived_key.hex()}"

    @classmethod
    def verify_password(cls, password: str, hashed_record: str) -> bool:
        """
        Memverifikasi password plaintext terhadap format tersimpan.
        Menggunakan hmac.compare_digest untuk mencegah timing attacks.
        """
        try:
            algorithm, iterations_str, salt_hex, expected_hash_hex = hashed_record.split('$')
            if algorithm != "pbkdf2_sha256":
                return False

            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected_key = bytes.fromhex(expected_hash_hex)

            candidate_key = hashlib.pbkdf2_hmac(
                hash_name='sha256',
                password=password.encode('utf-8'),
                salt=salt,
                iterations=iterations
            )
            # Timing-safe comparison wajib diterapkan di level credential check
            return hmac.compare_digest(candidate_key, expected_key)
        except (ValueError, TypeError):
            return False


class StatelessTokenEngine:
    """
    Implementasi Token Mandiri berbasis spesifikasi JSON Web Signature (JWS).
    Header.Payload.Signature (HMAC-SHA256).
    """
    SECRET_KEY = secrets.token_bytes(32)  # 256-bit secure runtime secret

    @classmethod
    def _b64_encode(cls, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

    @classmethod
    def _b64_decode(cls, encoded: str) -> bytes:
        rem = len(encoded) % 4
        if rem > 0:
            encoded += '=' * (4 - rem)
        return base64.urlsafe_b64decode(encoded.encode('utf-8'))

    @classmethod
    def issue_token(cls, payload: Dict[str, Any], ttl_seconds: int = 3600) -> str:
        """Menerbitkan stateless token bertanda tangan kriptografis."""
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        token_payload = payload.copy()
        token_payload.update({
            "iat": now,
            "exp": now + ttl_seconds
        })

        header_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
        payload_bytes = json.dumps(token_payload, separators=(',', ':')).encode('utf-8')

        header_b64 = cls._b64_encode(header_bytes)
        payload_b64 = cls._b64_encode(payload_bytes)

        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        signature = hmac.new(cls.SECRET_KEY, signing_input, hashlib.sha256).digest()
        sig_b64 = cls._b64_encode(signature)

        return f"{header_b64}.{payload_b64}.{sig_b64}"

    @classmethod
    def verify_token(cls, token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Memverifikasi integritas, autentisitas, dan masa berlaku token.
        Mengembalikan: (is_valid, decoded_payload, message)
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False, None, "Format token malformed (bukan format 3-segmen)."

            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
            expected_sig = hmac.new(cls.SECRET_KEY, signing_input, hashlib.sha256).digest()
            candidate_sig = cls._b64_decode(sig_b64)

            # Validasi integritas tanda tangan menggunakan timing-safe compare
            if not hmac.compare_digest(candidate_sig, expected_sig):
                return False, None, "Kriptografi Gagal: Tanda tangan digital (signature) invalid atau dimanipulasi!"

            # Parse payload
            payload_raw = cls._b64_decode(payload_b64)
            payload = json.loads(payload_raw.decode('utf-8'))

            # Validasi expiration
            now = int(time.time())
            if payload.get("exp", 0) < now:
                return False, None, f"Token telah kadaluwarsa (Expired at: {payload.get('exp')}, Now: {now})."

            return True, payload, "Token valid."

        except Exception as e:
            return False, None, f"Gagal parsing token: {str(e)}"


class RBACManager:
    """
    Engine Otorisasi: Role-Based Access Control (RBAC) dengan Granular Permissions.
    """
    ROLE_PERMISSIONS = {
        "viewer": {"read:reports", "read:profile"},
        "operator": {"read:reports", "read:profile", "write:deployments", "execute:restart"},
        "admin": {"read:reports", "read:profile", "write:deployments", "execute:restart", "system:purge", "auth:grant_role"}
    }

    @classmethod
    def is_authorized(cls, user_roles: List[str], required_permission: str) -> bool:
        """Memeriksa apakah salah satu role pengguna memiliki izin yang diminta."""
        for role in user_roles:
            permissions = cls.ROLE_PERMISSIONS.get(role, set())
            if required_permission in permissions:
                return True
        return False


class MockIdentityDatabase:
    """Database in-memory untuk simulasi entitas kredensial pengguna."""
    def __init__(self):
        self._users: Dict[str, Dict[str, Any]] = {}

    def register_user(self, username: str, raw_password: str, roles: List[str]) -> bool:
        if username in self._users:
            return False
        hashed = CryptoEngine.hash_password(raw_password)
        self._users[username] = {
            "password_hash": hashed,
            "roles": roles,
            "uid": f"usr_{secrets.token_hex(4)}"
        }
        return True

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        return self._users.get(username)


def simulate_protected_endpoint(token: str, required_permission: str, endpoint_path: str):
    """Simulasi API Gateway / Controller Guard yang memvalidasi AuthN & AuthZ."""
    print(f"\n---> [REQUEST] Mengakses Endpoint: {CLR_MAGENTA}{endpoint_path}{CLR_RESET}")
    print(f"     Target Permission: {CLR_YELLOW}{required_permission}{CLR_RESET}")

    # 1. Autentikasi (AuthN)
    valid, payload, msg = StatelessTokenEngine.verify_token(token)
    if not valid:
        SecurityLogger.alert(f"Autentikasi DITOLAK: {msg}")
        return False

    username = payload.get("sub")
    user_roles = payload.get("roles", [])
    SecurityLogger.info(f"Autentikasi Terverifikasi | Identitas: {username} | Roles: {user_roles}")

    # 2. Otorisasi (AuthZ)
    if not RBACManager.is_authorized(user_roles, required_permission):
        SecurityLogger.alert(
            f"Otorisasi DITOLAK: User '{username}' kekurangan permission '{required_permission}'."
        )
        return False

    SecurityLogger.success(f"200 OK: Akses diberikan ke '{endpoint_path}'. Eksekusi berhasil.")
    return True


def run_laboratory_exercise():
    db = MockIdentityDatabase()

    # ==========================================
    # SCENARIO 1: Hashing Password & Pendaftaran
    # ==========================================
    SecurityLogger.divider("SCENARIO 1: Password Salting & PBKDF2 Hash Generation")
    users_to_seed = [
        ("alice", "SuperSecretAdminPass#2026", ["admin"]),
        ("bob", "OperatorStandardPass$99", ["operator"]),
        ("eve", "WeakGuestPass", ["viewer"])
    ]

    for uname, raw_pwd, roles in users_to_seed:
        db.register_user(uname, raw_pwd, roles)
        rec = db.get_user(uname)
        # Ambil ringkasan hash untuk inspeksi keamanan
        h_preview = rec["password_hash"][:35] + "..." + rec["password_hash"][-10:]
        print(f"User '{CLR_BOLD}{uname}{CLR_RESET}' terdaftar.")
        print(f"  └─ Stored Hash Record: {CLR_CYAN}{h_preview}{CLR_RESET}")

    # ==========================================
    # SCENARIO 2: Verifikasi Credential & Login
    # ==========================================
    SecurityLogger.divider("SCENARIO 2: Verifikasi Kredensial (Timing-Safe Check)")
    test_creds = [
        ("bob", "OperatorStandardPass$99", True),
        ("bob", "WrongPasswordAttempt!", False)
    ]

    for uname, attempt_pwd, should_pass in test_creds:
        user_record = db.get_user(uname)
        is_authenticated = CryptoEngine.verify_password(attempt_pwd, user_record["password_hash"])
        if is_authenticated:
            SecurityLogger.success(f"Login valid untuk user '{uname}'. Password cocok.")
        else:
            SecurityLogger.warning(f"Login gagal untuk user '{uname}'. Password mismatch.")

    # ==========================================
    # SCENARIO 3: Penerbitan Stateless Token
    # ==========================================
    SecurityLogger.divider("SCENARIO 3: Penerbitan Stateless Token (HMAC-SHA256)")
    bob_record = db.get_user("bob")
    bob_token = StatelessTokenEngine.issue_token({
        "sub": "bob",
        "uid": bob_record["uid"],
        "roles": bob_record["roles"]
    }, ttl_seconds=10)

    alice_record = db.get_user("alice")
    alice_token = StatelessTokenEngine.issue_token({
        "sub": "alice",
        "uid": alice_record["uid"],
        "roles": alice_record["roles"]
    }, ttl_seconds=10)

    print(f"Token Alice (Admin):\n  {CLR_GREEN}{alice_token}{CLR_RESET}")
    print(f"Token Bob (Operator):\n  {CLR_GREEN}{bob_token}{CLR_RESET}")

    # ==========================================
    # SCENARIO 4: Akses Terproteksi & RBAC Guard
    # ==========================================
    SecurityLogger.divider("SCENARIO 4: Akses Endpoint Aman & Otorisasi RBAC")
    
    # 4A. Bob mengakses operasi yang diizinkan (write:deployments)
    simulate_protected_endpoint(bob_token, "write:deployments", "/api/v1/cluster/deploy")

    # 4B. Bob mencoba eskalasi hak akses ke aksi admin (system:purge)
    simulate_protected_endpoint(bob_token, "system:purge", "/api/v1/system/purge-database")

    # 4C. Alice mengakses aksi admin (system:purge)
    simulate_protected_endpoint(alice_token, "system:purge", "/api/v1/system/purge-database")

    # ==========================================
    # SCENARIO 5: Simulasi Serangan / Integrity Tampering
    # ==========================================
    SecurityLogger.divider("SCENARIO 5: Simulasi Serangan (Tampering & Forgery)")
    
    # Penyerang memodifikasi token Bob untuk menyisipkan role 'admin'
    parts = bob_token.split('.')
    h_b64, p_b64, s_b64 = parts
    tampered_payload_json = json.loads(StatelessTokenEngine._b64_decode(p_b64).decode())
    tampered_payload_json["roles"] = ["admin"]  # Privilege escalation payload injection
    tampered_payload_b64 = StatelessTokenEngine._b64_encode(json.dumps(tampered_payload_json).encode())
    forged_token = f"{h_b64}.{tampered_payload_b64}.{s_b64}"

    SecurityLogger.info(f"Token Asli Bob:   {bob_token[:40]}...")
    SecurityLogger.info(f"Token Dimanipulasi:{forged_token[:40]}...")
    
    simulate_protected_endpoint(forged_token, "system:purge", "/api/v1/system/purge-database")

    # ==========================================
    # SCENARIO 6: Token Expiration Lifecycle
    # ==========================================
    SecurityLogger.divider("SCENARIO 6: Token Expiration Life-cycle")
    
    short_lived_token = StatelessTokenEngine.issue_token(
        {"sub": "eve", "roles": ["viewer"]},
        ttl_seconds=1  # Expire dalam 1 detik
    )
    SecurityLogger.info("Menerbitkan token berdurasi sangat pendek (1 detik)...")
    time.sleep(1.2)  # Biarkan token kadaluwarsa
    simulate_protected_endpoint(short_lived_token, "read:reports", "/api/v1/analytics/reports")


if __name__ == "__main__":
    try:
        run_laboratory_exercise()
    except KeyboardInterrupt:
        print("\n[!] Program dihentikan pengguna.")
        sys.exit(0)
