#!/usr/bin/env python3
"""
Lab Exercise: Next.js Enterprise Security, Identity Management, and RBAC Simulation
BAB-07: Enterprise Security, Identity Management, dan RBAC

Topik yang disimulasikan:
1. Token & Session Management (HMAC-SHA256 Signed Session, Expiry, & Tamper Proofing)
2. Edge Middleware Route Guard (Zero Trust Path Authorization)
3. Role-Based Access Control (RBAC) & Attribute-Based Access Control (ABAC)
4. Multi-Tenant Boundary Isolation & Server Action Security Checks
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
BG_DARK = "\033[40m"


def header(title: str) -> None:
    sep = "=" * 70
    print(f"\n{CLR_CYAN}{CLR_BOLD}{sep}{CLR_RESET}")
    print(f"{CLR_WHITE}{CLR_BOLD} [LAB SIMULATION] {title.upper()}{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}{sep}{CLR_RESET}\n")


def subheader(text: str) -> None:
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}--- {text} ---{CLR_RESET}")


def badge_ok(msg: str) -> str:
    return f"{CLR_GREEN}{CLR_BOLD}[ALLOWED / 200 OK]{CLR_RESET} {msg}"


def badge_denied(msg: str) -> str:
    return f"{CLR_RED}{CLR_BOLD}[DENIED / 403 FORBIDDEN]{CLR_RESET} {msg}"


def badge_unauth(msg: str) -> str:
    return f"{CLR_YELLOW}{CLR_BOLD}[UNAUTHORIZED / 401]{CLR_RESET} {msg}"


# --- Cryptographic Helper: Signed JWT / Cookie Simulation ---
SECRET_SIGNING_KEY = b"enterprise-nextjs-super-secret-key-32b"


@dataclass
class UserSession:
    user_id: str
    email: str
    tenant_id: str
    role: str
    permissions: List[str]
    exp: int


def sign_payload(payload_bytes: bytes) -> str:
    sig = hmac.new(SECRET_SIGNING_KEY, payload_bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")


def create_signed_token(session: UserSession) -> str:
    payload_raw = json.dumps(asdict(session), separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("utf-8").rstrip("=")
    signature = sign_payload(payload_raw)
    return f"{payload_b64}.{signature}"


def verify_signed_token(token: str) -> Optional[UserSession]:
    parts = token.split(".")
    if len(parts) != 2:
        return None
    raw_b64, signature = parts
    padding = "=" * ((4 - len(raw_b64) % 4) % 4)
    try:
        raw_bytes = base64.urlsafe_b64decode(raw_b64 + padding)
        expected_sig = sign_payload(raw_bytes)
        if not hmac.compare_digest(signature, expected_sig):
            return None
        data = json.loads(raw_bytes.decode("utf-8"))
        if data.get("exp", 0) < int(time.time()):
            return None  # Expired
        return UserSession(**data)
    except Exception:
        return None


# --- Role and Permission Matrix Definition ---
ROLE_DEFINITIONS: Dict[str, Set[str]] = {
    "admin": {
        "org:manage",
        "billing:read",
        "billing:write",
        "users:invite",
        "users:delete",
        "data:export",
        "reports:view",
    },
    "compliance_officer": {
        "audit:read",
        "data:export",
        "reports:view",
    },
    "editor": {
        "content:read",
        "content:write",
        "content:publish",
        "reports:view",
    },
    "viewer": {
        "content:read",
        "reports:view",
    },
}

# Protected Routes Table in Next.js Middleware (matcher pattern simulation)
ROUTE_GUARD_POLICIES = [
    {
        "pattern": "/admin",
        "required_role": "admin",
        "required_perm": "org:manage",
    },
    {
        "pattern": "/dashboard/billing",
        "required_role": None,
        "required_perm": "billing:read",
    },
    {
        "pattern": "/dashboard/audit",
        "required_role": None,
        "required_perm": "audit:read",
    },
    {
        "pattern": "/dashboard/content",
        "required_role": None,
        "required_perm": "content:read",
    },
]


class NextEdgeMiddleware:
    """Simulates Next.js edge runtime middleware verifying tokens before hit."""

    def __init__(self, routes_table: List[Dict[str, Any]]) -> None:
        self.routes_table = routes_table

    def intercept(self, path: str, token: Optional[str]) -> Dict[str, Any]:
        matched_policy = None
        for policy in self.routes_table:
            if path.startswith(policy["pattern"]):
                matched_policy = policy
                break

        if not matched_policy:
            return {"status": 200, "user": None, "msg": "Public Route - Pass-through"}

        if not token:
            return {
                "status": 401,
                "user": None,
                "msg": f"Route '{path}' requires authentication header/cookie.",
            }

        session = verify_signed_token(token)
        if not session:
            return {
                "status": 401,
                "user": None,
                "msg": "Invalid, tampered, or expired session token.",
            }

        # RBAC Check
        if matched_policy["required_role"] and session.role != matched_policy["required_role"]:
            return {
                "status": 403,
                "user": session,
                "msg": f"Role '{session.role}' does not satisfy required role '{matched_policy['required_role']}'.",
            }

        # Permission Check
        if (
            matched_policy["required_perm"]
            and matched_policy["required_perm"] not in session.permissions
        ):
            return {
                "status": 403,
                "user": session,
                "msg": f"Missing permission: {matched_policy['required_perm']}",
            }

        return {
            "status": 200,
            "user": session,
            "msg": f"Authorized access to '{path}' as role '{session.role}'.",
        }


class ServerActionGuard:
    """
    Simulates Next.js Server Action defense in depth:
    Validates tenant isolation (ABAC) and granular permission bounds.
    """

    @staticmethod
    def execute_export_report(
        session: UserSession, target_tenant_id: str, classification: str
    ) -> Dict[str, Any]:
        # Rule 1: Tenant Boundary (ABAC)
        if session.tenant_id != target_tenant_id:
            return {
                "success": False,
                "code": "CROSS_TENANT_VIOLATION",
                "detail": f"User tenant '{session.tenant_id}' cannot access target tenant '{target_tenant_id}'.",
            }

        # Rule 2: Permission check
        if "data:export" not in session.permissions:
            return {
                "success": False,
                "code": "INSUFFICIENT_PERMISSIONS",
                "detail": "Missing 'data:export' permission.",
            }

        # Rule 3: Highly Confidential ABAC Policy
        if classification == "RESTRICTED" and session.role not in [
            "admin",
            "compliance_officer",
        ]:
            return {
                "success": False,
                "code": "ABAC_POLICY_REJECTED",
                "detail": "Data classification 'RESTRICTED' requires compliance or admin clearance.",
            }

        return {
            "success": True,
            "code": "EXECUTION_COMPLETE",
            "detail": f"Export report generated for tenant {target_tenant_id} [Classification: {classification}].",
        }


# --- Interactive Laboratory Execution Engine ---
def build_sample_sessions() -> Dict[str, UserSession]:
    now = int(time.time())
    ttl = 3600  # 1 hour
    return {
        "alice": UserSession(
            user_id="usr_001",
            email="alice@acme.corp",
            tenant_id="tenant_acme",
            role="admin",
            permissions=list(ROLE_DEFINITIONS["admin"]),
            exp=now + ttl,
        ),
        "bob": UserSession(
            user_id="usr_002",
            email="bob@acme.corp",
            tenant_id="tenant_acme",
            role="editor",
            permissions=list(ROLE_DEFINITIONS["editor"]),
            exp=now + ttl,
        ),
        "charlie": UserSession(
            user_id="usr_003",
            email="charlie@globex.org",
            tenant_id="tenant_globex",
            role="viewer",
            permissions=list(ROLE_DEFINITIONS["viewer"]),
            exp=now + ttl,
        ),
        "diana": UserSession(
            user_id="usr_004",
            email="diana@acme.corp",
            tenant_id="tenant_acme",
            role="compliance_officer",
            permissions=list(ROLE_DEFINITIONS["compliance_officer"]),
            exp=now + ttl,
        ),
        "expired_eva": UserSession(
            user_id="usr_999",
            email="eva@acme.corp",
            tenant_id="tenant_acme",
            role="admin",
            permissions=list(ROLE_DEFINITIONS["admin"]),
            exp=now - 60,  # Expired 60s ago
        ),
    }


def run_middleware_simulation(middleware: NextEdgeMiddleware, sessions: Dict[str, UserSession]) -> None:
    subheader("1. NEXT.JS EDGE MIDDLEWARE ROUTE GUARD TESTS")
    test_cases = [
        {"desc": "Anonymous request to public route", "path": "/public/about", "token": None},
        {"desc": "Anonymous request to protected admin route", "path": "/admin/settings", "token": None},
        {
            "desc": "Alice (Admin, Acme) accessing /admin",
            "path": "/admin/audit-log",
            "token": create_signed_token(sessions["alice"]),
        },
        {
            "desc": "Bob (Editor, Acme) accessing /admin (Unauthorized Role)",
            "path": "/admin/finance",
            "token": create_signed_token(sessions["bob"]),
        },
        {
            "desc": "Bob (Editor, Acme) accessing /dashboard/content",
            "path": "/dashboard/content/new",
            "token": create_signed_token(sessions["bob"]),
        },
        {
            "desc": "Charlie (Viewer, Globex) accessing /dashboard/billing (Forbidden)",
            "path": "/dashboard/billing",
            "token": create_signed_token(sessions["charlie"]),
        },
        {
            "desc": "Eva (Admin, Acme) accessing /admin with Expired Token",
            "path": "/admin",
            "token": create_signed_token(sessions["expired_eva"]),
        },
        {
            "desc": "Attacker sending Tampered HMAC Token",
            "path": "/admin",
            "token": create_signed_token(sessions["charlie"])[:-4] + "fake",
        },
    ]

    for tc in test_cases:
        res = middleware.intercept(tc["path"], tc["token"])
        status = res["status"]
        print(f"{CLR_BOLD}Case:{CLR_RESET} {tc['desc']}")
        print(f"  Path: {CLR_BLUE}{tc['path']}{CLR_RESET}")
        if status == 200:
            print(f"  Result: {badge_ok(res['msg'])}")
        elif status == 403:
            print(f"  Result: {badge_denied(res['msg'])}")
        else:
            print(f"  Result: {badge_unauth(res['msg'])}")
        print()


def run_abac_server_action_simulation(sessions: Dict[str, UserSession]) -> None:
    subheader("2. SERVER ACTIONS TENANT ISOLATION & ABAC ENFORCEMENT")
    scenarios = [
        {
            "name": "Alice (Acme Admin) exports Acme public reports",
            "user": sessions["alice"],
            "target_tenant": "tenant_acme",
            "classif": "PUBLIC",
        },
        {
            "name": "Alice (Acme Admin) attempts cross-tenant export to Globex",
            "user": sessions["alice"],
            "target_tenant": "tenant_globex",
            "classif": "INTERNAL",
        },
        {
            "name": "Bob (Acme Editor) attempts data export without permission",
            "user": sessions["bob"],
            "target_tenant": "tenant_acme",
            "classif": "INTERNAL",
        },
        {
            "name": "Diana (Compliance Officer) exports RESTRICTED Acme telemetry",
            "user": sessions["diana"],
            "target_tenant": "tenant_acme",
            "classif": "RESTRICTED",
        },
        {
            "name": "Charlie (Globex Viewer) attempts RESTRICTED export on Globex",
            "user": sessions["charlie"],
            "target_tenant": "tenant_globex",
            "classif": "RESTRICTED",
        },
    ]

    for sc in scenarios:
        res = ServerActionGuard.execute_export_report(
            session=sc["user"],
            target_tenant_id=sc["target_tenant"],
            classification=sc["classif"],
        )
        print(f"{CLR_BOLD}Scenario:{CLR_RESET} {sc['name']}")
        print(f"  Tenant Target: {CLR_CYAN}{sc['target_tenant']}{CLR_RESET} | Classification: {CLR_YELLOW}{sc['classif']}{CLR_RESET}")
        if res["success"]:
            print(f"  Status: {CLR_GREEN}{CLR_BOLD}[ACTION APPROVED]{CLR_RESET} {res['detail']}")
        else:
            print(f"  Status: {CLR_RED}{CLR_BOLD}[ACTION BLOCKED ({res['code']})]{CLR_RESET} {res['detail']}")
        print()


def interactive_menu(middleware: NextEdgeMiddleware, sessions: Dict[str, UserSession]) -> None:
    subheader("3. INTERACTIVE CONSOLE TESTER")
    print(f"{CLR_DIM}Pilih simulasi kustom untuk menguji runtime guard Next.js:{CLR_RESET}")
    print("1. Tes Edge Middleware Automated Suite")
    print("2. Tes Server Action ABAC / Multi-Tenant Isolation")
    print("3. Buat Custom Signed Token & Simulasikan Permintaan HTTP")
    print("4. Keluar (Exit)")

    while True:
        try:
            choice = input(f"\n{CLR_CYAN}Pilih opsi [1-4]: {CLR_RESET}").strip()
            if choice == "1":
                run_middleware_simulation(middleware, sessions)
            elif choice == "2":
                run_abac_server_action_simulation(sessions)
            elif choice == "3":
                custom_user = input("Masukkan user id (e.g. usr_test): ").strip() or "usr_test"
                role = input("Masukkan role (admin/editor/viewer/compliance_officer): ").strip() or "viewer"
                perms = list(ROLE_DEFINITIONS.get(role, []))
                s = UserSession(
                    user_id=custom_user,
                    email=f"{custom_user}@example.com",
                    tenant_id="tenant_custom",
                    role=role,
                    permissions=perms,
                    exp=int(time.time()) + 1800,
                )
                tok = create_signed_token(s)
                print(f"{CLR_GREEN}Generated Token:{CLR_RESET} {tok[:30]}...")
                req_path = input("Path target Next.js (e.g. /admin, /dashboard/billing): ").strip()
                res = middleware.intercept(req_path, tok)
                print(f"Middleware Output -> Status: {res['status']}, Message: {res['msg']}")
            elif choice == "4" or choice.lower() in ("q", "exit"):
                print(f"{CLR_GREEN}Lab selesai. Terus terapkan Zero-Trust di Next.js!{CLR_RESET}")
                break
            else:
                print(f"{CLR_YELLOW}Pilihan tidak valid. Silakan pilih 1-4.{CLR_RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CLR_GREEN}Keluar dari lab simulation.{CLR_RESET}")
            break


def main() -> None:
    header("Next.js Enterprise Security: Identity & RBAC Lab")
    print(f"{CLR_DIM}Inisialisasi konfigurasi keamanan, role matrix, dan token signer...{CLR_RESET}")

    sessions = build_sample_sessions()
    middleware = NextEdgeMiddleware(ROUTE_GUARD_POLICIES)

    # Otomatis jalankan suite 1 dan 2 sebagai verifikasi mandiri
    run_middleware_simulation(middleware, sessions)
    run_abac_server_action_simulation(sessions)

    # Cek mode eksekusi: non-interaktif vs interaktif
    if sys.stdin.isatty():
        interactive_menu(middleware, sessions)
    else:
        print(f"\n{CLR_GREEN}{CLR_BOLD}[VERIFIKASI SUKSES]{CLR_RESET} Semua test-case non-interaktif berhasil dijalankan tanpa galat.")


if __name__ == "__main__":
    main()
