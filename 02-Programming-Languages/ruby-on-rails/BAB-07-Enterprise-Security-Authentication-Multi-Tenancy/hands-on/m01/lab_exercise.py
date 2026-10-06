#!/usr/bin/env python3
"""
Lab Exercise: Rails Enterprise Security, Authentication & Multi-Tenancy Simulator
Simulasi teknis konsep fondasi Ruby on Rails:
- Authentication & Session Management (Devise/Rodauth pattern)
- Policy-Based Authorization (Pundit pattern)
- Context-Bound Multi-Tenancy Scoping (acts_as_tenant / CurrentAttributes pattern)
- Enterprise Hardening: Strong Parameters & CSRF Token Validation
"""

import hashlib
import hmac
import secrets
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def header(title: str) -> None:
    print(f"\n{TerminalColor.BOLD}{TerminalColor.CYAN}{'=' * 65}{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.YELLOW} [RAILS SECURITY LAB] {title}{TerminalColor.RESET}")
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}{'=' * 65}{TerminalColor.RESET}")


def log_step(name: str, passed: bool, detail: str = "") -> None:
    badge = (
        f"{TerminalColor.GREEN}[PASS]{TerminalColor.RESET}"
        if passed
        else f"{TerminalColor.RED}[BLOCKED]{TerminalColor.RESET}"
    )
    print(f" {badge} {TerminalColor.BOLD}{name}{TerminalColor.RESET} - {detail}")


# -----------------------------------------------------------------------------
# 1. Multi-Tenancy Context: Rails CurrentAttributes Simulation
# -----------------------------------------------------------------------------
class CurrentAttributes:
    """Simulasi ActiveSupport::CurrentAttributes untuk Thread-Isolated Tenant Context."""

    def __init__(self) -> None:
        self.tenant_id: Optional[str] = None
        self.user: Optional[Any] = None

    def reset(self) -> None:
        self.tenant_id = None
        self.user = None


Current = CurrentAttributes()


# -----------------------------------------------------------------------------
# 2. Authentication: PBKDF2 Password Hashing & Devise Lockout Simulation
# -----------------------------------------------------------------------------
@dataclass
class User:
    id: int
    email: str
    tenant_id: str
    role: str
    salt: str
    password_hash: str
    failed_attempts: int = 0
    locked_at: Optional[float] = None
    session_token: Optional[str] = None

    @classmethod
    def create(cls, user_id: int, email: str, tenant_id: str, role: str, raw_pass: str) -> "User":
        salt = secrets.token_hex(16)
        pw_hash = hashlib.pbkdf2_hmac("sha256", raw_pass.encode(), salt.encode(), iterations=100_000).hex()
        return cls(
            id=user_id,
            email=email,
            tenant_id=tenant_id,
            role=role,
            salt=salt,
            password_hash=pw_hash,
        )

    def verify_password(self, raw_pass: str) -> bool:
        test_hash = hashlib.pbkdf2_hmac("sha256", raw_pass.encode(), self.salt.encode(), iterations=100_000).hex()
        return hmac.compare_digest(self.password_hash, test_hash)


class AuthService:
    MAX_ATTEMPTS = 3
    LOCK_DURATION_SEC = 30

    @staticmethod
    def authenticate(user: User, password_attempt: str) -> bool:
        # Check lockout
        if user.locked_at:
            if time.time() - user.locked_at < AuthService.LOCK_DURATION_SEC:
                log_step("Devise Lockable", False, f"Account {user.email} is locked due to consecutive failures")
                return False
            # Unlock expired
            user.locked_at = None
            user.failed_attempts = 0

        if user.verify_password(password_attempt):
            user.failed_attempts = 0
            user.session_token = secrets.token_urlsafe(32)
            log_step("Devise DatabaseAuthenticatable", True, f"Credentials verified for {user.email}")
            return True
        else:
            user.failed_attempts += 1
            if user.failed_attempts >= AuthService.MAX_ATTEMPTS:
                user.locked_at = time.time()
                log_step("Devise Lockable Triggered", False, f"Account locked after {user.failed_attempts} failed attempts")
            else:
                log_step("Devise Authentication Failed", False, f"Invalid attempt {user.failed_attempts}/{AuthService.MAX_ATTEMPTS}")
            return False


