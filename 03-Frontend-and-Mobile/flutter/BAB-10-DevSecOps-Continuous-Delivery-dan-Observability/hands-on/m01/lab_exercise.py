#!/usr/bin/env python3
"""
Lab Exercise: Flutter DevSecOps, Continuous Delivery, and Observability Simulator
BAB-10: DevSecOps, Continuous Delivery, dan Observability

Simulasi interaktif pipeline CI/CD, audit keamanan (SAST/Secret Scanning),
distribusi artifact (Fastlane), serta monitoring observability (OpenTelemetry/Sentry).
"""

import os
import sys
import time
import json
import random
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# ANSI Color formatting
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"

@dataclass
class SecurityFinding:
    severity: str
    file_path: str
    rule_id: str
    description: str

@dataclass
class TelemetrySpan:
    trace_id: str
    span_id: str
    operation: str
    duration_ms: float
    status: str
    attributes: Dict[str, Any]

class DevSecOpsEngine:
    def __init__(self):
        self.pipeline_stage = "IDLE"
        self.findings: List[SecurityFinding] = []
        self.traces: List[TelemetrySpan] = []

    def log_step(self, stage: str, message: str, delay: float = 0.3):
        print(f"{Style.CYAN}[{stage}]{Style.RESET} {message}")
        time.sleep(delay)

    def log_success(self, message: str):
        print(f"  {Style.GREEN}✔ {message}{Style.RESET}")

    def log_warning(self, message: str):
        print(f"  {Style.YELLOW}⚠ {message}{Style.RESET}")

    def log_error(self, message: str):
        print(f"  {Style.RED}✖ {message}{Style.RESET}")

    def run_security_scan(self) -> bool:
        print(f"\n{Style.BOLD}{Style.MAGENTA}=== [FASE 1] SAST & Secret Scanning Security Gate ==={Style.RESET}")
        self.log_step("SAST", "Menginisialisasi pemindaian kode sumber Dart & manifest...")
        
        sample_scanned_files = [
            "lib/main.dart",
            "lib/services/api_client.dart",
            "android/app/build.gradle",
            "ios/Runner/Info.plist"
        ]
        
        for file in sample_scanned_files:
            self.log_step("SCAN", f"Menganalisis AST & pattern rule: {file}", delay=0.15)

        self.findings = [
            SecurityFinding(
                severity="HIGH",
                file_path="lib/services/api_client.dart",
                rule_id="SEC-004",
                description="Hardcoded API bearer token ditemukan dalam string literal."
            ),
            SecurityFinding(
                severity="MEDIUM",
                file_path="android/app/build.gradle",
                rule_id="SEC-012",
                description="AllowBackup disetel ke true tanpa custom backup rules."
            )
        ]

        print(f"\n{Style.BOLD}Hasil Audit Keamanan:{Style.RESET}")
        for finding in self.findings:
            if finding.severity == "HIGH":
                self.log_error(f"[{finding.severity}] {finding.rule_id}: {finding.description} ({finding.file_path})")
            else:
                self.log_warning(f"[{finding.severity}] {finding.rule_id}: {finding.description} ({finding.file_path})")

        print(f"\n{Style.YELLOW}Opsi Remediasi Keamanan:{Style.RESET}")
        print("  [1] Lakukan auto-patch (Gunakan secure_storage & env secrets)")
        print("  [2] Bypass (Tolak pipeline - Policy Failure)")
        choice = input(f"{Style.BOLD}Pilih tindakan remediation [1/2]: {Style.RESET}").strip()

        if choice == "1":
            self.log_step("PATCH", "Menerapkan flutter_secure_storage dan memindahkan secret ke CI vault...")
            self.log_success("Kerentanan HIGH berhasil ditutup! Zero critical issues remaining.")
            return True
        else:
            self.log_error("Pipeline diblokir oleh Security Gate. Status: FAILED.")
            return False

    def run_cd_build_and_release(self):
        print(f"\n{Style.BOLD}{Style.BLUE}=== [FASE 2] Continuous Delivery & Release Automation ==={Style.RESET}")
        self.log_step("FASTLANE", "Membaca Fastfile untuk flavor: production")
        self.log_step("KEYSTORE", "Mendekripsi Android release keystore & iOS provisioning profiles via Fastlane Match...")
        self.log_success("Sertifikat dan signing identities terverifikasi.")

        targets = [
            ("Android App Bundle (AAB)", "flutter build appbundle --release --obfuscate --split-debug-info=symbols/"),
            ("iOS IPA Archive", "flutter build ipa --release --export-options-plist=ExportOptions.plist")
        ]

        for target_name, cmd in targets:
            self.log_step("BUILD", f"Mengompilasi {target_name}...")
            print(f"    {Style.WHITE}Exec: {cmd}{Style.RESET}")
            time.sleep(0.4)
            self.log_success(f"{target_name} siap. Ukuran binary dioptimasi via Tree-Shaking.")

        self.log_step("UPLOAD", "Mengunggah build artifacts ke Google Play Internal App Sharing & Apple TestFlight...")
        time.sleep(0.3)
        self.log_success("Release v1.4.0 (Build 42) berhasil didistribusikan ke tester!")

    def run_observability_suite(self):
        print(f"\n{Style.BOLD}{Style.CYAN}=== [FASE 3] Observability, Tracing, & Crash Reporting ==={Style.RESET}")
        self.log_step("OTEL", "Menginisialisasi OpenTelemetry SDK & Sentry Tracing Bridge...")
        
        trace_id = f"trc-{random.randint(100000, 999999)}"
        operations = [
            ("AppBootstrap", 145.2, "OK"),
            ("AuthService.login", 310.8, "OK"),
            ("Dio.interceptors.request", 88.4, "OK"),
            ("ProductCatalog.fetchRemoteData", 420.5, "OK"),
            ("RenderSliverList.layout", 16.7, "OK")
        ]

        print(f"\n{Style.BOLD}Distributed Traces Captured:{Style.RESET}")
        for op, dur, status in operations:
            span_id = f"spn-{random.randint(1000, 9999)}"
            span = TelemetrySpan(
                trace_id=trace_id,
                span_id=span_id,
                operation=op,
                duration_ms=dur,
                status=status,
                attributes={"device": "Pixel 7 Pro", "flutter.version": "3.27.0"}
            )
            self.traces.append(span)
            
            perf_color = Style.GREEN if dur < 200 else Style.YELLOW
            print(f"  TraceID: {span.trace_id} | Span: {span.span_id} | {span.operation:<30} | {perf_color}{span.duration_ms:6.1f} ms{Style.RESET} | [{span.status}]")
            time.sleep(0.1)

        print(f"\n{Style.BOLD}Simulasi Crashlytics / Error Sentinel:{Style.RESET}")
        self.log_warning("Simulasi unhandled exception di zone runZonedGuarded...")
        time.sleep(0.2)
        print(f"  {Style.RED}StateError: Bad state: Stream has already been listened to.{Style.RESET}")
        self.log_step("SENTRY", "Mengunggah crash breadcrumbs dan symbolication mapping file (ProGuard/dSYM)...")
        self.log_success("Crash event ID: evt-9921 disinkronisasi ke dashboard Observability!")

    def export_telemetry_report(self):
        filename = "devsecops_telemetry_dump.json"
        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pipeline": "Flutter Enterprise CI/CD",
            "security_findings": [asdict(f) for f in self.findings],
            "telemetry_spans": [asdict(t) for t in self.traces]
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.log_success(f"Laporan telemetri berhasil diekspor ke: {filename}")

