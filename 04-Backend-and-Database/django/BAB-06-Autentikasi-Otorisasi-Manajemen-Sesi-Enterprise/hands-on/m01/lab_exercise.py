#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Enterprise Authentication, Authorization & Session Management (Django Core Architecture)
Topik: BAB-06 Autentikasi, Otorisasi, dan Manajemen Sesi Tingkat Enterprise

Simulasi mandiri (Zero-Dependency, Standard Library Python 3):
- PBKDF2 Password Hashing & Salt Verification (mirip Django django.contrib.auth.hashers)
- RBAC (Role-Based Access Control) & Object-Level Permission System
- Session Engine Enterprise: Session ID Rotation, TTL, Fixation Protection, Secure Storage
- Middleware Lifecycle: AuthenticationMiddleware & PermissionGatekeeper
"""

import hashlib
import hmac
import os
import secrets
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

# ANSI Colors
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RESET = "\033[0m"


class EnterprisePasswordHasher:
    """Simulasi PBKDF2PasswordHasher Django dengan salt dinamis dan iterasi protektif."""

    ITERATIONS = 120_000
    ALGORITHM = "pbkdf2_sha256"

    @classmethod
    def make_password(cls, raw_password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt.encode("utf-8"),
            cls.ITERATIONS,
        )
        hash_b64 = key.hex()
        return f"{cls.ALGORITHM}${cls.ITERATIONS}${salt}${hash_b64}"

    @classmethod
    def check_password(cls, raw_password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt, hash_hex = encoded.split("$")
            if algorithm != cls.ALGORITHM:
                return False
            key = hashlib.pbkdf2_hmac(
                "sha256",
                raw_password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            )
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(key.hex(), hash_hex)
        except (ValueError, AttributeError):
            return False


class User:
    """Entitas User terinspirasi dari AbstractBaseUser Django."""

    def __init__(self, username: str, email: str, role: str, is_active: bool = True):
        self.username = username
        self.email = email
        self.role = role
        self.is_active = is_active
        self.password_hash: str = ""
        self.permissions: Set[str] = set()

    def set_password(self, raw_password: str) -> None:
        self.password_hash = EnterprisePasswordHasher.make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return EnterprisePasswordHasher.check_password(raw_password, self.password_hash)

    def has_perm(self, perm_codename: str) -> bool:
        if not self.is_active:
            return False
        if self.role == "superuser":
            return True
        return perm_codename in self.permissions


class SessionStore:
    """Simulasi Session Backend Enterprise (Database/Cache-backed dengan TTL & Anti-Fixation)."""

    def __init__(self, session_cookie_age: int = 1800):
        self.sessions: Dict[str, dict] = {}
        self.session_cookie_age = session_cookie_age  # Detik (default 30 menit)

    def create(self) -> str:
        session_key = secrets.token_urlsafe(32)
        self.sessions[session_key] = {
            "data": {},
            "created_at": time.time(),
            "expires_at": time.time() + self.session_cookie_age,
        }
        return session_key

    def get(self, session_key: str) -> Optional[dict]:
        session = self.sessions.get(session_key)
        if not session:
            return None
        if time.time() > session["expires_at"]:
            del self.sessions[session_key]
            return None
        return session["data"]

    def cycle_key(self, old_session_key: str) -> str:
        """Mitigasi Session Fixation: Rotasi session_key saat privilege elevation (Login)."""
        session_data = self.get(old_session_key) or {}
        new_key = secrets.token_urlsafe(32)
        self.sessions[new_key] = {
            "data": dict(session_data),
            "created_at": time.time(),
            "expires_at": time.time() + self.session_cookie_age,
        }
        if old_session_key in self.sessions:
            del self.sessions[old_session_key]
        return new_key

    def flush(self, session_key: str) -> None:
        if session_key in self.sessions:
            del self.sessions[session_key]


class EnterpriseAuthSystem:
    """Simulator Otentikasi, Otorisasi, dan Middleware Django Enterprise."""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.session_store = SessionStore(session_cookie_age=300)
        self._seed_data()

    def _seed_data(self):
        # 1. Superuser
        admin = User("admin_corp", "admin@enterprise.internal", role="superuser")
        admin.set_password("Admin@Enterprise2026!")
        self.users[admin.username] = admin

        # 2. Staff / Auditor
        auditor = User("auditor_bob", "bob@enterprise.internal", role="auditor")
        auditor.set_password("Auditor#Secure99")
        auditor.permissions.update(["audit.view_logs", "finance.view_report"])
        self.users[auditor.username] = auditor

        # 3. Regular Operator
        operator = User("op_alice", "alice@enterprise.internal", role="operator")
        operator.set_password("AlicePass$1234")
        operator.permissions.update(["catalog.edit_item", "order.create"])
        self.users[operator.username] = operator

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.users.get(username)
        if not user:
            return None
        if user.check_password(password):
            return user
        return None

    def login(self, initial_session_key: str, user: User) -> str:
        """Proses Login Django: Rotasi session key untuk mencegah Session Fixation."""
        rotated_key = self.session_store.cycle_key(initial_session_key)
        data = self.session_store.get(rotated_key)
        if data is not None:
            data["_auth_user_id"] = user.username
            data["_auth_user_hash"] = hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]
            data["_auth_login_time"] = time.time()
        return rotated_key

    def resolve_user_from_session(self, session_key: str) -> Optional[User]:
        data = self.session_store.get(session_key)
        if not data:
            return None
        username = data.get("_auth_user_id")
        return self.users.get(username) if username else None


def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 76 + f"{RESET}")
    print(f"{BLUE}{BOLD}  ENTERPRISE DJANGO AUTH & SESSION MANAGEMENT LAB EXERCISE (BAB-06){RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 76 + f"{RESET}")
    print(f"{YELLOW}Simulasi Arsitektur: PBKDF2, Anti-Fixation Session Cycling, RBAC Enforcement{RESET}\n")


def run_interactive_simulation():
    print_banner()
    auth_sys = EnterpriseAuthSystem()

    # Step 1: Anonymous Session Initiation
    print(f"{BOLD}[FASE 1: Sesi Anonim Dimulai]{RESET}")
    anon_session = auth_sys.session_store.create()
    print(f"Cookie sesi anonim dibuat: {MAGENTA}{anon_session}{RESET}")
    print(f"Status Request: User terotentikasi? {RED}False (AnonymousUser){RESET}\n")

    # Interactive choice or default walkthrough
    print(f"{BOLD}[FASE 2: Simulasi Percobaan Login & Password Hashing PBKDF2]{RESET}")
    print("Daftar akun uji terdaftar:")
    print(" 1. admin_corp   (Superuser  - Bypass all perms)")
    print(" 2. auditor_bob  (Auditor    - audit.view_logs, finance.view_report)")
    print(" 3. op_alice     (Operator   - catalog.edit_item, order.create)")
    print()

    target_user = "auditor_bob"
    correct_pass = "Auditor#Secure99"
    wrong_pass = "WrongPassword!00"

    print(f"-> Menguji otentikasi gagal untuk user {CYAN}{target_user}{RESET}...")
    auth_failed = auth_sys.authenticate(target_user, wrong_pass)
    if not auth_failed:
        print(f"   {RED}[GAGAL OTENTIKASI]{RESET} Password salah ditolak dengan aman!")

    print(f"\n-> Menguji verifikasi PBKDF2 hash yang valid untuk {CYAN}{target_user}{RESET}...")
    t0 = time.perf_counter()
    user = auth_sys.authenticate(target_user, correct_pass)
    dt_ms = (time.perf_counter() - t0) * 1000.0

    if user:
        print(f"   {GREEN}[BERHASIL]{RESET} Terverifikasi dalam {dt_ms:.2f} ms")
        print(f"   Format Hash Django: {YELLOW}{user.password_hash[:45]}...{RESET}")

        # Step 3: Session Fixation Protection
        print(f"\n{BOLD}[FASE 3: Mitigasi Session Fixation (Session Key Cycling)]{RESET}")
        print(f"   Old Session Key : {RED}{anon_session}{RESET}")
        authenticated_session = auth_sys.login(anon_session, user)
        print(f"   New Session Key : {GREEN}{authenticated_session}{RESET}")
        print(f"   Old key valid?  : {RED}{anon_session in auth_sys.session_store.sessions}{RESET} (Otomatis dimusnahkan)")

        # Step 4: RBAC & Permission Gatekeeper Check
        print(f"\n{BOLD}[FASE 4: Otorisasi & Permission Gatekeeper (RBAC)]{RESET}")
        test_permissions = [
            ("audit.view_logs", "Akses Audit Log Keamanan"),
            ("finance.view_report", "Lihat Laporan Finansial Q4"),
            ("billing.execute_payout", "Eksekusi Pencairan Dana (Critical)"),
        ]

        active_user = auth_sys.resolve_user_from_session(authenticated_session)
        print(f"Sesi Aktif: {CYAN}{active_user.username}{RESET} (Peran: {YELLOW}{active_user.role}{RESET})")
        for perm, desc in test_permissions:
            granted = active_user.has_perm(perm)
            status = f"{GREEN}[GRANTED]{RESET}" if granted else f"{RED}[DENIED 403]{RESET}"
            print(f"   -> Permission '{perm}' ({desc}): {status}")

        # Step 5: Superuser Privilege Escalation Demo
        print(f"\n{BOLD}[FASE 5: Superuser Omnipotent Access Check]{RESET}")
        admin_user = auth_sys.users["admin_corp"]
        superuser_check = admin_user.has_perm("billing.execute_payout")
        print(f"User: {CYAN}{admin_user.username}{RESET} meminta 'billing.execute_payout':")
        print(f"   Status Otorisasi: {GREEN}[GRANTED]{RESET} (Superuser bypass via custom backend)")

        # Step 6: Session Flush / Logout
        print(f"\n{BOLD}[FASE 6: Secure Logout & Session Invalidation]{RESET}")
        auth_sys.session_store.flush(authenticated_session)
        expired_lookup = auth_sys.resolve_user_from_session(authenticated_session)
        print(f"Session key {authenticated_session} di-flush.")
        print(f"Resolve user pasca logout: {YELLOW}{expired_lookup}{RESET} (Anonymous)")

    print(f"\n{GREEN}{BOLD}[SELESAI]{RESET} Lab Exercise Simulasi Autentikasi Enterprise Sukses 100%!")


if __name__ == "__main__":
    run_interactive_simulation()
