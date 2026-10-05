#!/usr/bin/env python3
"""
Lab Exercise: DevSecOps Production Security Pipeline Simulator
Bab 09: DevSecOps dan Security

Simulasi interaktif pipeline keamanan end-to-end:
1. Secret Scanning (TruffleHog / GitGuardian)
2. SAST (Static Application Security Testing)
3. SCA & SBOM Analysis (Software Bill of Materials)
4. Container & Distroless Image Audit
5. IaC Compliance (Checkov / OPA Rego)
6. Admission Control & Runtime eBPF Security (Kyverno / Falco)
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes
class Color:
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class SecurityFinding:
    rule_id: str
    stage: str
    severity: Severity
    target: str
    description: str
    remediation: str
    cve_id: Optional[str] = None
    cvss_score: float = 0.0


@dataclass
class PipelineResult:
    total_scanned: int = 0
    passed_gates: int = 0
    failed_gates: int = 0
    findings: List[SecurityFinding] = field(default_factory=list)


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
======================================================================
  ____             ____               ___             ____  _           
 |  _ \\  _____   _/ ___|  ___  ___   / _ \\ _ __  ___ / ___|(_)_ __ ___  
 | | | |/ _ \\ \\ / /___ \\ / _ \\/ __| | | | | '_ \\/ __|\\___ \\| | '_ ` _ \\ 
 | |_| |  __/\\ V / ___) |  __/ (__  | |_| | |_) \\__ \\ ___) | | | | | | |
 |____/ \\___| \\_/ |____/ \\___|\\___|  \\___/| .__/|___/|____/|_|_| |_| |_|
                                          |_|                           
  Enterprise DevSecOps Gatekeeper & Policy Simulator (BAB-09)
======================================================================{Color.RESET}
"""
    print(banner)


def status_badge(severity: Severity) -> str:
    badges = {
        Severity.CRITICAL: f"{Color.BG_RED}{Color.WHITE}{Color.BOLD} CRITICAL {Color.RESET}",
        Severity.HIGH: f"{Color.RED}{Color.BOLD}[HIGH]{Color.RESET}",
        Severity.MEDIUM: f"{Color.YELLOW}[MED]{Color.RESET}",
        Severity.LOW: f"{Color.BLUE}[LOW]{Color.RESET}",
        Severity.INFO: f"{Color.DIM}[INFO]{Color.RESET}",
    }
    return badges.get(severity, "[UNKNOWN]")


def step_print(title: str, subtitle: str = ""):
    print(f"\n{Color.MAGENTA}==>{Color.RESET} {Color.BOLD}{title}{Color.RESET}")
    if subtitle:
        print(f"    {Color.DIM}{subtitle}{Color.RESET}")


def progress_indicator(label: str, duration: float = 0.6):
    print(f"  {Color.CYAN}* {label}...{Color.RESET} ", end="", flush=True)
    steps = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start = time.time()
    idx = 0
    while time.time() - start < duration:
        sys.stdout.write(f"\b{steps[idx % len(steps)]}")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.06)
    print(f"\b{Color.GREEN}DONE{Color.RESET}")


