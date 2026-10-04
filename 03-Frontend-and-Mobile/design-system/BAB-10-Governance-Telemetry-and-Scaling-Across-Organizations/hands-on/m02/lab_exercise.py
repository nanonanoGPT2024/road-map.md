#!/usr/bin/env python3
"""
Lab Hands-on: Design System Governance, Telemetry, and Scaling Engine
Topic: 03-Frontend-and-Mobile | Chapter 10: Governance, Telemetry & Scaling
Module 02 Deep Dive: Telemetry Ingest, Adoption Scoring & CI/CD Governance Gate
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# ANSI Escape Sequences untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[38;5;196m"
CLR_GREEN = "\033[38;5;46m"
CLR_YELLOW = "\033[38;5;220m"
CLR_BLUE = "\033[38;5;39m"
CLR_MAGENTA = "\033[38;5;201m"
CLR_CYAN = "\033[38;5;51m"
CLR_GRAY = "\033[38;5;244m"


@dataclass
class ComponentSpec:
    """Spesifikasi kanonikal komponen pada Design System Registry."""
    name: str
    version: str
    status: str  # 'STABLE', 'DEPRECATED', 'EXPERIMENTAL'
    replacement: Optional[str] = None
    sla_tier: str = "TIER_1"


@dataclass
class TelemetryPayload:
    """Payload telemetri AST (Abstract Syntax Tree) dari scanner micro-frontend."""
    repo_name: str
    file_path: str
    component_name: str
    version_imported: str
    token_compliance: bool      # True jika styling memakai Design Tokens resmi
    hardcoded_styles: int       # Jumlah deteksi hardcoded hex/inline override (detachment)
    props_overrides: List[str] = field(default_factory=list)


class DesignSystemRegistry:
    """Registry pusat Design System yang mengatur governance dan lifecycle kontrak komponen."""
    def __init__(self):
        self.catalog: Dict[str, ComponentSpec] = {
            "DSButton": ComponentSpec("DSButton", "3.2.0", "STABLE"),
            "DSTextInput": ComponentSpec("DSTextInput", "3.1.0", "STABLE"),
            "DSModal": ComponentSpec("DSModal", "2.8.0", "STABLE"),
            "OldDropdown": ComponentSpec("OldDropdown", "1.0.0", "DEPRECATED", replacement="DSSelect"),
            "DSSelect": ComponentSpec("DSSelect", "2.1.0", "STABLE"),
            "LegacyCard": ComponentSpec("LegacyCard", "0.9.0", "DEPRECATED", replacement="DSCard"),
            "DSCard": ComponentSpec("DSCard", "2.4.0", "STABLE"),
            "DataGridBeta": ComponentSpec("DataGridBeta", "0.1.0-alpha", "EXPERIMENTAL"),
        }

    def evaluate_component(self, name: str) -> Optional[ComponentSpec]:
        return self.catalog.get(name)


class TelemetryIngestPipeline:
    """
    Simulasi telemetry collector throughput tinggi yang menerima,
    memvalidasi, dan mengagregasi metrics penggunaan DS dari berbagai repositori.
    """
    def __init__(self, registry: DesignSystemRegistry):
        self.registry = registry
        self.raw_events: List[TelemetryPayload] = []

    def ingest_batch(self, payloads: List[TelemetryPayload]) -> int:
        """Memproses batch event melalui worker thread pool."""
        def _process(payload: TelemetryPayload) -> TelemetryPayload:
            # Simulasi validasi payload & checksum
            time.sleep(random.uniform(0.01, 0.03))
            return payload

        with ThreadPoolExecutor(max_workers=4) as executor:
            processed = list(executor.map(_process, payloads))
            self.raw_events.extend(processed)
        return len(processed)


class GovernanceEngine:
    """
    Analisis statistik, kepatuhan arsitektur, dan kalkulasi technical debt score
    berdasarkan telemetri penggunaan komponen di seluruh organisasi.
    """
    def __init__(self, registry: DesignSystemRegistry, events: List[TelemetryPayload]):
        self.registry = registry
        self.events = events

    def compute_repo_health(self, repo_name: str) -> Dict[str, any]:
        repo_events = [e for e in self.events if e.repo_name == repo_name]
        if not repo_events:
            return {}

        total_components = len(repo_events)
        deprecated_hits = 0
        detached_styles_count = 0
        token_compliant_hits = 0

        for ev in repo_events:
            spec = self.registry.evaluate_component(ev.component_name)
            if spec and spec.status == "DEPRECATED":
                deprecated_hits += 1
            if ev.token_compliance:
                token_compliant_hits += 1
            detached_styles_count += ev.hardcoded_styles

        # Formula Skor Adopsi: Rata-rata bobot Token Compliance & Zero Deprecation
        deprecation_penalty = (deprecated_hits / total_components) * 40.0
        token_score = (token_compliant_hits / total_components) * 60.0
        detachment_penalty = min(detached_styles_count * 2.0, 20.0)

        health_score = max(0.0, min(100.0, (token_score + (40.0 - deprecation_penalty)) - detachment_penalty))

        return {
            "repo": repo_name,
            "total_usages": total_components,
            "deprecated_count": deprecated_hits,
            "token_compliance_rate": (token_compliant_hits / total_components) * 100.0,
            "detachment_violations": detached_styles_count,
            "health_score": round(health_score, 2),
            "gate_passed": health_score >= 75.0 and deprecated_hits == 0
        }


def generate_mock_telemetry(repos: List[str], count_per_repo: int) -> List[TelemetryPayload]:
    """Menghasilkan telemetry AST sintetis merepresentasikan pemindaian kode frontend."""
    components_pool = [
        ("DSButton", "3.2.0", True, 0),
        ("DSTextInput", "3.1.0", True, 1),
        ("DSModal", "2.8.0", True, 0),
        ("DSCard", "2.4.0", True, 0),
        ("OldDropdown", "1.0.0", False, 3),    # Pelanggaran: Deprecated + detached
        ("LegacyCard", "0.9.0", False, 4),     # Pelanggaran: Deprecated
        ("DSSelect", "2.1.0", True, 0),
        ("DataGridBeta", "0.1.0-alpha", False, 2)
    ]
    
    payloads = []
    for repo in repos:
        for i in range(count_per_repo):
            c_name, ver, compliance, detach_base = random.choice(components_pool)
            # Acak noise deviasi detasemen token
            overrides = random.randint(detach_base, detach_base + random.choice([0, 1, 2]))
            payloads.append(TelemetryPayload(
                repo_name=repo,
                file_path=f"src/features/module_{i % 5}/view_{i}.tsx",
                component_name=c_name,
                version_imported=ver,
                token_compliance=(compliance and overrides == 0),
                hardcoded_styles=overrides,
                props_overrides=["!important-css-hack"] if overrides > 2 else []
            ))
    return payloads


def print_banner():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}    ENTERPRISE DESIGN SYSTEM GOVERNANCE & TELEMETRY ENGINE           {CLR_RESET}")
    print(f"{CLR_GRAY}    Scaling & Continuous Compliance Pipeline across Micro-Frontends  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")


def print_progress_bar(iteration: int, total: int, prefix: str = '', suffix: str = '', length: int = 30):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = "█" * filled_length + "░" * (length - filled_length)
    sys.stdout.write(f"\r{CLR_GRAY}{prefix} |{CLR_BLUE}{bar}{CLR_GRAY}| {percent}% {suffix}{CLR_RESET}")
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write("\n")


def main():
    print_banner()

    # 1. Inisialisasi Canonical Registry
    print(f"{CLR_BOLD}[1/4] Memuat Canonical Component Registry & Deprecation Rules...{CLR_RESET}")
    registry = DesignSystemRegistry()
    for name, spec in registry.catalog.items():
        status_color = CLR_GREEN if spec.status == "STABLE" else (CLR_RED if spec.status == "DEPRECATED" else CLR_YELLOW)
        replace_info = f"-> Replace with: {spec.replacement}" if spec.replacement else ""
        print(f"  • {spec.name:<14} [{spec.version}] Status: {status_color}{spec.status:<11}{CLR_RESET} {CLR_GRAY}{replace_info}{CLR_RESET}")
    print()

    # 2. Ingesti Telemetri dari Scanner Repositori Organisasi
    micro_frontends = ["checkout-web", "merchant-portal", "auth-shell", "analytics-mfe"]
    print(f"{CLR_BOLD}[2/4] Menjalankan Telemetry Ingestion Workers (Async Batch)...{CLR_RESET}")
    
    mock_events = generate_mock_telemetry(micro_frontends, count_per_repo=35)
    pipeline = TelemetryIngestPipeline(registry)
    
    batch_size = 35
    total_events = len(mock_events)
    for i in range(0, total_events, batch_size):
        chunk = mock_events[i:i + batch_size]
        pipeline.ingest_batch(chunk)
        print_progress_bar(min(i + batch_size, total_events), total_events, prefix="Ingesting AST Telemetry", suffix="Complete")

    print(f"{CLR_GREEN}✓ Berhasil menelan {len(pipeline.raw_events)} events dari {len(micro_frontends)} repositori.{CLR_RESET}\n")

    # 3. Analisis Kepatuhan & Perhitungan Health Metrics
    print(f"{CLR_BOLD}[3/4] Menganalisis Kepatuhan Token & Detachment Metric...{CLR_RESET}")
    engine = GovernanceEngine(registry, pipeline.raw_events)
    results = [engine.compute_repo_health(repo) for repo in micro_frontends]

    # Render Tabel Matriks
    col_fmt = "{:<18} | {:<8} | {:<12} | {:<14} | {:<12} | {:<10}"
    print(CLR_BOLD + col_fmt.format("Repository", "Usages", "Deprecated", "Token Compl.", "Detached CSS", "Health") + CLR_RESET)
    print("-" * 86)

    for r in results:
        h_color = CLR_GREEN if r["health_score"] >= 80 else (CLR_YELLOW if r["health_score"] >= 65 else CLR_RED)
        dep_color = CLR_RED if r["deprecated_count"] > 0 else CLR_GREEN
        print(col_fmt.format(
            r["repo"],
            r["total_usages"],
            f"{dep_color}{r['deprecated_count']}{CLR_RESET}",
            f"{r['token_compliance_rate']:.1f}%",
            f"{r['detachment_violations']} overrides",
            f"{h_color}{r['health_score']:.1f} / 100{CLR_RESET}"
        ))
    print()

    # 4. CI/CD Governance Deployment Gate
    print(f"{CLR_BOLD}[4/4] Mengeksekusi CI/CD Quality Gate (Deployment Policy)...{CLR_RESET}")
    print(f"{CLR_GRAY}Kebijakan: Health Score >= 75.0 DAN 0 Pemanggilan Komponen Deprecated.{CLR_RESET}\n")

    gate_all_passed = True
    for r in results:
        if r["gate_passed"]:
            status_badge = f"{CLR_GREEN}[PASSED]{CLR_RESET}"
            msg = "Memenuhi SLA Design System. Siap deploy."
        else:
            gate_all_passed = False
            status_badge = f"{CLR_RED}[BLOCKED]{CLR_RESET}"
            msg = f"Ditemukan {r['deprecated_count']} komponen usang atau pelanggaran token parah."

        print(f"  {status_badge} {CLR_BOLD}{r['repo']:<16}{CLR_RESET} -> {msg}")

    print("\n" + "=" * 70)
    if gate_all_passed:
        print(f"{CLR_BOLD}{CLR_GREEN}RESULT: Seluruh micro-frontend lolos Governance Audit.{CLR_RESET}")
        sys.exit(0)
    else:
        print(f"{CLR_BOLD}{CLR_YELLOW}RESULT: Audit menemukan technical debt yang melanggar SLA Design System.{CLR_RESET}")
        print(f"{CLR_GRAY}Gunakan panduan migrasi registry untuk memperbaiki komponen terdampak.{CLR_RESET}")
        sys.exit(0)  # Menghindari fatal crash pada demo/lab runner


if __name__ == "__main__":
    main()