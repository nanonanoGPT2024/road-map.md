#!/usr/bin/env python3
"""
Hands-On Lab: Mini Bundler & CI/CD Pipeline Simulator
BAB-09: Build Systems, Bundlers, dan CI/CD Pipeline

Simulasi teknis konsep fondasi inti frontend:
1. Dependency Graph Resolution & Topological Sorting
2. Tree Shaking & Dead Code Elimination (DCE)
3. Asset Minification & Content Hashing (Cache Busting)
4. Multi-Stage Automated CI/CD Pipeline Execution
"""

import sys
import time
import hashlib
from typing import Dict, List, Set, Any
from dataclasses import dataclass, field

# ANSI Escape Colors for Rich Terminal Output
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
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"


@dataclass
class Module:
    name: str
    code: str
    dependencies: List[str]
    exports: Dict[str, str] = field(default_factory=dict)
    imported_symbols: Dict[str, List[str]] = field(default_factory=dict)


class BundlerEngine:
    """Simulates a JavaScript/Frontend Bundler (Webpack/Rollup/Vite model)"""

    def __init__(self):
        self.modules: Dict[str, Module] = {}
        self.entry_point: str = "src/index.js"
        self._load_mock_codebase()

    def _load_mock_codebase(self):
        self.modules = {
            "src/index.js": Module(
                name="src/index.js",
                code="import { formatDate, calculateDiscount } from './utils/math.js';\n"
                     "import { renderBanner } from './components/banner.js';\n"
                     "renderBanner('Super Spring Sale');\n"
                     "console.log('Discounted Price:', calculateDiscount(100, 20));",
                dependencies=["src/utils/math.js", "src/components/banner.js"],
                imported_symbols={
                    "src/utils/math.js": ["formatDate", "calculateDiscount"],
                    "src/components/banner.js": ["renderBanner"],
                },
            ),
            "src/utils/math.js": Module(
                name="src/utils/math.js",
                code="export const calculateDiscount = (p, d) => p - (p * (d / 100));\n"
                     "export const formatDate = (d) => new Date(d).toISOString();\n"
                     "export const unusedFinancialEstimator = () => { return 42 * 1000; };",
                dependencies=[],
                exports={
                    "calculateDiscount": "(p, d) => p - (p * (d / 100))",
                    "formatDate": "(d) => new Date(d).toISOString()",
                    "unusedFinancialEstimator": "() => { return 42 * 1000; }",
                },
            ),
            "src/components/banner.js": Module(
                name="src/components/banner.js",
                code="import { createDomElement } from './dom.js';\n"
                     "export const renderBanner = (text) => createDomElement('h1', text);",
                dependencies=["src/components/dom.js"],
                imported_symbols={"src/components/dom.js": ["createDomElement"]},
                exports={
                    "renderBanner": "(text) => createDomElement('h1', text)"
                },
            ),
            "src/components/dom.js": Module(
                name="src/components/dom.js",
                code="export const createDomElement = (tag, val) => `<${tag}>${val}</${tag}>`;\n"
                     "export const sanitizeMarkup = (str) => str.replace(/</g, '&lt;');",
                dependencies=[],
                exports={
                    "createDomElement": "(tag, val) => `<${tag}>${val}</${tag}>`",
                    "sanitizeMarkup": "(str) => str.replace(/</g, '&lt;')"}
            ),
        }

    def resolve_dependency_graph(self) -> List[str]:
        """Performs DFS to build a Topological Sort order for bundling"""
        visited: Set[str] = set()
        resolved_order: List[str] = []

        def dfs(mod_name: str, path: Set[str]):
            if mod_name in path:
                raise ValueError(f"Circular dependency terdeteksi pada rantai impor: {mod_name}")
            if mod_name not in visited:
                path.add(mod_name)
                for dep in self.modules.get(mod_name, Module("", "", [])).dependencies:
                    dfs(dep, path)
                path.remove(mod_name)
                visited.add(mod_name)
                resolved_order.append(mod_name)

        dfs(self.entry_point, set())
        return resolved_order

    def analyze_tree_shaking(self) -> Dict[str, Any]:
        """Identifies dead code / unreferenced exports across modules"""
        used_exports: Dict[str, Set[str]] = {m: set() for m in self.modules}
        all_exports: Dict[str, Set[str]] = {
            m: set(mod.exports.keys()) for m, mod in self.modules.items()
        }

        # Traverse imports
        for mod in self.modules.values():
            for target_dep, symbols in mod.imported_symbols.items():
                if target_dep in used_exports:
                    used_exports[target_dep].update(symbols)

        dead_code: Dict[str, Set[str]] = {}
        total_symbols = 0
        retained_symbols = 0

        for mod_name, exports in all_exports.items():
            dead = exports - used_exports[mod_name]
            dead_code[mod_name] = dead
            total_symbols += len(exports)
            retained_symbols += len(used_exports[mod_name])

        return {
            "used": used_exports,
            "dead": dead_code,
            "total_exports": total_symbols,
            "shaken_exports": sum(len(d) for d in dead_code.values()),
        }

    def generate_bundle(self, enable_tree_shaking: bool = True) -> Dict[str, Any]:
        order = self.resolve_dependency_graph()
        tree_shake_info = self.analyze_tree_shaking()
        dead_map = tree_shake_info["dead"] if enable_tree_shaking else {}

        bundled_code_parts = [
            "/**",
            " * Auto-generated by MicroBundler Engine v1.0",
            f" * Mode: {'Tree-Shaken (Production)' if enable_tree_shaking else 'Standard (Development)'}",
            " */",
            "(function(modules) {",
            "  const installedModules = {};",
            "  function __require__(moduleId) {",
            "    if (installedModules[moduleId]) return installedModules[moduleId].exports;",
            "    const module = installedModules[moduleId] = { exports: {} };",
            "    modules[moduleId](module, module.exports, __require__);",
            "    return module.exports;",
            "  }",
            "  return __require__('" + self.entry_point + "');",
            "})({",
        ]

        for mod_name in order:
            mod = self.modules[mod_name]
            bundled_code_parts.append(f"  '{mod_name}': function(module, exports, __require__) {{")
            
            # Emit active exports
            dead_in_this_mod = dead_map.get(mod_name, set())
            for exp_name, exp_impl in mod.exports.items():
                if exp_name in dead_in_this_mod:
                    bundled_code_parts.append(f"    /* [TREE-SHAKEN DEAD CODE]: {exp_name} eliminated */")
                else:
                    bundled_code_parts.append(f"    exports.{exp_name} = {exp_impl};")

            # Simple transpiled code representation
            lines = [l for l in mod.code.splitlines() if not l.startswith("export ")]
            for line in lines:
                bundled_code_parts.append(f"    {line}")
            bundled_code_parts.append("  },")

        bundled_code_parts.append("});")
        full_source = "\n".join(bundled_code_parts)

        # Minification simulation (strip comments and excess whitespace)
        minified = ";".join([l.strip() for l in full_source.splitlines() if l.strip() and not l.strip().startswith("/*") and not l.strip().startswith("*") and not l.strip().startswith("/**")])

        # Content Hashing for Cache Busting
        content_hash = hashlib.sha256(minified.encode("utf-8")).hexdigest()[:10]
        bundle_filename = f"bundle.{content_hash}.min.js"

        return {
            "filename": bundle_filename,
            "hash": content_hash,
            "source_raw": full_source,
            "source_minified": minified,
            "raw_size_bytes": len(full_source.encode("utf-8")),
            "min_size_bytes": len(minified.encode("utf-8")),
            "eliminated_exports": tree_shake_info["shaken_exports"],
        }


