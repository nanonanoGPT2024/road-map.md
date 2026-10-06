#!/usr/bin/env python3
"""
BAB-09: Enterprise Security, Identity & Governance (Java Security Architecture Simulation)
Simulates core Java Security architecture:
 1. JAAS (Java Authentication and Authorization Service): Subject, Principal, LoginModule
 2. SecurityContext & SecurityContextHolder pattern
 3. RBAC (Role-Based Access Control) & ABAC (Attribute-Based Access Control) Policy Engine
 4. Enterprise Identity Governance & Tamper-Evident Audit Trail (HMAC hash-chaining)
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Dict, List, Optional, Set

# Terminal ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}================================================================================
  JAVA ENTERPRISE SECURITY, IDENTITY & GOVERNANCE SIMULATOR
  Architecture: JAAS, SecurityContext, RBAC/ABAC Engine & Tamper-Evident Audit
================================================================================{CLR_RESET}
"""
    print(banner)


# --- 1. JAAS & Enterprise Identity Model ---

class Principal:
    """Represents java.security.Principal."""
    def __init__(self, name: str, principal_type: str = "UserPrincipal"):
        self.name = name
        self.principal_type = principal_type

    def __repr__(self):
        return f"{self.principal_type}({self.name})"


class Subject:
    """Represents javax.security.auth.Subject."""
    def __init__(self):
        self.principals: Set[Principal] = set()
        self.roles: Set[str] = set()
        self.attributes: Dict[str, any] = {}
        self.read_only: bool = False

    def add_principal(self, principal: Principal):
        if self.read_only:
            raise PermissionError("Subject is read-only (immutable context)")
        self.principals.add(principal)

    def add_role(self, role: str):
        if self.read_only:
            raise PermissionError("Subject is read-only (immutable context)")
        self.roles.add(role)

    def set_read_only(self):
        self.read_only = True


class LoginModule:
    """Simulates JAAS LoginModule authentication lifecycle."""
    def __init__(self, user_db: Dict[str, Dict]):
        self.user_db = user_db
        self.authenticated = False
        self.staged_username = None

    def login(self, username: str, secret: str) -> bool:
        """Phase 1: Verify credentials."""
        user = self.user_db.get(username)
        if not user:
            self.authenticated = False
            return False

        # PBKDF2-HMAC password verification simulation
        salt = user["salt"]
        stored_hash = user["hash"]
        computed = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 100_000).hex()

        self.authenticated = hmac.compare_digest(stored_hash, computed)
        if self.authenticated:
            self.staged_username = username
        return self.authenticated

    def commit(self, subject: Subject) -> bool:
        """Phase 2: Populate Subject with Principals and Roles."""
        if not self.authenticated or not self.staged_username:
            return False

        user = self.user_db[self.staged_username]
        subject.add_principal(Principal(self.staged_username, "UserPrincipal"))
        for role in user.get("roles", []):
            subject.add_role(role)
        subject.attributes = user.get("attributes", {})
        subject.set_read_only()
        return True


# --- 2. Security Context & ContextHolder Pattern ---

class SecurityContext:
    """Represents Spring Security SecurityContext."""
    def __init__(self, subject: Optional[Subject] = None):
        self.subject = subject

    def is_authenticated(self) -> bool:
        return self.subject is not None and len(self.subject.principals) > 0


class SecurityContextHolder:
    """ThreadLocal simulation of SecurityContextHolder."""
    _current_context: Optional[SecurityContext] = None

    @classmethod
    def set_context(cls, context: SecurityContext):
        cls._current_context = context

    @classmethod
    def get_context(cls) -> SecurityContext:
        if cls._current_context is None:
            cls._current_context = SecurityContext()
        return cls._current_context

    @classmethod
    def clear_context(cls):
        cls._current_context = None


# --- 3. RBAC & ABAC Policy Enforcement (AccessDecisionManager) ---

