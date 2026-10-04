#!/usr/bin/env python3
"""
Cloudflare Zero Trust Network Access (ZTNA) & Cloudflare Tunnels
Interactive Production Architecture Simulator
BAB-08: Zero Trust Network Access (ZTNA) dan Tunnels
"""

import sys
import time
import uuid
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes for Rich Terminal Output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

@dataclass
class DeviceContext:
    device_id: str
    os_name: str
    disk_encrypted: bool
    warp_client_active: bool
    firewall_enabled: bool
    client_cert_installed: bool
    serial_number: str

@dataclass
class UserSession:
    email: str
    groups: List[str]
    idp_provider: str
    mfa_verified: bool
    country_iso: str
    client_ip: str
    service_token_id: Optional[str] = None
    service_token_secret: Optional[str] = None

@dataclass
class AccessEvaluationResult:
    allowed: bool
    status_code: int
    rule_name: str
    ray_id: str
    reasons: List[str]
    routed_target: Optional[str] = None

class DevicePostureEngine:
    """Simulates Cloudflare WARP Client & Gateway Posture Checks."""
    
    @staticmethod
    def evaluate_posture(device: DeviceContext) -> (bool, List[str]):
        findings = []
        passed = True
        
        if not device.warp_client_active:
            findings.append("FAILED: Cloudflare WARP daemon is not connected/healthy")
            passed = False
        else:
            findings.append("PASSED: WARP client authenticated with zero-trust tenant")

        if not device.disk_encrypted:
            findings.append("FAILED: FileVault/BitLocker disk encryption posture requirement failed")
            passed = False
        else:
            findings.append("PASSED: Full disk encryption verified (Hardware TPM/Secure Enclave)")

        if not device.firewall_enabled:
            findings.append("FAILED: Host OS local firewall is disabled")
            passed = False
        else:
            findings.append("PASSED: Host OS firewall active and filtering inbound connections")

        if not device.client_cert_installed:
            findings.append("WARNING: Enterprise mTLS corporate leaf certificate missing")
        else:
            findings.append("PASSED: Valid corporate mTLS certificate verified against Cloudflare CA")

        return passed, findings

class CloudflaredTunnelEdge:
    """Simulates cloudflared connector daemon terminating QUIC tunnels to CF Edge."""
    
    def __init__(self, tunnel_name: str, tunnel_id: str):
        self.tunnel_name = tunnel_name
        self.tunnel_id = tunnel_id
        self.connections = [
            {"colo": "SIN01 (Singapore)", "protocol": "QUIC/H3", "status": "REGISTERED", "rtt": "8.2ms"},
            {"colo": "CGK02 (Jakarta)",   "protocol": "QUIC/H3", "status": "REGISTERED", "rtt": "3.1ms"},
            {"colo": "KUL01 (Kuala Lumpur)", "protocol": "QUIC/H3", "status": "REGISTERED", "rtt": "12.4ms"},
            {"colo": "HKG05 (Hong Kong)", "protocol": "QUIC/H3", "status": "BACKUP",     "rtt": "32.0ms"},
        ]
        self.ingress_rules = [
            {"hostname": "k8s-api.internal.corp", "service": "https://10.240.0.10:6443", "no_tls_verify": False},
            {"hostname": "grafana.internal.corp", "service": "http://10.240.12.5:3000",  "no_tls_verify": True},
            {"hostname": "bastion-ssh.corp",      "service": "ssh://10.240.5.20:22",      "no_tls_verify": True},
            {"hostname": "*",                     "service": "http_status:404",           "no_tls_verify": True}
        ]

    def display_tunnel_status(self):
        print(f"\n{Colors.BOLD}{Colors.CYAN}--- CLOUDFLARED EDGE TUNNEL ORCHESTRATION ---{Colors.RESET}")
        print(f"Tunnel Name: {Colors.BOLD}{self.tunnel_name}{Colors.RESET} (ID: {self.tunnel_id})")
        print(f"Architecture: Outbound-only QUIC Dual-Stack Tunnels (Zero Inbound Open Ports)")
        print("\nActive Cloudflare Anycast Colo Connections:")
        for conn in self.connections:
            status_color = Colors.GREEN if conn['status'] == "REGISTERED" else Colors.YELLOW
            print(f"  [{status_color}{conn['status']}{Colors.RESET}] {conn['colo']:<25} | Proto: {conn['protocol']:<8} | Latency: {conn['rtt']}")

        print("\nIngress Route Mapping (config.yaml simulation):")
        for idx, rule in enumerate(self.ingress_rules, 1):
            print(f"  {idx}. {Colors.YELLOW}{rule['hostname']:<25}{Colors.RESET} -> {Colors.CYAN}{rule['service']}{Colors.RESET}")

    def route_request(self, requested_host: str) -> Optional[str]:
        for rule in self.ingress_rules:
            if rule['hostname'] == requested_host or rule['hostname'] == "*":
                if rule['service'].startswith("http_status:"):
                    return None
                return rule['service']
        return None

