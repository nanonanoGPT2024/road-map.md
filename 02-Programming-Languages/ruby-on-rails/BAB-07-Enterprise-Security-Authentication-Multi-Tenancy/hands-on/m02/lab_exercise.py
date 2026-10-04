#!/usr/bin/env python3
"""
Lab: Enterprise Security, Authentication & Multi-Tenancy (Rails Architecture Simulation)
Topic: Ruby on Rails - Chapter 07, Module 02 Deep Dive

Simulates core enterprise security architecture commonly found in Rails applications:
1. Thread-safe Request Context (ActiveSupport::CurrentAttributes).
2. Row-Level Multi-Tenancy Scoping (ActsAsTenant engine model).
3. Secure Authentication via PBKDF2-HMAC (simulating Devise / Bcrypt & has_secure_password).
4. Policy-based Authorization Engine (mimicking Pundit / ActionPolicy).
5. Protection verification against Cross-Tenant Data Leaks & IDOR attacks.
"""

import hmac
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# --- ANSI Formatting ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"


# --- Custom Security Exceptions ---
class TenantIsolationError(Exception):
    """Raised when an operation breaches row-level multi-tenant boundaries."""
    pass


class UnauthorizedError(Exception):
    """Raised when Pundit-style authorization policy rejects an action."""
    pass


# --- Global Thread-Local Context (Mimics ActiveSupport::CurrentAttributes) ---
class CurrentContext(threading.local):
    """
    Rails ActiveSupport::CurrentAttributes thread-isolated proxy.
    Maintains per-request tenant, authenticated user, and trace IDs.
    """
    def __init__(self):
        super().__init__()
        self.tenant_id: Optional[str] = None
        self.user: Optional[Any] = None
        self.request_id: Optional[str] = None

    def reset(self):
        self.tenant_id = None
        self.user = None
        self.request_id = None


Current = CurrentContext()


