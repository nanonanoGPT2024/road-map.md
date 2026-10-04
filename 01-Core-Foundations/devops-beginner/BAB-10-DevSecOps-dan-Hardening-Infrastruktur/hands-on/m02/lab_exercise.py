#!/usr/bin/env python3
"""
Lab Hands-on: DevSecOps & Infrastructure Hardening Engine
Kategori: 01-Core-Foundations | Bab 10: DevSecOps Pemula - Modul 02

Script ini mensimulasikan security gating engine otomatis pada CI/CD pipeline:
1. Secret & Credential Scanning (Shannon Entropy + RegEx Signatures)
2. Infrastructure-as-Code (IaC) & Dockerfile Hardening Policy Engine
3. Software Composition Analysis (SCA) / Vulnerability Matcher
4. Automated Security Gate & Risk Scoring (Pass/Fail criteria)
"""

import re
import math
import json
import time
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

# --- ANSI Terminal Color Codes ---
CLR_RESET  = "\033[0m"
CLR_RED    = "\033[91m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE   = "\033[94m"
CLR_CYAN   = "\033[96m"
CLR_BOLD   = "\033[1m"


@dataclass
class SecurityFinding:
    category: str      # SECRET, IAC_HARDENING, SCA_VULN
    severity: str      # CRITICAL, HIGH, MEDIUM, LOW
    target: str        # File / Resource path
    rule_id: str       # e.g., SEC-001, IAC-003
    description: str
    remediation: str


class SecretScanner:
    """Mendeteksi kredensial sensitif via Signature Matching & Shannon Entropy."""
    
    SIGNATURES = {
        "AWS_KEY": re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
        "GENERIC_SECRET": re.compile(r"(?i)(password|passwd|secret|api_key|access_token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]"),
        "PRIVATE_KEY": re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----")
    }

    @staticmethod
    def calculate_entropy(data: str) -> float:
        """Menghitung Shannon Entropy untuk mendeteksi token/kunci kriptografi terenkripsi."""
        if not data:
            return 0.0
        entropy = 0.0
        length = len(data)
        freq = {char: data.count(char) for char in set(data)}
        for count in freq.values():
            prob = count / length
            entropy -= prob * math.log2(prob)
        return entropy

    def scan(self, file_path: str, content: str) -> List[SecurityFinding]:
        findings = []
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            # 1. Regex Signature Match
            for rule_name, pattern in self.SIGNATURES.items():
                match = pattern.search(line)
                if match:
                    findings.append(SecurityFinding(
                        category="SECRET",
                        severity="CRITICAL",
                        target=f"{file_path}:{line_num}",
                        rule_id=f"SEC-{rule_name}",
                        description=f"Ditemukan plain-text credential pattern: {rule_name}",
                        remediation="Pindahkan secret ke Environment Variable atau Secret Manager (e.g., Vault, AWS Secrets Manager)."
                    ))

            # 2. Entropy Check pada assignment token panjang
            assign_match = re.search(r"=\s*['\"]?([A-Za-z0-9+/=_-]{20,})['\"]?", line)
            if assign_match:
                token = assign_match.group(1)
                entropy = self.calculate_entropy(token)
                # Nilai entropy > 4.2 biasanya mengindikasikan random API Key/Hashes
                if entropy > 4.2 and not any(sig in rule_name for sig in ["AWS_KEY"]):
                    findings.append(SecurityFinding(
                        category="SECRET",
                        severity="HIGH",
                        target=f"{file_path}:{line_num}",
                        rule_id="SEC-HIGH-ENTROPY",
                        description=f"String ber-entropi tinggi terdeteksi (Shannon Entropy: {entropy:.2f})",
                        remediation="Pastikan string acak bukan token runtime yang di-hardcode."
                    ))

        return findings


class IaCHardeningEngine:
    """Mengevaluasi konfigurasi container & deployment sesuai CIS Benchmark dasar."""

    def audit_dockerfile(self, file_path: str, dockerfile_content: str) -> List[SecurityFinding]:
        findings = []
        lines = [line.strip() for line in dockerfile_content.splitlines() if line.strip() and not line.startswith("#")]
        
        has_user = False
        uses_latest = False
        has_healthcheck = False

        for idx, line in enumerate(lines, start=1):
            # Check Base Image Tag
            if line.startswith("FROM"):
                if ":latest" in line or (":" not in line and "as" not in line.lower()):
                    uses_latest = True
                    findings.append(SecurityFinding(
                        category="IAC_HARDENING",
                        severity="MEDIUM",
                        target=f"{file_path}:{idx}",
                        rule_id="IAC-DOCKER-001",
                        description="Penggunaan tag base image ':latest' atau tanpa immutable digest/tag",
                        remediation="Spesifikasikan versi eksplisit (misal: python:3.11-slim-bookworm) untuk menghindari breaking changes tak terprediksi."
                    ))

            # Check User switching
            if line.startswith("USER"):
                parts = line.split()
                if len(parts) > 1 and parts[1] not in ["root", "0"]:
                    has_user = True

            # Check Healthcheck
            if line.startswith("HEALTHCHECK"):
                has_healthcheck = True

        if not has_user:
            findings.append(SecurityFinding(
                category="IAC_HARDENING",
                severity="HIGH",
                target=file_path,
                rule_id="IAC-DOCKER-002",
                description="Container berjalan sebagai default ROOT user (Least Privilege violated)",
                remediation="Buat dan tentukan user non-root menggunakan 'USER appuser' sebelum instruksi CMD/ENTRYPOINT."
            ))

        if not has_healthcheck:
            findings.append(SecurityFinding(
                category="IAC_HARDENING",
                severity="LOW",
                target=file_path,
                rule_id="IAC-DOCKER-003",
                description="Instruksi HEALTHCHECK tidak dideklarasikan",
                remediation="Tambahkan HEALTHCHECK agar orchestrator (Docker/K8s) dapat memantau status liveness aplikasi."
            ))

        return findings

    def audit_manifest(self, file_path: str, manifest_data: Dict[str, Any]) -> List[SecurityFinding]:
        """Audit mock Kubernetes/Container Runtime Security Context."""
        findings = []
        spec = manifest_data.get("spec", {})
        sec_context = spec.get("securityContext", {})

        if not sec_context.get("readOnlyRootFilesystem", False):
            findings.append(SecurityFinding(
                category="IAC_HARDENING",
                severity="HIGH",
                target=f"{file_path}#securityContext",
                rule_id="IAC-K8S-001",
                description="Root filesystem tidak berstatus read-only (Writable rootfs)",
                remediation="Set 'securityContext.readOnlyRootFilesystem: true' dan gunakan ephemeral volume untuk folder temporary."
            ))

        if sec_context.get("privileged", False):
            findings.append(SecurityFinding(
                category="IAC_HARDENING",
                severity="CRITICAL",
                target=f"{file_path}#securityContext.privileged",
                rule_id="IAC-K8S-002",
                description="Container diizinkan berjalan dalam 'privileged' mode (Container Escape Risk)",
                remediation="Hapus 'privileged: true'. Hanya berikan Linux capabilities yang benar-benar esensial."
            ))

        return findings


class VulnerabilityEngine:
    """Mock Software Composition Analysis (SCA) against CVE Advisory DB."""

    MOCK_CVE_DB = {
        "requests": {"vuln_version": "< 2.31.0", "cve": "CVE-2023-32681", "severity": "MEDIUM", "fix": "2.31.0"},
        "urllib3": {"vuln_version": "< 1.26.17", "cve": "CVE-2023-43804", "severity": "HIGH", "fix": "1.26.17"},
        "cryptography": {"vuln_version": "< 41.0.6", "cve": "CVE-2023-49083", "severity": "CRITICAL", "fix": "41.0.6"}
    }

    def scan_dependencies(self, file_path: str, reqs_content: str) -> List[SecurityFinding]:
        findings = []
        for line in reqs_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r"^([a-zA-Z0-9\-_]+)==([0-9\.]+)", line)
            if match:
                pkg_name, version = match.group(1).lower(), match.group(2)
                if pkg_name in self.MOCK_CVE_DB:
                    cve_info = self.MOCK_CVE_DB[pkg_name]
                    # Logika simulasi perbandingan versi dasar (misal string sederhana < fix)
                    if version < cve_info["fix"]:
                        findings.append(SecurityFinding(
                            category="SCA_VULN",
                            severity=cve_info["severity"],
                            target=f"{file_path} ({pkg_name}=={version})",
                            rule_id=cve_info["cve"],
                            description=f"Package {pkg_name} versi {version} rentan terhadap eksploitasi keamanan.",
                            remediation=f"Upgrade {pkg_name} ke versi {cve_info['fix']} atau lebih baru."
                        ))
        return findings