class CloudflareAccessPolicyEngine:
    """Evaluates Identity, Service Tokens, Contextual Geo/IP, and Posture."""
    
    def __init__(self, tunnel: CloudflaredTunnelEdge):
        self.tunnel = tunnel

    def evaluate_request(self, session: UserSession, device: Optional[DeviceContext], target_host: str) -> AccessEvaluationResult:
        ray_id = uuid.uuid4().hex[:16]
        reasons = []

        # 1. Service Token Bypass / Non-Identity check (for automated CI/CD or APIs)
        if session.service_token_id and session.service_token_secret:
            if session.service_token_id == "cf-svc-deployer-prod" and session.service_token_secret == "sec_tok_prod_9981a2f":
                dest = self.tunnel.route_request(target_host)
                if dest:
                    reasons.append("VALIDATED: Valid Cloudflare Service Token credentials presented.")
                    reasons.append("POLICY: Non-Identity Service Token policy matched (Allow).")
                    return AccessEvaluationResult(True, 200, "Automated-Service-Token-Rule", ray_id, reasons, dest)
                else:
                    return AccessEvaluationResult(False, 404, "Default-Ingress-Drop", ray_id, ["Target host not configured in tunnel ingress rules."])
            else:
                reasons.append("REJECTED: Invalid or expired Service Token secret headers.")
                return AccessEvaluationResult(False, 403, "Service-Token-Enforcement", ray_id, reasons)

        # 2. Geo-fencing & Threat Reputation
        sanctioned_countries = ["ID", "SG", "MY", "US", "AU"]
        if session.country_iso not in sanctioned_countries:
            reasons.append(f"DENIED: Geo-fencing block. Country '{session.country_iso}' is not permitted.")
            return AccessEvaluationResult(False, 403, "Corporate-Geo-Fence-Block", ray_id, reasons)
        else:
            reasons.append(f"PASSED: Geo location '{session.country_iso}' complies with corporate access policy.")

        # 3. Identity Provider (IdP) & MFA
        if not session.email.endswith("@enterprise.corp"):
            reasons.append(f"DENIED: Identity '{session.email}' does not belong to authorized tenant domain @enterprise.corp.")
            return AccessEvaluationResult(False, 403, "IdP-Domain-Validation", ray_id, reasons)
        
        if not session.mfa_verified:
            reasons.append("DENIED: Multi-Factor Authentication (FIDO2/WebAuthn/TOTP) claim missing.")
            return AccessEvaluationResult(False, 401, "MFA-Challenge-Required", ray_id, reasons)

        reasons.append(f"PASSED: User identity {session.email} validated via {session.idp_provider} (SAML 2.0/OIDC).")

        # 4. Device Posture Verification
        if device is None:
            reasons.append("DENIED: No device posture signals received. WARP client zero-trust posture is mandatory.")
            return AccessEvaluationResult(False, 403, "Device-Posture-Required", ray_id, reasons)

        posture_ok, posture_details = DevicePostureEngine.evaluate_posture(device)
        reasons.extend(posture_details)

        if not posture_ok:
            reasons.append("DENIED: Workstation failed one or more critical Zero Trust posture conditions.")
            return AccessEvaluationResult(False, 403, "Zero-Trust-Posture-Enforcement", ray_id, reasons)

        # 5. Role-Based Access Control (RBAC) per target host
        if target_host == "k8s-api.internal.corp":
            if "Platform-Engineers" not in session.groups and "Security-Admins" not in session.groups:
                reasons.append("DENIED: User lacks 'Platform-Engineers' group membership required for Kubernetes API access.")
                return AccessEvaluationResult(False, 403, "RBAC-K8s-Admin-Group", ray_id, reasons)

        dest = self.tunnel.route_request(target_host)
        if not dest:
            reasons.append(f"DENIED: Host '{target_host}' not found in Cloudflared private network routing tables.")
            return AccessEvaluationResult(False, 404, "Ingress-Host-Not-Found", ray_id, reasons)

        reasons.append(f"SUCCESS: Identity, MFA, RBAC, and Device Posture satisfy Zero Trust Access Policy.")
        return AccessEvaluationResult(True, 200, "Enterprise-ZTNA-Compliant-Rule", ray_id, reasons, dest)

