#!/usr/bin/env python3
"""
BAB-08: Autentikasi, Otorisasi, dan Keamanan Backend
Hands-on Lab Exercise (Modul 02)
Simulasi Arsitektur Produksi Tingkat Lanjut:
- PBKDF2-HMAC-SHA256 Password Hashing & Salt
- HMAC-SHA256 Signed Stateless JWT Generator & Verifier
- Role-Based & Attribute-Based Access Control (RBAC + ABAC) Engine
- Sliding Window Token Bucket Rate Limiter
- Tamper-Evident Immutable Security Audit Log
"""

import sys
import os
import time
import json
import hmac
import hashlib
import base64
import secrets
from typing import Dict, List, Optional, Tuple, Any

# ANSI Color Codes
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


def banner() -> None:
    print(f"\n{BOLD}{CYAN}" + "=" * 72)
    print("  🛡️  SIMULASI ARSITEKTUR KEAMANAN BACKEND & OTORISASI PRODUKSI  🛡️")
    print(f"     BAB-08: Authentication, Authorization (RBAC/ABAC) & Hardening")
    print("=" * 72 + f"{RESET}\n")


class PasswordHasher:
    """Implementasi Password Hashing berstandar industri dengan PBKDF2-HMAC-SHA256."""

    ITERATIONS = 120_000

    @classmethod
    def hash_password(cls, password: str) -> Tuple[str, str]:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), cls.ITERATIONS
        )
        return key.hex(), salt

    @classmethod
    def verify_password(cls, password: str, hashed_key: str, salt: str) -> bool:
        new_key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), cls.ITERATIONS
        )
        return hmac.compare_digest(new_key.hex(), hashed_key)


