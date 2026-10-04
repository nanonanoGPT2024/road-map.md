#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi DevSecOps Pipeline & Hardening Infrastruktur
BAB-10: DevSecOps dan Hardening Infrastruktur (DevOps Beginner)

Modul simulasi interaktif mencakup:
1. Secret Scanning (Deteksi hardcoded credentials & token bocor)
2. Static Application Security Testing (SAST & Code Linting)
3. Software Composition Analysis (SCA / Audit CVE Dependensi)
4. IaC & Container Hardening (Audit Dockerfile & CIS Benchmarks)
5. Interactive Policy Enforcement (Quality Gates PASS/FAIL)
"""

import sys
import time
import re
from typing import List, Dict, Any

# ANSI Color Codes untuk Terminal Output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"

def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
======================================================================
  [DEVSECOPS PIPELINE & INFRASTRUCTURE HARDENING LAB]
  Modul 01: Automated Security Gates & Baseline Hardening
======================================================================{Colors.RESET}"""
    print(banner)

def step_header(step_num: int, title: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}[TAHAP {step_num}] {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'-' * 65}{Colors.RESET}")

def scan_secrets(sample_code: str) -> List[Dict[str, Any]]:
    findings = []
    patterns = {
        "AWS Secret Key": r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/\+=]{20,}['\"]",
        "Generic API Token": r"(?i)(api_key|access_token|secret_token)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        "Hardcoded Password": r"(?i)(password|passwd|db_pass)\s*=\s*['\"][^'\"]{4,}['\"]",
        "Private Key Header": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
    }

    lines = sample_code.splitlines()
    for idx, line in enumerate(lines, 1):
        for vuln_name, regex in patterns.items():
            if re.search(regex, line):
                findings.append({
                    "line": idx,
                    "rule": vuln_name,
                    "snippet": line.strip(),
                    "severity": "CRITICAL"
                })
    return findings

def audit_iac_dockerfile(dockerfile_content: str) -> List[Dict[str, Any]]:
    violations = []
    lines = dockerfile_content.splitlines()
    has_user_non_root = False

    for idx, line in enumerate(lines, 1):
        clean_line = line.strip()
        if clean_line.startswith("#") or not clean_line:
            continue
        
        # Cek penggunaan user root
        if clean_line.upper().startswith("USER "):
            has_user_non_root = True

        # Anti-pattern: Base image menggunakan tag latest
        if clean_line.upper().startswith("FROM ") and (":latest" in clean_line or ":" not in clean_line):
            violations.append({
                "line": idx,
                "rule": "CIS-DI-0001: Unpinned / Latest Base Image Tag",
                "severity": "MEDIUM",
                "desc": "Menggunakan image mutable tanpa sha256 pin atau tag semver spesifik."
            })

        # Anti-pattern: SSH daemon terpasang di container
        if "openssh-server" in clean_line.lower():
            violations.append({
                "line": idx,
                "rule": "CIS-DI-0004: SSH Daemon running in Container",
                "severity": "HIGH",
                "desc": "SSH di container memperluas attack surface; gunakan 'docker exec' / ephemeral debugging."
            })

        # Anti-pattern: Expose port sensitif
        if clean_line.upper().startswith("EXPOSE ") and ("22" in clean_line or "3306" in clean_line):
            violations.append({
                "line": idx,
                "rule": "CIS-DI-0006: Insecure Ports Exposed",
                "severity": "HIGH",
                "desc": f"Port sensitif terbuka secara langsung: {clean_line}"
            })

    if not has_user_non_root:
        violations.append({
            "line": len(lines),
            "rule": "CIS-DI-0002: Missing Non-Root USER Directive",
            "severity": "HIGH",
            "desc": "Container berjalan sebagai ROOT (PID 1). Wajib definisikan non-root user (USER appuser)."
        })

    return violations

def audit_os_hardening(config: Dict[str, str]) -> List[Dict[str, Any]]:
    issues = []
    cis_rules = {
        "PermitRootLogin": ("no", "CIS-SSH-1.1: Root SSH Login Dilarang"),
        "PasswordAuthentication": ("no", "CIS-SSH-1.2: Otentikasi Password Wajib Disabled (Key-Only)"),
        "MaxAuthTries": ("3", "CIS-SSH-1.3: Batas Maksimal Percobaan Login SSH"),
        "UFW_STATUS": ("active", "CIS-NET-2.1: Host Firewall UFW Wajib Aktif"),
    }

    for param, (expected, rule_title) in cis_rules.items():
        actual = config.get(param, "unknown").lower()
        if actual != expected.lower():
            issues.append({
                "param": param,
                "rule": rule_title,
                "expected": expected,
                "actual": actual,
                "severity": "HIGH"
            })
    return issues

def scan_dependencies(dependencies: Dict[str, str]) -> List[Dict[str, Any]]:
    known_cves = {
        "requests": {"vulnerable_below": "2.31.0", "cve": "CVE-2023-32681", "sev": "MEDIUM"},
        "urllib3": {"vulnerable_below": "2.0.7", "cve": "CVE-2023-45803", "sev": "HIGH"},
        "flask": {"vulnerable_below": "2.2.5", "cve": "CVE-2023-30861", "sev": "HIGH"},
        "pyyaml": {"vulnerable_below": "5.4", "cve": "CVE-2020-14343", "sev": "CRITICAL"}
    }

    vulns = []
    for pkg, ver in dependencies.items():
        if pkg in known_cves:
            rule = known_cves[pkg]
            # Simulasi deteksi versi di bawah ambang aman
            vulns.append({
                "package": pkg,
                "installed_ver": ver,
                "cve": rule["cve"],
                "threshold": rule["vulnerable_below"],
                "severity": rule["sev"]
            })
    return vulns

def run_interactive_lab():
    print_banner()

    # Data simulasi
    dummy_source_code = """
import os
import requests

API_KEY = "ak_live_99482710482019482910"
db_pass = "SuperSecretDbPassword123!"

def fetch_data():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.get("https://internal.api/data", headers=headers)
"""

    dummy_dockerfile = """
FROM node:latest
WORKDIR /app
COPY package*.json ./
RUN apt-get update && apt-get install -y openssh-server
RUN npm install
COPY . .
EXPOSE 22
EXPOSE 3000
CMD ["npm", "start"]
"""

    dummy_ssh_config = {
        "PermitRootLogin": "yes",
        "PasswordAuthentication": "yes",
        "MaxAuthTries": "6",
        "UFW_STATUS": "inactive"
    }

    dummy_deps = {
        "flask": "2.0.1",
        "urllib3": "1.26.5",
        "pyyaml": "5.3.1"
    }

    print(f"\n{Colors.BOLD}Skenario DevSecOps & Hardening Target:{Colors.RESET}")
    print("1. Scan Secret & Static Analysis (SAST/TruffleHog/Semgrep)")
    print("2. Audit Dependensi / Software Composition Analysis (SCA/Trivy)")
    print("3. Audit Keamanan Container & Dockerfile (Hadolint/CIS)")
    print("4. Evaluasi Hardening SSH & Host Firewall (CIS Linux Benchmark)")
    print("5. Jalankan Simulasi Full CI/CD Security Gate (Automated Pipeline)")
    print("0. Keluar")

    while True:
        try:
            choice = input(f"\n{Colors.BOLD}Pilih menu [0-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Keluar dari lab.{Colors.RESET}")
            break

        if choice == "0":
            print(f"{Colors.GREEN}Sesi lab DevSecOps selesai.{Colors.RESET}")
            break

        elif choice == "1":
            step_header(1, "Secret Scanning & SAST Analysis")
            print(f"{Colors.YELLOW}[*] Memindai repositori untuk secret leaked...{Colors.RESET}")
            time.sleep(0.4)
            findings = scan_secrets(dummy_source_code)
            if findings:
                for f in findings:
                    print(f" {Colors.RED}[!] LEAK DETECTED (Line {f['line']}): {f['rule']}{Colors.RESET}")
                    print(f"     Severity : {Colors.BOLD}{f['severity']}{Colors.RESET}")
                    print(f"     Snippet  : {Colors.CYAN}{f['snippet']}{Colors.RESET}")
                print(f"\n{Colors.RED}[FAIL] Secret scanning mendeteksi kredensial aktif dalam repo!{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}[PASS] Tidak ada secret terdeteksi.{Colors.RESET}")

        elif choice == "2":
            step_header(2, "Software Composition Analysis (SCA)")
            print(f"{Colors.YELLOW}[*] Mengaudit manifest dependencies terhadap basis data CVE...{Colors.RESET}")
            time.sleep(0.4)
            vulns = scan_dependencies(dummy_deps)
            print(f"{'Package':<12} {'Installed':<10} {'Fix Required':<14} {'CVE ID':<16} {'Severity'}")
            print("-" * 65)
            for v in vulns:
                sev_color = Colors.RED if v['severity'] in ['HIGH', 'CRITICAL'] else Colors.YELLOW
                print(f"{v['package']:<12} {v['installed_ver']:<10} {v['threshold']:<14} {v['cve']:<16} {sev_color}{v['severity']}{Colors.RESET}")
            print(f"\n{Colors.RED}[ALERT] 3 dependensi rentan terhadap CVE kritis. Wajib bump versi!{Colors.RESET}")

        elif choice == "3":
            step_header(3, "Container & IaC Hardening Audit")
            print(f"{Colors.YELLOW}[*] Menganalisis Dockerfile terhadap CIS Docker Benchmark...{Colors.RESET}")
            time.sleep(0.4)
            issues = audit_iac_dockerfile(dummy_dockerfile)
            for iss in issues:
                print(f" {Colors.RED}[X] Line {iss['line']}: {iss['rule']}{Colors.RESET}")
                print(f"     Tingkat Resiko : {iss['severity']}")
                print(f"     Rekomendasi    : {iss['desc']}")
            print(f"\n{Colors.YELLOW}[REMEDIATION] Buat user unprivileged dan hapus openssh daemon.{Colors.RESET}")

        elif choice == "4":
            step_header(4, "OS Baseline Hardening & SSH Audit")
            print(f"{Colors.YELLOW}[*] Memverifikasi konfigurasi sshd_config & Firewall...{Colors.RESET}")
            time.sleep(0.4)
            ssh_issues = audit_os_hardening(dummy_ssh_config)
            for iss in ssh_issues:
                print(f" {Colors.RED}[VIOLATION] {iss['rule']}{Colors.RESET}")
                print(f"   Parameter : {iss['param']} = '{iss['actual']}' (Harusnya: '{iss['expected']}')")
            print(f"\n{Colors.RED}[FAIL] Server belum memenuhi standar CIS Level 1 OS Hardening.{Colors.RESET}")

        elif choice == "5":
            step_header(5, "Simulasi Automated CI/CD DevSecOps Quality Gate")
            print(f"{Colors.CYAN}Pipeline Triggered: commit #8f12a9b on main{Colors.RESET}")
            pipeline_steps = [
                ("1. Secret Detection (Gitleaks)", True),
                ("2. SAST Scanning (Semgrep)", True),
                ("3. Dependency Vulnerability (Trivy)", True),
                ("4. IaC Security Linting (Checkov)", True),
                ("5. Production Deploy Gate", False),
            ]

            blocked = False
            for step_name, is_failing in pipeline_steps:
                time.sleep(0.3)
                if is_failing and not blocked:
                    print(f" {step_name:<40} -> {Colors.RED}[FAILED - SECURITY GATE BLOCKED]{Colors.RESET}")
                    blocked = True
                elif blocked:
                    print(f" {step_name:<40} -> {Colors.YELLOW}[SKIPPED - PIPELINE HALTED]{Colors.RESET}")
                else:
                    print(f" {step_name:<40} -> {Colors.GREEN}[PASSED]{Colors.RESET}")

            print(f"\n{Colors.RED}{Colors.BOLD}STATUS: PIPELINE DITOLAK (Zero Tolerance pada Temuan Critical){Colors.RESET}")
            print(f"{Colors.GREEN}Prinsip Shift-Left DevSecOps berhasil mencegah deployment tidak aman!{Colors.RESET}")

        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 0-5.{Colors.RESET}")

if __name__ == "__main__":
    run_interactive_lab()
