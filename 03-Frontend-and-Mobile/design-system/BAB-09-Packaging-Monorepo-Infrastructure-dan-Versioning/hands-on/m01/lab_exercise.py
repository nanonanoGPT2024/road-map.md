#!/usr/bin/env python3
"""
Lab Exercise: Monorepo Infrastructure, Packaging & SemVer Engine
BAB-09: Packaging, Monorepo Infrastructure, dan Versioning (Design System)

Simulasi teknis komprehensif:
1. Monorepo Dependency Graph & Topological Build Order (DAG)
2. Dual-Module Export Resolution (ESM vs CJS) & subpath exports
3. Semantic Versioning & Changeset Pipeline (Major / Minor / Patch bump)
4. Bundle Budgeting & Tree-Shaking Guard Simulation
"""

import sys
import json
import time
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional

# ANSI Color Codes for terminal rendering
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_DARK = "\033[48;5;236m"


def print_banner():
    banner = f"""
{TermColor.CYAN}{TermColor.BOLD}========================================================================
   DESIGN SYSTEM PACKAGING & MONOREPO INFRASTRUCTURE ENGINE (BAB-09)
   Simulasi Topological Build, Dual ESM/CJS Resolution, & SemVer Automation
========================================================================{TermColor.RESET}
"""
    print(banner)


# ---------------------------------------------------------------------------
# 1. Monorepo Workspace & Topological DAG Resolver
# ---------------------------------------------------------------------------
class WorkspacePackage:
    def __init__(self, name: str, version: str, dependencies: List[str], bundle_kb: float, side_effects: bool):
        self.name = name
        self.version = version
        self.dependencies = dependencies
        self.bundle_kb = bundle_kb
        self.side_effects = side_effects
        self.exports_manifest = {
            ".": {
                "types": f"./dist/{name.split('/')[-1]}.d.ts",
                "import": f"./dist/{name.split('/')[-1]}.esm.js",
                "require": f"./dist/{name.split('/')[-1]}.cjs.js"
            },
            "./package.json": "./package.json"
        }


class MonorepoGraph:
    def __init__(self):
        self.packages: Dict[str, WorkspacePackage] = {}

    def register(self, pkg: WorkspacePackage):
        self.packages[pkg.name] = pkg

    def compute_build_order(self) -> List[str]:
        """Kahn's Algorithm for Topological Sorting to resolve build pipeline order."""
        in_degree: Dict[str, int] = {name: 0 for name in self.packages}
        adj_list: Dict[str, List[str]] = defaultdict(list)

        for name, pkg in self.packages.items():
            for dep in pkg.dependencies:
                if dep in self.packages:
                    adj_list[dep].append(name)
                    in_degree[name] += 1

        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.packages):
            raise ValueError(f"{TermColor.RED}Error: Siklus dependency terdeteksi dalam monorepo!{TermColor.RESET}")

        return order


# ---------------------------------------------------------------------------
# 2. Dual-Package Export Resolver
# ---------------------------------------------------------------------------
class ExportResolver:
    @staticmethod
    def resolve_specifier(pkg: WorkspacePackage, subpath: str, environment: str) -> Tuple[bool, str]:
        """Simulasi NodeJS Conditional Exports (ESM `import` vs CJS `require`)."""
        manifest = pkg.exports_manifest
        if subpath not in manifest:
            return False, f"ERR_PACKAGE_PATH_NOT_EXPORTED: Subpath '{subpath}' tidak diexport di package.json."

        target_map = manifest[subpath]
        if isinstance(target_map, str):
            return True, target_map

        if environment in target_map:
            return True, target_map[environment]
        elif "default" in target_map:
            return True, target_map["default"]
        else:
            return False, f"ERR_PACKAGE_CONDITION_NOT_FOUND: Environment '{environment}' tidak ditemukan."