class DevSecOpsEngine:
    def __init__(self, fail_on_severity: Severity = Severity.HIGH):
        self.fail_on = fail_on_severity
        self.findings: List[SecurityFinding] = []
        self.stage_status: Dict[str, bool] = {}

    def scan_secrets(self) -> List[SecurityFinding]:
        step_print("Stage 1: Pre-Commit & Secret Scanning", "Engine: TruffleHog / GitGuardian Core")
        progress_indicator("Scanning git commit delta & uncommitted staging index")
        time.sleep(0.2)
        
        detected = [
            SecurityFinding(
                rule_id="SEC-001",
                stage="Secret Scanning",
                severity=Severity.CRITICAL,
                target="deploy/helm/values-prod.yaml:44",
                description="Hardcoded AWS Access Key ID & Secret Key terdeteksi",
                remediation="Migrasikan ke AWS IAM Roles for Service Accounts (IRSA) / HashiCorp Vault",
                cvss_score=9.8
            ),
            SecurityFinding(
                rule_id="SEC-002",
                stage="Secret Scanning",
                severity=Severity.HIGH,
                target="src/config/database.ts:18",
                description="Plaintext Postgres Database Connection String dengan password produksi",
                remediation="Inject via Kubernetes External-Secrets Operator (ESO) dengan sealed storage",
                cvss_score=8.5
            )
        ]
        self.findings.extend(detected)
        self.stage_status["Secret Scanning"] = False
        return detected

    def scan_sast(self) -> List[SecurityFinding]:
        step_print("Stage 2: Static Application Security Testing (SAST)", "Engine: Semgrep Community Ruleset & SonarQube")
        progress_indicator("AST Parsing & Semantic Taint Analysis pada 142 source files")
        time.sleep(0.2)
        
        detected = [
            SecurityFinding(
                rule_id="SAST-104",
                stage="SAST",
                severity=Severity.CRITICAL,
                target="src/controllers/auth.py:89",
                description="SQL Injection via string concatenation tanpa parameterized queries",
                remediation="Gunakan ORM query builder atau prepared statement SQLAlchemy",
                cve_id="CWE-89",
                cvss_score=9.1
            ),
            SecurityFinding(
                rule_id="SAST-209",
                stage="SAST",
                severity=Severity.MEDIUM,
                target="src/utils/crypto.py:22",
                description="Penggunaan fungsi hashing usang (MD5 / SHA1) untuk token reset password",
                remediation="Upgrade ke Argon2id atau bcrypt dengan cost factor >= 12",
                cve_id="CWE-328",
                cvss_score=5.9
            )
        ]
        self.findings.extend(detected)
        self.stage_status["SAST"] = False
        return detected

    def scan_sca_sbom(self) -> List[SecurityFinding]:
        step_print("Stage 3: Software Composition Analysis (SCA) & SBOM", "Engine: Trivy / Syft / CycloneDX Spec")
        progress_indicator("Menghasilkan CycloneDX SBOM json & cross-referencing NVD database")
        time.sleep(0.2)
        
        detected = [
            SecurityFinding(
                rule_id="SCA-301",
                stage="SCA / Dependency",
                severity=Severity.CRITICAL,
                target="package-lock.json -> jsonwebtoken@8.5.1",
                description="Bypass verification via insecure key header parameter",
                remediation="Bumping package jsonwebtoken >= 9.0.0",
                cve_id="CVE-2022-23529",
                cvss_score=9.8
            ),
            SecurityFinding(
                rule_id="SCA-305",
                stage="SCA / Dependency",
                severity=Severity.LOW,
                target="requirements.txt -> urllib3@1.26.4",
                description="Cookie leak on redirect antar subdomain",
                remediation="Update ke urllib3 >= 1.26.18",
                cve_id="CVE-2023-45803",
                cvss_score=3.7
            )
        ]
        self.findings.extend(detected)
        self.stage_status["SCA/SBOM"] = False
        return detected

    def scan_container(self) -> List[SecurityFinding]:
        step_print("Stage 4: Container Image & Base OS Security", "Engine: Trivy Container Scanner & Dockle CIS Benchmark")
        progress_indicator("Inspecting multi-stage Dockerfile layers & base image rootfs")
        time.sleep(0.2)
        
        detected = [
            SecurityFinding(
                rule_id="DOCKLE-CIS-001",
                stage="Container Audit",
                severity=Severity.HIGH,
                target="Dockerfile:3",
                description="Container berjalan sebagai UID root (0). CIS Benchmark 4.1 violated",
                remediation="Tambahkan directive: USER 65534:65534 (nonroot) atau gunakan distroless base",
                cvss_score=7.8
            ),
            SecurityFinding(
                rule_id="DOCKLE-CIS-002",
                stage="Container Audit",
                severity=Severity.MEDIUM,
                target="Dockerfile:14",
                description="Package manager (apt-get) dan cache compiler tertinggal di layer produksi",
                remediation="Gunakan multi-stage build dan distroless/static-debian12",
                cvss_score=5.3
            )
        ]
        self.findings.extend(detected)
        self.stage_status["Container"] = False
        return detected

    def scan_iac(self) -> List[SecurityFinding]:
        step_print("Stage 5: Infrastructure as Code (IaC) & OPA Policies", "Engine: Checkov & Open Policy Agent (Rego)")
        progress_indicator("Evaluasi Kubernetes manifest terhadap NSA/CISA Hardening Guidance")
        time.sleep(0.2)
        
        detected = [
            SecurityFinding(
                rule_id="CKV_K8S_16",
                stage="IaC / Kubernetes",
                severity=Severity.HIGH,
                target="k8s/deployment.yaml",
                description="Container tidak mengaktifkan 'readOnlyRootFilesystem: true'",
                remediation="Pasang readOnlyRootFilesystem=true dan mount emptyDir untuk /tmp jika butuh write",
                cvss_score=7.4
            ),
            SecurityFinding(
                rule_id="CKV_K8S_28",
                stage="IaC / Kubernetes",
                severity=Severity.CRITICAL,
                target="k8s/deployment.yaml",
                description="Privileged container flag aktif atau capabilities CAP_SYS_ADMIN di-allow",
                remediation="Hapus 'privileged: true' dan pasang securityContext.capabilities.drop: ['ALL']",
                cvss_score=9.0
            )
        ]
        self.findings.extend(detected)
        self.stage_status["IaC"] = False
        return detected

    def simulate_runtime_ebpf(self) -> List[SecurityFinding]:
        step_print("Stage 6: Runtime Security & eBPF Behavioral Detection", "Engine: Falco Cloud-Native Runtime")
        progress_indicator("Tracing syscalls (execve, openat, connect) via eBPF probe ring buffer")
        time.sleep(0.2)
        
        detected = [
            SecurityFinding(
                rule_id="FALCO-01",
                stage="Runtime eBPF",
                severity=Severity.CRITICAL,
                target="pod/payment-service-7f98b-kx9a (namespace: prod)",
                description="Spawn shell binary (/bin/sh) di dalam production container",
                remediation="Isolasi pod via NetworkPolicy, kill process, dan deploy distroless image",
                cvss_score=9.5
            )
        ]
        self.findings.extend(detected)
        self.stage_status["Runtime"] = False
        return detected

    def auto_remediate_all(self):
        step_print("Applying Automated DevSecOps Remediation...", "GitOps Shift-Left Auto-Fix Workflow")
        remediations = [
            ("Secret Scanning", "Kunci AWS dan DB Secret dipindahkan ke Vault & External-Secrets Operator"),
            ("SAST", "Query string diubah menjadi Prepared Statements & Hashing diupdate ke Argon2id"),
            ("SCA/SBOM", "Dependency bumping jsonwebtoken 8.5.1 -> 9.0.2 via Automated Dependabot PR"),
            ("Container", "Base image diganti ke gcr.io/distroless/python3-debian12:nonroot (UID 65532)"),
            ("IaC / K8s", "Menetapkan readOnlyRootFilesystem: true & drop ALL Linux capabilities"),
            ("Runtime eBPF", "Memasang Kyverno admission policy untuk memblokir exec pod secara preventif")
        ]
        for stage, action in remediations:
            progress_indicator(f"Auto-fixing [{stage}]")
            print(f"      {Color.GREEN}✔{Color.RESET} {action}")
            time.sleep(0.15)
        
        self.findings.clear()
        print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} STATUS: SEMUA VULNERABILITY TELAH BERHASIL DIREMEDIASI! {Color.RESET}\n")

    def display_report(self):
        print(f"\n{Color.BOLD}{'='*70}{Color.RESET}")
        print(f"{Color.BOLD}                RINGKASAN AUDIT KEAMANAN DEVSECOPS{Color.RESET}")
        print(f"{Color.BOLD}{'='*70}{Color.RESET}\n")

        if not self.findings:
            print(f"  {Color.GREEN}{Color.BOLD}✔ CLEAN PIPELINE:{Color.RESET} Zero vulnerability detected! Security Gate Passed.")
            print(f"  {Color.CYAN}Ready for Production Deployment via CD Pipeline.{Color.RESET}\n")
            return

        crit_count = sum(1 for f in self.findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in self.findings if f.severity == Severity.HIGH)
        med_count = sum(1 for f in self.findings if f.severity == Severity.MEDIUM)
        low_count = sum(1 for f in self.findings if f.severity == Severity.LOW)

        print(f"  Total Temuan      : {Color.BOLD}{len(self.findings)}{Color.RESET}")
        print(f"  Breakdown         : {Color.RED}Critical: {crit_count}{Color.RESET} | "
              f"{Color.YELLOW}High: {high_count}{Color.RESET} | "
              f"{Color.BLUE}Medium: {med_count}{Color.RESET} | "
              f"{Color.DIM}Low: {low_count}{Color.RESET}\n")

        print(f"{Color.BOLD}Daftar Temuan Prioritas:{Color.RESET}")
        print("-" * 70)
        for i, f in enumerate(self.findings, 1):
            badge = status_badge(f.severity)
            cve_info = f"({f.cve_id}) " if f.cve_id else ""
            print(f"{i:2d}. {badge} [{f.stage}] {Color.BOLD}{f.rule_id}{Color.RESET} {cve_info}(CVSS: {f.cvss_score})")
            print(f"    Lokasi      : {Color.CYAN}{f.target}{Color.RESET}")
            print(f"    Masalah     : {f.description}")
            print(f"    Remediasi   : {Color.GREEN}{f.remediation}{Color.RESET}")
            print("-" * 70)

        print(f"\n{Color.BG_RED}{Color.WHITE}{Color.BOLD} [PIPELINE BLOCKED] {Color.RESET} Kebijakan CI/CD Gatekeeper menolak build.")
        print(f"{Color.RED}Alasan: Ditemukan {crit_count} Critical dan {high_count} High vulnerability melampaui batas toleransi.{Color.RESET}\n")


