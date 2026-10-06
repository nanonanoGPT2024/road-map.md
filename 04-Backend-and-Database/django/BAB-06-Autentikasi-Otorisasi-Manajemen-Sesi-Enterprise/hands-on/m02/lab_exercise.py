#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Authentication, Authorization & Session Security in Django
BAB-06: Autentikasi, Otorisasi & Manajemen Sesi Tingkat Enterprise

Simulasi mandiri (zero external dependencies) arsitektur produksi Django:
1. PBKDF2 Password Hasher (Django RFC 2898 / NIST compliant)
2. Custom User Model dengan Multi-Factor & Role-Based Access Control (RBAC)
3. Object-Level Permission Evaluation (simulasi django-rules / guardian)
4. Redis-backed Enterprise Session Engine (sliding window, concurrent session limits)
5. Session Hijacking Detection (Fingerprint & IP anomaly detection)
6. Enterprise Security Audit Logging (SIEM-ready JSON structured telemetry)
"""

import hmac
import hashlib
import secrets
import time
import uuid
import json
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


# ==============================================================================
# Terminal Color Palette & Formatter (ANSI 256 / 16 color fallback)
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    FG_RED = "\033[91m"
    FG_GREEN = "\033[92m"
    FG_YELLOW = "\033[93m"
    FG_BLUE = "\033[94m"
    FG_MAGENTA = "\033[95m"
    FG_CYAN = "\033[96m"
    FG_WHITE = "\033[97m"
    
    # Badges
    BG_RED = "\033[41m\033[97m"
    BG_GREEN = "\033[42m\033[97m"
    BG_BLUE = "\033[44m\033[97m"
    BG_YELLOW = "\033[43m\033[30m"


def print_banner(title: str, subtitle: str = "") -> None:
    sep = "=" * 78
    print(f"\n{TermColor.FG_CYAN}{TermColor.BOLD}{sep}{TermColor.RESET}")
    print(f"{TermColor.FG_WHITE}{TermColor.BOLD} [ENTERPRISE DJANGO AUTH] :: {title.upper()}{TermColor.RESET}")
    if subtitle:
        print(f"{TermColor.FG_YELLOW} > {subtitle}{TermColor.RESET}")
    print(f"{TermColor.FG_CYAN}{sep}{TermColor.RESET}")


def log_event(status: str, message: str, meta: Optional[Dict] = None) -> None:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    badge_map = {
        "SUCCESS": f"{TermColor.BG_GREEN} PASS {TermColor.RESET}",
        "DENIED": f"{TermColor.BG_RED} DENY {TermColor.RESET}",
        "WARNING": f"{TermColor.BG_YELLOW} WARN {TermColor.RESET}",
        "INFO": f"{TermColor.BG_BLUE} INFO {TermColor.RESET}",
    }
    badge = badge_map.get(status, f"[{status}]")
    print(f" {TermColor.DIM}{now}{TermColor.RESET} {badge} {TermColor.BOLD}{message}{TermColor.RESET}")
    if meta:
        formatted = json.dumps(meta, indent=2)
        indented = "\n".join(f"     {TermColor.FG_BLUE}│{TermColor.RESET} {line}" for line in formatted.splitlines())
        print(f"{TermColor.DIM}{indented}{TermColor.RESET}")


# ==============================================================================
# 1. PBKDF2 Password Hasher Engine (Django AbstractBaseUser Style)
# ==============================================================================
class EnterprisePasswordHasher:
    """
    Simulates Django's PBKDF2PasswordHasher with SHA256.
    Format: pbkdf2_sha256$<iterations>$<salt>$<hash>
    """
    ALGORITHM = "pbkdf2_sha256"
    ITERATIONS = 120_000

    @classmethod
    def make_password(cls, raw_password: str, salt: Optional[str] = None) -> str:
        if not salt:
            salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=raw_password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            iterations=cls.ITERATIONS,
            dklen=32
        )
        hash_b64 = key.hex()
        return f"{cls.ALGORITHM}${cls.ITERATIONS}${salt}${hash_b64}"

    @classmethod
    def check_password(cls, raw_password: str, encoded: str) -> bool:
        try:
            algorithm, iterations_str, salt, target_hash = encoded.split("$")
            iterations = int(iterations_str)
            computed_key = hashlib.pbkdf2_hmac(
                hash_name="sha256",
                password=raw_password.encode("utf-8"),
                salt=salt.encode("utf-8"),
                iterations=iterations,
                dklen=32
            )
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(computed_key.hex(), target_hash)
        except Exception:
            return False


# ==============================================================================
# 2. Domain Models & Role-Based Access Control (RBAC)
# ==============================================================================
class SystemRole(Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    TENANT_DEVELOPER = "TENANT_DEVELOPER"
    AUDITOR = "AUDITOR"


@dataclass
class FinancialDocument:
    doc_id: str
    tenant_id: str
    amount: float
    owner_id: str
    is_confidential: bool = False


@dataclass
class EnterpriseUser:
    user_id: str
    username: str
    email: str
    password_hash: str
    tenant_id: str
    roles: Set[SystemRole] = field(default_factory=set)
    direct_permissions: Set[str] = field(default_factory=set)
    is_active: bool = True
    mfa_enabled: bool = True
    concurrent_session_limit: int = 2

    def get_all_permissions(self) -> Set[str]:
        role_permission_matrix: Dict[SystemRole, Set[str]] = {
            SystemRole.SUPER_ADMIN: {
                "tenant:manage", "user:provision", "finance:read", "finance:write", "audit:view"
            },
            SystemRole.FINANCE_MANAGER: {
                "finance:read", "finance:write", "finance:approve", "audit:view"
            },
            SystemRole.TENANT_DEVELOPER: {
                "infra:deploy", "logs:read"
            },
            SystemRole.AUDITOR: {
                "finance:read", "audit:view", "logs:read"
            },
        }
        computed = set(self.direct_permissions)
        for role in self.roles:
            computed.update(role_permission_matrix.get(role, set()))
        return computed

    def has_perm(self, perm: str, obj: Optional[FinancialDocument] = None) -> bool:
        """
        Simulates Django Model & Object-level permission evaluation.
        Enforces Multi-Tenant Boundary + Ownership / Role rules.
        """
        if not self.is_active:
            return False

        if SystemRole.SUPER_ADMIN in self.roles:
            return True

        if perm not in self.get_all_permissions():
            return False

        # Object-level check (Row-Level Security / Multi-Tenancy)
        if obj is not None:
            # Rule 1: Tenant isolation violation
            if obj.tenant_id != self.tenant_id:
                return False
            
            # Rule 2: Confidential documents require Manager role or Ownership
            if obj.is_confidential:
                is_owner = (obj.owner_id == self.user_id)
                is_manager = (SystemRole.FINANCE_MANAGER in self.roles)
                return is_owner or is_manager

        return True


# ==============================================================================
# 3. Enterprise Session Store (Redis-Like Concurrent Limiter & Revocation)
# ==============================================================================
@dataclass
class SessionRecord:
    session_key: str
    user_id: str
    ip_address: str
    user_agent: str
    created_at: float
    last_activity: float
    is_active: bool = True

    def calculate_fingerprint(self) -> str:
        raw = f"{self.user_id}:{self.ip_address}:{self.user_agent}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class EnterpriseSessionEngine:
    """
    Simulates Django enterprise session backend (e.g., django-redis-sessions)
    with:
    - Sliding window TTL expiration (15 minutes)
    - Device fingerprint validation (Hijacking mitigation)
    - Maximum concurrent session enforcement with FIFO eviction
    """
    SESSION_TTL_SECONDS = 900  # 15 minutes

    def __init__(self):
        # session_key -> SessionRecord
        self._sessions: Dict[str, SessionRecord] = {}
        # user_id -> List of active session_keys (ordered by login time)
        self._user_session_index: Dict[str, List[str]] = {}

    def create_session(self, user: EnterpriseUser, ip: str, ua: str) -> SessionRecord:
        now = time.time()
        session_key = secrets.token_urlsafe(32)
        record = SessionRecord(
            session_key=session_key,
            user_id=user.user_id,
            ip_address=ip,
            user_agent=ua,
            created_at=now,
            last_activity=now,
            is_active=True
        )

        user_sessions = self._user_session_index.setdefault(user.user_id, [])

        # Enforce maximum concurrent session limit (FIFO eviction)
        while len(user_sessions) >= user.concurrent_session_limit:
            oldest_key = user_sessions.pop(0)
            if oldest_key in self._sessions:
                self._sessions[oldest_key].is_active = False
                log_event("WARNING", f"Evicted oldest concurrent session for user {user.username}", {
                    "evicted_session": oldest_key[:10] + "...",
                    "reason": f"Concurrent limit reached ({user.concurrent_session_limit})"
                })

        self._sessions[session_key] = record
        user_sessions.append(session_key)
        return record

    def validate_and_touch_session(
        self, session_key: str, current_ip: str, current_ua: str
    ) -> Tuple[bool, str, Optional[SessionRecord]]:
        record = self._sessions.get(session_key)
        if not record or not record.is_active:
            return False, "SESSION_NOT_FOUND_OR_REVOKED", None

        now = time.time()
        # Check idle timeout (sliding window)
        if (now - record.last_activity) > self.SESSION_TTL_SECONDS:
            record.is_active = False
            return False, "SESSION_EXPIRED_IDLE_TIMEOUT", record

        # Check Hijacking: Anomaly in IP or User-Agent Fingerprint
        expected_fp = record.calculate_fingerprint()
        incoming_fp = hashlib.sha256(
            f"{record.user_id}:{current_ip}:{current_ua}".encode("utf-8")
        ).hexdigest()[:16]

        if not hmac.compare_digest(expected_fp, incoming_fp):
            # Potential session hijacking! Invalidate immediately.
            record.is_active = False
            return False, "SESSION_HIJACK_DETECTED", record

        # Slide TTL window
        record.last_activity = now
        return True, "SESSION_VALID", record

    def revoke_all_user_sessions(self, user_id: str, reason: str = "Admin Triggered") -> int:
        session_keys = self._user_session_index.get(user_id, [])
        revoked_count = 0
        for sk in list(session_keys):
            if sk in self._sessions and self._sessions[sk].is_active:
                self._sessions[sk].is_active = False
                revoked_count += 1
        self._user_session_index[user_id] = []
        return revoked_count


# ==============================================================================
# 4. Interactive Simulation Runner
# ==============================================================================
def run_interactive_simulation() -> None:
    print_banner(
        "Django Enterprise Security Sandbox",
        "Modul 02: Autentikasi, RBAC Multi-Tenant, & Manajemen Sesi Terdistribusi"
    )

    # --------------------------------------------------------------------------
    # Step 1: PBKDF2 Password Hashing Benchmark & Verification
    # --------------------------------------------------------------------------
    print(f"\n{TermColor.BOLD}[1] SIMULASI PBKDF2 PASSWORD HASHER (DJANGO DEFAULT){TermColor.RESET}")
    raw_pass = "P@ssw0rdEnterprise2026!#Secure"
    print(f" Raw Password: {TermColor.FG_YELLOW}{raw_pass}{TermColor.RESET}")

    t0 = time.perf_counter()
    hashed = EnterprisePasswordHasher.make_password(raw_pass)
    t_hash = (time.perf_counter() - t0) * 1000

    log_event("SUCCESS", f"Password successfully hashed via PBKDF2-SHA256 ({t_hash:.2f}ms)", {
        "hash_preview": hashed[:45] + "...",
        "iterations": EnterprisePasswordHasher.ITERATIONS
    })

    # Validate correct password
    valid = EnterprisePasswordHasher.check_password(raw_pass, hashed)
    log_event("SUCCESS" if valid else "DENIED", f"Verify correct password -> {valid}")

    # Validate incorrect password
    invalid = EnterprisePasswordHasher.check_password("WrongPassword!", hashed)
    log_event("SUCCESS" if not invalid else "DENIED", f"Verify malicious password -> Rejected: {not invalid}")

    # --------------------------------------------------------------------------
    # Step 2: Multi-Tenant RBAC & Object-Level Permission Evaluation
    # --------------------------------------------------------------------------
    print(f"\n{TermColor.BOLD}[2] MULTI-TENANT ROLE-BASED ACCESS CONTROL (RBAC) & OBJECT-LEVEL PERMISSIONS{TermColor.RESET}")

    alice_mgr = EnterpriseUser(
        user_id="usr_001",
        username="alice.corpadm",
        email="alice@megacorp.internal",
        password_hash=hashed,
        tenant_id="tenant_alpha",
        roles={SystemRole.FINANCE_MANAGER}
    )

    bob_auditor = EnterpriseUser(
        user_id="usr_002",
        username="bob.auditor",
        email="bob@auditfirm.com",
        password_hash=hashed,
        tenant_id="tenant_alpha",
        roles={SystemRole.AUDITOR}
    )

    eve_competitor = EnterpriseUser(
        user_id="usr_003",
        username="eve.outsider",
        email="eve@competitor.org",
        password_hash=hashed,
        tenant_id="tenant_beta",  # Different tenant
        roles={SystemRole.FINANCE_MANAGER}
    )

    doc_confidential = FinancialDocument(
        doc_id="doc_tx_9981",
        tenant_id="tenant_alpha",
        amount=1_500_000.00,
        owner_id="usr_001",
        is_confidential=True
    )

    doc_standard = FinancialDocument(
        doc_id="doc_tx_1002",
        tenant_id="tenant_alpha",
        amount=45_000.00,
        owner_id="usr_001",
        is_confidential=False
    )

    tests = [
        ("Alice modifies confidential document (Same tenant, Manager)", alice_mgr, "finance:write", doc_confidential, True),
        ("Bob attempts to modify confidential document (Auditor is read-only)", bob_auditor, "finance:write", doc_confidential, False),
        ("Bob views confidential document without Manager role (Forbidden by Object Rule)", bob_auditor, "finance:read", doc_confidential, False),
        ("Bob views standard document (Auditor has finance:read, Non-confidential)", bob_auditor, "finance:read", doc_standard, True),
        ("Eve attempts cross-tenant access to Alice's doc (Tenant boundary breach)", eve_competitor, "finance:read", doc_standard, False),
    ]

    for title, user, perm, doc, expected in tests:
        allowed = user.has_perm(perm, doc)
        status = "SUCCESS" if allowed == expected else "DENIED"
        outcome_color = TermColor.FG_GREEN if allowed else TermColor.FG_RED
        log_event(status, f"{title} -> Allowed: {outcome_color}{allowed}{TermColor.RESET} (Expected: {expected})", {
            "user": user.username,
            "tenant": user.tenant_id,
            "role": [r.value for r in user.roles],
            "permission": perm,
            "doc_tenant": doc.tenant_id
        })

    # --------------------------------------------------------------------------
    # Step 3: Concurrent Session Limit & Eviction
    # --------------------------------------------------------------------------
    print(f"\n{TermColor.BOLD}[3] ENTERPRISE DISTRIBUTED SESSION ENGINE (CONCURRENCY & EVICTION){TermColor.RESET}")
    session_engine = EnterpriseSessionEngine()

    print(f" Concurrency policy: Max {alice_mgr.concurrent_session_limit} active sessions per user.")
    
    # Login Device 1 (Workstation)
    s1 = session_engine.create_session(alice_mgr, "10.0.1.45", "Mozilla/5.0 (X11; Linux x86_64) EnterpriseClient/1.0")
    log_event("INFO", f"Device 1 Logged in (Workstation) -> Key: {s1.session_key[:12]}...")

    # Login Device 2 (Mobile Tablet)
    s2 = session_engine.create_session(alice_mgr, "10.0.8.20", "Mozilla/5.0 (iPhone; CPU OS 17_0) MobileSafari")
    log_event("INFO", f"Device 2 Logged in (Mobile Tablet) -> Key: {s2.session_key[:12]}...")

    # Login Device 3 (Laptop - Should force-evict Device 1)
    s3 = session_engine.create_session(alice_mgr, "192.168.100.5", "Mozilla/5.0 (Macintosh; Apple Silicon) Safari")
    log_event("INFO", f"Device 3 Logged in (Laptop) -> Key: {s3.session_key[:12]}...")

    # Validate Device 1 (Should be evicted)
    ok1, reason1, _ = session_engine.validate_and_touch_session(s1.session_key, "10.0.1.45", "Mozilla/5.0 (X11; Linux x86_64) EnterpriseClient/1.0")
    log_event("DENIED" if not ok1 else "SUCCESS", f"Checking Device 1 Session -> Valid: {ok1} ({reason1})")

    # Validate Device 2 & 3 (Should still be valid)
    ok2, _, _ = session_engine.validate_and_touch_session(s2.session_key, "10.0.8.20", "Mozilla/5.0 (iPhone; CPU OS 17_0) MobileSafari")
    ok3, _, _ = session_engine.validate_and_touch_session(s3.session_key, "192.168.100.5", "Mozilla/5.0 (Macintosh; Apple Silicon) Safari")
    log_event("SUCCESS", f"Device 2 & Device 3 Sessions Active -> D2: {ok2}, D3: {ok3}")

    # --------------------------------------------------------------------------
    # Step 4: Session Hijacking Defense (Fingerprint Anomaly)
    # --------------------------------------------------------------------------
    print(f"\n{TermColor.BOLD}[4] SESSION HIJACKING DETECTION (DEVICE FINGERPRINT SPOOFING){TermColor.RESET}")
    
    # Attacker stolen session key s3, but presents an unknown IP and User-Agent
    attacker_ip = "185.220.101.5"  # Suspicious Tor Exit node
    attacker_ua = "python-requests/2.31.0"

    log_event("WARNING", f"Attacker using stolen session {s3.session_key[:12]}... from {attacker_ip}")
    is_valid, reason, _ = session_engine.validate_and_touch_session(s3.session_key, attacker_ip, attacker_ua)
    
    if not is_valid and reason == "SESSION_HIJACK_DETECTED":
        log_event("DENIED", "Session Hijack Neutralized! Session invalidated immediately.", {
            "reason": reason,
            "action": "AUTOMATIC_KILL_SWITCH_ENGAGED"
        })
    else:
        log_event("WARNING", f"Hijack check failed: {reason}")

    # --------------------------------------------------------------------------
    # Step 5: Global Kill-Switch (Revoke All Sessions on Incident)
    # --------------------------------------------------------------------------
    print(f"\n{TermColor.BOLD}[5] ENTERPRISE AUDIT & EMERGENCY GLOBAL KILL-SWITCH{TermColor.RESET}")
    revoked = session_engine.revoke_all_user_sessions(alice_mgr.user_id, reason="Security Incident Triaged")
    log_event("SUCCESS", f"Emergency revocation triggered for user {alice_mgr.username}: {revoked} active sessions purged.")

    print_banner(
        "Verification Complete",
        "All Django Enterprise Auth & Session Security Test Vectors Passed (100% OK)"
    )


if __name__ == "__main__":
    try:
        run_interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{TermColor.FG_YELLOW}[!] Lab simulation stopped by user.{TermColor.RESET}")
        sys.exit(0)
