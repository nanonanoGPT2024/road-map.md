#!/usr/bin/env python3
"""
ASP.NET Core Security Simulation - Lab Exercise
Topic: Authentication, Authorization, Identity & Security Middleware Pipeline
Module: BAB-05 Modul 01

Simulasi teknis independen arsitektur keamanan ASP.NET Core:
1. ClaimsIdentity & ClaimsPrincipal
2. Password Hashing (PBKDF2 - RFC 2898 / ASP.NET Identity standard)
3. JWT Bearer Token Issuer & Validator
4. Security Pipeline: UseAuthentication() & UseAuthorization()
5. Policy-Based Authorization & Custom Authorization Handlers
"""

import base64
import hashlib
import hmac
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palette for Terminal Presentation
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
    BG_BLUE = "\033[44m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


def header(text: str) -> None:
    print(f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} [ASP.NET CORE SECURITY] {text} {Colors.RESET}")


def subheader(text: str) -> None:
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- {text} ---{Colors.RESET}")


def success(text: str) -> None:
    print(f"{Colors.GREEN}[✓ OK] {text}{Colors.RESET}")


def warn(text: str) -> None:
    print(f"{Colors.YELLOW}[!] {text}{Colors.RESET}")


def error(text: str) -> None:
    print(f"{Colors.RED}[✗ DENIED] {text}{Colors.RESET}")


def info(label: str, value: Any) -> None:
    print(f"  {Colors.WHITE}{label}:{Colors.RESET} {Colors.MAGENTA}{value}{Colors.RESET}")


# ==============================================================================
# 1. Identity Core: Claims, ClaimsIdentity, and ClaimsPrincipal
# ==============================================================================
@dataclass
class Claim:
    type: str
    value: str
    issuer: str = "LOCAL_AUTHORITY"


@dataclass
class ClaimsIdentity:
    authentication_type: Optional[str]
    claims: List[Claim] = field(default_factory=list)

    @property
    def is_authenticated(self) -> bool:
        return self.authentication_type is not None and len(self.claims) > 0

    def find_first(self, claim_type: str) -> Optional[Claim]:
        for c in self.claims:
            if c.type == claim_type:
                return c
        return None

    def find_all(self, claim_type: str) -> List[Claim]:
        return [c for c in self.claims if c.type == claim_type]


class ClaimsPrincipal:
    def __init__(self, identities: Optional[List[ClaimsIdentity]] = None):
        self.identities = identities or []

    @property
    def identity(self) -> Optional[ClaimsIdentity]:
        return self.identities[0] if self.identities else None

    @property
    def is_authenticated(self) -> bool:
        return any(i.is_authenticated for i in self.identities)

    def is_in_role(self, role_name: str) -> bool:
        for ident in self.identities:
            for c in ident.find_all("http://schemas.microsoft.com/ws/2008/06/identity/claims/role"):
                if c.value.lower() == role_name.lower():
                    return True
        return False

    def find_first(self, claim_type: str) -> Optional[Claim]:
        for ident in self.identities:
            c = ident.find_first(claim_type)
            if c:
                return c
        return None


# ==============================================================================
# 2. Password Hasher (ASP.NET Core Identity Compatible PBKDF2)
# ==============================================================================
class PasswordHasher:
    """Simulasi Microsoft.AspNetCore.Identity.PasswordHasher<TUser> v3 format."""
    SALT_SIZE = 16
    ITERATIONS = 100_000

    @classmethod
    def hash_password(cls, password: str) -> str:
        import os
        salt = os.urandom(cls.SALT_SIZE)
        sub_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, cls.ITERATIONS, dklen=32)
        combined = b"\x01" + salt + sub_key
        return base64.b64encode(combined).decode("ascii")

    @classmethod
    def verify_password(cls, hashed: str, password: str) -> bool:
        try:
            payload = base64.b64decode(hashed)
            if payload[0] != 1:
                return False
            salt = payload[1:1 + cls.SALT_SIZE]
            expected_key = payload[1 + cls.SALT_SIZE:]
            sub_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, cls.ITERATIONS, dklen=32)
            return hmac.compare_digest(expected_key, sub_key)
        except Exception:
            return False