class CICDPipelineRunner:
    """Simulates an enterprise CI/CD pipeline executing quality gates and build triggers"""

    def __init__(self, bundler: BundlerEngine):
        self.bundler = bundler
        self.stages = [
            ("Stage 1: Lint & Static Typing", self.stage_lint),
            ("Stage 2: Unit & Integration Tests", self.stage_test),
            ("Stage 3: Security & Vulnerability Scan", self.stage_security),
            ("Stage 4: Bundling & Asset Optimization", self.stage_build),
            ("Stage 5: Artifact Registry & CDN Release", self.stage_deploy),
        ]

    def _progress_spinner(self, duration: float = 0.5):
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        end_time = time.time() + duration
        i = 0
        while time.time() < end_time:
            sys.stdout.write(f"\r  {CYAN}{chars[i % len(chars)]}{RESET} Memproses pipeline checks...")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1
        sys.stdout.write("\r" + " " * 45 + "\r")

    def stage_lint(self) -> bool:
        print(f"{CYAN}  -> Menjalankan ESLint dan TypeScript Compiler (tsc --noEmit)...{RESET}")
        self._progress_spinner(0.6)
        print(f"  {GREEN}✓{RESET} 4/4 file memenuhi kaidah ESLint Airbnb & Strict TypeScript checks.")
        return True

    def stage_test(self) -> bool:
        print(f"{CYAN}  -> Menjalankan Vitest test suite with Code Coverage...{RESET}")
        self._progress_spinner(0.8)
        tests = [
            ("src/utils/math.test.js", "calculateDiscount() validasi persentase diskon", "PASSED"),
            ("src/utils/math.test.js", "formatDate() format ISO-8601 validation", "PASSED"),
            ("src/components/banner.test.js", "renderBanner() DOM node snapshot check", "PASSED"),
        ]
        for f, desc, status in tests:
            print(f"  {GREEN}✓{RESET} {DIM}[{f}]{RESET} {desc} -> {GREEN}{status}{RESET}")
        print(f"  {BOLD}Statement Coverage: 98.4% | Branch: 95.0% | Functions: 100%{RESET}")
        return True

    def stage_security(self) -> bool:
        print(f"{CYAN}  -> Menjalankan Audit Ketergantungan (npm audit / Snyk)...{RESET}")
        self._progress_spinner(0.5)
        print(f"  {GREEN}✓{RESET} 0 Kerentanan Ditemukan (0 critical, 0 high, 0 moderate).")
        return True

    def stage_build(self) -> Dict[str, Any]:
        print(f"{CYAN}  -> Menjalankan Production Bundler dengan Rollup/Vite engine...{RESET}")
        self._progress_spinner(0.7)
        bundle_res = self.bundler.generate_bundle(enable_tree_shaking=True)
        print(f"  {GREEN}✓{RESET} Bundle terkompilasi: {BOLD}{bundle_res['filename']}{RESET}")
        print(f"      Ukuran Awal     : {bundle_res['raw_size_bytes']} bytes")
        print(f"      Ukuran Minified : {bundle_res['min_size_bytes']} bytes")
        savings = (1 - (bundle_res['min_size_bytes'] / bundle_res['raw_size_bytes'])) * 100
        print(f"      Total Optimasi  : {GREEN}{savings:.1f}% kompresi ukuran file!{RESET}")
        print(f"      Dead Code Shaken: {YELLOW}{bundle_res['eliminated_exports']} unreferenced export(s) dibuang.{RESET}")
        return bundle_res

    def stage_deploy(self, artifact_name: str) -> bool:
        print(f"{CYAN}  -> Mengunggah bundle ke Edge CDN Cache & Triggering Blue-Green Deploy...{RESET}")
        self._progress_spinner(0.6)
        print(f"  {GREEN}✓{RESET} Asset dipublikasikan ke: {BLUE}https://cdn.production.app/static/{artifact_name}{RESET}")
        print(f"  {GREEN}✓{RESET} Cache-Control: {BOLD}public, max-age=31536000, immutable{RESET}")
        print(f"  {BG_GREEN}{WHITE}{BOLD} DEPLOYMENT SUCCESSFUL: Zero-Downtime Rollout Completed! {RESET}")
        return True

    def execute_all(self):
        print(f"\n{BOLD}{BG_BLUE}{WHITE}  === MEMULAI SIMULASI CI/CD AUTOMATED PIPELINE ===  {RESET}\n")
        start_ts = time.time()
        
        last_artifact = ""
        for name, stage_fn in self.stages:
            print(f"\n{BOLD}▶ {MAGENTA}{name}{RESET}")
            if name.startswith("Stage 4"):
                result = stage_fn()
                last_artifact = result["filename"]
            elif name.startswith("Stage 5"):
                stage_fn(last_artifact)
            else:
                success = stage_fn()
                if not success:
                    print(f"\n{RED} Pipeline FAILED pada tahap: {name}{RESET}")
                    return

        total_elapsed = time.time() - start_ts
        print(f"\n{GREEN}{BOLD}Pipeline selesai dalam tempo {total_elapsed:.2f} detik tanpa anomali!{RESET}\n")


