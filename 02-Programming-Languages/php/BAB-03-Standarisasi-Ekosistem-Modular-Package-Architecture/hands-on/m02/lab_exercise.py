#!/usr/bin/env python3
"""
Lab Hands-on: PHP Ecosystem Standardization & Modular Package Architecture
Simulasi Engine Composer (SemVer & Dependency Graph Resolver), 
PSR-4 Autoloader Engine, dan PSR-11 Dependency Injection Container.
"""

import sys
import re
import time
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Callable

# ==============================================================================
# ANSI Color Palette untuk Output Terminal
# ==============================================================================
class TermColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

def print_header(title: str) -> None:
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.YELLOW} >> {title}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'='*70}{TermColor.RESET}")

def print_status(tag: str, msg: str, color: str = TermColor.GREEN) -> None:
    print(f"[{color}{TermColor.BOLD}{tag:^9}{TermColor.RESET}] {msg}")

# ==============================================================================
# 1. COMPOSER DEPENDENCY RESOLVER (SemVer & Topological DAG Resolver)
# ==============================================================================
class SemVer:
    """Representasi dan perbandingan Semantic Versioning (SemVer 2.0.0)."""
    def __init__(self, version_str: str):
        match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", version_str.strip())
        if not match:
            raise ValueError(f"Format SemVer tidak valid: {version_str}")
        self.major, self.minor, self.patch = map(int, match.groups())
        self.raw = f"{self.major}.{self.minor}.{self.patch}"

    def satisfies(self, constraint: str) -> bool:
        """Evaluasi constraint sederhana: misal '^1.2.0' (kompatibel minor/patch)."""
        constraint = constraint.strip()
        if constraint == "*":
            return True
        if constraint.startswith("^"):
            target = SemVer(constraint[1:])
            # Caret constraint: major harus sama, versi >= target
            if self.major != target.major:
                return False
            return (self.minor, self.patch) >= (target.minor, target.patch)
        if constraint.startswith(">="):
            target = SemVer(constraint[2:])
            return (self.major, self.minor, self.patch) >= (target.major, target.minor, target.patch)
        
        target = SemVer(constraint)
        return (self.major, self.minor, self.patch) == (target.major, target.minor, target.patch)

    def __repr__(self) -> str:
        return self.raw

class ComposerPackage:
    """Manifest representasi 'composer.json' suatu modular package."""
    def __init__(self, name: str, version: str, requires: Optional[Dict[str, str]] = None):
        self.name = name
        self.version = SemVer(version)
        self.requires = requires or {}