class AccessDecisionManager:
    """Enterprise Policy Decision Point (PDP)."""
    @staticmethod
    def check_access(is_public: bool, required_role: Optional[str], required_dept: Optional[str] = None, max_clearance: int = 1) -> (bool, str):
        # 1. Public endpoint (permitAll)
        if is_public:
            return True, "200 Authorized (Public Endpoint / permitAll)"

        context = SecurityContextHolder.get_context()
        if not context.is_authenticated():
            return False, "401 Unauthorized: Anonymous user in SecurityContext"

        subject = context.subject

        # 2. RBAC Check
        if required_role and required_role not in subject.roles:
            return False, f"403 Forbidden: Missing required Role [{required_role}] (Has: {list(subject.roles)})"

        # 3. ABAC Attribute Check (Department)
        user_dept = subject.attributes.get("department")
        if required_dept and user_dept != required_dept:
            return False, f"403 Forbidden: ABAC Mismatch - Requires Dept [{required_dept}], User has [{user_dept}]"

        # 4. ABAC Clearance Level Check
        user_clearance = subject.attributes.get("clearance", 0)
        if user_clearance < max_clearance:
            return False, f"403 Forbidden: ABAC Clearance Denied - Requires Lvl {max_clearance}, User has Lvl {user_clearance}"

        return True, "200 Authorized"


# --- 4. Governance & Tamper-Evident Audit Trail ---

class AuditEvent:
    """Audit entry chained cryptographically."""
    def __init__(self, prev_hash: str, actor: str, action: str, resource: str, status: str):
        self.timestamp = time.time()
        self.prev_hash = prev_hash
        self.actor = actor
        self.action = action
        self.resource = resource
        self.status = status
        self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = f"{self.prev_hash}:{self.timestamp}:{self.actor}:{self.action}:{self.resource}:{self.status}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def as_dict(self) -> dict:
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.timestamp)),
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "status": self.status,
            "prev_hash": self.prev_hash[:8] + "...",
            "hash": self.entry_hash[:12] + "..."
        }


class AuditLedger:
    """Tamper-evident audit log with hash-chain integrity verification."""
    def __init__(self):
        self.chain: List[AuditEvent] = []
        self.genesis_hash = "0" * 64

    def log(self, actor: str, action: str, resource: str, status: str):
        prev = self.chain[-1].entry_hash if self.chain else self.genesis_hash
        event = AuditEvent(prev, actor, action, resource, status)
        self.chain.append(event)
        return event

    def verify_integrity(self) -> (bool, Optional[int]):
        expected_prev = self.genesis_hash
        for i, event in enumerate(self.chain):
            if event.prev_hash != expected_prev:
                return False, i
            if event._compute_hash() != event.entry_hash:
                return False, i
            expected_prev = event.entry_hash
        return True, None


# --- 5. Interactive Test Scenarios & Runner ---

def setup_in_memory_directory() -> Dict[str, Dict]:
    salt_admin = "f4c9a812"
    hash_admin = hashlib.pbkdf2_hmac("sha256", b"Admin@Sec2026", salt_admin.encode(), 100_000).hex()

    salt_dev = "7b2e19d0"
    hash_dev = hashlib.pbkdf2_hmac("sha256", b"Dev#SecureKey", salt_dev.encode(), 100_000).hex()

    return {
        "alice.admin": {
            "salt": salt_admin,
            "hash": hash_admin,
            "roles": ["ROLE_ADMIN", "ROLE_AUDITOR"],
            "attributes": {"department": "SecurityOperations", "clearance": 3}
        },
        "bob.developer": {
            "salt": salt_dev,
            "hash": hash_dev,
            "roles": ["ROLE_DEVELOPER"],
            "attributes": {"department": "Engineering", "clearance": 1}
        }
    }


def execute_request(resource: str, is_public: bool, req_role: Optional[str], req_dept: Optional[str], clearance: int, ledger: AuditLedger):
    ctx = SecurityContextHolder.get_context()
    actor_name = "ANONYMOUS"
    if ctx.is_authenticated():
        actor_name = next(iter(ctx.subject.principals)).name

    allowed, reason = AccessDecisionManager.check_access(is_public, req_role, req_dept, clearance)
    status_str = "SUCCESS" if allowed else "DENIED"

    ledger.log(actor_name, f"ACCESS {resource}", resource, status_str)

    tag = f"{CLR_GREEN}[PASS]{CLR_RESET}" if allowed else f"{CLR_RED}[FAIL]{CLR_RESET}"
    print(f" {tag} Resource: {CLR_BOLD}{resource:<26}{CLR_RESET} Actor: {CLR_YELLOW}{actor_name:<14}{CLR_RESET} Result: {reason}")


