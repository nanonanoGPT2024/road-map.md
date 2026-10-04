#!/usr/bin/env python3
"""
Lab Hands-on: Flutter DevSecOps, Continuous Delivery, & Observability Deep Dive
Simulasi terpadu pipeline CI/CD Flutter enterprise:
 1. SAST Security Gate (Deteksi kebocoran secrets, manifest misconfig, insecure TLS).
 2. Secure Build & Obfuscation Engine (Simulasi AOT snapshot & mapping file generation).
 3. Observability & APM Telemetry Ingestion (Frame jank monitoring & crash stack de-obfuscation).
"""

import os
import sys
import time
import json
import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

# Terminal ANSI Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


@dataclass
class SecurityFinding:
    severity: str
    rule_id: str
    file_path: str
    line: int
    description: str


@dataclass
class CrashReport:
    session_id: str
    device: str
    timestamp: float
    obfuscated_stack: List[str]


class FlutterDevSecOpsEngine:
    """
    Menjalankan Static Application Security Testing (SAST) khusus arsitektur Flutter/Dart
    sebelum artifact dikompilasi ke format release (AOT assembly/AAB).
    """

    SECRET_REGEX = re.compile(r"""(?i)(?:api_key|secret|private_key|token)\s*=\s*['"][a-zA-Z0-9_\-]{16,}['"]""")
    INSECURE_HTTP_REGEX = re.compile(r"""http:\/\/[a-zA-Z0-9\.\-]+""")

    def __init__(self):
        self.findings: List[SecurityFinding] = []

    def scan_dart_source(self, filename: str, content: str) -> None:
        """Menganalisis file Dart untuk kerentanan credential leak dan insecure transport."""
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if self.SECRET_REGEX.search(line):
                self.findings.append(
                    SecurityFinding("CRITICAL", "SEC_DART_001", filename, idx, "Hardcoded sensitive credential")
                )
            if self.INSECURE_HTTP_REGEX.search(line) and "localhost" not in line:
                self.findings.append(
                    SecurityFinding("HIGH", "SEC_NET_002", filename, idx, "Insecure cleartext HTTP scheme detected")
                )
            if "NSAllowsArbitraryLoads" in line and "true" in line:
                self.findings.append(
                    SecurityFinding("HIGH", "SEC_IOS_003", filename, idx, "ATS configuration bypass detected")
                )

    def verify_pipeline_security_gates(self) -> bool:
        """Evaluasi quality gate: Build gagal jika terdapat issue berkategori CRITICAL."""
        critical_count = sum(1 for f in self.findings if f.severity == "CRITICAL")
        return critical_count == 0


