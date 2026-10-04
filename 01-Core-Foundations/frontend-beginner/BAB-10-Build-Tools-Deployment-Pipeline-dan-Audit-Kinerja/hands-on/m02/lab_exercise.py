#!/usr/bin/env python3
"""
Lab Hands-on: Modern Build Tools, Deployment Pipeline & Audit Kinerja
Modul 02 Deep Dive - 01-Core-Foundations / frontend-beginner

Simulasi komprehensif sistem build pipeline frontend modern:
1. Static Dependency Graph & Tree-Shaking Engine
2. Code Minification & Content-Addressable Asset Hashing
3. CI/CD Deployment Pipeline Simulator
4. Lighthouse-Style Performance Audit (FCP, LCP, TBT, CLS & Performance Score)
"""

import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

# Terminal ANSI Color Formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


@dataclass
class SourceModule:
    path: str
    content: str
    exports: Dict[str, str]  # symbol_name -> code block
    imports: List[Tuple[str, str]]  # (source_path, imported_symbol)


@dataclass
class BuildArtifact:
    filename: str
    raw_content: str
    original_size: int
    minified_size: int
    content_hash: str


class ModernBundler:
    """
    Simulasi bundler modern (seperti Rollup/esbuild):
    Melakukan dependency graph resolution, static dead-code elimination (Tree-Shaking),
    minifikasi sederhana, dan content hashing untuk cache busting.
    """

    def __init__(self):
        self.modules: Dict[str, SourceModule] = {}

    def register_module(self, path: str, content: str, exports: Dict[str, str], imports: List[Tuple[str, str]]):
        self.modules[path] = SourceModule(path, content, exports, imports)

    def tree_shake_and_bundle(self, entry_point: str) -> BuildArtifact:
        """
        Menelusuri AST/Dependency references untuk mengekstrak hanya kode yang dipakai,
        mengeliminasi export yang tidak terpakai (dead-code).
        """
        if entry_point not in self.modules:
            raise ValueError(f"Entry module {entry_point} not found.")

        visited_symbols: Set[Tuple[str, str]] = set()
        queue: List[Tuple[str, str]] = []

        # Parse import dari entry module
        entry = self.modules[entry_point]
        for src, symbol in entry.imports:
            queue.append((src, symbol))
            visited_symbols.add((src, symbol))

        bundled_code = [f"// [Entry] {entry_point}", entry.content]

        # Tree shaking traversal
        while queue:
            current_src, symbol = queue.pop(0)
            if current_src in self.modules:
                mod = self.modules[current_src]
                if symbol in mod.exports:
                    code_block = mod.exports[symbol]
                    bundled_code.append(f"// [Exported] {current_src} -> {symbol}\n{code_block}")

        raw_bundle = "\n\n".join(bundled_code)
        minified = self._minify_js(raw_bundle)

        # Generasi Content-Based Hash (SHA-256 slice) untuk long-term HTTP caching
        content_hash = hashlib.sha256(minified.encode("utf-8")).hexdigest()[:8]
        filename = f"bundle.{content_hash}.js"

        return BuildArtifact(
            filename=filename,
            raw_content=minified,
            original_size=len(raw_bundle.encode("utf-8")),
            minified_size=len(minified.encode("utf-8")),
            content_hash=content_hash,
        )

    @staticmethod
    def _minify_js(code: str) -> str:
        """Menghapus komentar, trailing spaces, dan baris kosong berlebih."""
        # Hapus komentar multi-line & single-line
        code = re.sub(r"/\*[\s\S]*?\*/", "", code)
        code = re.sub(r"//.*", "", code)
        # Hapus spasi berlebih antar token
        lines = [line.strip() for line in code.splitlines() if line.strip()]
        return ";".join(lines).replace(";;", ";")