def run_simulation():
    print_banner()
    user_db = setup_in_memory_directory()
    login_module = LoginModule(user_db)
    ledger = AuditLedger()

    print(f"{CLR_BOLD}{CLR_BLUE}== STEP 1: Unauthenticated Anonymous Access =={CLR_RESET}")
    SecurityContextHolder.clear_context()
    execute_request("/api/v1/public/health", is_public=True, req_role=None, req_dept=None, clearance=0, ledger=ledger)
    execute_request("/api/v1/vault/secrets", is_public=False, req_role="ROLE_ADMIN", req_dept="SecurityOperations", clearance=3, ledger=ledger)
    print()

    print(f"{CLR_BOLD}{CLR_BLUE}== STEP 2: JAAS Authentication Flow (bob.developer) =={CLR_RESET}")
    print(f"[*] Authenticating 'bob.developer'...")
    if login_module.login("bob.developer", "Dev#SecureKey"):
        bob_subject = Subject()
        login_module.commit(bob_subject)
        SecurityContextHolder.set_context(SecurityContext(bob_subject))
        print(f"{CLR_GREEN}[✓] JAAS LoginModule Commit: Principals={bob_subject.principals}, Roles={bob_subject.roles}{CLR_RESET}")
    else:
        print(f"{CLR_RED}[✗] Authentication failed{CLR_RESET}")

    execute_request("/api/v1/repo/commit", is_public=False, req_role="ROLE_DEVELOPER", req_dept="Engineering", clearance=1, ledger=ledger)
    execute_request("/api/v1/vault/secrets", is_public=False, req_role="ROLE_ADMIN", req_dept="SecurityOperations", clearance=3, ledger=ledger)
    print()

    print(f"{CLR_BOLD}{CLR_BLUE}== STEP 3: JAAS Authentication & Privilege Escalation Check (alice.admin) =={CLR_RESET}")
    print(f"[*] Authenticating 'alice.admin'...")
    if login_module.login("alice.admin", "Admin@Sec2026"):
        alice_subject = Subject()
        login_module.commit(alice_subject)
        SecurityContextHolder.set_context(SecurityContext(alice_subject))
        print(f"{CLR_GREEN}[✓] JAAS LoginModule Commit: Principals={alice_subject.principals}, Roles={alice_subject.roles}{CLR_RESET}")

    execute_request("/api/v1/vault/secrets", is_public=False, req_role="ROLE_ADMIN", req_dept="SecurityOperations", clearance=3, ledger=ledger)
    execute_request("/api/v1/governance/export", is_public=False, req_role="ROLE_AUDITOR", req_dept="SecurityOperations", clearance=2, ledger=ledger)
    print()

    print(f"{CLR_BOLD}{CLR_BLUE}== STEP 4: Governance & Cryptographic Audit Ledger =={CLR_RESET}")
    print(f"{CLR_CYAN}{'TIMESTAMP (UTC)':<22} | {'ACTOR':<16} | {'RESOURCE':<24} | {'STATUS':<8} | {'HASH'}{CLR_RESET}")
    print("-" * 84)
    for entry in ledger.chain:
        d = entry.as_dict()
        color = CLR_GREEN if d['status'] == "SUCCESS" else CLR_RED
        print(f"{d['timestamp']:<22} | {d['actor']:<16} | {d['resource']:<24} | {color}{d['status']:<8}{CLR_RESET} | {d['hash']}")

    intact, corrupted_idx = ledger.verify_integrity()
    if intact:
        print(f"\n{CLR_GREEN}{CLR_BOLD}[✓] Audit Trail Integrity Verified: Hash chain consistent across {len(ledger.chain)} events.{CLR_RESET}")
    else:
        print(f"\n{CLR_RED}{CLR_BOLD}[✗] Tampering Detected at Block Index {corrupted_idx}!{CLR_RESET}")

    print(f"\n{CLR_MAGENTA}{CLR_BOLD}Simulation Completed Successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    run_simulation()