# -----------------------------------------------------------------------------
# 3. Authorization: Pundit Policy Simulation
# -----------------------------------------------------------------------------
@dataclass
class Document:
    id: int
    tenant_id: str
    owner_id: int
    title: str
    confidential: bool = False


class DocumentPolicy:
    """Simulasi Pundit::Policy untuk otorisasi berbasis Resource & Role."""

    def __init__(self, user: User, record: Document) -> None:
        self.user = user
        self.record = record

    def view(self) -> bool:
        if self.user.tenant_id != self.record.tenant_id:
            return False
        if self.user.role == "superadmin":
            return True
        if self.record.confidential and self.user.role not in ("tenant_admin", "compliance_officer"):
            return False
        return True

    def delete(self) -> bool:
        if self.user.tenant_id != self.record.tenant_id:
            return False
        if self.user.role in ("superadmin", "tenant_admin"):
            return True
        return self.record.owner_id == self.user.id


# -----------------------------------------------------------------------------
# 4. Multi-Tenancy Scoping: acts_as_tenant Simulation
# -----------------------------------------------------------------------------
class DocumentRepository:
    def __init__(self) -> None:
        self._database: List[Document] = []

    def seed(self, docs: List[Document]) -> None:
        self._database = docs

    def all_unscoped(self) -> List[Document]:
        """Direct DB query without tenant barrier (LEAK RISK)."""
        return list(self._database)

    def scoped_query(self) -> List[Document]:
        """Simulasi default_scope { where(tenant_id: Current.tenant_id) }."""
        if not Current.tenant_id:
            raise PermissionError("MultiTenancyViolation: Current.tenant_id is unassigned!")
        return [doc for doc in self._database if doc.tenant_id == Current.tenant_id]


# -----------------------------------------------------------------------------
# 5. Enterprise Security Hardening: CSRF & Strong Parameters
# -----------------------------------------------------------------------------
class SecurityHardening:
    @staticmethod
    def verify_csrf(session_token: str, request_token: str) -> bool:
        """Simulasi ActionController::RequestForgeryProtection."""
        if not session_token or not request_token:
            return False
        return hmac.compare_digest(session_token, request_token)

    @staticmethod
    def sanitize_strong_params(params: Dict[str, Any], permitted_keys: List[str]) -> Dict[str, Any]:
        """Simulasi params.require(...).permit(:title, :content)."""
        filtered = {k: v for k, v in params.items() if k in permitted_keys}
        stripped = [k for k in params.keys() if k not in permitted_keys]
        if stripped:
            print(f" {TerminalColor.YELLOW}[STRONG PARAMS]{TerminalColor.RESET} Mass-assignment protected! Stripped keys: {stripped}")
        return filtered


