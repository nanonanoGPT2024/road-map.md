#!/usr/bin/env python3
"""
Cloudflare Zero Trust Network Access (ZTNA) & Cloudflare Tunnel Simulation Lab
Module: M01 - Core Foundations & Hands-On Architecture
BAB-08: Zero Trust Network Access (ZTNA) & Tunnels

Features Simulated:
1. Origin Service (Private Network / Localhost with no inbound public ports)
2. Cloudflare Tunnel (cloudflared daemon establishing outbound-only QUIC/HTTP2 tunnels)
3. Cloudflare Access Policy Engine (Identity, Context, Device Posture, JWT Validation)
4. Interactive scenario evaluation & end-to-end request tracing
"""

import sys
import time
import json
import uuid
import hmac
import hashlib
import base64
from typing import Dict, Any, List, Tuple

# ANSI Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
BG_BLUE = "\033[44m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================{RESET}
{CYAN}{BOLD}  CLOUDFLARE ZERO TRUST NETWORK ACCESS (ZTNA) & TUNNEL LAB (M01)       {RESET}
{CYAN}{BOLD}  Architecture: Private Origin <-> cloudflared <-> Edge POP <-> Access  {RESET}
{CYAN}{BOLD}========================================================================{RESET}
"""
    print(banner)


class DevicePosture:
    def __init__(self, warp_client: bool, os_updated: bool, disk_encrypted: bool, corporate_cert: bool):
        self.warp_client = warp_client
        self.os_updated = os_updated
        self.disk_encrypted = disk_encrypted
        self.corporate_cert = corporate_cert

    def to_dict(self) -> Dict[str, bool]:
        return {
            "warp_installed": self.warp_client,
            "os_up_to_date": self.os_updated,
            "disk_encrypted": self.disk_encrypted,
            "corporate_cert_present": self.corporate_cert,
        }


class IdentitySession:
    def __init__(self, email: str, idp: str, mfa_verified: bool, country: str, posture: DevicePosture):
        self.session_id = str(uuid.uuid4())
        self.email = email
        self.idp = idp
        self.mfa_verified = mfa_verified
        self.country = country
        self.posture = posture


class CloudflareTunnel:
    """Simulates Cloudflare Tunnel (cloudflared) daemon architecture"""
    def __init__(self, tunnel_name: str, origin_url: str):
        self.tunnel_id = str(uuid.uuid4())
        self.tunnel_name = tunnel_name
        self.origin_url = origin_url
        self.edge_connections: List[str] = []
        self.inbound_ports_open = False  # Zero Trust fundamental: ZERO inbound open ports

    def establish_connections(self):
        print(f"\n{YELLOW}[cloudflared]{RESET} Initializing tunnel daemon: {BOLD}{self.tunnel_name}{RESET}")
        print(f"{YELLOW}[cloudflared]{RESET} Tunnel UUID: {CYAN}{self.tunnel_id}{RESET}")
        print(f"{YELLOW}[cloudflared]{RESET} Target Local Origin: {BOLD}{self.origin_url}{RESET}")
        time.sleep(0.3)

        pops = ["SIN01 (Singapore)", "CGK02 (Jakarta)", "HKG03 (Hong Kong)", "NRT01 (Tokyo)"]
        for pop in pops:
            conn_id = f"conn-{uuid.uuid4().hex[:6]}"
            self.edge_connections.append(f"{pop} [{conn_id}]")
            print(f"{GREEN}  -> [QUIC Outbound]{RESET} Connected to Edge POP: {BOLD}{pop}{RESET}")
            time.sleep(0.15)

        print(f"{GREEN}[cloudflared]{RESET} Tunnel status: {BOLD}HEALTHY{RESET} (4 active multiplexed connections)")
        print(f"{MAGENTA}[Security Audit]{RESET} Origin Firewall Status: Inbound Ports = {RED}CLOSED{RESET} | Outbound TLS/QUIC = {GREEN}ESTABLISHED{RESET}")

    def forward_to_origin(self, path: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Origin service processes request received through tunnel only"""
        jwt_claim = headers.get("Cf-Access-Jwt-Assertion", "NONE")
        return {
            "origin_status": 200,
            "handled_by": self.origin_url,
            "path": path,
            "jwt_present": jwt_claim != "NONE",
            "body": f"HTTP 200 OK: Sensitive Internal Application Served Safely via {self.origin_url}{path}"
        }