# ==============================================================================
# 3. JWT Bearer Token Infrastructure
# ==============================================================================
class JwtService:
    SECRET_KEY = b"SuperSecretAspnetCoreMasterKeySigningKey2026!#"

    @classmethod
    def _b64url_encode(cls, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @classmethod
    def _b64url_decode(cls, text: str) -> bytes:
        rem = len(text) % 4
        if rem > 0:
            text += "=" * (4 - rem)
        return base64.urlsafe_b64decode(text.encode("ascii"))

    @classmethod
    def generate_token(cls, username: str, roles: List[str], department: str, clearance: int, exp_seconds: int = 300) -> str:
        header_data = {"alg": "HS256", "typ": "JWT"}
        payload_data = {
            "sub": username,
            "jti": hashlib.sha256(f"{username}{time.time()}".encode()).hexdigest()[:12],
            "exp": int(time.time()) + exp_seconds,
            "iss": "https://auth.contoso.com",
            "aud": "https://api.contoso.com",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": roles,
            "department": department,
            "clearance_level": clearance,
        }
        b64_header = cls._b64url_encode(json.dumps(header_data).encode("utf-8"))
        b64_payload = cls._b64url_encode(json.dumps(payload_data).encode("utf-8"))
        msg = f"{b64_header}.{b64_payload}".encode("ascii")
        signature = hmac.new(cls.SECRET_KEY, msg, hashlib.sha256).digest()
        b64_sig = cls._b64url_encode(signature)
        return f"{b64_header}.{b64_payload}.{b64_sig}"

    @classmethod
    def validate_and_parse(cls, token: str) -> Tuple[bool, Optional[ClaimsPrincipal], str]:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None, "Invalid token format (3 segment requirement failed)"
        b64_hdr, b64_pld, b64_sig = parts
        msg = f"{b64_hdr}.{b64_pld}".encode("ascii")
        expected_sig = cls._b64url_encode(hmac.new(cls.SECRET_KEY, msg, hashlib.sha256).digest())

        if not hmac.compare_digest(b64_sig, expected_sig):
            return False, None, "Token signature verification failed (TAMPERED)"

        try:
            pld_bytes = cls._b64url_decode(b64_pld)
            payload = json.loads(pld_bytes.decode("utf-8"))
        except Exception as e:
            return False, None, f"Payload decode error: {e}"

        now = int(time.time())
        if payload.get("exp", 0) < now:
            return False, None, f"Token expired at {payload.get('exp')} (Now: {now})"

        claims: List[Claim] = []
        for k, v in payload.items():
            if isinstance(v, list):
                for item in v:
                    claims.append(Claim(type=k, value=str(item), issuer=payload.get("iss", "LOCAL")))
            else:
                claims.append(Claim(type=k, value=str(v), issuer=payload.get("iss", "LOCAL")))

        identity = ClaimsIdentity(authentication_type="Bearer", claims=claims)
        principal = ClaimsPrincipal([identity])
        return True, principal, "Token valid"


# ==============================================================================
# 4. Policy-Based Authorization Engine (IAuthorizationRequirement & Handlers)
# ==============================================================================
class IAuthorizationRequirement:
    pass


@dataclass
class MinimumClearanceRequirement(IAuthorizationRequirement):
    required_level: int


@dataclass
class DepartmentRequirement(IAuthorizationRequirement):
    allowed_departments: List[str]


class AuthorizationContext:
    def __init__(self, user: ClaimsPrincipal, requirements: List[IAuthorizationRequirement]):
        self.user = user
        self.requirements = requirements
        self._succeeded: List[IAuthorizationRequirement] = []

    def succeed(self, requirement: IAuthorizationRequirement):
        self._succeeded.append(requirement)

    @property
    def has_succeeded(self) -> bool:
        return len(self._succeeded) >= len(self.requirements)


class AuthorizationHandler:
    @classmethod
    def evaluate(cls, context: AuthorizationContext) -> None:
        for req in context.requirements:
            if isinstance(req, MinimumClearanceRequirement):
                claim = context.user.find_first("clearance_level")
                if claim and int(claim.value) >= req.required_level:
                    context.succeed(req)
            elif isinstance(req, DepartmentRequirement):
                claim = context.user.find_first("department")
                if claim and claim.value in req.allowed_departments:
                    context.succeed(req)


@dataclass
class AuthorizationPolicy:
    name: str
    requirements: List[IAuthorizationRequirement]
    allowed_roles: List[str] = field(default_factory=list)

    def evaluate(self, user: ClaimsPrincipal) -> bool:
        if not user.is_authenticated:
            return False

        # Role checks
        if self.allowed_roles:
            if not any(user.is_in_role(r) for r in self.allowed_roles):
                return False

        # Requirements checks
        if self.requirements:
            ctx = AuthorizationContext(user, self.requirements)
            AuthorizationHandler.evaluate(ctx)
            return ctx.has_succeeded

        return True


# ==============================================================================
# 5. ASP.NET Core Middleware Pipeline Simulation
# ==============================================================================
@dataclass
class HttpRequest:
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HttpResponse:
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""


class HttpContext:
    def __init__(self, request: HttpRequest):
        self.request = request
        self.response = HttpResponse()
        self.user = ClaimsPrincipal()  # Defaults to anonymous (unauthenticated)
        self.items: Dict[str, Any] = {}


class Endpoint:
    def __init__(self, path: str, handler: Callable[[HttpContext], None], policy: Optional[AuthorizationPolicy] = None, allow_anonymous: bool = False):
        self.path = path
        self.handler = handler
        self.policy = policy
        self.allow_anonymous = allow_anonymous


class AspNetSecurityPipeline:
    def __init__(self):
        self.endpoints: Dict[str, Endpoint] = {}
        self.policies: Dict[str, AuthorizationPolicy] = {}

    def add_policy(self, policy: AuthorizationPolicy):
        self.policies[policy.name] = policy

    def map_endpoint(self, path: str, handler: Callable[[HttpContext], None], policy: Optional[AuthorizationPolicy] = None, allow_anonymous: bool = False):
        self.endpoints[path] = Endpoint(path, handler, policy, allow_anonymous)

    def use_authentication(self, ctx: HttpContext) -> None:
        """Authentication Middleware: inspects Authorization header, populates ctx.user."""
        auth_header = ctx.request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            valid, principal, msg = JwtService.validate_and_parse(token)
            if valid and principal:
                ctx.user = principal
                ctx.items["auth_success"] = True
            else:
                ctx.items["auth_error"] = msg
        else:
            # Anonymous context
            ctx.user = ClaimsPrincipal()

    def use_authorization(self, ctx: HttpContext, endpoint: Endpoint) -> bool:
        """Authorization Middleware: checks policies against ctx.user."""
        if endpoint.allow_anonymous:
            return True

        if not ctx.user.is_authenticated:
            ctx.response.status_code = 401
            ctx.response.body = json.dumps({"error": "Unauthorized", "message": "Authentication required"})
            return False

        if endpoint.policy:
            if not endpoint.policy.evaluate(ctx.user):
                ctx.response.status_code = 403
                ctx.response.body = json.dumps({"error": "Forbidden", "policy": endpoint.policy.name, "message": "Policy requirement unsatisfied"})
                return False

        return True

    def execute_request(self, request: HttpRequest) -> HttpResponse:
        ctx = HttpContext(request)
        endpoint = self.endpoints.get(request.path)

        if not endpoint:
            ctx.response.status_code = 404
            ctx.response.body = json.dumps({"error": "NotFound", "path": request.path})
            return ctx.response

        # 1. Pipeline step: Authentication
        self.use_authentication(ctx)

        # 2. Pipeline step: Authorization
        if not self.use_authorization(ctx, endpoint):
            return ctx.response

        # 3. Pipeline step: Endpoint Execution
        endpoint.handler(ctx)
        return ctx.response


# ==============================================================================
# 6. Database Mock & Application Setup
# ==============================================================================
USER_DATABASE = {
    "alice_dev": {
        "password_hash": PasswordHasher.hash_password("DevPass2026!"),
        "roles": ["Developer"],
        "department": "Engineering",
        "clearance": 2,
    },
    "bob_lead": {
        "password_hash": PasswordHasher.hash_password("LeadPass2026!"),
        "roles": ["Developer", "TeamLead"],
        "department": "Engineering",
        "clearance": 4,
    },
    "eve_hacker": {
        "password_hash": PasswordHasher.hash_password("Guess123"),
        "roles": ["Guest"],
        "department": "External",
        "clearance": 1,
    },
}


def build_application() -> AspNetSecurityPipeline:
    app = AspNetSecurityPipeline()

    # Define Policies
    policy_dev = AuthorizationPolicy(name="RequireDeveloperRole", requirements=[], allowed_roles=["Developer"])
    policy_eng_high_clearance = AuthorizationPolicy(
        name="HighClearanceEngineering",
        requirements=[MinimumClearanceRequirement(required_level=3), DepartmentRequirement(allowed_departments=["Engineering", "DevOps"])],
        allowed_roles=["TeamLead", "Admin"],
    )

    app.add_policy(policy_dev)
    app.add_policy(policy_eng_high_clearance)

    # Map Endpoints
    def public_info_handler(ctx: HttpContext):
        ctx.response.status_code = 200
        ctx.response.body = json.dumps({"status": "Healthy", "system": "ASP.NET Core 9.0 LTS Mock", "timestamp": time.ctime()})

    def dev_dashboard_handler(ctx: HttpContext):
        user_name = ctx.user.find_first("sub").value if ctx.user.find_first("sub") else "Unknown"
        ctx.response.status_code = 200
        ctx.response.body = json.dumps({"message": f"Welcome to Dev Dashboard, {user_name}!", "repo": "git://internal.org/core-api"})

    def nuclear_deploy_handler(ctx: HttpContext):
        user_name = ctx.user.find_first("sub").value
        clearance = ctx.user.find_first("clearance_level").value
        ctx.response.status_code = 200
        ctx.response.body = json.dumps({
            "action": "PRODUCTION_DEPLOYMENT_TRIGGERED",
            "authorized_by": user_name,
            "verified_clearance": clearance,
            "pipeline_status": "PROCEEDING_TO_KUBERNETES",
        })

    app.map_endpoint("/api/public/info", public_info_handler, allow_anonymous=True)
    app.map_endpoint("/api/dev/dashboard", dev_dashboard_handler, policy=policy_dev)
    app.map_endpoint("/api/ops/deploy-prod", nuclear_deploy_handler, policy=policy_eng_high_clearance)

    return app


# ==============================================================================
# 7. Interactive Technical Demonstrator
# ==============================================================================
def run_simulation():
    app = build_application()
    active_tokens: Dict[str, str] = {}

    header("ASP.NET Core Identity & Security Pipeline Simulator")
    print(f"{Colors.WHITE}Demonstrating: Authentication -> ClaimsPrincipal -> Claims-based & Policy Authorization{Colors.RESET}")

    # Generate tokens for preconfigured users
    subheader("Step 1: Generating Valid & Simulated JWT Tokens")
    for username, data in USER_DATABASE.items():
        token = JwtService.generate_token(
            username=username,
            roles=data["roles"],
            department=data["department"],
            clearance=data["clearance"],
            exp_seconds=300,
        )
        active_tokens[username] = token
        print(f"{Colors.BOLD}{username}:{Colors.RESET}")
        info("Roles", data["roles"])
        info("Department", data["department"])
        info("Clearance", data["clearance"])
        print(f"  {Colors.DIM}JWT: {token[:45]}...{Colors.RESET}")

    # Create Tampered Token
    tampered_parts = active_tokens["eve_hacker"].split(".")
    tampered_token = f"{tampered_parts[0]}.{tampered_parts[1]}.BADSIGNATUREABCXYZ"

    # Test Scenarios
    scenarios = [
        {
            "desc": "Request Anonymous Endpoint (/api/public/info)",
            "path": "/api/public/info",
            "headers": {},
        },
        {
            "desc": "Request Protected Dev Dashboard with NO Token",
            "path": "/api/dev/dashboard",
            "headers": {},
        },
        {
            "desc": "Request Dev Dashboard with Tampered Token (Eve)",
            "path": "/api/dev/dashboard",
            "headers": {"Authorization": f"Bearer {tampered_token}"},
        },
        {
            "desc": "Request Dev Dashboard with Valid Alice Token (Role=Developer)",
            "path": "/api/dev/dashboard",
            "headers": {"Authorization": f"Bearer {active_tokens['alice_dev']}"},
        },
        {
            "desc": "Request High Clearance Ops Deploy with Alice Token (Clearance=2 < 3)",
            "path": "/api/ops/deploy-prod",
            "headers": {"Authorization": f"Bearer {active_tokens['alice_dev']}"},
        },
        {
            "desc": "Request High Clearance Ops Deploy with Bob Token (Clearance=4 >= 3, Role=TeamLead)",
            "path": "/api/ops/deploy-prod",
            "headers": {"Authorization": f"Bearer {active_tokens['bob_lead']}"},
        },
    ]

    subheader("Step 2: Executing Security Pipeline Scenarios")
    for idx, scn in enumerate(scenarios, 1):
        print(f"\n{Colors.BOLD}[Scenario #{idx}] {scn['desc']}{Colors.RESET}")
        info("Path", scn["path"])
        req = HttpRequest(path=scn["path"], headers=scn["headers"])
        res = app.execute_request(req)

        if res.status_code == 200:
            success(f"Status: {res.status_code} OK")
        elif res.status_code == 401:
            warn(f"Status: {res.status_code} Unauthorized (Authentication Failed)")
        elif res.status_code == 403:
            error(f"Status: {res.status_code} Forbidden (Authorization Policy Failed)")
        else:
            error(f"Status: {res.status_code}")

        print(f"  {Colors.WHITE}Response Payload:{Colors.RESET} {res.body}")

    subheader("Step 3: Verification of Password Hashing (PBKDF2)")
    test_pwd = "MySecretPassphrase2026!"
    hashed = PasswordHasher.hash_password(test_pwd)
    info("Plain Password", test_pwd)
    info("PBKDF2-SHA256 Hash", hashed)
    verify_ok = PasswordHasher.verify_password(hashed, test_pwd)
    verify_bad = PasswordHasher.verify_password(hashed, "WrongPass123")
    if verify_ok and not verify_bad:
        success("PBKDF2 Identity PasswordHasher cryptographic verification passed!")
    else:
        error("Password hasher verification failed!")

    header("ASP.NET Core Security Pipeline Lab Completed Successfully")


if __name__ == "__main__":
    run_simulation()
