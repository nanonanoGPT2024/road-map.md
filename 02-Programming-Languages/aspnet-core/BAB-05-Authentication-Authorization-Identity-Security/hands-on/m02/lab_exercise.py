#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core Deep Dive
Bab 05: Authentication, Authorization, & Identity Security Pipeline Simulation

Memodelkan arsitektur keamanan ASP.NET Core:
1. ClaimsIdentity & ClaimsPrincipal Model (WIF / .NET Identity Standard)
2. PBKDF2 Password Hashing (mirip Microsoft.AspNetCore.Identity.PasswordHasher<T>)
3. Token Validation & JWT Handler (HMAC-SHA256 signing, validation, claim extraction)
4. IAuthorizationRequirement & AuthorizationHandler<T> Engine
5. ASP.NET Core HTTP Middleware Pipeline (UseAuthentication -> UseAuthorization)
"""

import hmac
import hashlib
import base64
import json
import time
import uuid
from typing import List, Dict, Any, Optional

# ==============================================================================
# ANSI Color Codes untuk visualisasi terminal terstruktur
# ==============================================================================
class TermColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"

def print_header(title: str):
    line = "=" * 80
    print(f"\n{TermColor.CYAN}{TermColor.BOLD}{line}")
    print(f" [*] ASP.NET CORE IDENTITY & SECURITY: {title}")
    print(f"{line}{TermColor.RESET}\n")

# ==============================================================================
# Bagian 1: Model Identitas & Klaim (.NET ClaimsPrincipal / ClaimsIdentity)
# ==============================================================================
class ClaimTypes:
    NAME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
    NAME_IDENTIFIER = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"
    ROLE = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
    EMAIL = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
    CLEARANCE_LEVEL = "urn:corp:clearance"
    DEPARTMENT = "urn:corp:department"

class Claim:
    def __init__(self, claim_type: str, value: str, issuer: str = "LOCAL AUTHORITY"):
        self.type = claim_type
        self.value = value
        self.issuer = issuer

    def __repr__(self):
        short_type = self.type.split("/")[-1].split(":")[-1]
        return f"Claim({short_type}={self.value})"

class ClaimsIdentity:
    def __init__(self, claims: Optional[List[Claim]] = None, authentication_type: Optional[str] = None):
        self.claims: List[Claim] = claims or []
        self.authentication_type = authentication_type

    @property
    def is_authenticated(self) -> bool:
        return self.authentication_type is not None

    def find_all(self, claim_type: str) -> List[Claim]:
        return [c for c in self.claims if c.type == claim_type]

    def find_first(self, claim_type: str) -> Optional[Claim]:
        for c in self.claims:
            if c.type == claim_type:
                return c
        return None

class ClaimsPrincipal:
    def __init__(self, identities: Optional[List[ClaimsIdentity]] = None):
        self.identities: List[ClaimsIdentity] = identities or []

    @property
    def identity(self) -> Optional[ClaimsIdentity]:
        return self.identities[0] if self.identities else None

    def is_in_role(self, role: str) -> bool:
        for ident in self.identities:
            for claim in ident.find_all(ClaimTypes.ROLE):
                if claim.value.lower() == role.lower():
                    return True
        return False

    def find_first_value(self, claim_type: str) -> Optional[str]:
        for ident in self.identities:
            c = ident.find_first(claim_type)
            if c:
                return c.value
        return None

# ==============================================================================
# Bagian 2: PasswordHasher & JWT Engine (Security Cryptography)
# ==============================================================================
class AspNetPasswordHasher:
    """Simulasi Microsoft.AspNetCore.Identity.PasswordHasher Version 3 (PBKDF2-HMAC-SHA256)."""
    @staticmethod
    def hash_password(password: str) -> str:
        salt = uuid.uuid4().bytes[:16]
        iterations = 10000
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
        payload = b"\x01" + salt + key  # Format: header (0x01) + salt + subkey
        return base64.b64encode(payload).decode("ascii")

    @staticmethod
    def verify_hashed_password(hashed_password: str, provided_password: str) -> bool:
        payload = base64.b64decode(hashed_password)
        if payload[0] != 1:
            return False
        salt = payload[1:17]
        expected_subkey = payload[17:49]
        actual_subkey = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 10000, dklen=32)
        return hmac.compare_digest(actual_subkey, expected_subkey)

class JwtTokenService:
    """Simulasi JwtSecurityTokenHandler ASP.NET Core."""
    def __init__(self, secret_key: str, issuer: str, audience: str):
        self.secret_key = secret_key.encode("utf-8")
        self.issuer = issuer
        self.audience = audience

    def _b64_url_encode(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _b64_url_decode(self, val: str) -> bytes:
        padding = "=" * (-len(val) % 4)
        return base64.urlsafe_b64decode((val + padding).encode("ascii"))

    def create_token(self, claims: List[Claim], expires_in_sec: int = 300) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "aud": self.audience,
            "nbf": now,
            "iat": now,
            "exp": now + expires_in_sec
        }
        for c in claims:
            # Petakan type umum ke payload keys jika berulang
            if c.type in payload:
                if isinstance(payload[c.type], list):
                    payload[c.type].append(c.value)
                else:
                    payload[c.type] = [payload[c.type], c.value]
            else:
                payload[c.type] = c.value

        encoded_header = self._b64_url_encode(json.dumps(header).encode("utf-8"))
        encoded_payload = self._b64_url_encode(json.dumps(payload).encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        encoded_signature = self._b64_url_encode(signature)

        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def validate_token(self, token: str) -> ClaimsPrincipal:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token.")

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        provided_sig = self._b64_url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            raise ValueError("SecurityTokenInvalidSignatureException: Signature mismatch.")

        payload_bytes = self._b64_url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Validasi Expire, Issuer, & Audience
        now = int(time.time())
        if payload.get("exp", 0) < now:
            raise ValueError("SecurityTokenExpiredException: Token has expired.")
        if payload.get("iss") != self.issuer:
            raise ValueError("SecurityTokenInvalidIssuerException: Issuer mismatch.")
        if payload.get("aud") != self.audience:
            raise ValueError("SecurityTokenInvalidAudienceException: Audience mismatch.")

        extracted_claims: List[Claim] = []
        for k, v in payload.items():
            if k in ["iss", "aud", "exp", "nbf", "iat"]:
                continue
            if isinstance(v, list):
                for sub_val in v:
                    extracted_claims.append(Claim(k, str(sub_val)))
            else:
                extracted_claims.append(Claim(k, str(v)))

        identity = ClaimsIdentity(claims=extracted_claims, authentication_type="Bearer")
        return ClaimsPrincipal([identity])

# ==============================================================================
# Bagian 3: Authorization Framework (Policy, Requirements, & Handlers)
# ==============================================================================
class AuthorizationHandlerContext:
    def __init__(self, requirements: List[Any], user: ClaimsPrincipal):
        self.requirements = requirements
        self.user = user
        self._succeeded: set = set()
        self.has_failed: bool = False

    def succeed(self, requirement: Any):
        self._succeeded.add(requirement)

    def fail(self):
        self.has_failed = True

    @property
    def has_succeeded(self) -> bool:
        if self.has_failed:
            return False
        return all(r in self._succeeded for r in self.requirements)

class IAuthorizationRequirement:
    pass

class RolesAuthorizationRequirement(IAuthorizationRequirement):
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = [r.lower() for r in allowed_roles]

class ClearanceRequirement(IAuthorizationRequirement):
    def __init__(self, minimum_clearance: int):
        self.minimum_clearance = minimum_clearance

class DepartmentRequirement(IAuthorizationRequirement):
    def __init__(self, allowed_departments: List[str]):
        self.allowed_departments = allowed_departments

class RolesAuthorizationHandler:
    def handle(self, context: AuthorizationHandlerContext, requirement: RolesAuthorizationRequirement):
        for role in requirement.allowed_roles:
            if context.user.is_in_role(role):
                context.succeed(requirement)
                return

class ClearanceAuthorizationHandler:
    def handle(self, context: AuthorizationHandlerContext, requirement: ClearanceRequirement):
        val = context.user.find_first_value(ClaimTypes.CLEARANCE_LEVEL)
        if val and val.isdigit():
            if int(val) >= requirement.minimum_clearance:
                context.succeed(requirement)

class DepartmentAuthorizationHandler:
    def handle(self, context: AuthorizationHandlerContext, requirement: DepartmentRequirement):
        user_dept = context.user.find_first_value(ClaimTypes.DEPARTMENT)
        if user_dept in requirement.allowed_departments:
            context.succeed(requirement)

class AuthorizationPolicy:
    def __init__(self, requirements: List[IAuthorizationRequirement]):
        self.requirements = requirements

class DefaultAuthorizationService:
    def __init__(self):
        self.role_handler = RolesAuthorizationHandler()
        self.clearance_handler = ClearanceAuthorizationHandler()
        self.dept_handler = DepartmentAuthorizationHandler()

    def authorize(self, user: ClaimsPrincipal, policy: AuthorizationPolicy) -> bool:
        context = AuthorizationHandlerContext(policy.requirements, user)
        for req in policy.requirements:
            if isinstance(req, RolesAuthorizationRequirement):
                self.role_handler.handle(context, req)
            elif isinstance(req, ClearanceRequirement):
                self.clearance_handler.handle(context, req)
            elif isinstance(req, DepartmentRequirement):
                self.dept_handler.handle(context, req)
        return context.has_succeeded

# ==============================================================================
# Bagian 4: ASP.NET Core Mock HTTP Pipeline Engine
# ==============================================================================
class HttpContext:
    def __init__(self, path: str, method: str = "GET", headers: Optional[Dict[str, str]] = None):
        self.path = path
        self.method = method
        self.headers = headers or {}
        self.user: ClaimsPrincipal = ClaimsPrincipal([ClaimsIdentity()]) # Default Anonymous
        self.response_status: int = 200
        self.response_body: str = ""

class MockEndpoint:
    def __init__(self, route: str, policy_name: Optional[str] = None):
        self.route = route
        self.policy_name = policy_name

class AspNetSecurityPipeline:
    def __init__(self, jwt_service: JwtTokenService):
        self.jwt_service = jwt_service
        self.auth_service = DefaultAuthorizationService()
        self.policies: Dict[str, AuthorizationPolicy] = {}
        self.endpoints: Dict[str, MockEndpoint] = {}

    def register_policy(self, name: str, policy: AuthorizationPolicy):
        self.policies[name] = policy

    def register_endpoint(self, endpoint: MockEndpoint):
        self.endpoints[endpoint.route] = endpoint

    def execute(self, ctx: HttpContext):
        # 1. UseAuthentication() Middleware
        auth_header = ctx.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()
            try:
                principal = self.jwt_service.validate_token(raw_token)
                ctx.user = principal
            except Exception as ex:
                ctx.response_status = 401
                ctx.response_body = f"Authentication Failure: {str(ex)}"
                return

        # Cari endpoint
        endpoint = self.endpoints.get(ctx.path)
        if not endpoint:
            ctx.response_status = 404
            ctx.response_body = "404 Not Found"
            return

        # 2. UseAuthorization() Middleware
        if endpoint.policy_name:
            if not ctx.user.identity or not ctx.user.identity.is_authenticated:
                ctx.response_status = 401
                ctx.response_body = "401 Unauthorized: Endpoint requires authenticated identity."
                return

            policy = self.policies.get(endpoint.policy_name)
            if not policy:
                ctx.response_status = 500
                ctx.response_body = f"Configuration Error: Policy '{endpoint.policy_name}' not defined."
                return

            is_authorized = self.auth_service.authorize(ctx.user, policy)
            if not is_authorized:
                ctx.response_status = 403
                ctx.response_body = "403 Forbidden: Identity failed policy requirements evaluation."
                return

        # Endpoint execution
        ctx.response_status = 200
        username = ctx.user.find_first_value(ClaimTypes.NAME) or "Anonymous"
        ctx.response_body = f"200 OK: Payload accessed successfully by [{username}]."

# ==============================================================================
# Bagian 5: Lab Execution Runner
# ==============================================================================
def main():
    print_header("Claims, JWT Security Token, & Policy-Based Authorization Pipeline")

    SECRET = "SuperSecretCryptographicKeyOfAtLeast32BytesLength!"
    ISSUER = "https://identity.acme-corp.internal"
    AUDIENCE = "https://api.acme-corp.internal"

    jwt_service = JwtTokenService(SECRET, ISSUER, AUDIENCE)
    pipeline = AspNetSecurityPipeline(jwt_service)

    # Menyiapkan Policy: Level 3 SecOps atau SuperAdmin
    pipeline.register_policy(
        "TopSecretSecOps",
        AuthorizationPolicy([
            RolesAuthorizationRequirement(["SecOps", "EnterpriseAdmin"]),
            ClearanceRequirement(minimum_clearance=3),
            DepartmentRequirement(["CyberDefense", "Infrastructure"])
        ])
    )

    # Mendaftarkan Mock Endpoints
    pipeline.register_endpoint(MockEndpoint("/api/public/health", policy_name=None))
    pipeline.register_endpoint(MockEndpoint("/api/vault/classified-keys", policy_name="TopSecretSecOps"))

    # Uji Coba Hash Password Terlebih Dahulu
    print(f"{TermColor.BOLD}[1] Pengujian Identity PasswordHasher (PBKDF2-HMAC-SHA256){TermColor.RESET}")
    sample_pwd = "P@ssw0rdSecureComplex!"
    hashed = AspNetPasswordHasher.hash_password(sample_pwd)
    verified = AspNetPasswordHasher.verify_hashed_password(hashed, sample_pwd)
    wrong_verified = AspNetPasswordHasher.verify_hashed_password(hashed, "WrongPass123")
    print(f"  Plaintext Password : {sample_pwd}")
    print(f"  Storage Hash (Base64): {hashed[:35]}... (Length: {len(hashed)})")
    print(f"  Verify Valid Pass  : {TermColor.GREEN if verified else TermColor.RED}{verified}{TermColor.RESET}")
    print(f"  Verify Invalid Pass: {TermColor.GREEN if not wrong_verified else TermColor.RED}{wrong_verified}{TermColor.RESET}\n")

    # Membuat Berbagai Macam JWT Token Identitas
    print(f"{TermColor.BOLD}[2] Minting Tokens untuk Simulasi Identitas Pengguna{TermColor.RESET}")

    # User A: SecOps Engineer (Clearance 3, Dept: CyberDefense) -> Valid
    claims_a = [
        Claim(ClaimTypes.NAME, "alice_secops"),
        Claim(ClaimTypes.NAME_IDENTIFIER, "user-001"),
        Claim(ClaimTypes.ROLE, "SecOps"),
        Claim(ClaimTypes.CLEARANCE_LEVEL, "3"),
        Claim(ClaimTypes.DEPARTMENT, "CyberDefense")
    ]
    token_alice = jwt_service.create_token(claims_a)

    # User B: Junior Dev (Clearance 1, Dept: SoftwareDev) -> Invalid Role, Dept & Clearance
    claims_b = [
        Claim(ClaimTypes.NAME, "bob_junior"),
        Claim(ClaimTypes.NAME_IDENTIFIER, "user-002"),
        Claim(ClaimTypes.ROLE, "Developer"),
        Claim(ClaimTypes.CLEARANCE_LEVEL, "1"),
        Claim(ClaimTypes.DEPARTMENT, "SoftwareDev")
    ]
    token_bob = jwt_service.create_token(claims_b)

    # User C: SecOps Trainee (Role: SecOps, tapi Clearance 2 < 3) -> Forbidden
    claims_c = [
        Claim(ClaimTypes.NAME, "charlie_trainee"),
        Claim(ClaimTypes.NAME_IDENTIFIER, "user-003"),
        Claim(ClaimTypes.ROLE, "SecOps"),
        Claim(ClaimTypes.CLEARANCE_LEVEL, "2"),
        Claim(ClaimTypes.DEPARTMENT, "CyberDefense")
    ]
    token_charlie = jwt_service.create_token(claims_c)

    # User D: Expired Token
    token_expired = jwt_service.create_token(claims_a, expires_in_sec=-10)

    # User E: Tampered Signature Token
    parts = token_alice.split(".")
    tampered_sig = parts[2][:-4] + "WXYZ"
    token_tampered = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    print(f"  Token Alice   (Role: SecOps, Clearance: 3, Dept: CyberDefense) -> {token_alice[:30]}...")
    print(f"  Token Bob     (Role: Dev, Clearance: 1, Dept: SoftwareDev)   -> {token_bob[:30]}...")
    print(f"  Token Charlie (Role: SecOps, Clearance: 2, Dept: CyberDefense) -> {token_charlie[:30]}...")
    print()

    # Eksekusi Skenario Pipeline ASP.NET Core
    print(f"{TermColor.BOLD}[3] Simulasi Middleware Pipeline Request Execution{TermColor.RESET}")

    test_cases = [
        ("Skenario 1: Akses Endpoint Publik Tanpa Auth Header",
         HttpContext(path="/api/public/health")),
        
        ("Skenario 2: Akses Endpoint Terlindungi Tanpa Kredensial (Anonymous)",
         HttpContext(path="/api/vault/classified-keys")),
         
        ("Skenario 3: Token Signature Tampered / Corrupted",
         HttpContext(path="/api/vault/classified-keys", headers={"Authorization": f"Bearer {token_tampered}"})),

        ("Skenario 4: Token Kedaluwarsa (Expired Token)",
         HttpContext(path="/api/vault/classified-keys", headers={"Authorization": f"Bearer {token_expired}"})),

        ("Skenario 5: Role & Clearance Tidak Mencukupi (Bob the Dev)",
         HttpContext(path="/api/vault/classified-keys", headers={"Authorization": f"Bearer {token_bob}"})),

        ("Skenario 6: Role Cocok, tetapi Clearance Kurang (Charlie Clearance 2 vs Min 3)",
         HttpContext(path="/api/vault/classified-keys", headers={"Authorization": f"Bearer {token_charlie}"})),

        ("Skenario 7: Kredensial Memenuhi Semua Requirement Policy (Alice SecOps)",
         HttpContext(path="/api/vault/classified-keys", headers={"Authorization": f"Bearer {token_alice}"}))
    ]

    for title, ctx in test_cases:
        pipeline.execute(ctx)
        
        if ctx.response_status == 200:
            status_badge = f"{TermColor.GREEN}[200 OK]{TermColor.RESET}"
        elif ctx.response_status == 401:
            status_badge = f"{TermColor.YELLOW}[401 UNAUTHORIZED]{TermColor.RESET}"
        elif ctx.response_status == 403:
            status_badge = f"{TermColor.RED}[403 FORBIDDEN]{TermColor.RESET}"
        else:
            status_badge = f"{TermColor.MAGENTA}[{ctx.response_status}]{TermColor.RESET}"

        print(f"{TermColor.BOLD}--> {title}{TermColor.RESET}")
        print(f"    Target : {ctx.method} {ctx.path}")
        print(f"    Result : {status_badge} -> {ctx.response_body}\n")

    print(f"{TermColor.CYAN}Pipeline simulation executed cleanly without external dependencies.{TermColor.RESET}")

if __name__ == "__main__":
    main()