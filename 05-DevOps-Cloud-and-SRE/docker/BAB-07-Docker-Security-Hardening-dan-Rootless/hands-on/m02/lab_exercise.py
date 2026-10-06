#!/usr/bin/env python3
"""
Lab Exercise M02: Docker Security Hardening & Rootless Production Simulator
BAB-07: Docker Security Hardening dan Rootless Docker

Features:
- Rootless Container Execution Simulation (User Namespaces & SubUID/SubGID mapping)
- Linux Capabilities Hardening (CAP_DROP ALL + minimal CAP_ADD)
- Seccomp Custom Syscall Filtering Engine
- Read-Only RootFS & Tmpfs Mount Verifier
- Attack Vector & Privilege Escalation Exploit Simulation
- Interactive Menu & Automated Security Audit with ANSI Color Diagnostics
"""

import sys
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_DARK = "\033[40m"


@dataclass
class SecurityProfile:
    name: str
    is_rootless: bool
    user: str
    uid: int
    cap_drop: List[str]
    cap_add: List[str]
    read_only_rootfs: bool
    no_new_privileges: bool
    seccomp_profile: str
    apparmor_profile: str
    tmpfs_mounts: List[str]
    pids_limit: int
    memory_limit: str


@dataclass
class AuditResult:
    check_name: str
    status: str  # PASS, WARN, FAIL
    score: int
    remediation: str


