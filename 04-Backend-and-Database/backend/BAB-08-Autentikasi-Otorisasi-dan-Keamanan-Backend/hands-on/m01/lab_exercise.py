#!/usr/bin/env python3
"""
Lab Exercise: Modul 01 - Autentikasi, Otorisasi, dan Keamanan Backend
Simulasi interaktif teknis fondasi keamanan:
 1. Password Hashing & Salt verification (PBKDF2-HMAC-SHA256)
 2. Custom JWT (Header, Payload, Signature HMAC-SHA256) & Tamper Detection
 3. Role-Based Access Control (RBAC) Enforcement
 4. In-Memory Rate Limiting (Token Bucket Algorithm)
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Codes & Formatting Helpers
# ==============================================================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"


def print_header(title: str) -> None:
    line = "=" * 68
    print(f"\n{Colors.CYAN}{Colors.BOLD}{line}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD} [*] {title.upper()}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{line}{Colors.RESET}")


def print_success(msg: str) -> None:
    print(f" {Colors.GREEN}✔ [BERHASIL]{Colors.RESET} {msg}")


def print_error(msg: str) -> None:
    print(f" {Colors.RED}✘ [GAGAL/BLOCKED]{Colors.RESET} {msg}")


def print_info(msg: str) -> None:
    print(f" {Colors.BLUE}ℹ [INFO]{Colors.RESET} {msg}")


def print_warning(msg: str) -> None:
    print(f" {Colors.YELLOW}⚠ [PERINGATAN]{Colors.RESET} {msg}")


# ==============================================================================
# Bagian 1: Password Hashing Berstandar Industri (PBKDF2 + Salt)
# ==============================================================================
class PasswordManager:
    """Implementasi password hashing aman menggunakan PBKDF2-HMAC-SHA256."""
    ITERATIONS = 120_000

    @staticmethod
    def hash_password(password: str) -> Tuple[str, str]:
        """Menghasilkan salt acak CSPRNG dan hash kunci turunan."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            iterations=PasswordManager.ITERATIONS
        )
        return salt, key.hex()

    @staticmethod
    def verify_password(stored_salt: str, stored_hash: str, password_attempt: str) -> bool:
        """Verifikasi kecocokan password dengan constant-time comparison."""
        new_key = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=password_attempt.encode("utf-8"),
            salt=stored_salt.encode("utf-8"),
            iterations=PasswordManager.ITERATIONS
        )
        # Cegah timing-attack dengan hmac.compare_digest
        return hmac.compare_digest(new_key.hex(), stored_hash)