def main():
    os.system("clear" if os.name == "posix" else "cls")
    print(f"{Style.BOLD}{Style.CYAN}================================================================={Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}  FLUTTER DEVSECOPS, CONTINUOUS DELIVERY & OBSERVABILITY LAB   {Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}================================================================={Style.RESET}")
    print(f"{Style.WHITE}Materi Praktik: Pemindaian Keamanan, Fastlane Build, & Observability{Style.RESET}\n")

    engine = DevSecOpsEngine()

    while True:
        print(f"\n{Style.BOLD}Menu Simulasi DevSecOps:{Style.RESET}")
        print("  [1] Jalankan Pemindaian Keamanan SAST & Secret Scanner")
        print("  [2] Jalankan CD Build & Release Artifact (Fastlane Simulation)")
        print("  [3] Jalankan Observability Suite (Tracing & Crashlytics)")
        print("  [4] Jalankan Full End-to-End Pipeline (1 -> 2 -> 3)")
        print("  [5] Ekspor Telemetri JSON & Keluar")
        
        choice = input(f"\n{Style.BOLD}Pilih opsi [1-5]: {Style.RESET}").strip()

        if choice == "1":
            engine.run_security_scan()
        elif choice == "2":
            engine.run_cd_build_and_release()
        elif choice == "3":
            engine.run_observability_suite()
        elif choice == "4":
            passed = engine.run_security_scan()
            if passed:
                engine.run_cd_build_and_release()
                engine.run_observability_suite()
                print(f"\n{Style.BG_GREEN}{Style.BOLD} ALL PIPELINE GATES PASSED! READY FOR PRODUCTION DEPLOYMENT {Style.RESET}")
            else:
                print(f"\n{Style.BG_RED}{Style.BOLD} PIPELINE ABORTED: Security standards not fulfilled {Style.RESET}")
        elif choice == "5":
            engine.export_telemetry_report()
            print(f"\n{Style.GREEN}Sesi lab selesai. Terima kasih.{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan coba lagi.{Style.RESET}")

if __name__ == "__main__":
    main()