class PerformanceAuditor:
    """
    Simulasi Audit Engine (seperti Google Lighthouse / Web Vitals).
    Mengestimasi FCP, LCP, TBT, dan CLS berdasarkan payload size dan simulasi throttling.
    """

    # Ambang batas metrik (Core Web Vitals Thresholds)
    THRESHOLDS = {
        "FCP": {"good": 1800, "poor": 3000},    # ms
        "LCP": {"good": 2500, "poor": 4000},    # ms
        "TBT": {"good": 200, "poor": 600},      # ms
        "CLS": {"good": 0.1, "poor": 0.25},     # score
    }

    @classmethod
    def audit_artifact(cls, js_size_bytes: int, css_size_bytes: int, dom_nodes: int = 450) -> Dict[str, any]:
        """
        Menghitung estimasi performa sintetis menggunakan Fast 4G / Slow 4G profile:
        - Network Download Time = Payload / Bandwidth + RTT
        - Execution Time = Script Size * Execution Factor
        """
        # Profil: Fast 4G (1.6 Mbps = 200 KB/s, RTT 150ms)
        bandwidth_bytes_per_sec = 200 * 1024
        rtt_ms = 150.0

        total_bytes = js_size_bytes + css_size_bytes
        download_time_ms = (total_bytes / bandwidth_bytes_per_sec) * 1000 + rtt_ms

        # Estimasi CPU Parse + Compile + Execution
        execution_time_ms = (js_size_bytes / 1024) * 3.2  # ~3.2ms per KB pada mid-tier mobile

        # Web Vitals Metrics
        fcp = round(download_time_ms + (css_size_bytes / 1024) * 1.5, 1)
        lcp = round(fcp + execution_time_ms * 0.85, 1)
        tbt = round(max(0.0, execution_time_ms - 50.0), 1)
        cls = 0.045  # Statically computed layout stability

        # Hitung Lighthouse v10 Weighted Score
        # FCP (10%), LCP (25%), TBT (30%), CLS (25%), Speed Index / Other (10%)
        def score_metric(val: float, good: float, poor: float) -> float:
            if val <= good:
                return 1.0
            if val >= poor:
                return 0.0
            return max(0.0, 1.0 - (val - good) / (poor - good))

        s_fcp = score_metric(fcp, cls.THRESHOLDS["FCP"]["good"], cls.THRESHOLDS["FCP"]["poor"])
        s_lcp = score_metric(lcp, cls.THRESHOLDS["LCP"]["good"], cls.THRESHOLDS["LCP"]["poor"])
        s_tbt = score_metric(tbt, cls.THRESHOLDS["TBT"]["good"], cls.THRESHOLDS["TBT"]["poor"])
        s_cls = score_metric(cls, cls.THRESHOLDS["CLS"]["good"], cls.THRESHOLDS["CLS"]["poor"])

        overall_score = round((s_fcp * 0.10 + s_lcp * 0.25 + s_tbt * 0.30 + s_cls * 0.25 + 0.10) * 100)

        return {
            "overall_score": overall_score,
            "metrics": {
                "FCP": {"value": f"{fcp} ms", "status": "GOOD" if fcp <= cls.THRESHOLDS["FCP"]["good"] else "POOR"},
                "LCP": {"value": f"{lcp} ms", "status": "GOOD" if lcp <= cls.THRESHOLDS["LCP"]["good"] else "POOR"},
                "TBT": {"value": f"{tbt} ms", "status": "GOOD" if tbt <= cls.THRESHOLDS["TBT"]["good"] else "POOR"},
                "CLS": {"value": f"{cls}", "status": "GOOD" if cls <= cls.THRESHOLDS["CLS"]["good"] else "POOR"},
            },
            "payload": {
                "js_kb": round(js_size_bytes / 1024, 2),
                "css_kb": round(css_size_bytes / 1024, 2),
                "total_kb": round(total_bytes / 1024, 2),
            },
        }


def print_stage(title: str):
    print(f"\n{BOLD}{CYAN}=== [PIPELINE STAGE] {title} ==={RESET}")