class ZeroTrustAccessEngine:
    """Simulates Cloudflare Access Policy Evaluation Engine"""
    def __init__(self, allowed_domain: str, required_idp: str, secret_key: str):
        self.allowed_domain = allowed_domain
        self.required_idp = required_idp
        self.secret_key = secret_key

    def create_jwt(self, session: IdentitySession) -> str:
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": session.email,
            "iss": "https://company.cloudflareaccess.com",
            "idp": session.idp,
            "session_id": session.session_id,
            "country": session.country,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600
        }).encode()).decode().rstrip("=")
        
        signature_raw = hmac.new(self.secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        signature = base64.urlsafe_b64encode(signature_raw).decode().rstrip("=")
        return f"{header}.{payload}.{signature}"

    def evaluate_request(self, session: IdentitySession, tunnel: CloudflareTunnel, path: str) -> Tuple[bool, str, Dict[str, Any]]:
        print(f"\n{CYAN}{BOLD}--- [Cloudflare Access Decision Engine] ---{RESET}")
        print(f"{DIM}Requestor:{RESET} {session.email} via {session.idp} | Origin: {session.country}")
        time.sleep(0.2)

        # Check 1: Identity / Email Domain Check
        if not session.email.endswith(self.allowed_domain):
            reason = f"Identity Denied: Email domain '{session.email.split('@')[-1]}' does not match '{self.allowed_domain}'"
            print(f" {RED}[FAIL]{RESET} {reason}")
            return False, reason, {"http_code": 403}
        print(f" {GREEN}[PASS]{RESET} Identity Policy: User belongs to {self.allowed_domain}")

        # Check 2: MFA Requirement
        if not session.mfa_verified:
            reason = "Security Rule Violation: MFA (Multi-Factor Authentication) required but not validated."
            print(f" {RED}[FAIL]{RESET} {reason}")
            return False, reason, {"http_code": 401}
        print(f" {GREEN}[PASS]{RESET} Context Policy: MFA verification active")

        # Check 3: Device Posture Checks (WARP + Corporate Cert + Disk Encryption)
        posture = session.posture
        if not posture.warp_client:
            reason = "Device Posture Violation: Cloudflare WARP client is inactive or not installed."
            print(f" {RED}[FAIL]{RESET} {reason}")
            return False, reason, {"http_code": 403}
        print(f" {GREEN}[PASS]{RESET} Device Posture: Cloudflare WARP Client Gateway connected")

        if not posture.corporate_cert:
            reason = "Device Posture Violation: Corporate mTLS Root CA certificate missing on client."
            print(f" {RED}[FAIL]{RESET} {reason}")
            return False, reason, {"http_code": 403}
        print(f" {GREEN}[PASS]{RESET} Device Posture: Corporate Trust Certificate Verified")

        if not posture.disk_encrypted:
            reason = "Device Posture Violation: Host disk encryption (FileVault / BitLocker) is disabled."
            print(f" {RED}[FAIL]{RESET} {reason}")
            return False, reason, {"http_code": 403}
        print(f" {GREEN}[PASS]{RESET} Device Posture: Full Disk Encryption active")

        # Check 4: Country / Geo-fencing (example: embargoed IP simulation)
        if session.country in ["SUSPECT_REGION", "UNKNOWN"]:
            reason = f"Context Rule Violation: Access from region {session.country} is blocked by perimeter policy."
            print(f" {RED}[FAIL]{RESET} {reason}")
            return False, reason, {"http_code": 403}
        print(f" {GREEN}[PASS]{RESET} Context Policy: Geo-fence checks passed ({session.country})")

        # Grant access & issue Cloudflare Access Assertion JWT
        jwt_token = self.create_jwt(session)
        print(f"\n{GREEN}{BOLD}[ACCESS GRANTED]{RESET} All Zero Trust checks satisfied. Generating Cf-Access-Jwt-Assertion...")
        print(f"{DIM}JWT Token Header Preview:{RESET} {CYAN}{jwt_token[:35]}...{RESET}")

        headers = {
            "Host": "internal-prod-db.corp.internal",
            "Cf-Access-Authenticated-User-Email": session.email,
            "Cf-Access-Jwt-Assertion": jwt_token
        }

        # Tunnel handles forwarding to private loopback
        print(f"{CYAN}[Edge -> Tunnel]{RESET} Routing request through active QUIC multiplexed tunnel...")
        response = tunnel.forward_to_origin(path, headers)
        return True, "Authorized and Relayed to Origin", response


def run_scenario(name: str, session: IdentitySession, engine: ZeroTrustAccessEngine, tunnel: CloudflareTunnel, path: str):
    print(f"\n{BOLD}{BG_BLUE} SCENARIO: {name} {RESET}")
    allowed, message, details = engine.evaluate_request(session, tunnel, path)
    if allowed:
        print(f"{GREEN}{BOLD}Result:{RESET} {GREEN}HTTP 200 OK - Secure Tunnel Access Success{RESET}")
        print(f"{DIM}Origin Body:{RESET} {details.get('body')}")
    else:
        code = details.get("http_code", 403)
        print(f"{RED}{BOLD}Result:{RESET} {RED}HTTP {code} BLOCKED - Zero Trust Policy Enforced{RESET}")
        print(f"{DIM}Reason:{RESET} {message}")


def interactive_menu(engine: ZeroTrustAccessEngine, tunnel: CloudflareTunnel):
    while True:
        print(f"\n{BOLD}{CYAN}--- CLOUDFLARE ZTNA SIMULATOR MENU ---{RESET}")
        print("1. [Scenario A] Authorized Staff (Corporate Laptop + WARP + MFA)")
        print("2. [Scenario B] External Attacker (Unauthorized Domain / Phishing)")
        print("3. [Scenario C] BYOD Employee without WARP Client / Device Posture")
        print("4. [Scenario D] Compromised Laptop without Disk Encryption")
        print("5. [Custom Test] Build and Evaluate Your Own Zero Trust Request")
        print("6. Exit")
        
        choice = input(f"{YELLOW}Select option [1-6]: {RESET}").strip()
        if choice == "1":
            posture = DevicePosture(warp_client=True, os_updated=True, disk_encrypted=True, corporate_cert=True)
            session = IdentitySession("alice@enterprise.corp", "Okta-SAML", True, "ID (Indonesia)", posture)
            run_scenario("Authorized Staff accessing internal Kubernetes dashboard", session, engine, tunnel, "/k8s/dashboard")
        elif choice == "2":
            posture = DevicePosture(warp_client=False, os_updated=False, disk_encrypted=False, corporate_cert=False)
            session = IdentitySession("mallory@evil-external.net", "Google-OAuth", False, "UNKNOWN", posture)
            run_scenario("External actor attempting direct access to private endpoint", session, engine, tunnel, "/admin/db")
        elif choice == "3":
            posture = DevicePosture(warp_client=False, os_updated=True, disk_encrypted=True, corporate_cert=False)
            session = IdentitySession("bob@enterprise.corp", "Okta-SAML", True, "SG (Singapore)", posture)
            run_scenario("Employee using personal phone without Cloudflare WARP/Cert", session, engine, tunnel, "/api/v1/customer-records")
        elif choice == "4":
            posture = DevicePosture(warp_client=True, os_updated=True, disk_encrypted=False, corporate_cert=True)
            session = IdentitySession("charlie@enterprise.corp", "Okta-SAML", True, "JP (Japan)", posture)
            run_scenario("Employee on laptop with disabled full-disk encryption", session, engine, tunnel, "/finance/ledger")
        elif choice == "5":
            print(f"\n{CYAN}--- Configure Custom Request Context ---{RESET}")
            email = input("User Email (e.g., dev@enterprise.corp): ").strip() or "dev@enterprise.corp"
            mfa = input("MFA Verified? (y/n) [y]: ").strip().lower() != "n"
            warp = input("WARP Client Running? (y/n) [y]: ").strip().lower() != "n"
            cert = input("Corporate Device Cert Installed? (y/n) [y]: ").strip().lower() != "n"
            enc = input("Disk Encryption Active? (y/n) [y]: ").strip().lower() != "n"
            country = input("Country Code (e.g. ID, SG, US) [ID]: ").strip() or "ID"
            path = input("Target Resource Path [/api/v2/metrics]: ").strip() or "/api/v2/metrics"

            custom_posture = DevicePosture(warp_client=warp, os_updated=True, disk_encrypted=enc, corporate_cert=cert)
            custom_session = IdentitySession(email, "Company-SSO", mfa, country, custom_posture)
            run_scenario("Custom User Defined Request", custom_session, engine, tunnel, path)
        elif choice == "6":
            print(f"{GREEN}Exiting Cloudflare ZTNA simulation. Keep your tunnels private!{RESET}")
            break
        else:
            print(f"{RED}Invalid choice, please select 1-6.{RESET}")


def main():
    print_banner()

    # 1. Initialize Private Origin & Cloudflare Tunnel
    tunnel = CloudflareTunnel(
        tunnel_name="prod-corp-private-tunnel-01",
        origin_url="http://127.0.0.1:8080"
    )
    tunnel.establish_connections()

    # 2. Initialize Access Policy Engine
    engine = ZeroTrustAccessEngine(
        allowed_domain="enterprise.corp",
        required_idp="Okta-SAML",
        secret_key="cloudflare_access_secret_super_key_lab"
    )

    # 3. Check execution arguments (headless test or interactive)
    if len(sys.argv) > 1 and sys.argv[1] == "--auto-test":
        print(f"\n{YELLOW}[Automated Lab Verification Mode Active]{RESET}")
        p1 = DevicePosture(warp_client=True, os_updated=True, disk_encrypted=True, corporate_cert=True)
        s1 = IdentitySession("admin@enterprise.corp", "Okta-SAML", True, "ID", p1)
        ok1, _, _ = engine.evaluate_request(s1, tunnel, "/internal")

        p2 = DevicePosture(warp_client=False, os_updated=True, disk_encrypted=True, corporate_cert=False)
        s2 = IdentitySession("intruder@gmail.com", "Google", False, "US", p2)
        ok2, _, _ = engine.evaluate_request(s2, tunnel, "/internal")

        assert ok1 is True, "Scenario 1 should succeed"
        assert ok2 is False, "Scenario 2 should be rejected"
        print(f"\n{GREEN}{BOLD}[VERIFIED]{RESET} All automated assertions passed successfully.")
        return

    # Interactive mode
    interactive_menu(engine, tunnel)


if __name__ == "__main__":
    main()