def interactive_menu(engine: DevSecOpsEngine):
    while True:
        print(f"{Color.BOLD}PILIHAN AKSI DEVSECOPS SIMULATOR:{Color.RESET}")
        print(f"  {Color.CYAN}[1]{Color.RESET} Jalankan Pemindaian Lengkap (Shift-Left Pipeline)")
        print(f"  {Color.CYAN}[2]{Color.RESET} Tampilkan Laporan Temuan & Security Gate Evaluation")
        print(f"  {Color.CYAN}[3]{Color.RESET} Eksekusi Automated Hardening & Remediasi Cepat")
        print(f"  {Color.CYAN}[4]{Color.RESET} Simulasi Runtime Exploit Attack & eBPF Falco Alert")
        print(f"  {Color.CYAN}[5]{Color.RESET} Ekspor SBOM & Laporan Audit (Format JSON)")
        print(f"  {Color.RED}[0] Keluar Simulator{Color.RESET}")

        try:
            choice = input(f"\n{Color.YELLOW}Pilih opsi [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            engine.findings.clear()
            engine.scan_secrets()
            engine.scan_sast()
            engine.scan_sca_sbom()
            engine.scan_container()
            engine.scan_iac()
            engine.display_report()
        elif choice == "2":
            engine.display_report()
        elif choice == "3":
            engine.auto_remediate_all()
        elif choice == "4":
            engine.simulate_runtime_ebpf()
            engine.display_report()
        elif choice == "5":
            filename = "security_audit_report.json"
            data = [
                {
                    "rule_id": f.rule_id,
                    "stage": f.stage,
                    "severity": f.severity.value,
                    "target": f.target,
                    "description": f.description,
                    "remediation": f.remediation,
                    "cve_id": f.cve_id,
                    "cvss": f.cvss_score
                }
                for f in engine.findings
            ]
            with open(filename, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)
            print(f"\n{Color.GREEN}✔ Laporan audit berhasil diekspor ke: {filename}{Color.RESET}\n")
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah menggunakan DevSecOps Simulator.{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan ulangi.{Color.RESET}\n")


def main():
    print_banner()
    engine = DevSecOpsEngine()
    
    # Check if run non-interactively or with flags
    if "--auto" in sys.argv:
        print(f"{Color.YELLOW}Mode Otomatis Aktif (--auto): Menjalankan pipeline standar...{Color.RESET}")
        engine.scan_secrets()
        engine.scan_sast()
        engine.scan_sca_sbom()
        engine.scan_container()
        engine.scan_iac()
        engine.display_report()
        engine.auto_remediate_all()
        engine.display_report()
        return

    interactive_menu(engine)


if __name__ == "__main__":
    main()