def print_result_banner(res: AccessEvaluationResult, host: str):
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    if res.allowed:
        status_txt = f"{Colors.GREEN}{Colors.BOLD}ACCESS GRANTED (HTTP {res.status_code}){Colors.RESET}"
    else:
        status_txt = f"{Colors.RED}{Colors.BOLD}ACCESS BLOCKED (HTTP {res.status_code}){Colors.RESET}"
    
    print(f"Target Resource : {Colors.CYAN}{host}{Colors.RESET}")
    print(f"Decision Status : {status_txt}")
    print(f"Enforced Rule   : {Colors.YELLOW}{res.rule_name}{Colors.RESET}")
    print(f"Cloudflare RayID: {Colors.DIM}{res.ray_id}{Colors.RESET}")
    
    if res.routed_target:
        print(f"Routed Ingress  : {Colors.GREEN}{res.routed_target}{Colors.RESET} (via Cloudflared QUIC)")
    
    print(f"\n{Colors.UNDERLINE}Evaluation Audit Trail:{Colors.RESET}")
    for log_item in res.reasons:
        if "PASSED" in log_item or "VALIDATED" in log_item or "SUCCESS" in log_item:
            print(f"  {Colors.GREEN}✓ {log_item}{Colors.RESET}")
        elif "WARNING" in log_item:
            print(f"  {Colors.YELLOW}▲ {log_item}{Colors.RESET}")
        else:
            print(f"  {Colors.RED}✗ {log_item}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

def simulate_developer_valid(engine: CloudflareAccessPolicyEngine):
    print(f"\n{Colors.BOLD}{Colors.BLUE}[SCENARIO 1] Senior SRE accessing internal Kubernetes Control Plane API{Colors.RESET}")
    dev_device = DeviceContext(
        device_id="DEV-MAC-M3-4412",
        os_name="macOS Sonoma 14.5",
        disk_encrypted=True,
        warp_client_active=True,
        firewall_enabled=True,
        client_cert_installed=True,
        serial_number="C02G89A2MD6R"
    )
    user = UserSession(
        email="alex.pratama@enterprise.corp",
        groups=["Platform-Engineers", "DevOps-Core"],
        idp_provider="Okta SSO (SAML 2.0)",
        mfa_verified=True,
        country_iso="ID",
        client_ip="103.111.20.45"
    )
    res = engine.evaluate_request(user, dev_device, "k8s-api.internal.corp")
    print_result_banner(res, "k8s-api.internal.corp")

def simulate_device_posture_failure(engine: CloudflareAccessPolicyEngine):
    print(f"\n{Colors.BOLD}{Colors.YELLOW}[SCENARIO 2] Employee on non-compliant laptop (Unencrypted Disk & No WARP){Colors.RESET}")
    bad_device = DeviceContext(
        device_id="WIN-HOME-991",
        os_name="Windows 11 Home",
        disk_encrypted=False,      # Fails posture check
        warp_client_active=False,  # Fails posture check
        firewall_enabled=False,
        client_cert_installed=False,
        serial_number="UNKNOWN-OEM"
    )
    user = UserSession(
        email="alex.pratama@enterprise.corp",
        groups=["Platform-Engineers"],
        idp_provider="Okta SSO (SAML 2.0)",
        mfa_verified=True,
        country_iso="ID",
        client_ip="182.1.22.88"
    )
    res = engine.evaluate_request(user, bad_device, "k8s-api.internal.corp")
    print_result_banner(res, "k8s-api.internal.corp")

def simulate_ci_cd_service_token(engine: CloudflareAccessPolicyEngine):
    print(f"\n{Colors.BOLD}{Colors.CYAN}[SCENARIO 3] GitLab CI/CD Pipeline requesting metrics via Service Token{Colors.RESET}")
    ci_session = UserSession(
        email="ci-runner@enterprise.corp",
        groups=["Automation-Bots"],
        idp_provider="Non-Identity Service Token",
        mfa_verified=False,
        country_iso="SG",
        client_ip="34.87.12.11",
        service_token_id="cf-svc-deployer-prod",
        service_token_secret="sec_tok_prod_9981a2f"
    )
    res = engine.evaluate_request(ci_session, None, "grafana.internal.corp")
    print_result_banner(res, "grafana.internal.corp")

def interactive_evaluation(engine: CloudflareAccessPolicyEngine):
    print(f"\n{Colors.BOLD}{Colors.HEADER}--- CUSTOM INTERACTIVE ZTNA POLICY TESTER ---{Colors.RESET}")
    try:
        email = input("User corporate email (e.g. user@enterprise.corp): ").strip()
        if not email:
            email = "tester@enterprise.corp"
        
        country = input("Country Code ISO (e.g. ID, SG, US, RU): ").strip().upper()
        if not country:
            country = "ID"
            
        mfa_in = input("MFA completed? (y/n, default y): ").strip().lower()
        mfa = False if mfa_in == 'n' else True
        
        group_in = input("Roles/Groups comma-separated (e.g. Platform-Engineers, Sales): ").strip()
        groups = [g.strip() for g in group_in.split(",")] if group_in else ["General-Employees"]
        
        warp_in = input("Is Cloudflare WARP client running? (y/n, default y): ").strip().lower()
        warp_active = False if warp_in == 'n' else True

        disk_in = input("Is device disk encrypted with BitLocker/FileVault? (y/n, default y): ").strip().lower()
        disk_enc = False if disk_in == 'n' else True

        target_host = input("Target Resource (1: k8s-api.internal.corp, 2: grafana.internal.corp): ").strip()
        if target_host == "1":
            target = "k8s-api.internal.corp"
        elif target_host == "2":
            target = "grafana.internal.corp"
        else:
            target = target_host if target_host else "k8s-api.internal.corp"

        device = DeviceContext(
            device_id=f"DEV-{uuid.uuid4().hex[:6].upper()}",
            os_name="Enterprise Managed OS",
            disk_encrypted=disk_enc,
            warp_client_active=warp_active,
            firewall_enabled=True,
            client_cert_installed=True,
            serial_number="ENT-8849-SN"
        )
        user = UserSession(
            email=email,
            groups=groups,
            idp_provider="Enterprise IdP (OIDC)",
            mfa_verified=mfa,
            country_iso=country,
            client_ip="203.0.113.45"
        )

        print(f"\n{Colors.DIM}Evaluating policy against Cloudflare Zero Trust Edge Rules...{Colors.RESET}")
        time.sleep(0.5)
        res = engine.evaluate_request(user, device, target)
        print_result_banner(res, target)

    except (KeyboardInterrupt, EOFError):
        print("\nEvaluation cancelled.")

def display_menu():
    print(f"\n{Colors.BOLD}{Colors.HEADER}======================================================================{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN} CLOUDFLARE ZERO TRUST NETWORK ACCESS (ZTNA) & TUNNELS LAB SIMULATOR{Colors.RESET}")
    print(f"{Colors.DIM} Module 02 Hands-On Exercise - BAB-08 Production Architecture{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}======================================================================{Colors.RESET}")
    print("1. [Scenario] Legitimate SRE Access to Private Kubernetes API (All Passes)")
    print("2. [Scenario] Block Insecure/Compromised Device (Posture Failure)")
    print("3. [Scenario] CI/CD Automation Bypass via Cloudflare Service Token")
    print("4. [Inspect] View Active Cloudflared Tunnel Topology & Ingress Maps")
    print("5. [Custom] Run Custom Interactive Access & Device Posture Evaluation")
    print("0. Exit Lab")
    print(f"{Colors.HEADER}----------------------------------------------------------------------{Colors.RESET}")

def main():
    tunnel = CloudflaredTunnelEdge(
        tunnel_name="prod-core-tunnel-sgp",
        tunnel_id="8f912be1-d641-4702-8611-1a0cf83b749d"
    )
    engine = CloudflareAccessPolicyEngine(tunnel=tunnel)

    while True:
        display_menu()
        choice = input(f"{Colors.BOLD}Select simulation option [0-5]: {Colors.RESET}").strip()
        if choice == "1":
            simulate_developer_valid(engine)
        elif choice == "2":
            simulate_device_posture_failure(engine)
        elif choice == "3":
            simulate_ci_cd_service_token(engine)
        elif choice == "4":
            tunnel.display_tunnel_status()
        elif choice == "5":
            interactive_evaluation(engine)
        elif choice in ("0", "q", "exit"):
            print(f"\n{Colors.GREEN}Terminating ZTNA Lab Simulator. Stay Secure!{Colors.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Colors.RED}Invalid option selected. Please choose between 0 and 5.{Colors.RESET}")

if __name__ == "__main__":
    main()