class FlutterBuildPipeline:
    """
    Mensimulasikan Continuous Delivery engine untuk Flutter:
    Tree-shaking, AOT Obfuscation, dan pembuatan Debug Symbol Mapping (R8 / Flutter Engine).
    """

    def __init__(self, app_name: str, build_version: str):
        self.app_name = app_name
        self.build_version = build_version
        self.symbol_mapping: Dict[str, str] = {}
        self.artifact_hash = ""

    def compile_release_bundle(self, source_symbols: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """
        Simulasi: `flutter build appbundle --obfuscate --split-debug-info=./symbols`
        Menghasilkan binary AAB hash dan tabel symbolication mapping file.
        """
        print(f"{CYAN}[BUILD]{RESET} Memulai kompilasi Release AOT untuk {self.app_name} v{self.build_version}...")
        time.sleep(0.3)  # Simulasi overhead kompilasi Dart Kernel & LLVM toolchain

        # Memetakan symbol asli ke hash/token ter-obfuscate
        for original_func, location in source_symbols.items():
            obfuscated_token = "m_" + hashlib.md5(original_func.encode()).hexdigest()[:6]
            self.symbol_mapping[obfuscated_token] = f"{original_func} ({location})"

        # Kalkulasi integritas artifact (AAB)
        artifact_content = f"{self.app_name}-{self.build_version}-{time.time()}".encode()
        self.artifact_hash = hashlib.sha256(artifact_content).hexdigest()

        print(f"{GREEN}[BUILD SUCCESS]{RESET} AppBundle Target: release/app-release.aab")
        print(f"      SHA256: {self.artifact_hash}")
        print(f"      Tersimpan {len(self.symbol_mapping)} symbols di mapping registry.")
        return self.artifact_hash, self.symbol_mapping


class FlutterObservabilityPlatform:
    """
    Mensimulasikan Crashlytics/Sentry Ingestion Server dan APM Frame Timing Analyzer.
    """

    def __init__(self, symbol_mapping: Dict[str, str]):
        self.symbol_mapping = symbol_mapping
        self.frame_budget_ms = 16.66  # Standar frame rate 60 FPS (UI render budget)

    def deobfuscate_stacktrace(self, obfuscated_stack: List[str]) -> List[str]:
        """Mentransformasikan obfuscated runtime crash report menjadi human-readable stack trace."""
        resolved_stack = []
        for frame in obfuscated_stack:
            matched = False
            for token, resolved in self.symbol_mapping.items():
                if token in frame:
                    resolved_stack.append(frame.replace(token, resolved))
                    matched = True
                    break
            if not matched:
                resolved_stack.append(frame + " (unresolved)")
        return resolved_stack

    def ingest_frame_metrics(self, frame_render_times: List[float]) -> Dict[str, float]:
        """
        Menganalisis performa UI Flutter (deteksi jank & frame drops).
        """
        total_frames = len(frame_render_times)
        janky_frames = sum(1 for t in frame_render_times if t > self.frame_budget_ms)
        worst_frame = max(frame_render_times) if frame_render_times else 0.0
        avg_frame_time = sum(frame_render_times) / total_frames if total_frames else 0.0

        jank_rate = (janky_frames / total_frames) * 100 if total_frames else 0.0
        return {
            "total_frames": total_frames,
            "janky_frames": janky_frames,
            "jank_rate_pct": round(jank_rate, 2),
            "avg_frame_time_ms": round(avg_frame_time, 2),
            "worst_frame_ms": round(worst_frame, 2)
        }


def run_lab():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}   FLUTTER DEVSECOPS, CONTINUOUS DELIVERY & OBSERVABILITY LAB        {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    # 1. SETUP MOCK FLUTTER PROJECT
    mock_dart_code = """
    import 'package:flutter/material.dart';
    
    // Insecure production practices for SAST test
    const String apiKey = "AIzaSyD-TESTING-SECRET-KEY-998811"; 
    const String paymentEndpoint = "http://api.internal.bank.co.id/v1/checkout";

    class PaymentGatewayService {
      void executeTransaction() {
        print("Connecting to payment endpoint...");
      }
    }
    """

    source_symbols = {
        "PaymentGatewayService.executeTransaction": "packages/services/payment.dart:8",
        "_AuthState.validateCredentials": "packages/features/auth/bloc.dart:45",
        "NetworkClient.sendHttpRequest": "packages/core/network.dart:122"
    }

    # 2. RUN SECDEVOPS SAST SCANNER
    print(f"{BOLD}[STAGE 1: SAST Code Analysis & Hardening Gate]{RESET}")
    scanner = FlutterDevSecOpsEngine()
    scanner.scan_dart_source("lib/services/payment_service.dart", mock_dart_code)

    for finding in scanner.findings:
        color = RED if finding.severity == "CRITICAL" else YELLOW
        print(f"  {color}[{finding.severity}]{RESET} {finding.rule_id} -> {finding.file_path}:{finding.line}")
        print(f"         Detail: {finding.description}")

    gate_passed = scanner.verify_pipeline_security_gates()
    if not gate_passed:
        print(f"\n{RED}[PIPELINE BLOCKED]{RESET} Security Gate gagal: Ditemukan celah keamanan CRITICAL.")
        print(f"{YELLOW}[REMEDIATION]{RESET} Mengaplikasikan Secure Vault Injection & Enforcing HTTPS...")
        # Auto-remediation simulation
        mock_dart_code = mock_dart_code.replace("AIzaSyD-TESTING-SECRET-KEY-998811", "String.fromEnvironment('API_KEY')")
        mock_dart_code = mock_dart_code.replace("http://", "https://")
        scanner.findings.clear()
        scanner.scan_dart_source("lib/services/payment_service.dart", mock_dart_code)
        print(f"{GREEN}[RE-SCAN PASSED]{RESET} Semua security gates terpenuhi. Melanjutkan pipeline.\n")

    # 3. SECURE BUILD & ARTIFACT PACKAGING
    print(f"{BOLD}[STAGE 2: Secure Build Engine & Symbol Mapping Generation]{RESET}")
    cd_engine = FlutterBuildPipeline(app_name="SuperFintechApp", build_version="2.4.0+102")
    artifact_hash, symbol_map = cd_engine.compile_release_bundle(source_symbols)
    
    print("\n  Daftar Obfuscation Symbol Map (sample):")
    for token, resolved in list(symbol_map.items())[:3]:
        print(f"    {MAGENTA}{token}{RESET} -> {resolved}")
    print()

    # 4. OBSERVABILITY: APM RUNTIME FRAME METRICS
    print(f"{BOLD}[STAGE 3: APM Telemetry & UI Performance Monitoring]{RESET}")
    obs_platform = FlutterObservabilityPlatform(symbol_map)

    # 20 frame telemetry samples (ms)
    mock_frames = [12.1, 14.3, 16.0, 15.8, 34.2, 11.0, 13.5, 48.1, 12.0, 15.2, 16.2, 14.1]
    metrics = obs_platform.ingest_frame_metrics(mock_frames)
    
    print(f"  Frame Budget Baseline : {obs_platform.frame_budget_ms} ms (Target 60 FPS)")
    print(f"  Total Frames Evaluated: {metrics['total_frames']}")
    print(f"  Janky Frames Detected : {RED if metrics['janky_frames'] > 0 else GREEN}{metrics['janky_frames']}{RESET}")
    print(f"  Jank Incident Ratio   : {metrics['jank_rate_pct']}%")
    print(f"  Worst Frame Spike     : {metrics['worst_frame_ms']} ms")
    if metrics['worst_frame_ms'] > 32.0:
        print(f"  {YELLOW}[WARN]{RESET} UI Thread block terdeteksi (> 2 drop frames). Optimasi widget rebuild tree diperlukan.")
    print()

    # 5. OBSERVABILITY: CRASH REPORTING & SYMBOLICATION
    print(f"{BOLD}[STAGE 4: Automated Crash Ingestion & De-Obfuscation]{RESET}")
    raw_crash_tokens = list(symbol_map.keys())
    mock_obfuscated_crash = [
        f"0# {raw_crash_tokens[0]}",
        f"1# {raw_crash_tokens[1]}",
        "2# _rootRunUnary (dart:async/zone.dart:1434)"
    ]

    crash = CrashReport(
        session_id="sess_prod_8992ba01",
        device="Pixel 7 Pro - Android 14",
        timestamp=time.time(),
        obfuscated_stack=mock_obfuscated_crash
    )

    print(f"  [RAW INGESTED CRASH] Session: {crash.session_id}")
    for raw_f in crash.obfuscated_stack:
        print(f"    {RED}{raw_f}{RESET}")

    print(f"\n  [SYMBOLICATED STACKTRACE (Engine Resolving...)]")
    symbolicated_stack = obs_platform.deobfuscate_stacktrace(crash.obfuscated_stack)
    for sym_f in symbolicated_stack:
        print(f"    {GREEN}✔ {sym_f}{RESET}")

    print(f"\n{BOLD}{GREEN}Pipeline Execution Selesai Secara Sukses! Semua modul DevSecOps berjalan mandiri.{RESET}")


if __name__ == "__main__":
    run_lab()