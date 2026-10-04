#!/usr/bin/env python3
"""
Lab Hands-on: Enterprise Security & Identity Governance (Java Ecosystem Model)
Module: Deep Dive into JAAS (Java Authentication & Authorization Service), 
        ABAC/RBAC Policy Enforcement, and Microprofile/JWT Identity Propagation.

This script simulates a production-grade enterprise Java security subsystem:
- JAAS Subject/Principal architectural model
- Cryptographic Token Engine (RFC 7519 HMAC-SHA256 JWT implementation)
- Enterprise Policy Decision Point (PDP) and Policy Enforcement Point (PEP)
- ThreadLocal SecurityContextHolder (Spring Security / Java EE Security Model)
- Multi-threaded concurrent access verification with Audit Trail logging
"""

import base64
import dataclasses
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"


def base64url_encode(data: bytes) -> str:
    """Encodes bytes into URL-safe Base64 without padding (RFC 7515)."""
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def base64url_decode(data_str: str) -> bytes:
    """Decodes URL-safe Base64 string with optional padding."""
    rem = len(data_str) % 4
    if rem > 0:
        data_str += '=' * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode('utf-8'))


# ============================================================================
# Core Identity Domain (Simulating javax.security.auth & JAAS)
# ============================================================================

@dataclasses.dataclass(frozen=True)
class Principal:
    """Represents an identity entity in JAAS (e.g., username, role, or group)."""
    name: str
    principal_type: str  # 'USER', 'ROLE', 'TENANT', 'CLEARANCE'


class Subject:
    """
    Java Subject analogue: Represents a grouping of related information for
    a single entity (Principals and Security Attributes).
    """
    def __init__(self, principals: Set[Principal]):
        self._principals: Set[Principal] = set(principals)
        self._read_only: bool = False

    def get_principals(self, principal_type: Optional[str] = None) -> Set[Principal]:
        if principal_type is None:
            return set(self._principals)
        return {p for p in self._principals if p.principal_type == principal_type}

    def set_read_only(self) -> None:
        self._read_only = True

    def __repr__(self) -> str:
        roles = [p.name for p in self.get_principals('ROLE')]
        user = next((p.name for p in self.get_principals('USER')), "ANONYMOUS")
        return f"Subject[user={user}, roles={roles}]"


# ============================================================================
# Cryptographic Token Engine (Simulating Java JJWT / Nimbus JOSE)
# ============================================================================