def display_dependency_graph(bundler: BundlerEngine):
    print(f"\n{BOLD}{CYAN}=== VISUALISASI DEPENDENCY GRAPH (RESOLUSI AST) ==={RESET}")
    print(f"{DIM}Mengurai rantai impor modul dari entrypoint: {bundler.entry_point}{RESET}\n")
    order = bundler.resolve_dependency_graph()
    for idx, mod in enumerate(order, 1):
        deps = bundler.modules[mod].dependencies
        deps_str = f"{YELLOW}-> depends on: {deps}{RESET}" if deps else f"{GREEN}(Leaf Module / No Dependency){RESET}"
        print(f"  {BOLD}[{idx}]{RESET} {CYAN}{mod:<25}{RESET} {deps_str}")
    print(f"\n{BOLD}Urutan Topological Sort Pembungkusan (Bundling):{RESET}")
    print("  " + "  ➔  ".join([f"{GREEN}{m}{RESET}" for m in order]))


def display_tree_shaking_demo(bundler: BundlerEngine):
    print(f"\n{BOLD}{CYAN}=== ANALISIS TREE SHAKING & DEAD CODE ELIMINATION ==={RESET}")
    shake = bundler.analyze_tree_shaking()
    print(f"Analisis impor simbol dan deteksi kode mati (dead exports):\n")
    for mod_name, mod in bundler.modules.items():
        if not mod.exports:
            continue
        print(f"  Modul: {BOLD}{mod_name}{RESET}")
        for exp in mod.exports:
            if exp in shake["dead"].get(mod_name, set()):
                print(f"    {RED}✗ [DEAD CODE - ELIMINATED]{RESET} Symbol '{exp}' tidak pernah diimpor.")
            else:
                print(f"    {GREEN}✓ [ACTIVE - RETAINED]{RESET} Symbol '{exp}' aktif dirujuk aplikasi.")
    print(f"\n  Ringkasan: {YELLOW}{shake['shaken_exports']} dari {shake['total_exports']} ekspor dieliminasi dari bundle.{RESET}")