# ---------------------------------------------------------------------------
# 3. SemVer & Changeset Manager
# ---------------------------------------------------------------------------
class ChangesetManager:
    @staticmethod
    def bump_semver(current: str, release_type: str) -> str:
        major, minor, patch = map(int, current.split("."))
        if release_type == "major":
            return f"{major + 1}.0.0"
        elif release_type == "minor":
            return f"{major}.{minor + 1}.0"
        elif release_type == "patch":
            return f"{major}.{minor}.{patch + 1}"
        return current

    @staticmethod
    def analyze_commit(commit_msg: str) -> Tuple[str, str]:
        """Konvensi Conventional Commits menentukan jenis SemVer bump."""
        if commit_msg.startswith("feat!") or "BREAKING CHANGE" in commit_msg:
            return "major", "Breaking Change terdeteksi"
        elif commit_msg.startswith("feat"):
            return "minor", "Fitur baru backward-compatible"
        elif commit_msg.startswith("fix") or commit_msg.startswith("perf"):
            return "patch", "Patch perbaikan bug / performa"
        else:
            return "none", "Non-releasable chore/docs"


# ---------------------------------------------------------------------------
# 4. Interactive Simulation Runner
# ---------------------------------------------------------------------------
def setup_default_monorepo() -> MonorepoGraph:
    repo = MonorepoGraph()
    repo.register(WorkspacePackage("@ds/tokens", "1.2.0", [], bundle_kb=4.5, side_effects=False))
    repo.register(WorkspacePackage("@ds/icons", "2.0.1", ["@ds/tokens"], bundle_kb=18.2, side_effects=False))
    repo.register(WorkspacePackage("@ds/primitives", "1.0.0", ["@ds/tokens"], bundle_kb=12.0, side_effects=False))
    repo.register(WorkspacePackage("@ds/components", "2.4.0", ["@ds/tokens", "@ds/primitives", "@ds/icons"], bundle_kb=42.8, side_effects=False))
    repo.register(WorkspacePackage("@ds/docs", "1.0.0", ["@ds/components"], bundle_kb=120.0, side_effects=True))
    return repo


def run_pipeline_demo(repo: MonorepoGraph):
    print(f"\n{TermColor.BOLD}[1/4] ANALISIS DEPENDENCY GRAPH & TOPOLOGICAL SORT{TermColor.RESET}")
    print(f"{TermColor.DIM}Memeriksa directed acyclic graph (DAG) paket monorepo...{TermColor.RESET}")
    
    order = repo.compute_build_order()
    for idx, pkg_name in enumerate(order, 1):
        pkg = repo.packages[pkg_name]
        dep_str = ", ".join(pkg.dependencies) if pkg.dependencies else "(Root Foundation)"
        print(f"  Step {idx}: {TermColor.GREEN}{pkg_name:<18}{TermColor.RESET} v{pkg.version:<6} | Dep: {TermColor.DIM}{dep_str}{TermColor.RESET}")

    print(f"\n{TermColor.BOLD}[2/4] DUAL-PACKAGE ESM/CJS RESOLUTION CHECK{TermColor.RESET}")
    sample_pkg = repo.packages["@ds/components"]
    scenarios = [
        (".", "import"),
        (".", "require"),
        (".", "types"),
        ("./button", "import")  # Path tidak sah
    ]

    for subpath, env in scenarios:
        ok, res = ExportResolver.resolve_specifier(sample_pkg, subpath, env)
        status = f"{TermColor.GREEN}[RESOLVED]{TermColor.RESET}" if ok else f"{TermColor.RED}[REJECTED]{TermColor.RESET}"
        print(f"  {status} Query ({subpath}, mode={env}) => {TermColor.CYAN}{res}{TermColor.RESET}")

    print(f"\n{TermColor.BOLD}[3/4] SEMVER & CHANGESET IMPACT CALCULATION{TermColor.RESET}")
    sample_commits = [
        ("fix(button): perbaiki outline focus accessibility", "@ds/components"),
        ("feat(tokens): tambah palet warna semantic dark-mode", "@ds/tokens"),
        ("feat!(primitives): ubah API ref forwarding ke slot model", "@ds/primitives"),
        ("chore: update prettier config", "@ds/docs")
    ]

    for commit, target_pkg in sample_commits:
        bump_type, reason = ChangesetManager.analyze_commit(commit)
        pkg = repo.packages[target_pkg]
        new_version = ChangesetManager.bump_semver(pkg.version, bump_type) if bump_type != "none" else pkg.version
        
        color = TermColor.YELLOW if bump_type == "minor" else (TermColor.RED if bump_type == "major" else TermColor.BLUE)
        print(f"  Commit: {TermColor.BOLD}\"{commit}\"{TermColor.RESET}")
        print(f"    Target  : {target_pkg} ({pkg.version} -> {TermColor.BOLD}{new_version}{TermColor.RESET})")
        print(f"    Release : {color}{bump_type.upper()}{TermColor.RESET} ({reason})\n")

    print(f"{TermColor.BOLD}[4/4] BUNDLE SIZE BUDGET & TREE-SHAKABILITY AUDIT{TermColor.RESET}")
    BUDGET_LIMIT_KB = 50.0
    for name in order:
        pkg = repo.packages[name]
        is_safe = pkg.bundle_kb <= BUDGET_LIMIT_KB
        shake_status = f"{TermColor.GREEN}Penuh (sideEffects: false){TermColor.RESET}" if not pkg.side_effects else f"{TermColor.YELLOW}Terbatas (sideEffects: true){TermColor.RESET}"
        budget_status = f"{TermColor.GREEN}PASS{TermColor.RESET}" if is_safe else f"{TermColor.RED}EXCEEDED{TermColor.RESET}"
        
        print(f"  * {name:<18} : {pkg.bundle_kb:>5.1f} KB / {BUDGET_LIMIT_KB} KB [{budget_status}] | Tree-shakability: {shake_status}")

    print(f"\n{TermColor.GREEN}{TermColor.BOLD}Semua verifikasi infrastruktur packaging monorepo berhasil dieksekusi.{TermColor.RESET}\n")


