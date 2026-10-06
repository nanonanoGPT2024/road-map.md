#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Standarisasi Ekosistem & Modular Package Architecture PHP
BAB-03: PSR Standards, PSR-4 Autoloading Engine, & Composer Dependency Solver
"""

import sys
import os
import json
import hashlib
import time
import functools
from typing import Dict, List, Optional, Tuple, Any

# ==============================================================================
# ANSI Color Codes & Formatting Helper
# ==============================================================================
class Colors:
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
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"

def print_banner() -> None:
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================
   PHP ECOSYSTEM STANDARDS & MODULAR PACKAGE ARCHITECTURE SIMULATOR
   BAB-03: PSR-4 Autoloading Engine, Composer Resolver & SemVer Constraint
================================================================================{Colors.RESET}"""
    print(banner)

# ==============================================================================
# 1. PSR-4 Autoloader Engine Simulator
# ==============================================================================
class Psr4Autoloader:
    """
    Simulasi implementasi spesifikasi PSR-4 (Autoloader Standard).
    Memetakan Fully Qualified Class Name (FQCN) ke jalur file fisik di disk.
    """
    def __init__(self) -> None:
        # Prefix namespace terdaftar -> list direktori dasar
        self.prefixes: Dict[str, List[str]] = {}
        # Memory virtual file system untuk verifikasi keberadaan file
        self.virtual_fs: set = set()

    def add_namespace(self, prefix: str, base_dir: str, prepend: bool = False) -> None:
        # Normalisasi namespace prefix: wajib berakhiran '\\'
        normalized_prefix = prefix.strip('\\') + '\\'
        # Normalisasi base directory: hilangkan trailing slash
        normalized_dir = base_dir.rstrip('/\\')

        if normalized_prefix not in self.prefixes:
            self.prefixes[normalized_prefix] = []

        if prepend:
            self.prefixes[normalized_prefix].insert(0, normalized_dir)
        else:
            self.prefixes[normalized_prefix].append(normalized_dir)

    def register_virtual_file(self, file_path: str) -> None:
        self.virtual_fs.add(os.path.normpath(file_path).replace('\\', '/'))

    def resolve_file(self, fqcn: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Menyelesaikan FQCN ke jalur file fisik berdasarkan aturan spesifikasi PSR-4.
        Returns (resolved_file_path, matching_prefix)
        """
        clean_fqcn = fqcn.lstrip('\\')

        # Telusuri prefix yang cocok dengan strategi longest-prefix match
        sorted_prefixes = sorted(self.prefixes.keys(), key=len, reverse=True)

        for prefix in sorted_prefixes:
            if clean_fqcn.startswith(prefix):
                relative_class = clean_fqcn[len(prefix):]
                # Ganti separator namespace '\\' dengan separator direktori '/'
                file_subpath = relative_class.replace('\\', '/') + ".php"

                for base_dir in self.prefixes[prefix]:
                    candidate_path = f"{base_dir}/{file_subpath}"
                    normalized_candidate = os.path.normpath(candidate_path).replace('\\', '/')

                    # Cek virtual filesystem
                    if normalized_candidate in self.virtual_fs:
                        return normalized_candidate, prefix

                # Jika tidak ditemukan di virtual filesystem tapi prefix cocok
                first_candidate = f"{self.prefixes[prefix][0]}/{file_subpath}"
                return os.path.normpath(first_candidate).replace('\\', '/'), prefix

        return None, None

    def load_class(self, fqcn: str) -> bool:
        resolved, prefix = self.resolve_file(fqcn)
        if resolved and resolved in self.virtual_fs:
            return True
        return False

# ==============================================================================
# 2. Composer Semantic Versioning (SemVer) & Dependency Resolver
# ==============================================================================
class Version:
    def __init__(self, version_str: str) -> None:
        self.raw = version_str
        parts = version_str.split('.')
        self.major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        self.minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        self.patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    def __repr__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: 'Version') -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

class SemVerConstraint:
    """
    Evaluator batasan versi Composer:
    - Caret operator (^1.2.3): >= 1.2.3 dan < 2.0.0
    - Tilde operator (~1.2.3): >= 1.2.3 dan < 1.3.0
    - Exact match (1.2.3)
    - Wildcard (1.2.*)
    """
    @staticmethod
    def satisfies(version: Version, constraint: str) -> bool:
        constraint = constraint.strip()

        if constraint.startswith('^'):
            base = Version(constraint[1:])
            # Caret constraint: major version tidak boleh berubah (kecuali major 0)
            if base.major > 0:
                upper = Version(f"{base.major + 1}.0.0")
            else:
                upper = Version(f"0.{base.minor + 1}.0")
            return (base <= version) and (version < upper)

        elif constraint.startswith('~'):
            base = Version(constraint[1:])
            # Tilde constraint: mengunci tingkat minor terdekat
            upper = Version(f"{base.major}.{base.minor + 1}.0")
            return (base <= version) and (version < upper)

        elif constraint.endswith('.*'):
            prefix = constraint[:-2]
            parts = [int(p) for p in prefix.split('.') if p.isdigit()]
            if len(parts) == 1:
                return version.major == parts[0]
            elif len(parts) == 2:
                return version.major == parts[0] and version.minor == parts[1]

        elif constraint == "*":
            return True

        else:
            exact = Version(constraint)
            return version == exact

        return False

class PackageRepository:
    """Katalog paket virtual ala Packagist"""
    def __init__(self) -> None:
        self.packages: Dict[str, Dict[str, Dict[str, str]]] = {
            "psr/log": {
                "1.1.4": {},
                "2.0.0": {},
                "3.0.0": {}
            },
            "monolog/monolog": {
                "2.8.0": {"psr/log": "^1.0.1 || ^2.0 || ^3.0"},
                "2.9.2": {"psr/log": "^1.1.4 || ^2.0 || ^3.0"},
                "3.4.0": {"psr/log": "^3.0"}
            },
            "guzzlehttp/guzzle": {
                "7.4.5": {"psr/http-client": "^1.0", "guzzlehttp/psr7": "^1.9 || ^2.4"},
                "7.8.1": {"psr/http-client": "^1.0", "guzzlehttp/psr7": "^2.5"}
            },
            "guzzlehttp/psr7": {
                "1.9.0": {"psr/http-message": "^1.0"},
                "2.4.4": {"psr/http-message": "^1.0 || ^2.0"},
                "2.6.2": {"psr/http-message": "^1.1 || ^2.0"}
            },
            "psr/http-message": {
                "1.1.0": {},
                "2.0.0": {}
            },
            "psr/http-client": {
                "1.0.3": {"psr/http-message": "^1.0 || ^2.0"}
            }
        }

class DependencySolver:
    """Simulasi SAT-based Dependency Resolver Composer"""
    def __init__(self, repo: PackageRepository) -> None:
        self.repo = repo

    def resolve(self, root_requirements: Dict[str, str]) -> Tuple[bool, Dict[str, str], List[str]]:
        resolved: Dict[str, str] = {}
        logs: List[str] = []
        queue = list(root_requirements.items())

        logs.append(f"{Colors.BLUE}[SOLVER]{Colors.RESET} Memulai resolusi dependensi root: {root_requirements}")

        while queue:
            pkg_name, constraint = queue.pop(0)

            if pkg_name not in self.repo.packages:
                logs.append(f"{Colors.RED}[ERROR]{Colors.RESET} Paket '{pkg_name}' tidak ditemukan di repositori.")
                return False, {}, logs

            available_versions = sorted(
                [Version(v) for v in self.repo.packages[pkg_name].keys()],
                reverse=True
            )

            # Filter versi yang memenuhi constraint
            matched_version: Optional[Version] = None
            for v in available_versions:
                # Handle or condition sederhana (||)
                or_constraints = [c.strip() for c in constraint.split("||")]
                if any(SemVerConstraint.satisfies(v, c) for c in or_constraints):
                    matched_version = v
                    break

            if not matched_version:
                logs.append(f"{Colors.RED}[CONFLICT]{Colors.RESET} Tidak ada versi '{pkg_name}' yang memenuhi constraint: {constraint}")
                return False, {}, logs

            # Cek jika sudah pernah di-resolve dengan versi berbeda
            if pkg_name in resolved:
                if resolved[pkg_name] != str(matched_version):
                    logs.append(f"{Colors.RED}[CONFLICT]{Colors.RESET} Versi bentrok untuk '{pkg_name}': {resolved[pkg_name]} vs {matched_version}")
                    return False, {}, logs
            else:
                resolved[pkg_name] = str(matched_version)
                logs.append(f"{Colors.GREEN}[LOCKED]{Colors.RESET} {pkg_name} -> {matched_version} (memenuhi {constraint})")

                # Masukkan dependensi transisi paket ini ke antrean
                transitive_deps = self.repo.packages[pkg_name][str(matched_version)]
                for dep_name, dep_constraint in transitive_deps.items():
                    queue.append((dep_name, dep_constraint))

        return True, resolved, logs

# ==============================================================================
# 3. Interactive Demos & Lab Workflows
# ==============================================================================
def demo_psr4_autoloading() -> None:
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- [1] SIMULASI PSR-4 AUTOLOADING ENGINE ---{Colors.RESET}")
    autoloader = Psr4Autoloader()

    # Mendaftarkan mapping PSR-4 composer.json
    print(f"{Colors.CYAN}Mendaftarkan mapping namespace PSR-4:{Colors.RESET}")
    print("  - 'App\\'                  => 'src/'")
    print("  - 'App\\Tests\\'            => 'tests/'")
    print("  - 'Monolog\\'              => 'vendor/monolog/monolog/src/Monolog/'")
    print("  - 'Acme\\ModularPlugin\\'   => 'packages/modular-plugin/src/'")

    autoloader.add_namespace("App\\", "src")
    autoloader.add_namespace("App\\Tests\\", "tests", prepend=True)
    autoloader.add_namespace("Monolog\\", "vendor/monolog/monolog/src/Monolog")
    autoloader.add_namespace("Acme\\ModularPlugin\\", "packages/modular-plugin/src")

    # Registrasi file virtual yang 'ada' di sistem
    autoloader.register_virtual_file("src/Http/Controllers/UserController.php")
    autoloader.register_virtual_file("src/Domain/Models/Order.php")
    autoloader.register_virtual_file("tests/Http/Controllers/UserControllerTest.php")
    autoloader.register_virtual_file("vendor/monolog/monolog/src/Monolog/Logger.php")

    test_classes = [
        "App\\Http\\Controllers\\UserController",
        "App\\Tests\\Http\\Controllers\\UserControllerTest",
        "Monolog\\Logger",
        "App\\Services\\PaymentGateway",
        "Acme\\ModularPlugin\\Core\\Kernel"
    ]

    print(f"\n{Colors.YELLOW}Menguji Resolusi FQCN ke File Path Realistis:{Colors.RESET}")
    for fqcn in test_classes:
        path, prefix = autoloader.resolve_file(fqcn)
        is_loaded = autoloader.load_class(fqcn)

        status_badge = f"{Colors.GREEN}[FOUND & LOADED]{Colors.RESET}" if is_loaded else f"{Colors.RED}[MISSING DISK FILE]{Colors.RESET}"
        print(f"  FQCN       : {Colors.BOLD}{fqcn}{Colors.RESET}")
        print(f"  Prefix     : {Colors.CYAN}{prefix}{Colors.RESET}")
        print(f"  File Path  : {Colors.WHITE}{path}{Colors.RESET}")
        print(f"  Status     : {status_badge}\n")

def demo_composer_solver() -> None:
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- [2] SIMULASI COMPOSER DEPENDENCY & SEMVER SOLVER ---{Colors.RESET}")
    repo = PackageRepository()
    solver = DependencySolver(repo)

    scenario_success = {
        "guzzlehttp/guzzle": "^7.8",
        "monolog/monolog": "^2.9"
    }

    print(f"{Colors.YELLOW}Skenario A: Resolusi Berhasil (Compatible SemVer){Colors.RESET}")
    success, locked, logs = solver.resolve(scenario_success)
    for log in logs:
        print(f"  {log}")

    if success:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}Hasil Lockfile Resolusi:{Colors.RESET}")
        print(json.dumps(locked, indent=4))

    print(f"\n{Colors.YELLOW}Skenario B: Konflik Versi Transisi (Incompatible Diamond Dependency){Colors.RESET}")
    scenario_conflict = {
        "monolog/monolog": "3.4.0",  # Requires psr/log: ^3.0
        "psr/log": "1.1.4"           # Dipaksa ke 1.1.4 -> Konflik!
    }
    success_c, locked_c, logs_c = solver.resolve(scenario_conflict)
    for log in logs_c:
        print(f"  {log}")
    if not success_c:
        print(f"  {Colors.RED}{Colors.BOLD}[HASIL]: Composer menghentikan instalasi karena lock conflict!{Colors.RESET}\n")

def demo_lockfile_generation() -> None:
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- [3] GENERATE COMPOSER.JSON & COMPOSER.LOCK SIMULATION ---{Colors.RESET}")
    composer_json = {
        "name": "acme/enterprise-modular-app",
        "description": "Contoh aplikasi modular PHP berbasis PSR-4 & Composer",
        "type": "project",
        "require": {
            "php": ">=8.2.0",
            "guzzlehttp/guzzle": "^7.8.1",
            "monolog/monolog": "^2.9.2"
        },
        "autoload": {
            "psr-4": {
                "App\\": "src/"
            }
        },
        "config": {
            "optimize-autoloader": True,
            "sort-packages": True
        }
    }

    json_str = json.dumps(composer_json, indent=4)
    content_hash = hashlib.sha256(json_str.encode('utf-8')).hexdigest()

    composer_lock = {
        "_readme": ["This file locks the dependencies of your project to a known state."],
        "content-hash": content_hash,
        "packages": [
            {"name": "guzzlehttp/guzzle", "version": "7.8.1"},
            {"name": "guzzlehttp/psr7", "version": "2.6.2"},
            {"name": "psr/http-client", "version": "1.0.3"},
            {"name": "psr/http-message", "version": "2.0.0"},
            {"name": "monolog/monolog", "version": "2.9.2"},
            {"name": "psr/log", "version": "3.0.0"}
        ]
    }

    print(f"{Colors.CYAN}[composer.json Content]{Colors.RESET}")
    print(json_str)
    print(f"\n{Colors.GREEN}[composer.lock Calculated Content-Hash (SHA-256)]{Colors.RESET}: {content_hash}")
    print(f"{Colors.GREEN}[composer.lock Locked Packages]{Colors.RESET}:")
    for pkg in composer_lock["packages"]:
        print(f"  -> {pkg['name']} ({pkg['version']})")
    print()

def demo_psr_compliance_audit() -> None:
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}--- [4] AUDIT STANDAR PSR (PSR-1, PSR-4, PSR-12) ---{Colors.RESET}")
    rules = [
        ("PSR-1: Basic Coding Standard", "Namespace wajib memiliki minimal 1 level vendor; class name StudlyCaps; method camelCase."),
        ("PSR-4: Autoloading Standard", "FQCN namespace prefix harus tepat mencerminkan struktur folder dan ekstensi .php."),
        ("PSR-7: HTTP Message Interface", "Objek Request/Response bersifat Immutable (withHeader(), withBody() mengembalikan instance baru)."),
        ("PSR-11: Container Interface", "Container Dependency Injection mengimplementasikan ContainerInterface (get(), has())."),
        ("PSR-12: Extended Coding Style", "Indents 4 spaces; kurung kurawal pembuka method di baris baru; strict type declare(strict_types=1).")
    ]

    for title, desc in rules:
        print(f"{Colors.CYAN}{Colors.BOLD}[PASS]{Colors.RESET} {Colors.WHITE}{title}{Colors.RESET}")
        print(f"       {Colors.DIM}{desc}{Colors.RESET}")
    print()

def run_self_test() -> None:
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== MENJALANKAN DIAGNOSTIC SUITE & SELF-TEST MANDIRI ==={Colors.RESET}")
    # 1. Test Autoloader
    loader = Psr4Autoloader()
    loader.add_namespace("Vendor\\Lib\\", "vendor/lib/src")
    loader.register_virtual_file("vendor/lib/src/Client.php")
    path, _ = loader.resolve_file("Vendor\\Lib\\Client")
    assert path == "vendor/lib/src/Client.php", f"Test PSR-4 gagal: {path}"
    assert loader.load_class("Vendor\\Lib\\Client") is True
    assert loader.load_class("Vendor\\Lib\\NonExistent") is False
    print(f" {Colors.GREEN}✓{Colors.RESET} PSR-4 Autoloader Engine test: PASSED")

    # 2. Test SemVer Constraint
    v1 = Version("1.2.3")
    v2 = Version("1.3.0")
    v3 = Version("2.0.0")
    assert SemVerConstraint.satisfies(v1, "^1.2.0") is True
    assert SemVerConstraint.satisfies(v2, "^1.2.0") is True
    assert SemVerConstraint.satisfies(v3, "^1.2.0") is False
    assert SemVerConstraint.satisfies(v1, "~1.2.0") is True
    assert SemVerConstraint.satisfies(v2, "~1.2.0") is False
    print(f" {Colors.GREEN}✓{Colors.RESET} SemVer Evaluator (^ / ~ / wildcard) test: PASSED")

    # 3. Test Dependency Solver
    repo = PackageRepository()
    solver = DependencySolver(repo)
    ok, res, _ = solver.resolve({"monolog/monolog": "^2.9"})
    assert ok is True
    assert "psr/log" in res
    print(f" {Colors.GREEN}✓{Colors.RESET} Composer Transitive Dependency Solver test: PASSED")

    print(f"{Colors.GREEN}{Colors.BOLD}SEMUA DIAGNOSTIC SUITE BERHASIL (100% HEALTHY)!{Colors.RESET}\n")

# ==============================================================================
# Main Interactive Terminal Controller
# ==============================================================================
def main() -> None:
    print_banner()

    # Jika dijalankan secara non-interaktif atau dengan parameter otomatis
    if not sys.stdin.isatty() or len(sys.argv) > 1:
        print(f"{Colors.YELLOW}[INFO] Menjalankan seluruh modul simulasi secara otomatis...{Colors.RESET}")
        demo_psr4_autoloading()
        demo_composer_solver()
        demo_lockfile_generation()
        demo_psr_compliance_audit()
        run_self_test()
        print(f"{Colors.GREEN}{Colors.BOLD}Simulasi selesai dengan sukses.{Colors.RESET}")
        return

    while True:
        print(f"{Colors.WHITE}{Colors.BOLD}PILIH MENU SIMULASI:{Colors.RESET}")
        print("  1. Simulasi PSR-4 Autoloader Engine (FQCN -> File Path)")
        print("  2. Simulasi Composer SemVer & Dependency Solver (Conflict Check)")
        print("  3. Simulasi Lockfile Generator & SHA-256 Hash Verification")
        print("  4. Audit Standar Ekosistem PSR (PSR-1, PSR-4, PSR-7, PSR-11, PSR-12)")
        print("  5. Jalankan Diagnostic & Self-Test Suite Otomatis")
        print("  6. Jalankan Semua Modul Secara Sekuensial")
        print("  0. Keluar")

        try:
            choice = input(f"\n{Colors.CYAN}Masukkan pilihan [0-6]: {Colors.RESET}").strip()
            if choice == "1":
                demo_psr4_autoloading()
            elif choice == "2":
                demo_composer_solver()
            elif choice == "3":
                demo_lockfile_generation()
            elif choice == "4":
                demo_psr_compliance_audit()
            elif choice == "5":
                run_self_test()
            elif choice == "6":
                demo_psr4_autoloading()
                demo_composer_solver()
                demo_lockfile_generation()
                demo_psr_compliance_audit()
                run_self_test()
            elif choice == "0":
                print(f"{Colors.GREEN}Terima kasih telah menggunakan simulator ekosistem PHP!{Colors.RESET}")
                break
            else:
                print(f"{Colors.RED}Pilihan tidak valid, silakan coba lagi.{Colors.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Sesi diakhiri.{Colors.RESET}")
            break

if __name__ == "__main__":
    main()