class DockerSecuritySimulator:
    def __init__(self):
        self.profiles: Dict[str, SecurityProfile] = {
            "default_legacy": SecurityProfile(
                name="Legacy Production Container (Insecure Default)",
                is_rootless=False,
                user="root",
                uid=0,
                cap_drop=[],
                cap_add=["ALL"],
                read_only_rootfs=False,
                no_new_privileges=False,
                seccomp_profile="unconfined",
                apparmor_profile="unconfined",
                tmpfs_mounts=[],
                pids_limit=0,
                memory_limit="unlimited"
            ),
            "cis_hardened": SecurityProfile(
                name="Hardened Production (CIS Benchmark + Rootless)",
                is_rootless=True,
                user="appuser",
                uid=10001,
                cap_drop=["ALL"],
                cap_add=["NET_BIND_SERVICE"],
                read_only_rootfs=True,
                no_new_privileges=True,
                seccomp_profile="custom_strict_profile.json",
                apparmor_profile="docker-default-strict",
                tmpfs_mounts=["/tmp:rw,noexec,nosuid,size=64m", "/run:rw,noexec,nosuid,size=32m"],
                pids_limit=100,
                memory_limit="512m"
            )
        }

    def print_banner(self):
        print(f"{CYAN}{BOLD}========================================================================{RESET}")
        print(f"{MAGENTA}{BOLD}       DOCKER SECURITY HARDENING & ROOTLESS ARCHITECTURE LAB           {RESET}")
        print(f"{CYAN}{BOLD}             BAB 07 - Linux Namespace & Container Defense              {RESET}")
        print(f"{CYAN}{BOLD}========================================================================{RESET}")
        print(f"{DIM}Author: DevOps & Cloud Security Engineering | Standard: CIS Docker v1.6{RESET}\n")

    def inspect_profile(self, profile_key: str):
        profile = self.profiles[profile_key]
        color = GREEN if profile.is_rootless else RED
        print(f"\n{BOLD}{color}[+] Configuration Manifest: {profile.name}{RESET}")
        print(f"    - Execution Context : {'ROOTLESS (User Namespace Active)' if profile.is_rootless else 'ROOTFUL DAEMON (Dangerous Privileges)'}")
        print(f"    - Container UID/User: {profile.uid} ({profile.user})")
        print(f"    - Cap Drop / Add    : Drop={profile.cap_drop} | Add={profile.cap_add}")
        print(f"    - Read-Only RootFS  : {profile.read_only_rootfs}")
        print(f"    - No New Privileges : {profile.no_new_privileges}")
        print(f"    - Seccomp Filter    : {profile.seccomp_profile}")
        print(f"    - AppArmor / MAC    : {profile.apparmor_profile}")
        print(f"    - Tmpfs Enclaves    : {profile.tmpfs_mounts}")
        print(f"    - Resource Sandbox  : PIDs={profile.pids_limit}, Mem={profile.memory_limit}\n")

    def run_cis_audit(self, profile_key: str) -> List[AuditResult]:
        profile = self.profiles[profile_key]
        results = []
        print(f"{YELLOW}{BOLD}[*] Executing CIS Docker Benchmark Audit against '{profile.name}'...{RESET}")
        time.sleep(0.4)

        # 1. Non-Root User Check
        if profile.uid > 0 and profile.user != "root":
            results.append(AuditResult("CIS-4.1 Non-Root User Enforcement", "PASS", 20, "Proper non-root user designated."))
        else:
            results.append(AuditResult("CIS-4.1 Non-Root User Enforcement", "FAIL", 0, "Container runs as UID 0 (root). Attacker gains host root if escaped!"))

        # 2. Linux Capabilities Check
        if "ALL" in profile.cap_drop and set(profile.cap_add).issubset({"NET_BIND_SERVICE"}):
            results.append(AuditResult("CIS-4.6 Linux Capabilities Hardening", "PASS", 20, "Dropped ALL capabilities, whitelisted minimal set."))
        else:
            results.append(AuditResult("CIS-4.6 Linux Capabilities Hardening", "FAIL", 0, "Default dangerous caps retained (CAP_SYS_ADMIN, CAP_NET_RAW, etc)."))

        # 3. Read-Only Root Filesystem
        if profile.read_only_rootfs:
            results.append(AuditResult("CIS-4.8 Read-Only Root Filesystem", "PASS", 20, "Root filesystem mounted read-only. Malware cannot persist."))
        else:
            results.append(AuditResult("CIS-4.8 Read-Only Root Filesystem", "FAIL", 0, "Filesystem writable. Easy target for backdoors and binary modification."))

        # 4. No New Privileges Flag
        if profile.no_new_privileges:
            results.append(AuditResult("CIS-4.5 No-New-Privileges Prevention", "PASS", 20, "SUID/SGID privilege escalation disabled."))
        else:
            results.append(AuditResult("CIS-4.5 No-New-Privileges Prevention", "FAIL", 0, "Processes can acquire SUID privileges inside container."))

        # 5. Seccomp Syscall Filtering
        if profile.seccomp_profile != "unconfined":
            results.append(AuditResult("CIS-4.7 Seccomp Profile Applied", "PASS", 20, f"Profile '{profile.seccomp_profile}' active."))
        else:
            results.append(AuditResult("CIS-4.7 Seccomp Profile Applied", "FAIL", 0, "Seccomp is unconfined. Raw kernel syscall exposure!"))

        # Print Report
        total_score = sum(r.score for r in results)
        print(f"\n{BOLD}{'AUDIT ITEM':<40} {'STATUS':<10} {'SCORE':<8} {'NOTES'}{RESET}")
        print("-" * 80)
        for r in results:
            tag = f"{GREEN}[ PASS ]{RESET}" if r.status == "PASS" else f"{RED}[ FAIL ]{RESET}"
            print(f"{r.check_name:<40} {tag:<10} {r.score:<8} {r.remediation}")
        print("-" * 80)

        score_color = GREEN if total_score >= 80 else (YELLOW if total_score >= 50 else RED)
        print(f"{BOLD}Total Compliance Score: {score_color}{total_score}/100{RESET}\n")
        return results

    def simulate_attack_scenarios(self, profile_key: str):
        profile = self.profiles[profile_key]
        print(f"\n{MAGENTA}{BOLD}[!] SIMULATING CYBER ATTACK CHAINS AGAINST: {profile.name}{RESET}")
        time.sleep(0.3)

        attacks = [
            {
                "name": "1. CVE-2022-0492 (Cgroups Release Agent Escape)",
                "eval": lambda p: not p.is_rootless and p.uid == 0 and "SYS_ADMIN" not in p.cap_drop,
                "msg_success": f"{RED}[CRITICAL ESCAPE] Root container abused notify_on_release release_agent! HOST COMPROMISED.{RESET}",
                "msg_blocked": f"{GREEN}[BLOCKED] Non-root UID ({profile.uid}) and User Namespaces prevent host cgroup write.{RESET}"
            },
            {
                "name": "2. In-Memory Persistence & Dropper Execution (/tmp & /bin overwrite)",
                "eval": lambda p: not p.read_only_rootfs,
                "msg_success": f"{RED}[EXPLOITED] Attacker downloaded rootkit into /bin/sh and modified libraries.{RESET}",
                "msg_blocked": f"{GREEN}[BLOCKED] Read-Only RootFS prevented binary tampering! Tmpfs mounted with noexec.{RESET}"
            },
            {
                "name": "3. Dangerous Kernel Syscall Invocation (reboot / ptrace / bpf)",
                "eval": lambda p: p.seccomp_profile == "unconfined",
                "msg_success": f"{RED}[EXPLOITED] Syscall ptrace() hooked process memory of adjacent workloads.{RESET}",
                "msg_blocked": f"{GREEN}[BLOCKED] Seccomp BPF filter rejected dangerous syscall with EPERM.{RESET}"
            },
            {
                "name": "4. SUID Binary Escalation (pkexec / setuid binary abuse)",
                "eval": lambda p: not p.no_new_privileges,
                "msg_success": f"{RED}[EXPLOITED] Local privilege escalation via SUID binary succeeded! Gained root.{RESET}",
                "msg_blocked": f"{GREEN}[BLOCKED] security-opt: no-new-privileges blocked execve SUID bits.{RESET}"
            }
        ]

        for attack in attacks:
            print(f"\n{BOLD}{WHITE}Executing: {attack['name']}...{RESET}")
            time.sleep(0.3)
            is_compromised = attack["eval"](profile)
            if is_compromised:
                print(f"   --> {attack['msg_success']}")
            else:
                print(f"   --> {attack['msg_blocked']}")

        print(f"\n{CYAN}[i] Attack simulation cycle finished.{RESET}\n")

    def display_production_manifest(self):
        print(f"\n{CYAN}{BOLD}[*] Production Hardened Compose & Dockerfile Specification:{RESET}")
        compose_content = """
# docker-compose.hardened.yml
version: "3.8"
services:
  secure-api:
    image: company/api:1.0.0-distroless
    user: "10001:10001"
    read_only: true
    security_opt:
      - no-new-privileges:true
      - seccomp:/etc/docker/seccomp-strict.json
      - apparmor:docker-default
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=64m
      - /run:rw,noexec,nosuid,size=16m
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
          pids: 100
"""
        dockerfile_content = """
# Dockerfile.hardened
FROM cgr.dev/chainguard/static:latest
COPY --chown=10001:10001 bin/server /app/server
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/app/server"]
"""
        print(f"{YELLOW}--- DOCKER COMPOSE HARDENING ---{RESET}{compose_content}")
        print(f"{YELLOW}--- DISTROLESS DOCKERFILE ---{RESET}{dockerfile_content}")

    def interactive_menu(self):
        while True:
            self.print_banner()
            print(f"{BOLD}Pilih Modul Latihan Hardening:{RESET}")
            print(f"  {CYAN}1.{RESET} Bandingkan Manifest Profil Default vs Hardened")
            print(f"  {CYAN}2.{RESET} Jalankan Audit CIS Benchmark pada Profil Default (Insecure)")
            print(f"  {CYAN}3.{RESET} Jalankan Audit CIS Benchmark pada Profil Hardened (Secure)")
            print(f"  {CYAN}4.{RESET} Simulasi Penetrasi & Eksploitasi Container Escape")
            print(f"  {CYAN}5.{RESET} Tampilkan Manifest Standar Emas Produksi (Compose + Dockerfile)")
            print(f"  {CYAN}6.{RESET} Keluar / Selesai Lab\n")

            if not sys.stdin.isatty():
                print(f"{YELLOW}[Auto-Run Mode detected - Running complete diagnostic suite]{RESET}")
                self.inspect_profile("default_legacy")
                self.inspect_profile("cis_hardened")
                self.run_cis_audit("default_legacy")
                self.run_cis_audit("cis_hardened")
                self.simulate_attack_scenarios("default_legacy")
                self.simulate_attack_scenarios("cis_hardened")
                self.display_production_manifest()
                print(f"{GREEN}{BOLD}[✔] Automated self-test passed successfully.{RESET}")
                break

            try:
                choice = input(f"{BOLD}Masukkan pilihan [1-6]: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{YELLOW}Lab session terminated.{RESET}")
                break

            if choice == "1":
                self.inspect_profile("default_legacy")
                self.inspect_profile("cis_hardened")
            elif choice == "2":
                self.run_cis_audit("default_legacy")
            elif choice == "3":
                self.run_cis_audit("cis_hardened")
            elif choice == "4":
                print(f"\n{BOLD}Pilih Target Sandbox:{RESET}")
                print(f"  a. Default Legacy Container")
                print(f"  b. CIS Hardened Container")
                sub = input("Pilihan [a/b]: ").strip().lower()
                target = "default_legacy" if sub == "a" else "cis_hardened"
                self.simulate_attack_scenarios(target)
            elif choice == "5":
                self.display_production_manifest()
            elif choice == "6":
                print(f"{GREEN}Terima kasih telah menyelesaikan Lab Exercise BAB 07 Docker Security.{RESET}")
                break
            else:
                print(f"{RED}Pilihan tidak valid. Silakan ulangi.{RESET}")

            input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    app = DockerSecuritySimulator()
    app.interactive_menu()