class StatelessTokenEngine:
    """Implementasi Mini-JWT HMAC-SHA256 Stateless Session."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode("utf-8")

    @staticmethod
    def _b64_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64_decode(data: str) -> bytes:
        padding = "=" * (4 - (len(data) % 4))
        return base64.urlsafe_b64decode(data + padding)

    def generate_token(self, payload: Dict[str, Any], ttl_seconds: int = 60) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        payload_copy = payload.copy()
        payload_copy["iat"] = int(time.time())
        payload_copy["exp"] = int(time.time()) + ttl_seconds

        h_enc = self._b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_enc = self._b64_encode(json.dumps(payload_copy, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_enc}.{p_enc}".encode("utf-8")

        sig = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        sig_enc = self._b64_encode(sig)

        return f"{h_enc}.{p_enc}.{sig_enc}"

    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None, "Invalid token structure"

        h_enc, p_enc, sig_enc = parts
        signing_input = f"{h_enc}.{p_enc}".encode("utf-8")
        expected_sig = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        actual_sig = self._b64_decode(sig_enc)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, None, "Signature mismatch / Token tampered"

        try:
            payload = json.loads(self._b64_decode(p_enc).decode("utf-8"))
        except Exception as e:
            return False, None, f"Payload decoding error: {e}"

        current_time = int(time.time())
        if payload.get("exp", 0) < current_time:
            return False, payload, "Token expired"

        return True, payload, "Valid"


class TokenBucketRateLimiter:
    """Sliding Window Token Bucket Rate Limiter per Client Identity."""

    def __init__(self, capacity: int = 5, refill_rate_per_sec: float = 1.0):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.buckets: Dict[str, Dict[str, Any]] = {}

    def is_allowed(self, client_id: str) -> Tuple[bool, int, float]:
        now = time.time()
        if client_id not in self.buckets:
            self.buckets[client_id] = {"tokens": self.capacity, "last_updated": now}

        bucket = self.buckets[client_id]
        elapsed = now - bucket["last_updated"]
        bucket["tokens"] = min(self.capacity, bucket["tokens"] + (elapsed * self.refill_rate))
        bucket["last_updated"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True, int(bucket["tokens"]), 0.0
        else:
            wait_time = (1.0 - bucket["tokens"]) / self.refill_rate
            return False, int(bucket["tokens"]), round(wait_time, 2)


class AuditLogger:
    """Tamper-Evident Security Audit Log dengan Hash Chaining."""

    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        self.last_hash = "GENESIS_ROOT_HASH_000000000000"

    def record(self, event_type: str, actor: str, status: str, details: str) -> str:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = f"{timestamp}|{event_type}|{actor}|{status}|{details}|{self.last_hash}"
        entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        entry = {
            "index": len(self.logs),
            "timestamp": timestamp,
            "event": event_type,
            "actor": actor,
            "status": status,
            "details": details,
            "prev_hash": self.last_hash,
            "hash": entry_hash,
        }
        self.logs.append(entry)
        self.last_hash = entry_hash
        return entry_hash

    def verify_integrity(self) -> bool:
        prev = "GENESIS_ROOT_HASH_000000000000"
        for log in self.logs:
            expected_payload = (
                f"{log['timestamp']}|{log['event']}|{log['actor']}|{log['status']}|"
                f"{log['details']}|{prev}"
            )
            recalculated = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
            if recalculated != log["hash"]:
                return False
            prev = log["hash"]
        return True


class SecurityGateway:
    """Gerbang Keamanan Backend Utama menggabungkan Auth, RBAC, ABAC, dan Rate Limiting."""

    def __init__(self):
        self.hasher = PasswordHasher()
        self.jwt = StatelessTokenEngine(secret_key="SECRET_ENTERPRISE_KEY_XYZ_9921")
        self.limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_sec=0.5)
        self.audit = AuditLogger()
        self.user_db: Dict[str, Dict[str, Any]] = {}
        self._init_seed_data()

    def _init_seed_data(self):
        users = [
            ("alice", "PasswordAdmin!23", "admin", "Finance", 90),
            ("bob", "DevSecure#2026", "developer", "Engineering", 60),
            ("guest_charlie", "Guest12345!", "viewer", "Marketing", 20),
        ]
        for username, raw_pass, role, department, clearance in users:
            hashed, salt = self.hasher.hash_password(raw_pass)
            self.user_db[username] = {
                "hash": hashed,
                "salt": salt,
                "role": role,
                "department": department,
                "clearance": clearance,
            }

    def login(self, username: str, raw_pass: str) -> Optional[str]:
        if username not in self.user_db:
            self.audit.record("AUTH_LOGIN", username, "FAILURE", "User not found")
            return None

        data = self.user_db[username]
        if not self.hasher.verify_password(raw_pass, data["hash"], data["salt"]):
            self.audit.record("AUTH_LOGIN", username, "FAILURE", "Invalid credential")
            return None

        token = self.jwt.generate_token(
            {
                "sub": username,
                "role": data["role"],
                "dept": data["department"],
                "clearance": data["clearance"],
            },
            ttl_seconds=30,
        )
        self.audit.record("AUTH_LOGIN", username, "SUCCESS", "Issued JWT token")
        return token

    def authorize_request(
        self, token: str, resource: str, action: str, env_context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        # 1. Rate Limiting Check
        valid, payload, err = self.jwt.verify_token(token)
        if not valid or not payload:
            self.audit.record("API_ACCESS", "unknown", "REJECTED", f"JWT validation failed: {err}")
            return False, f"401 Unauthorized: {err}"

        user = payload["sub"]
        allowed, remaining, wait_time = self.limiter.is_allowed(user)
        if not allowed:
            self.audit.record("RATE_LIMIT", user, "THROTTLED", f"Cooldown required: {wait_time}s")
            return False, f"429 Too Many Requests: Rate limit exceeded. Retry in {wait_time}s"

        role = payload["role"]
        dept = payload["dept"]
        clearance = payload["clearance"]

        # 2. RBAC Policy Check
        rbac_matrix = {
            "admin": ["read", "write", "delete", "export"],
            "developer": ["read", "write"],
            "viewer": ["read"],
        }
        if action not in rbac_matrix.get(role, []):
            self.audit.record("ACCESS_CONTROL", user, "FORBIDDEN", f"RBAC failed for action: {action}")
            return False, f"403 Forbidden: Role '{role}' cannot perform action '{action}'"

        # 3. ABAC Policy Check (Resource Classification & Department Context)
        if resource == "FINANCIAL_LEDGER_CONFIDENTIAL":
            if dept != "Finance" or clearance < 80:
                self.audit.record(
                    "ACCESS_CONTROL",
                    user,
                    "FORBIDDEN",
                    f"ABAC failed: clearance {clearance}, dept {dept}",
                )
                return False, f"403 Forbidden: ABAC policy denied. High-clearance Finance only."

        if env_context.get("is_production_maintenance", False) and role != "admin":
            self.audit.record("ACCESS_CONTROL", user, "FORBIDDEN", "System in maintenance mode")
            return False, "503 Service Unavailable: Maintenance mode active, admin-only."

        self.audit.record("API_ACCESS", user, "GRANTED", f"Resource: {resource} [{action}]")
        return True, f"200 OK: Akses diberikan ke {resource} ({action}) [Sisa Token Limit: {remaining}]"


def run_automated_suite(gateway: SecurityGateway) -> None:
    print(f"{BOLD}{YELLOW}>>> Menjalankan Automated Verification Suite...{RESET}\n")

    # Test 1: Hashing & Login
    print(f"{BLUE}[1] Uji Autentikasi Password Hashing (PBKDF2){RESET}")
    token_alice = gateway.login("alice", "PasswordAdmin!23")
    if token_alice:
        print(f"  {GREEN}✔ Login Alice (Admin) Berhasil. JWT Diperoleh.{RESET}")
    else:
        print(f"  {RED}✘ Gagal Login Alice{RESET}")

    token_wrong = gateway.login("alice", "WrongPassword")
    if not token_wrong:
        print(f"  {GREEN}✔ Proteksi Password Salah Terverifikasi.{RESET}")

    # Test 2: RBAC Policy
    print(f"\n{BLUE}[2] Uji RBAC Policy Matrix{RESET}")
    token_bob = gateway.login("bob", "DevSecure#2026")
    ok, msg = gateway.authorize_request(
        token_bob, "SOURCE_CODE_REPO", "delete", {"is_production_maintenance": False}
    )
    print(f"  Bob mencoba aksi 'delete': {RED if not ok else GREEN}{msg}{RESET}")

    ok, msg = gateway.authorize_request(
        token_bob, "SOURCE_CODE_REPO", "write", {"is_production_maintenance": False}
    )
    print(f"  Bob mencoba aksi 'write': {GREEN if ok else RED}{msg}{RESET}")

    # Test 3: ABAC Dynamic Policy
    print(f"\n{BLUE}[3] Uji ABAC (Attribute-Based Access Control){RESET}")
    ok, msg = gateway.authorize_request(
        token_bob, "FINANCIAL_LEDGER_CONFIDENTIAL", "read", {"is_production_maintenance": False}
    )
    print(f"  Bob (Eng) akses Buku Kas Rahasia: {RED if not ok else GREEN}{msg}{RESET}")

    ok, msg = gateway.authorize_request(
        token_alice, "FINANCIAL_LEDGER_CONFIDENTIAL", "read", {"is_production_maintenance": False}
    )
    print(f"  Alice (Finance, Clearance 90) akses Buku Kas: {GREEN if ok else RED}{msg}{RESET}")

    # Test 4: Rate Limiting
    print(f"\n{BLUE}[4] Uji Token Bucket Rate Limiter (Burst & Throttling){RESET}")
    for i in range(1, 5):
        ok, msg = gateway.authorize_request(
            token_alice, "PUBLIC_DATA", "read", {"is_production_maintenance": False}
        )
        status_color = GREEN if ok else RED
        print(f"  Request #{i}: {status_color}{msg}{RESET}")

    # Test 5: Audit Log Integrity Hash Chain
    print(f"\n{BLUE}[5] Uji Integritas Audit Log (Tamper Detection){RESET}")
    is_intact = gateway.audit.verify_integrity()
    print(f"  Status Rantai Hash Audit: {GREEN if is_intact else RED}{'UTUH (VALID)' if is_intact else 'TERKOMPROMISI'}{RESET}")
    print(f"  Total entri tercatat: {BOLD}{len(gateway.audit.logs)}{RESET}")


def interactive_menu(gateway: SecurityGateway) -> None:
    session_token: Optional[str] = None
    current_user: Optional[str] = None

    while True:
        print(f"\n{BOLD}{MAGENTA}--- MENU INTERAKTIF BACKEND SECURITY LAB ---{RESET}")
        print(f"Pengguna aktif: {BOLD}{CYAN}{current_user if current_user else '[Belum Login]'}{RESET}")
        print("1. Login Pengguna (Alice/Bob/Charlie)")
        print("2. Simulasi Request API Berotorisasi (RBAC/ABAC)")
        print("3. Uji Serangan Manipulasi Token (Tamper Attack)")
        print("4. Lihat Security Audit Log & Verifikasi Hash Chain")
        print("5. Jalankan Automated Verification Suite")
        print("6. Keluar")

        try:
            choice = input(f"\n{BOLD}Pilih opsi [1-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Keluar dari program.{RESET}")
            break

        if choice == "1":
            print("\nAkun Demo:")
            print(" - alice         : PasswordAdmin!23 (Admin, Finance, Clearance 90)")
            print(" - bob           : DevSecure#2026   (Developer, Eng, Clearance 60)")
            print(" - guest_charlie : Guest12345!      (Viewer, Marketing, Clearance 20)")
            user = input("Username: ").strip()
            pwd = input("Password: ").strip()
            t = gateway.login(user, pwd)
            if t:
                session_token = t
                current_user = user
                print(f"{GREEN}✔ Berhasil login sebagai {user}! Token aktif.{RESET}")
            else:
                print(f"{RED}✘ Autentikasi gagal! Kredensial tidak valid.{RESET}")

        elif choice == "2":
            if not session_token:
                print(f"{RED}Harap login terlebih dahulu (Pilihan 1).{RESET}")
                continue
            print("\nSumber Daya:")
            print(" a. SOURCE_CODE_REPO")
            print(" b. FINANCIAL_LEDGER_CONFIDENTIAL")
            print(" c. PUBLIC_DASHBOARD")
            res_opt = input("Pilih resource [a/b/c]: ").strip().lower()
            res_map = {
                "a": "SOURCE_CODE_REPO",
                "b": "FINANCIAL_LEDGER_CONFIDENTIAL",
                "c": "PUBLIC_DASHBOARD",
            }
            res = res_map.get(res_opt, "PUBLIC_DASHBOARD")
            action = input("Aksi yang diinginkan [read/write/delete]: ").strip().lower()
            ok, msg = gateway.authorize_request(
                session_token, res, action, {"is_production_maintenance": False}
            )
            print(f"Hasil: {GREEN if ok else RED}{msg}{RESET}")

        elif choice == "3":
            if not session_token:
                print(f"{RED}Harap login terlebih dahulu untuk mendapatkan token asli.{RESET}")
                continue
            parts = session_token.split(".")
            # Ubah payload JWT untuk privilege escalation
            fake_payload = base64.urlsafe_b64encode(
                json.dumps({"sub": "hacker", "role": "admin", "exp": 9999999999}).encode()
            ).decode().rstrip("=")
            tampered_token = f"{parts[0]}.{fake_payload}.{parts[2]}"
            print(f"{YELLOW}Mencoba request dengan token yang diubah payload-nya...{RESET}")
            ok, msg = gateway.authorize_request(
                tampered_token, "FINANCIAL_LEDGER_CONFIDENTIAL", "read", {}
            )
            print(f"Hasil Evaluasi Gateway: {GREEN if ok else RED}{msg}{RESET}")

        elif choice == "4":
            print(f"\n{BOLD}{CYAN}=== DAFTAR AUDIT TRAIL LOG ==={RESET}")
            for entry in gateway.audit.logs[-8:]:
                print(
                    f"{DIM}[{entry['timestamp']}]{RESET} {BOLD}{entry['event']}{RESET} | "
                    f"Aktor: {CYAN}{entry['actor']}{RESET} | Status: {entry['status']} | "
                    f"Hash: {entry['hash'][:12]}... (Prev: {entry['prev_hash'][:8]}...)"
                )
            intact = gateway.audit.verify_integrity()
            status_text = f"{GREEN}VALID & TIDAK TERKOMPROMISI{RESET}" if intact else f"{RED}RUSAK / DIRUSAK{RESET}"
            print(f"Integritas Rantai: {status_text}")

        elif choice == "5":
            run_automated_suite(gateway)

        elif choice == "6":
            print(f"{CYAN}Terima kasih telah menjalankan simulasi keamanan backend.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid.{RESET}")


def main() -> None:
    banner()
    gateway = SecurityGateway()
    # Jika dijalankan di lingkungan non-interaktif atau dengan argumen '--suite'
    if len(sys.argv) > 1 and sys.argv[1] == "--suite":
        run_automated_suite(gateway)
    elif not sys.stdin.isatty():
        run_automated_suite(gateway)
    else:
        interactive_menu(gateway)


if __name__ == "__main__":
    main()