def interactive_menu():
    bundler = BundlerEngine()
    pipeline = CICDPipelineRunner(bundler)

    menu = f"""
{BOLD}{MAGENTA}================================================================
   FRONTEND BUILD SYSTEMS, BUNDLER & CI/CD INTERACTIVE LAB
   BAB-09: Build Systems, Bundlers, dan CI/CD Pipeline
================================================================{RESET}
 {BOLD}1.{RESET} Visualisasi Dependency Graph & Topological Sort
 {BOLD}2.{RESET} Simulasi Tree Shaking & Dead Code Elimination (DCE)
 {BOLD}3.{RESET} Inspeksi Bundling, Minifikasi & Content Hashing
 {BOLD}4.{RESET} Eksekusi Penuh Automated CI/CD Pipeline Simulation
 {BOLD}5.{RESET} Jalankan Semua Modul Otomatis (Demo Lengkap)
 {BOLD}6.{RESET} Keluar
"""
    while True:
        print(menu)
        try:
            choice = input(f"{BOLD}Pilih opsi latihan (1-6): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            display_dependency_graph(bundler)
        elif choice == "2":
            display_tree_shaking_demo(bundler)
        elif choice == "3":
            res = bundler.generate_bundle(enable_tree_shaking=True)
            print(f"\n{BOLD}{CYAN}=== HASIL BUNDLE DAN OPTIMASI ASET ==={RESET}")
            print(f"Nama File Output  : {GREEN}{BOLD}{res['filename']}{RESET}")
            print(f"Content Hash      : {YELLOW}{res['hash']}{RESET} (SHA-256 slice for Immutable Caching)")
            print(f"Ukuran Mentah     : {res['raw_size_bytes']} bytes")
            print(f"Ukuran Minifikasi : {res['min_size_bytes']} bytes")
            print(f"\n{BOLD}Snippet Hasil Minifikasi:{RESET}\n{DIM}{res['source_minified'][:180]}...{RESET}")
        elif choice == "4":
            pipeline.execute_all()
        elif choice == "5":
            display_dependency_graph(bundler)
            display_tree_shaking_demo(bundler)
            pipeline.execute_all()
        elif choice == "6":
            print(f"\n{GREEN}Lab selesai. Selamat belajar arsitektur build frontend!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan masukkan nomor 1-6.{RESET}")

        try:
            input(f"\n{DIM}[Tekan Enter untuk kembali ke menu...]{RESET}")
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    interactive_menu()