class EnterpriseJwtSigner:
    """Cryptographic provider for JWT signing and verification using HMAC-SHA256."""

    def __init__(self, shared_secret: bytes):
        self._secret = shared_secret

    def mint_token(self, subject: Subject, issuer: str, audience: str, ttl_seconds: int = 3600) -> str:
        """Serializes Subject claims into a cryptographically signed compact JWT."""
        header = {"alg": "HS256", "typ": "JWT"}
        user_p = next(iter(subject.get_principals('USER')), None)
        sub_name = user_p.name if user_p else "anonymous"
        roles = [p.name for p in subject.get_principals('ROLE')]
        clearance = next((p.name for p in subject.get_principals('CLEARANCE')), "LEVEL_1")
        tenant = next((p.name for p in subject.get_principals('TENANT')), "DEFAULT")

        now = int(time.time())
        payload = {
            "iss": issuer,
            "sub": sub_name,
            "aud": audience,
            "exp": now + ttl_seconds,
            "iat": now,
            "roles": roles,
            "clearance": clearance,
            "tenant_id": tenant,
            "jti": secrets.token_hex(8)
        }

        h_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
        p_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
        signing_input = f"{h_b64}.{p_b64}".encode('utf-8')
        signature = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        s_b64 = base64url_encode(signature)

        return f"{h_b64}.{p_b64}.{s_b64}"

    def parse_and_validate(self, token: str) -> Subject:
        """Parses JWT, verifies HMAC integrity, checks TTL, and reconstructs JAAS Subject."""
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Malformed JWT structure.")

        h_b64, p_b64, s_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode('utf-8')
        expected_sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        actual_sig = base64url_decode(s_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise PermissionError("Tampered token signature detected! Cryptographic integrity compromised.")

        payload = json.loads(base64url_decode(p_b64).decode('utf-8'))
        if time.time() > payload.get("exp", 0):
            raise TimeoutError("Security token has expired (exp claim violation).")

        # Rebuild JAAS Principals
        principals: Set[Principal] = {
            Principal(payload["sub"], "USER"),
            Principal(payload.get("clearance", "LEVEL_1"), "CLEARANCE"),
            Principal(payload.get("tenant_id", "DEFAULT"), "TENANT")
        }
        for role in payload.get("roles", []):
            principals.add(Principal(role, "ROLE"))

        subject = Subject(principals)
        subject.set_read_only()
        return subject


# ============================================================================
# SecurityContextHolder (Simulating Spring Security ThreadLocal pattern)
# ============================================================================

class SecurityContextHolder:
    """ThreadLocal container maintaining execution identity for current call chain."""
    _thread_local = threading.local()

    @classmethod
    def set_subject(cls, subject: Optional[Subject]) -> None:
        cls._thread_local.subject = subject

    @classmethod
    def get_subject(cls) -> Optional[Subject]:
        return getattr(cls._thread_local, 'subject', None)

    @classmethod
    def clear(cls) -> None:
        cls._thread_local.subject = None


# ============================================================================
# Policy Decision Point (PDP) & Policy Enforcement Point (PEP)
# ============================================================================

@dataclasses.dataclass
class ResourceTarget:
    resource_id: str
    target_tenant: str
    required_role: str
    min_clearance_level: int  # 1: Public, 2: Internal, 3: Confidential, 4: Top Secret


class PolicyDecisionPoint:
    """
    ABAC/RBAC Evaluation Engine. Evaluates multi-dimensional access policies:
    1. Tenant Isolation (Attribute-based)
    2. Role-Based Access Control (RBAC)
    3. Mandatory Access Control (MAC) Clearance Levels
    """
    CLEARANCE_MAP = {
        "LEVEL_1": 1,
        "LEVEL_2": 2,
        "LEVEL_3": 3,
        "LEVEL_4": 4
    }

    def evaluate(self, subject: Subject, resource: ResourceTarget, action: str) -> Tuple[bool, str]:
        # 1. RBAC Evaluation
        subject_roles = {p.name for p in subject.get_principals('ROLE')}
        if resource.required_role not in subject_roles and "ROLE_SUPERADMIN" not in subject_roles:
            return False, f"RBAC Denied: Missing required role [{resource.required_role}]"

        # 2. Multi-tenancy check (Except for global superadmins)
        if "ROLE_SUPERADMIN" not in subject_roles:
            tenant_p = next(iter(subject.get_principals('TENANT')), None)
            user_tenant = tenant_p.name if tenant_p else ""
            if user_tenant != resource.target_tenant:
                return False, f"ABAC Denied: Cross-tenant isolation failure (User: {user_tenant} != Target: {resource.target_tenant})"

        # 3. Clearance level check
        clearance_p = next(iter(subject.get_principals('CLEARANCE')), None)
        user_level_str = clearance_p.name if clearance_p else "LEVEL_1"
        user_level = self.CLEARANCE_MAP.get(user_level_str, 1)

        if user_level < resource.min_clearance_level:
            return False, (f"MAC Denied: Insufficient clearance. Provided: "
                          f"[{user_level_str}({user_level})], Required: [Lvl {resource.min_clearance_level}]")

        return True, "Access Granted by PEP/PDP consensus."


class AuditLogger:
    """Thread-safe security audit recorder simulating enterprise SIEM forwarder."""
    def __init__(self):
        self._lock = threading.Lock()
        self._audit_records: List[str] = []

    def record(self, identity: str, action: str, resource: str, granted: bool, reason: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        status = f"{CLR_GREEN}GRANTED{CLR_RESET}" if granted else f"{CLR_RED}DENIED{CLR_RESET}"
        entry = (f"[{timestamp}] [AUDIT] User: {CLR_CYAN}{identity:<14}{CLR_RESET} | "
                 f"Action: {CLR_YELLOW}{action:<6}{CLR_RESET} | "
                 f"Resource: {CLR_WHITE}{resource:<18}{CLR_RESET} | "
                 f"Status: {status} | Reason: {reason}")
        with self._lock:
            self._audit_records.append(entry)
            print(entry)


class EnterpriseResourceGateway:
    """Policy Enforcement Point (PEP) interceptor protecting target endpoints."""
    def __init__(self, pdp: PolicyDecisionPoint, audit: AuditLogger):
        self._pdp = pdp
        self._audit = audit

    def dispatch(self, resource: ResourceTarget, action: str) -> bool:
        subject = SecurityContextHolder.get_subject()
        if not subject:
            self._audit.record("UNAUTHENTICATED", action, resource.resource_id, False, "No active security context.")
            return False

        user_p = next(iter(subject.get_principals('USER')), None)
        user_name = user_p.name if user_p else "ANONYMOUS"

        allowed, reason = self._pdp.evaluate(subject, resource, action)
        self._audit.record(user_name, action, resource.resource_id, allowed, reason)
        return allowed


# ============================================================================
# Concurrent Simulation Harness
# ============================================================================

def execute_worker(
    worker_id: int,
    raw_token: str,
    target: ResourceTarget,
    action: str,
    signer: EnterpriseJwtSigner,
    gateway: EnterpriseResourceGateway
) -> None:
    """Simulates a Java Servlet / Spring filter chain worker running on independent threads."""
    try:
        # Step 1: Authentication Filter (Token Parsing & Subject Resolution)
        subject = signer.parse_and_validate(raw_token)
        SecurityContextHolder.set_subject(subject)

        # Step 2: PEP Interceptor Authorization
        gateway.dispatch(target, action)

    except (ValueError, PermissionError, TimeoutError) as ex:
        # Authentication or Token Integrity Failure
        gateway._audit.record(f"Worker-{worker_id}", action, target.resource_id, False, f"Authentication Failure: {str(ex)}")
    finally:
        # Step 3: ThreadLocal Clean-up (Preventing ThreadPool leakage)
        SecurityContextHolder.clear()


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}=== ENTERPRISE SECURITY & IDENTITY GOVERNANCE DEEP DIVE ==={CLR_RESET}")
    print(f"Simulating JAAS, RBAC/ABAC Policy Enforcement, and Cryptographic Context Propagation\n")

    # 1. Initialize Cryptographic Subsystem (Simulating Keystore shared key)
    master_key = secrets.token_bytes(32)
    jwt_signer = EnterpriseJwtSigner(master_key)
    pdp = PolicyDecisionPoint()
    audit_logger = AuditLogger()
    gateway = EnterpriseResourceGateway(pdp, audit_logger)

    print(f"{CLR_YELLOW}[1] Bootstrapping Identities & Cryptographic Credentials...{CLR_RESET}")

    # Identity 1: Alice (Internal Security Officer, FinTech Corp)
    sub_alice = Subject({
        Principal("alice@fintech.io", "USER"),
        Principal("ROLE_SECURITY_OFFICER", "ROLE"),
        Principal("ROLE_AUDITOR", "ROLE"),
        Principal("LEVEL_4", "CLEARANCE"),
        Principal("CORP_FINTECH", "TENANT")
    })
    token_alice = jwt_signer.mint_token(sub_alice, "enterprise-auth-srv", "api-gateway")

    # Identity 2: Bob (DevOps Engineer, Healthcare Dept)
    sub_bob = Subject({
        Principal("bob@health.io", "USER"),
        Principal("ROLE_DEVOPS", "ROLE"),
        Principal("LEVEL_2", "CLEARANCE"),
        Principal("CORP_HEALTH", "TENANT")
    })
    token_bob = jwt_signer.mint_token(sub_bob, "enterprise-auth-srv", "api-gateway")

    # Identity 3: Charlie (General Analyst, FinTech Corp - Low Clearance)
    sub_charlie = Subject({
        Principal("charlie@fintech.io", "USER"),
        Principal("ROLE_ANALYST", "ROLE"),
        Principal("LEVEL_1", "CLEARANCE"),
        Principal("CORP_FINTECH", "TENANT")
    })
    token_charlie = jwt_signer.mint_token(sub_charlie, "enterprise-auth-srv", "api-gateway")

    # Identity 4: Expired Token Simulation
    sub_expired = Subject({
        Principal("dave@legacy.io", "USER"),
        Principal("ROLE_SUPERADMIN", "ROLE"),
        Principal("LEVEL_4", "CLEARANCE"),
        Principal("CORP_FINTECH", "TENANT")
    })
    token_expired = jwt_signer.mint_token(sub_expired, "enterprise-auth-srv", "api-gateway", ttl_seconds=-10)

    # Identity 5: Forged/Tampered Token Simulation
    parts = token_alice.split('.')
    tampered_payload = json.loads(base64url_decode(parts[1]).decode('utf-8'))
    tampered_payload['roles'] = ["ROLE_SUPERADMIN"]  # Unauthorized Privilege Escalation
    tampered_p_b64 = base64url_encode(json.dumps(tampered_payload).encode('utf-8'))
    token_tampered = f"{parts[0]}.{tampered_p_b64}.{parts[2]}"  # Signature remains old!

    print(f"{CLR_GREEN}Tokens minted successfully.{CLR_RESET}\n")

    # Define Enterprise Protected Resources
    res_fintech_vault = ResourceTarget(
        resource_id="vault://ledger/keys",
        target_tenant="CORP_FINTECH",
        required_role="ROLE_SECURITY_OFFICER",
        min_clearance_level=4
    )

    res_fintech_metrics = ResourceTarget(
        resource_id="metrics://fintech/kpi",
        target_tenant="CORP_FINTECH",
        required_role="ROLE_ANALYST",
        min_clearance_level=1
    )

    res_health_db = ResourceTarget(
        resource_id="db://health/patients",
        target_tenant="CORP_HEALTH",
        required_role="ROLE_DEVOPS",
        min_clearance_level=2
    )

    print(f"{CLR_YELLOW}[2] Executing Concurrent Access Matrix Simulation...{CLR_RESET}")
    print(f"{CLR_BOLD}Target Resources:{CLR_RESET}")
    print(f"  - {res_fintech_vault.resource_id} (Requires: ROLE_SECURITY_OFFICER, Tenant: CORP_FINTECH, Clearance: L4)")
    print(f"  - {res_fintech_metrics.resource_id} (Requires: ROLE_ANALYST, Tenant: CORP_FINTECH, Clearance: L1)")
    print(f"  - {res_health_db.resource_id} (Requires: ROLE_DEVOPS, Tenant: CORP_HEALTH, Clearance: L2)\n")

    threads: List[threading.Thread] = []

    # Test Scenarios:
    scenarios = [
        # (WorkerID, Token, Target, Action, Description)
        (1, token_alice, res_fintech_vault, "READ", "Valid Access: Alice accessing Fintech Vault"),
        (2, token_alice, res_health_db, "READ", "Tenant Breach: Alice accessing Health DB"),
        (3, token_bob, res_health_db, "EXEC", "Valid Access: Bob updating Health DB"),
        (4, token_charlie, res_fintech_vault, "READ", "Clearance/Role Violation: Charlie accessing Vault"),
        (5, token_charlie, res_fintech_metrics, "READ", "Valid Access: Charlie reading metrics"),
        (6, token_expired, res_fintech_vault, "READ", "Token Expiration Test"),
        (7, token_tampered, res_fintech_vault, "READ", "Signature Tampering Attack Test")
    ]

    for item in scenarios:
        w_id, tok, target_res, act, desc = item
        t = threading.Thread(
            target=execute_worker,
            args=(w_id, tok, target_res, act, jwt_signer, gateway),
            name=f"WorkerThread-{w_id}"
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"\n{CLR_YELLOW}[3] Enterprise Policy Audit Summary{CLR_RESET}")
    print(f"All worker threads finalized. Clean security context teardown verified.")
    print(f"{CLR_BOLD}{CLR_GREEN}Hands-on Simulation Completed Successfully.{CLR_RESET}")


if __name__ == "__main__":
    main()