# ==============================================================================
# Bagian 2: Implementasi Standar JWT (JSON Web Token) dari Dasar
# ==============================================================================
class MiniJWT:
    """Implementasi penandatanganan dan validasi JWT menggunakan HMAC-SHA256."""

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    @staticmethod
    def _b64url_decode(segment: str) -> bytes:
        rem = len(segment) % 4
        if rem > 0:
            segment += "=" * (4 - rem)
        return base64.urlsafe_b64decode(segment.encode("utf-8"))

    @classmethod
    def create_token(cls, payload: Dict[str, Any], secret: str, ttl_seconds: int = 300) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        token_payload = {
            **payload,
            "iat": now,
            "exp": now + ttl_seconds
        }

        h_b64 = cls._b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_b64 = cls._b64url_encode(json.dumps(token_payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")

        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        s_b64 = cls._b64url_encode(signature)

        return f"{h_b64}.{p_b64}.{s_b64}"

    @classmethod
    def verify_token(cls, token: str, secret: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None, "Format token tidak valid (harus 3 bagian terpisah titik)"

        h_b64, p_b64, s_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = cls._b64url_encode(
            hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        )

        if not hmac.compare_digest(s_b64, expected_sig):
            return False, None, "Integritas signature rusak (Token telah dimanipulasi/tampered!)"

        try:
            payload = json.loads(cls._b64url_decode(p_b64).decode("utf-8"))
        except Exception:
            return False, None, "Gagal mengurai payload JSON"

        now = int(time.time())
        if "exp" in payload and payload["exp"] < now:
            return False, payload, "Token sudah kedaluwarsa (Expired)"

        return True, payload, "Token valid dan terverifikasi"


# ==============================================================================
# Bagian 3: Rate Limiter (Token Bucket Algorithm)
# ==============================================================================
class TokenBucketLimiter:
    """Membatasi kecepatan request per IP/User untuk mencegah Brute-Force & DoS."""

    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.buckets: Dict[str, Dict[str, float]] = {}

    def allow_request(self, client_id: str) -> Tuple[bool, float]:
        now = time.time()
        if client_id not in self.buckets:
            self.buckets[client_id] = {"tokens": float(self.capacity), "last_refill": now}

        bucket = self.buckets[client_id]
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(float(self.capacity), bucket["tokens"] + (elapsed * self.refill_rate))
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True, bucket["tokens"]
        return False, bucket["tokens"]


# ==============================================================================
# Bagian 4: RBAC (Role-Based Access Control) & Protected Endpoints Simulation
# ==============================================================================
class SecuritySimulator:
    SECRET_KEY = "kunci-rahasia-super-aman-jwt-backend-simulasi"

    def __init__(self):
        self.user_db: Dict[str, Dict[str, Any]] = {}
        self.rate_limiter = TokenBucketLimiter(capacity=3, refill_rate_per_sec=0.5)

    def register(self, username: str, password: str, role: str) -> None:
        salt, p_hash = PasswordManager.hash_password(password)
        self.user_db[username] = {
            "salt": salt,
            "hash": p_hash,
            "role": role
        }

    def login(self, username: str, password: str, client_ip: str) -> Optional[str]:
        # Cek rate limiter
        allowed, remaining = self.rate_limiter.allow_request(client_ip)
        if not allowed:
            print_error(f"Rate limit terlampaui untuk {client_ip}! Permintaan diblokir.")
            return None

        user = self.user_db.get(username)
        if not user:
            print_error(f"Kredensial salah: Pengguna '{username}' tidak ditemukan.")
            return None

        if not PasswordManager.verify_password(user["salt"], user["hash"], password):
            print_error(f"Kredensial salah: Password untuk '{username}' keliru.")
            return None

        # Berhasil login -> Buat JWT Token
        payload = {
            "sub": username,
            "role": user["role"]
        }
        token = MiniJWT.create_token(payload, self.SECRET_KEY, ttl_seconds=60)
        return token

    def access_endpoint(self, token: str, endpoint: str, required_role: str) -> None:
        print_info(f"Mengakses endpoint: {Colors.BOLD}{endpoint}{Colors.RESET} (Wajib Role: {required_role})")
        valid, payload, msg = MiniJWT.verify_token(token, self.SECRET_KEY)

        if not valid:
            print_error(f"Akses Ditolak [401 Unauthorized]: {msg}")
            return

        user_role = payload.get("role", "guest")
        username = payload.get("sub", "anon")

        # Cek otorisasi RBAC (Admin memiliki hak hierarki tertinggi)
        has_permission = (user_role == required_role) or (user_role == "admin")
        if not has_permission:
            print_error(
                f"Akses Ditolak [403 Forbidden]: User '{username}' role '{user_role}' "
                f"tidak berhak mengakses resource '{required_role}'!"
            )
            return

        print_success(
            f"Akses Diberikan [200 OK]: Selamat datang {Colors.MAGENTA}{username}{Colors.RESET} "
            f"[{user_role}] pada endpoint {endpoint}!"
        )


# ==============================================================================
# Main Interactive Runner & Automated Demo
# ==============================================================================
def run_automated_demo():
    print_header("Simulasi Fondasi Keamanan Backend (BAB-08)")
    print(f"{Colors.DIM}Menguji Hashing PBKDF2, Pembuatan JWT, Proteksi RBAC, dan Rate Limiter{Colors.RESET}\n")

    sim = SecuritySimulator()

    # 1. Registrasi Akun Contoh
    print_header("Langkah 1: Registrasi User & Hashing Password")
    print_info("Mendaftarkan akun 'budi_dev' (role: user) dan 'admin_super' (role: admin)...")
    sim.register("budi_dev", "Rahasia123!", "user")
    sim.register("admin_super", "K4t4S4ndiKuat#", "admin")

    budi_data = sim.user_db["budi_dev"]
    print_success(f"User 'budi_dev' tersimpan di DB:")
    print(f"    - Salt (16-bytes hex) : {Colors.YELLOW}{budi_data['salt']}{Colors.RESET}")
    print(f"    - Hash PBKDF2-SHA256 : {Colors.GREEN}{budi_data['hash'][:32]}... [120.000 iterasi]{Colors.RESET}")

    # 2. Login & Token Generation
    print_header("Langkah 2: Autentikasi & Penerbitan JWT")
    token_budi = sim.login("budi_dev", "Rahasia123!", "192.168.1.100")
    if token_budi:
        print_success("User 'budi_dev' berhasil diautentikasi. Token JWT diterbitkan:")
        parts = token_budi.split(".")
        print(f"    - Header    : {Colors.CYAN}{parts[0]}{Colors.RESET}")
        print(f"    - Payload   : {Colors.MAGENTA}{parts[1]}{Colors.RESET}")
        print(f"    - Signature : {Colors.RED}{parts[2]}{Colors.RESET}")

    token_admin = sim.login("admin_super", "K4t4S4ndiKuat#", "192.168.1.101")
    if token_admin:
        print_success("Admin 'admin_super' berhasil login.")

    # 3. Pengujian Otorisasi RBAC
    print_header("Langkah 3: Otorisasi & Access Control (RBAC)")
    # Budi akses endpoint publik/user
    sim.access_endpoint(token_budi, "/api/v1/profile", "user")

    # Budi mencoba akses endpoint admin
    print()
    sim.access_endpoint(token_budi, "/api/v1/financial/export", "admin")

    # Admin mencoba akses endpoint admin
    print()
    sim.access_endpoint(token_admin, "/api/v1/financial/export", "admin")

    # 4. Serangan Manipulasi Token (Tampering Attack)
    print_header("Langkah 4: Simulasi Serangan Tampering Token JWT")
    print_info("Penyerang mengubah isi payload JWT budi_dev dari role 'user' menjadi 'admin' secara manual:")
    h_b64, p_b64, s_b64 = token_budi.split(".")
    payload_dict = json.loads(MiniJWT._b64url_decode(p_b64).decode("utf-8"))
    payload_dict["role"] = "admin"  # Serangan privilege escalation ilegal
    p_tampered = MiniJWT._b64url_encode(json.dumps(payload_dict, separators=(",", ":")).encode("utf-8"))
    tampered_token = f"{h_b64}.{p_tampered}.{s_b64}"

    print_warning(f"Token palsu dikirim ke backend: {tampered_token[:45]}...")
    sim.access_endpoint(tampered_token, "/api/v1/financial/export", "admin")

    # 5. Simulasi Brute-Force & Rate Limiting
    print_header("Langkah 5: Pertahanan Brute-Force (Rate Limiting Token Bucket)")
    attacker_ip = "203.0.113.42"
    print_info(f"Serangan brute-force tebak password dari IP {attacker_ip} (Kapasitas bucket = 3)...")
    for attempt in range(1, 6):
        print(f"\n{Colors.BOLD}Percobaan login #{attempt}:{Colors.RESET}")
        sim.login("admin_super", f"salah_tebak_{attempt}", attacker_ip)
        time.sleep(0.1)

    print_header("Ringkasan Eksekusi")
    print_success("Semua skenario pengujian pertahanan backend telah selesai dijalankan!")
    print(f"{Colors.GREEN}✔ Hashing Kata Sandi Tangguh{Colors.RESET}")
    print(f"{Colors.GREEN}✔ Verifikasi Integritas Tanda Tangan Kriptografi JWT{Colors.RESET}")
    print(f"{Colors.GREEN}✔ Penegakan Prinsip Least Privilege & RBAC{Colors.RESET}")
    print(f"{Colors.GREEN}✔ Mitigasi DoS/Brute-force via Token Bucket Limiter{Colors.RESET}\n")


if __name__ == "__main__":
    run_automated_demo()