def interactive_menu(repo: MonorepoGraph):
    while True:
        print(f"{TermColor.BOLD}--- MENU SIMULASI INTERAKTIF ---{TermColor.RESET}")
        print("1. Jalankan Analisis Pipeline Lengkap")
        print("2. Uji Coba Custom Conventional Commit Bump")
        print("3. Cek Conditional Exports Resolution Paket")
        print("4. Keluar")
        
        try:
            choice = input(f"{TermColor.CYAN}Pilih opsi [1-4]: {TermColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            run_pipeline_demo(repo)
        elif choice == "2":
            print(f"\n{TermColor.BOLD}--- Uji Conventional Commit ---{TermColor.RESET}")
            msg = input("Masukkan pesan commit (misal: 'feat!(icons): migrate svg core'): ").strip()
            pkg_name = input("Masukkan target package (misal: '@ds/icons'): ").strip()
            if pkg_name not in repo.packages:
                print(f"{TermColor.RED}Paket '{pkg_name}' tidak terdaftar!{TermColor.RESET}\n")
                continue
            bump, reason = ChangesetManager.analyze_commit(msg)
            cur = repo.packages[pkg_name].version
            nxt = ChangesetManager.bump_semver(cur, bump)
            print(f"Hasil: Tipe bump={TermColor.YELLOW}{bump}{TermColor.RESET} | {cur} -> {TermColor.GREEN}{nxt}{TermColor.RESET} ({reason})\n")
        elif choice == "3":
            print(f"\n{TermColor.BOLD}--- Uji Export Resolution ---{TermColor.RESET}")
            pkg_name = input("Pilih paket (default @ds/components): ").strip() or "@ds/components"
            if pkg_name not in repo.packages:
                print(f"{TermColor.RED}Paket tidak ditemukan.{TermColor.RESET}\n")
                continue
            subpath = input("Subpath (contoh: '.' atau './package.json'): ").strip() or "."
            env = input("Environment condition ('import', 'require', 'types'): ").strip() or "import"
            ok, res = ExportResolver.resolve_specifier(repo.packages[pkg_name], subpath, env)
            color = TermColor.GREEN if ok else TermColor.RED
            print(f"Status: {color}{'SUKSES' if ok else 'GAGAL'}{TermColor.RESET} -> {res}\n")
        elif choice == "4":
            print(f"{TermColor.GREEN}Selesai. Terima kasih!{TermColor.RESET}")
            break
        else:
            print(f"{TermColor.RED}Pilihan tidak valid.{TermColor.RESET}\n")


def main():
    print_banner()
    repo = setup_default_monorepo()
    
    # Otomatis jalankan demo jika non-interaktif, atau jika ada argumen --demo / stdin di-redirect
    if not sys.stdin.isatty() or "--demo" in sys.argv:
        run_pipeline_demo(repo)
    else:
        # Menjalankan overview pertama kali lalu membuka menu interaktif
        run_pipeline_demo(repo)
        interactive_menu(repo)


if __name__ == "__main__":
    main()