def run_pipeline():
    print(f"{BOLD}{BG_BLUE}{WHITE}  FRONTEND BUILD & AUDIT PIPELINE ENGINE  {RESET}")
    print(f"{WHITE}Memulai simulasi build toolchain, tree-shaking, minifikasi, dan web vitals audit.{RESET}")

    bundler = ModernBundler()

    # 1. SETUP VIRTUAL SOURCE FILES
    # Modul utilitas dengan 3 fungsi: calculateTax & formatCurrency dipakai; deadCodeHeavyFunction TIDAK dipakai
    utils_code = """
    export function calculateTax(amount) { return amount * 0.11; }
    export function formatCurrency(val) { return 'IDR ' + val.toLocaleString(); }
    export function deadCodeHeavyFunction() {
        let buffer = [];
        for(let i=0; i<5000; i++) { buffer.push(Math.sin(i) * Math.cos(i)); }
        return buffer;
    }
    """
    utils_exports = {
        "calculateTax": "function calculateTax(a){return a*0.11;}",
        "formatCurrency": "function formatCurrency(v){return 'IDR '+v.toLocaleString();}",
        "deadCodeHeavyFunction": "function deadCodeHeavyFunction(){let b=[];for(let i=0;i<5000;i++){b.push(Math.sin(i)*Math.cos(i));}return b;}",
    }
    bundler.register_module("./src/utils.js", utils_code, utils_exports, [])

    # Modul App Entry
    entry_code = """
    import { calculateTax, formatCurrency } from './src/utils.js';
    const subtotal = 500000;
    const tax = calculateTax(subtotal);
    console.log(formatCurrency(subtotal + tax));
    """
    entry_imports = [
        ("./src/utils.js", "calculateTax"),
        ("./src/utils.js", "formatCurrency"),
    ]
    bundler.register_module("./src/index.js", entry_code, {}, entry_imports)

    # 2. RUN BUILD STAGE (Tree-Shaking + Minify + Hash)
    print_stage("1. STATIC ANALYSIS & BUNDLING")
    start_time = time.perf_counter()

    artifact = bundler.tree_shake_and_bundle("./src/index.js")
    elapsed = (time.perf_counter() - start_time) * 1000

    print(f"[{GREEN}OK{RESET}] Entry Point: {BOLD}./src/index.js{RESET}")
    print(f"[{GREEN}OK{RESET}] Dead code elimination: 'deadCodeHeavyFunction' disingkirkan.")
    print(f"[{GREEN}OK{RESET}] Output Chunk: {YELLOW}{artifact.filename}{RESET}")
    print(f"[{GREEN}OK{RESET}] Original Code Size : {artifact.original_size} bytes")
    print(f"[{GREEN}OK{RESET}] Minified Bundle Size: {BOLD}{artifact.minified_size} bytes{RESET} "
          f"({GREEN}-{round((1 - artifact.minified_size / artifact.original_size) * 100, 1)}%{RESET})")
    print(f"[{GREEN}OK{RESET}] Build Execution Time: {elapsed:.2f} ms")

    # 3. RUN DEPLOYMENT VERIFICATION & BUDGET CHECK
    print_stage("2. DEPLOYMENT BUDGET VERIFICATION")
    PERFORMANCE_BUDGET_JS_KB = 150.0  # Budget limit
    actual_js_kb = artifact.minified_size / 1024

    if actual_js_kb <= PERFORMANCE_BUDGET_JS_KB:
        print(f"[{GREEN}PASSED{RESET}] JS Bundle Budget: {actual_js_kb:.2f} KB <= {PERFORMANCE_BUDGET_JS_KB} KB")
    else:
        print(f"[{RED}FAILED{RESET}] JS Bundle Budget Exceeded: {actual_js_kb:.2f} KB > {PERFORMANCE_BUDGET_JS_KB} KB")
        sys.exit(1)

    # 4. LIGHTHOUSE-STYLE AUDIT
    print_stage("3. SYNTHETIC PERFORMANCE AUDIT (LIGHTHOUSE EMULATION)")
    mock_css_size = 18 * 1024  # 18 KB CSS
    audit_results = PerformanceAuditor.audit_artifact(artifact.minified_size, mock_css_size)

    score = audit_results["overall_score"]
    score_color = GREEN if score >= 90 else (YELLOW if score >= 50 else RED)

    print(f"\nAudit Overall Score: {BOLD}{score_color}{score}/100{RESET}\n")
    print(f"{'METRIC':<10} | {'VALUE':<12} | {'STATUS':<10}")
    print("-" * 38)

    for metric_name, data in audit_results["metrics"].items():
        status_color = GREEN if data["status"] == "GOOD" else RED
        print(f"{metric_name:<10} | {data['value']:<12} | {status_color}{data['status']:<10}{RESET}")

    print("-" * 38)
    print(f"Transfer Payload: JS={audit_results['payload']['js_kb']} KB, "
          f"CSS={audit_results['payload']['css_kb']} KB "
          f"(Total={audit_results['payload']['total_kb']} KB)")

    print_stage("4. ARTIFACT MANIFEST GENERATION")
    manifest = {
        "app_version": "1.0.0",
        "entry": artifact.filename,
        "hash": artifact.content_hash,
        "performance_score": score,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(json.dumps(manifest, indent=2))
    print(f"\n{BOLD}{GREEN}Pipeline selesai tanpa error. Artefak siap untuk dideploy ke CDN/Edge Network.{RESET}\n")


if __name__ == "__main__":
    run_pipeline()