class ComposerResolver:
    """
    Simulasi SAT/DAG Solver Composer:
    Menyusun pohon dependensi, mendeteksi konflik dan dependensi sirkular,
    serta menghasilkan 'composer.lock' melalui topological sorting.
    """
    def __init__(self, repository_pool: List[ComposerPackage]):
        self.pool = repository_pool

    def resolve(self, root_requirements: Dict[str, str]) -> List[ComposerPackage]:
        selected: Dict[str, ComposerPackage] = {}
        in_degree: Dict[str, int] = defaultdict(int)
        graph: Dict[str, List[str]] = defaultdict(list)

        # Temukan paket yang cocok di repository pool
        queue = deque(root_requirements.items())
        
        while queue:
            pkg_name, constraint = queue.popleft()
            if pkg_name in selected:
                # Verifikasi idempotensi dan kompatibilitas
                if not selected[pkg_name].version.satisfies(constraint):
                    raise RuntimeError(f"Konflik dependensi: {pkg_name} ({selected[pkg_name].version}) tidak memenuhi {constraint}")
                continue

            # Cari rilis paket terbaik (versi tertinggi yang kompatibel)
            candidates = [
                p for p in self.pool 
                if p.name == pkg_name and p.version.satisfies(constraint)
            ]
            if not candidates:
                raise RuntimeError(f"Tidak dapat menemukan paket yang memenuhi: {pkg_name}:{constraint}")
            
            best_pkg = max(candidates, key=lambda p: (p.version.major, p.version.minor, p.version.patch))
            selected[pkg_name] = best_pkg

            # Tambahkan sub-dependensi ke antrian penyelesaian
            for dep_name, dep_constraint in best_pkg.requires.items():
                graph[pkg_name].append(dep_name)
                in_degree[dep_name] += 1
                queue.append((dep_name, dep_constraint))

        # Topological Sort (Kahn's Algorithm) untuk menentukan urutan instalasi
        install_order = []
        zero_in = deque([pkg for pkg in selected if in_degree[pkg] == 0])

        while zero_in:
            node = zero_in.popleft()
            install_order.append(selected[node])
            for neighbor in graph[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        zero_in.append(neighbor)

        if len(install_order) != len(selected):
            raise RuntimeError("Dependensi sirkular (Circular Dependency) terdeteksi pada graph paket!")

        return install_order

# ==============================================================================
# 2. PSR-4 COMPLIANT CLASS LOADER SIMULATION
# ==============================================================================
class Psr4ClassLoader:
    """
    Implementasi standar PSR-4: Mapping Namespace Prefix ke Base Directory.
    Menerjemahkan FQCN (Fully Qualified Class Name) menjadi path filesystem virtual.
    """
    def __init__(self):
        # Struktur: {prefix: [base_dir1, base_dir2]}
        self.prefixes: Dict[str, List[str]] = defaultdict(list)
        self.class_map_cache: Dict[str, str] = {}

    def add_namespace(self, prefix: str, base_dir: str, prepend: bool = False) -> None:
        """Mendaftarkan prefix namespace PSR-4 dengan base directory."""
        prefix = prefix.strip('\\') + '\\'
        base_dir = base_dir.rstrip('/\\') + '/'
        if prepend:
            self.prefixes[prefix].insert(0, base_dir)
        else:
            self.prefixes[prefix].append(base_dir)

    def find_file(self, fqcn: str) -> Optional[str]:
        """Algoritma resolusi nama kelas PSR-4 ke relative/absolute path."""
        # 1. Cek Class Map Cache (optimasi level 2 pada composer)
        if fqcn in self.class_map_cache:
            return self.class_map_cache[fqcn]

        logical_path = fqcn.lstrip('\\')
        sub_path = logical_path

        # 2. Longest prefix matching
        while True:
            last_slash = sub_path.rfind('\\')
            if last_slash == -1:
                break
            sub_path = sub_path[:last_slash]
            search_prefix = sub_path + '\\'
            
            if search_prefix in self.prefixes:
                relative_class = logical_path[len(search_prefix):].replace('\\', '/') + '.php'
                for base_dir in self.prefixes[search_prefix]:
                    file_candidate = base_dir + relative_class
                    # Simpan dalam cache (simulasi class-map dump)
                    self.class_map_cache[fqcn] = file_candidate
                    return file_candidate

        return None

# ==============================================================================
# 3. PSR-11 CONTAINER INTERFACE & DEPENDENCY INJECTION
# ==============================================================================
class ContainerException(Exception): pass
class NotFoundException(ContainerException): pass

class Psr11Container:
    """
    Implementasi standar PSR-11 Service Container.
    Menyediakan method get($id) dan has($id) dengan autowiring & service sharing.
    """
    def __init__(self):
        self._definitions: Dict[str, Callable[['Psr11Container'], Any]] = {}
        self._resolved_instances: Dict[str, Any] = {}

    def set(self, id: str, factory: Callable[['Psr11Container'], Any]) -> None:
        """Mendaftarkan dependency definition."""
        self._definitions[id] = factory

    def get(self, id: str) -> Any:
        """Mengambil instance dari container (Shared Singleton lifecycle)."""
        if id in self._resolved_instances:
            return self._resolved_instances[id]

        if not self.has(id):
            raise NotFoundException(f"Service identifier '{id}' tidak ditemukan dalam container.")

        factory = self._definitions[id]
        instance = factory(self)
        self._resolved_instances[id] = instance
        return instance

    def has(self, id: str) -> bool:
        """Memeriksa keberadaan identifier di container."""
        return id in self._definitions or id in self._resolved_instances

# ==============================================================================
# SIMULASI DUMMY SERVICES UNTUK LAB RUNTIME
# ==============================================================================
class DatabaseConnection:
    def __init__(self, dsn: str):
        self.dsn = dsn
    def query(self, sql: str) -> str:
        return f"Executing [{sql}] against {self.dsn}"

class Logger:
    def __init__(self, channel: str):
        self.channel = channel
    def info(self, msg: str) -> str:
        return f"[{self.channel}] INFO: {msg}"

class UserRepository:
    def __init__(self, db: DatabaseConnection, logger: Logger):
        self.db = db
        self.logger = logger
    def find_user(self, user_id: int) -> str:
        log_out = self.logger.info(f"Mencari record ID {user_id}")
        db_out = self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return f"{log_out}\n       {db_out}"

# ==============================================================================
# MAIN SIMULATOR LAB EXECUTION
# ==============================================================================
def main():
    print_header("LAB ENGINE: EKOSISTEM PHP & MODULAR PACKAGE ARCHITECTURE")
    start_total_time = time.perf_counter()

    # --------------------------------------------------------------------------
    # Bagian 1: Composer Dependency SAT/DAG Resolution
    # --------------------------------------------------------------------------
    print(f"\n{TermColor.BOLD}[1] SIMULASI COMPOSER PACKAGE RESOLVER & SEMVER{TermColor.RESET}")
    repo_pool = [
        ComposerPackage("psr/log", "1.1.4"),
        ComposerPackage("psr/log", "1.0.2"),
        ComposerPackage("psr/container", "1.1.1"),
        ComposerPackage("monolog/monolog", "2.8.0", {"psr/log": "^1.0.0"}),
        ComposerPackage("monolog/monolog", "1.26.0", {"psr/log": "^1.0.0"}),
        ComposerPackage("doctrine/dbal", "2.13.0"),
        ComposerPackage("app/framework-core", "1.0.0", {
            "psr/container": "^1.1.0",
            "monolog/monolog": "^2.0.0",
            "doctrine/dbal": "^2.10.0"
        })
    ]

    resolver = ComposerResolver(repo_pool)
    root_reqs = {"app/framework-core": "^1.0.0"}

    print_status("ANALYZE", f"Menganalisis root requirements: {root_reqs}", TermColor.BLUE)
    
    try:
        resolved_manifest = resolver.resolve(root_reqs)
        print_status("RESOLVE", "Penyelesaian dependensi berhasil tanpa konflik!", TermColor.GREEN)
        print(f"\n{TermColor.BOLD}Simulasi 'composer.lock' Plan Installs:{TermColor.RESET}")
        for idx, pkg in enumerate(resolved_manifest, 1):
            print(f"  {idx}. {TermColor.CYAN}{pkg.name:<25}{TermColor.RESET} "
                  f"Versi Terkunci: {TermColor.YELLOW}{pkg.version}{TermColor.RESET}")
    except RuntimeError as err:
        print_status("FAILED", f"Resolusi paket gagal: {err}", TermColor.RED)
        sys.exit(1)

    # --------------------------------------------------------------------------
    # Bagian 2: PSR-4 Autoloader Resolution
    # --------------------------------------------------------------------------
    print_header("BAGIAN 2: PSR-4 CLASS LOADER RESOLUTION BENCHMARK")
    loader = Psr4ClassLoader()
    
    # Registrasi PSR-4 prefix (mirip composer.json -> autoload -> psr-4)
    loader.add_namespace("App\\", "src/")
    loader.add_namespace("Monolog\\", "vendor/monolog/monolog/src/Monolog/")
    loader.add_namespace("Psr\\Log\\", "vendor/psr/log/Psr/Log/")
    loader.add_namespace("Doctrine\\DBAL\\", "vendor/doctrine/dbal/lib/Doctrine/DBAL/")

    test_classes = [
        "App\\Http\\Controllers\\UserController",
        "Monolog\\Handler\\StreamHandler",
        "Psr\\Log\\LoggerInterface",
        "Doctrine\\DBAL\\Connection",
        "Unknown\\Vendor\\ServiceWorker"
    ]

    print_status("REGISTER", "Namespace prefixes berhasil didaftarkan ke ClassLoader.", TermColor.BLUE)
    print(f"\n{TermColor.BOLD}Evaluasi Resolusi FQCN ke File Path (PSR-4):{TermColor.RESET}")

    for fqcn in test_classes:
        resolved_path = loader.find_file(fqcn)
        if resolved_path:
            print_status("FOUND", f"{fqcn:<40} => {TermColor.WHITE}{resolved_path}{TermColor.RESET}")
        else:
            print_status("NOT_FOUND", f"{fqcn:<40} => [File Tidak Ditemukan]", TermColor.RED)

    # --------------------------------------------------------------------------
    # Bagian 3: PSR-11 Service Container & Dependency Injection
    # --------------------------------------------------------------------------
    print_header("BAGIAN 3: PSR-11 CONTAINER & DEPENDENCY INJECTION RUNTIME")
    container = Psr11Container()

    # Bindings service definitions
    container.set("config.db_dsn", lambda c: "mysql:host=127.0.0.1;port=3306;dbname=production")
    container.set("database", lambda c: DatabaseConnection(c.get("config.db_dsn")))
    container.set("logger", lambda c: Logger("APP_CORE"))
    container.set("user_repository", lambda c: UserRepository(c.get("database"), c.get("logger")))

    print_status("BINDING", "Mendaftarkan service definitions ke Psr11Container...", TermColor.BLUE)
    
    # Resolve and verify service execution
    print_status("CONTAINER", "Resolving 'user_repository' dari Container Interface...", TermColor.MAGENTA)
    repo = container.get("user_repository")

    print_status("INVOKE", "Mengeksekusi UserRepository::find_user(42):", TermColor.GREEN)
    result = repo.find_user(42)
    print(f"{TermColor.BOLD}{TermColor.YELLOW}   --- Result Payload ---{TermColor.RESET}")
    for line in result.split("\n"):
        print(f"   {TermColor.GREEN}|{TermColor.RESET} {line}")
    print(f"{TermColor.BOLD}{TermColor.YELLOW}   ----------------------{TermColor.RESET}")

    # Pengujian Singleton / Instance Sharing Lifecycle
    first_inst = container.get("database")
    second_inst = container.get("database")
    is_singleton = first_inst is second_inst
    
    print_status("SHARED", f"Verifikasi Shared Instance (Singleton pattern): {is_singleton} (ID: {hex(id(first_inst))})", TermColor.GREEN)

    # Uji Exception penanganan PSR-11
    try:
        container.get("unregistered.mailer")
    except NotFoundException as err:
        print_status("PSR-11", f"Handled Exception Sesuai Standar: {err}", TermColor.YELLOW)

    elapsed_ms = (time.perf_counter() - start_total_time) * 1000
    print_header("SIMULASI LAB SELESAI")
    print_status("METRICS", f"Waktu eksekusi modul: {elapsed_ms:.2f} ms", TermColor.CYAN)

if __name__ == "__main__":
    main()