class DevSecOpsGate:
    """Aggregator dan Policy Decision Point (PDP) untuk integrasi build pipeline."""

    SEVERITY_WEIGHTS = {
        "CRITICAL": 10.0,
        "HIGH": 5.0,
        "MEDIUM": 2.0,
        "LOW": 0.5
    }

    def __init__(self, max_allowed_risk: float = 8.0, block_on_critical: bool = True):
        self.max_allowed_risk = max_allowed_risk
        self.block_on_critical = block_on_critical

    def evaluate(self, findings: List[SecurityFinding]) -> Tuple[bool, float, Dict[str, int]]:
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        total_risk = 0.0

        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
            total_risk += self.SEVERITY_WEIGHTS.get(f.severity, 0.0)

        # Evaluasi Policy Gate
        gate_passed = True
        if self.block_on_critical and counts["CRITICAL"] > 0:
            gate_passed = False
        elif total_risk > self.max_allowed_risk:
            gate_passed = False

        return gate_passed, total_risk, counts


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}============================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  AUTOMATED DEVSECOPS AUDIT & INFRASTRUCTURE HARDENING LAB  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}============================================================{CLR_RESET}\n")

    # 1. Setup Mock Assets dalam CI Pipeline
    mock_app_code = """
import os
import boto3

# Insecure Hardcoded API Key
AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE"
API_AUTH_TOKEN = "a7f3b89c0e2d14892c90df1b8e4f5a6b7c8d9e0f"

def init_s3():
    return boto3.client('s3', aws_access_key_id=AWS_SECRET_KEY)
"""

    mock_dockerfile = """
FROM python:latest
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Warning: Running as root by default, missing USER and HEALTHCHECK
CMD ["python", "app.py"]
"""

    mock_k8s_pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "payment-service"},
        "spec": {
            "securityContext": {
                "readOnlyRootFilesystem": False,
                "privileged": True
            },
            "containers": [{"name": "payment-api", "image": "payment:v1.0.0"}]
        }
    }

    mock_requirements = """
flask==2.3.2
urllib3==1.26.15
requests==2.28.1
cryptography==40.0.1
"""

    all_findings: List[SecurityFinding] = []

    # 2. Scanning Phase
    print(f"{CLR_BLUE}[+] Menjalankan Secret Scanner Engine...{CLR_RESET}")
    secret_scanner = SecretScanner()
    all_findings.extend(secret_scanner.scan("src/config.py", mock_app_code))

    print(f"{CLR_BLUE}[+] Menjalankan IaC & Container Hardening Linter...{CLR_RESET}")
    iac_engine = IaCHardeningEngine()
    all_findings.extend(iac_engine.audit_dockerfile("Dockerfile", mock_dockerfile))
    all_findings.extend(iac_engine.audit_manifest("deploy/pod.json", mock_k8s_pod))

    print(f"{CLR_BLUE}[+] Menjalankan SCA Dependency Vulnerability Matcher...{CLR_RESET}")
    sca_engine = VulnerabilityEngine()
    all_findings.extend(sca_engine.scan_dependencies("requirements.txt", mock_requirements))

    time.sleep(0.5) # Simulasi processing delay

    # 3. Presentasi Temuan
    print(f"\n{CLR_BOLD}--- DETAIL HASIL AUDIT KEAMANAN ---{CLR_RESET}")
    for item in all_findings:
        sev_color = {
            "CRITICAL": CLR_RED + CLR_BOLD,
            "HIGH": CLR_RED,
            "MEDIUM": CLR_YELLOW,
            "LOW": CLR_CYAN
        }.get(item.severity, CLR_RESET)

        print(f"[{sev_color}{item.severity:<8}{CLR_RESET}] [{item.category:<12}] {CLR_BOLD}{item.target}{CLR_RESET}")
        print(f"  Rule ID    : {item.rule_id}")
        print(f"  Deskripsi  : {item.description}")
        print(f"  Rekomendasi: {CLR_GREEN}{item.remediation}{CLR_RESET}")
        print("-" * 60)

    # 4. CI/CD Gate Evaluation
    gate = DevSecOpsGate(max_allowed_risk=15.0, block_on_critical=True)
    passed, total_score, breakdown = gate.evaluate(all_findings)

    print(f"\n{CLR_BOLD}=== RINGKASAN SECURITY GATE EVALUATION ==={CLR_RESET}")
    print(f"Total Temuan : {len(all_findings)}")
    print(f"Breakdown    : CRITICAL={breakdown['CRITICAL']}, HIGH={breakdown['HIGH']}, "
          f"MEDIUM={breakdown['MEDIUM']}, LOW={breakdown['LOW']}")
    print(f"Risk Score   : {CLR_BOLD}{total_score:.1f}{CLR_RESET} (Maksimum Diizinkan: {gate.max_allowed_risk:.1f})")

    if passed:
        print(f"\nStatus Pipeline: {CLR_GREEN}{CLR_BOLD}[PASSED] Memenuhi batas minimum compliance standar devops.{CLR_RESET}\n")
    else:
        print(f"\nStatus Pipeline: {CLR_RED}{CLR_BOLD}[FAILED] BUILD DIBLOKIR! Ditemukan pelanggaran keamanan kritis.{CLR_RESET}")
        print(f"{CLR_YELLOW}Tindakan: Perbaiki temuan CRITICAL dan turunkan risk score sebelum merge ke main branch.{CLR_RESET}\n")


if __name__ == "__main__":
    main()