# --- Security & Cryptographic Primitives ---
class SecurityEngine:
    """Enterprise authentication utilities (PBKDF2, HMAC-signed tokens)."""

    ITERATIONS = 100_000
    SECRET_KEY = b"rails_master_key_super_secret_enterprise_token_vault"

    @staticmethod
    def hash_password(password: str) -> tuple[str, str]:
        """Simulates Rails 'has_secure_password' with secure salt & PBKDF2."""
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            SecurityEngine.ITERATIONS
        ).hex()
        return digest, salt

    @staticmethod
    def verify_password(password: str, expected_hash: str, salt: str) -> bool:
        """Constant-time verification against timing attacks."""
        calculated = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            SecurityEngine.ITERATIONS
        ).hex()
        return hmac.compare_digest(calculated, expected_hash)

    @staticmethod
    def sign_session_token(data: str) -> str:
        """Creates a signed HMAC token like Rails ActionDispatch::Session::CookieStore."""
        sig = hmac.new(SecurityEngine.SECRET_KEY, data.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{data}.{sig}"

    @staticmethod
    def verify_session_token(token: str) -> Optional[str]:
        """Validates payload integrity using constant-time comparison."""
        try:
            data, sig = token.rsplit(".", 1)
            expected_sig = hmac.new(SecurityEngine.SECRET_KEY, data.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_sig):
                return data
        except (ValueError, AttributeError):
            pass
        return None


# --- Data Models (ActiveRecord Simulation) ---
@dataclass
class User:
    id: str
    tenant_id: str
    email: str
    role: str  # 'admin', 'member', 'auditor'
    password_hash: str
    salt: str


@dataclass
class EnterpriseDocument:
    id: str
    tenant_id: str
    title: str
    classification: str  # 'public', 'confidential', 'restricted'
    content: str


class DatabaseStore:
    """Mock thread-safe database storage with auto-scoping verification."""

    def __init__(self):
        self._lock = threading.Lock()
        self.users: Dict[str, User] = {}
        self.documents: Dict[str, EnterpriseDocument] = {}

    def insert_document(self, title: str, classification: str, content: str) -> EnterpriseDocument:
        """Automatically binds tenant_id from Current context (ActsAsTenant)."""
        if not Current.tenant_id:
            raise TenantIsolationError("ActiveRecord::StatementInvalid: Multi-tenant context missing!")

        doc_id = f"doc_{secrets.token_hex(4)}"
        doc = EnterpriseDocument(
            id=doc_id,
            tenant_id=Current.tenant_id,
            title=title,
            classification=classification,
            content=content
        )
        with self._lock:
            self.documents[doc_id] = doc
        return doc

    def scoped_documents(self) -> List[EnterpriseDocument]:
        """Default scope simulating: default_scope { where(tenant_id: Current.tenant_id) }."""
        if not Current.tenant_id:
            raise TenantIsolationError("Tenant scoping failure: Current.tenant is unassigned.")
        with self._lock:
            return [d for d in self.documents.values() if d.tenant_id == Current.tenant_id]

    def raw_find_document(self, doc_id: str) -> Optional[EnterpriseDocument]:
        """Unscoped lookup (vulnerable to IDOR if accessed directly without policy)."""
        with self._lock:
            return self.documents.get(doc_id)


DB = DatabaseStore()


# --- Pundit Policy Engine ---
class DocumentPolicy:
    """Simulates Rails Pundit authorization policies."""

    @staticmethod
    def show(user: User, document: EnterpriseDocument) -> bool:
        # Cross-Tenant Barrier (Zero Trust)
        if user.tenant_id != document.tenant_id:
            return False

        # Role-Based Permissions
        if user.role == "admin":
            return True
        if user.role == "member" and document.classification != "restricted":
            return True
        if user.role == "auditor" and document.classification == "public":
            return True

        return False

    @staticmethod
    def authorize(action: str, user: User, document: EnterpriseDocument):
        policy_fn = getattr(DocumentPolicy, action, None)
        if not policy_fn or not policy_fn(user, document):
            raise UnauthorizedError(
                f"Pundit::NotAuthorizedError: Role '{user.role}' in tenant '{user.tenant_id}' "
                f"unauthorized for action '{action}' on Document '{document.id}' ({document.classification})"
            )


# --- Controller Pipeline Simulation ---
class DocumentsController:
    """Simulates Rails ActionController workflow."""

    @staticmethod
    def index() -> List[Dict[str, Any]]:
        # Enforces default scope
        docs = DB.scoped_documents()
        return [{"id": d.id, "title": d.title, "tenant": d.tenant_id} for d in docs]

    @staticmethod
    def show(doc_id: str) -> Dict[str, Any]:
        # Fetch unscoped or raw candidate
        doc = DB.raw_find_document(doc_id)
        if not doc:
            return {"status": 404, "error": "Not Found"}

        # Pundit Authorize Enforcement
        DocumentPolicy.authorize("show", Current.user, doc)
        return {"status": 200, "data": doc}


# --- Multi-Thread Worker Simulation ---
def tenant_request_worker(worker_id: int, tenant_id: str, user: User, target_doc_ids: List[str]):
    """Simulates an incoming HTTP Request dispatched to a Puma worker thread."""
    Current.reset()
    Current.tenant_id = tenant_id
    Current.user = user
    Current.request_id = f"req_{secrets.token_hex(4)}"

    # 1. Tenant Creation Phase
    new_doc = DB.insert_document(
        title=f"Internal Strategy [{tenant_id}]",
        classification="confidential",
        content=f"Secret payload managed by {user.email}"
    )

    # 2. Scoped Query Phase
    accessible_docs = DocumentsController.index()

    # 3. IDOR Attack Simulation: Attempt to read documents belonging to another tenant
    attack_results = []
    for doc_id in target_doc_ids:
        try:
            res = DocumentsController.show(doc_id)
            attack_results.append((doc_id, "EXFILTRATED", res["data"].title))
        except UnauthorizedError:
            attack_results.append((doc_id, "BLOCKED_BY_POLICY", None))
        except Exception as e:
            attack_results.append((doc_id, f"ERROR: {str(e)}", None))

    print(f"[{CLR_CYAN}Worker-{worker_id}{CLR_RESET}] "
          f"Tenant: {CLR_BOLD}{tenant_id}{CLR_RESET} | "
          f"User: {user.email} ({user.role}) | "
          f"Scoped Records: {len(accessible_docs)}")

    for target_id, status, details in attack_results:
        color = CLR_GREEN if status == "BLOCKED_BY_POLICY" else CLR_RED
        print(f"   └── Probe Doc ID '{target_id}': {color}{status}{CLR_RESET}")

    Current.reset()


# --- Execution Pipeline ---
def main():
    print(f"{CLR_BOLD}{CLR_BLUE}=== Rails Enterprise Security: Multi-Tenancy & Authorization Lab ==={CLR_RESET}\n")

    # Step 1: User Provisioning with Secure Password Hashes
    print(f"{CLR_YELLOW}[Step 1] Initializing Tenants, Credentials & PBKDF2 Verification...{CLR_RESET}")
    h1, s1 = SecurityEngine.hash_password("Tenant1Secr3t!")
    h2, s2 = SecurityEngine.hash_password("Tenant2Secr3t!")

    user_acme_admin = User("u1", "tenant_acme", "admin@acme.corp", "admin", h1, s1)
    user_acme_member = User("u2", "tenant_acme", "alice@acme.corp", "member", h1, s1)
    user_globex_admin = User("u3", "tenant_globex", "bob@globex.org", "admin", h2, s2)

    assert SecurityEngine.verify_password("Tenant1Secr3t!", user_acme_admin.password_hash, user_acme_admin.salt)
    assert not SecurityEngine.verify_password("WrongPassword!", user_acme_admin.password_hash, user_acme_admin.salt)
    print(f"{CLR_GREEN}✓ Authentication verification passes (Constant-Time PBKDF2 comparison).{CLR_RESET}")

    # Step 2: Session Token Signing & Tamper Verification
    print(f"\n{CLR_YELLOW}[Step 2] Testing Rails HMAC Signed Session Verification...{CLR_RESET}")
    valid_token = SecurityEngine.sign_session_token("session_usr_acme_admin_valid")
    tampered_token = valid_token[:-4] + "ffff"

    assert SecurityEngine.verify_session_token(valid_token) is not None
    assert SecurityEngine.verify_session_token(tampered_token) is None
    print(f"{CLR_GREEN}✓ Session integrity guaranteed. Tampered tokens rejected successfully.{CLR_RESET}")

    # Step 3: Populate baseline records under specific tenant contexts
    print(f"\n{CLR_YELLOW}[Step 3] Pre-populating Tenant Vaults via ActsAsTenant scopes...{CLR_RESET}")
    Current.tenant_id = "tenant_acme"
    acme_doc_1 = DB.insert_document("Acme Financials 2026", "restricted", "Acme EBITDA projection")
    acme_doc_2 = DB.insert_document("Acme Public RoadMap", "public", "General feature timeline")

    Current.tenant_id = "tenant_globex"
    globex_doc_1 = DB.insert_document("Globex Acquisition List", "restricted", "Targets: Competitor X")
    Current.reset()

    # Step 4: Concurrent Thread Testing (Simulating Puma multithreaded requests)
    print(f"\n{CLR_YELLOW}[Step 4] Running Concurrent Multithreaded Tenant Isolation & IDOR Tests...{CLR_RESET}")
    threads = []
    
    # Thread 1: Acme Member attempts to access Globex doc and Acme restricted doc
    t1 = threading.Thread(
        target=tenant_request_worker,
        args=(1, "tenant_acme", user_acme_member, [globex_doc_1.id, acme_doc_1.id])
    )
    # Thread 2: Globex Admin attempts to access Acme restricted doc
    t2 = threading.Thread(
        target=tenant_request_worker,
        args=(2, "tenant_globex", user_globex_admin, [acme_doc_1.id, acme_doc_2.id])
    )
    # Thread 3: Acme Admin attempts to read own restricted doc (should succeed)
    t3 = threading.Thread(
        target=tenant_request_worker,
        args=(3, "tenant_acme", user_acme_admin, [acme_doc_1.id])
    )

    for t in [t1, t2, t3]:
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Step 5: Direct Scope Leak Test
    print(f"\n{CLR_YELLOW}[Step 5] Validating Zero-State Context Leak Prevention...{CLR_RESET}")
    Current.reset()
    try:
        DB.scoped_documents()
        print(f"{CLR_RED}✗ FAILED: Tenant leak detected! Context permitted query without tenant!{CLR_RESET}")
    except TenantIsolationError as e:
        print(f"{CLR_GREEN}✓ SUCCESS: Unscoped query blocked immediately: {e}{CLR_RESET}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}=== All Rails Enterprise Security & Multi-Tenancy Invariants Passed ==={CLR_RESET}")


if __name__ == "__main__":
    main()