# -----------------------------------------------------------------------------
# Test Harness & Interactive Execution
# -----------------------------------------------------------------------------
def run_simulation() -> None:
    header("MODULE 1: Enterprise Authentication & Lockout Pipeline")
    alice = User.create(1, "alice@enterprise-corp.com", "tenant_alpha", "tenant_admin", "SuperSecret123!")

    # Successful login
    print(f"\n{TerminalColor.BOLD}Test 1.1: Valid Login Attempt{TerminalColor.RESET}")
    AuthService.authenticate(alice, "SuperSecret123!")

    # Lockout triggers
    print(f"\n{TerminalColor.BOLD}Test 1.2: Brute Force Resistance Simulation{TerminalColor.RESET}")
    for i in range(1, 4):
        print(f"  > Attempt {i} with bad password:")
        AuthService.authenticate(alice, "WrongPassword!")

    print(f"  > Attempt 4 while locked:")
    AuthService.authenticate(alice, "SuperSecret123!")

    header("MODULE 2: Multi-Tenancy Scoping (acts_as_tenant Pattern)")
    repo = DocumentRepository()
    repo.seed([
        Document(101, "tenant_alpha", 1, "Alpha Quarterly Financials", confidential=True),
        Document(102, "tenant_alpha", 1, "Alpha Public Roadmap", confidential=False),
        Document(201, "tenant_beta", 2, "Beta Acquisition Pitch", confidential=True),
        Document(202, "tenant_beta", 2, "Beta Architecture Whitepaper", confidential=False),
    ])

    print(f"\n{TerminalColor.BOLD}Test 2.1: Tenant Isolation Verification{TerminalColor.RESET}")
    Current.tenant_id = "tenant_alpha"
    scoped_alpha = repo.scoped_query()
    log_step(
        "acts_as_tenant Scope",
        all(d.tenant_id == "tenant_alpha" for d in scoped_alpha) and len(scoped_alpha) == 2,
        f"Retrieved {len(scoped_alpha)} documents strictly for tenant_alpha",
    )

    for doc in scoped_alpha:
        print(f"    - Doc #{doc.id}: '{doc.title}' [Tenant: {doc.tenant_id}]")

    print(f"\n{TerminalColor.BOLD}Test 2.2: Cross-Tenant Data Leak Attack Simulation{TerminalColor.RESET}")
    unscoped = repo.all_unscoped()
    cross_tenant_records = [d for d in unscoped if d.tenant_id != "tenant_alpha"]
    log_step(
        "Direct SQL / Unscoped Threat",
        False,
        f"Detected {len(cross_tenant_records)} alien records exposed if scope is bypassed!",
    )

    header("MODULE 3: Policy-Based Authorization (Pundit Pattern)")
    bob_member = User.create(2, "bob@enterprise-corp.com", "tenant_alpha", "member", "Pass123!")
    confidential_doc = scoped_alpha[0]
    public_doc = scoped_alpha[1]

    policy_member_confidential = DocumentPolicy(bob_member, confidential_doc)
    policy_member_public = DocumentPolicy(bob_member, public_doc)
    policy_admin_confidential = DocumentPolicy(alice, confidential_doc)

    log_step(
        "Pundit Policy (Member -> Confidential)",
        not policy_member_confidential.view(),
        "Regular member denied view access to confidential asset",
    )
    log_step(
        "Pundit Policy (Member -> Public)",
        policy_member_public.view(),
        "Regular member granted view access to public company asset",
    )
    log_step(
        "Pundit Policy (Admin -> Confidential)",
        policy_admin_confidential.view(),
        "Tenant Admin authorized to inspect confidential asset",
    )

    header("MODULE 4: CSRF & Strong Parameters Hardening")
    print(f"\n{TerminalColor.BOLD}Test 4.1: CSRF Protection Barrier{TerminalColor.RESET}")
    valid_csrf = alice.session_token
    forged_csrf = secrets.token_urlsafe(32)

    log_step(
        "Authenticity Token Verification",
        SecurityHardening.verify_csrf(alice.session_token, valid_csrf),
        "Legitimate request token validated",
    )
    log_step(
        "CSRF Exploit Interception",
        not SecurityHardening.verify_csrf(alice.session_token, forged_csrf),
        "Forged request rejected by protect_from_forgery",
    )

    print(f"\n{TerminalColor.BOLD}Test 4.2: Mass-Assignment Protection (Strong Parameters){TerminalColor.RESET}")
    incoming_request_payload = {
        "title": "Updated Strategy Deck",
        "description": "Internal roadmap 2026",
        "is_admin": True,
        "tenant_id": "tenant_hacked",
    }
    permitted_fields = ["title", "description"]
    clean_params = SecurityHardening.sanitize_strong_params(incoming_request_payload, permitted_fields)
    log_step(
        "Strong Parameters Gate",
        "is_admin" not in clean_params and "tenant_id" not in clean_params,
        f"Protected fields blocked from mass assignment: {clean_params}",
    )

    print(f"\n{TerminalColor.BOLD}{TerminalColor.GREEN}=== ALL ENTERPRISE SECURITY CHECKS EXECUTED SUCCESSFULLY ==={TerminalColor.RESET}\n")


if __name__ == "__main__":
    run_simulation()
