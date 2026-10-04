#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Dynamic Linker & Package Dependency Resolver
BAB-09: Manajemen Paket dan Pustaka Dinamis (Linux Core Foundations)

Simulasi interaktif konsep:
1. Dynamic Linker resolution (ld.so, LD_LIBRARY_PATH, /etc/ld.so.cache, default paths)
2. Package Dependency Resolver & Topological Sort (dpkg/apt simulation)
"""

import sys
import time
from collections import defaultdict, deque

# ANSI Color Codes
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

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{WHITE}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")

def print_step(step_num: int, title: str):
    print(f"{BOLD}{YELLOW}[Step {step_num}]{RESET} {BOLD}{WHITE}{title}{RESET}")

class DynamicLinkerSimulator:
    """
    Simulasi alur pencarian dynamic linker (ld-linux.so):
    1. DT_RPATH (jika DT_RUNPATH tidak ada)
    2. LD_LIBRARY_PATH environment variable
    3. DT_RUNPATH
    4. /etc/ld.so.cache (hasil kompilasi ldconfig)
    5. Default system paths (/lib64, /usr/lib64, /lib, /usr/lib)
    """

    def __init__(self):
        # Database virtual filesystem library
        self.virtual_fs = {
            "/custom/app/lib": ["libcryptoutils.so.1"],
            "/opt/internal/lib": ["libdbconnector.so.2"],
            "/usr/local/lib": ["libssl_custom.so.1.1"],
            "/usr/lib64": ["libc.so.6", "libm.so.6", "libpthread.so.0", "libz.so.1"],
            "/lib64": ["ld-linux-x86-64.so.2"],
        }
        # Simulasi isi /etc/ld.so.cache
        self.ld_so_cache = {
            "libc.so.6": "/usr/lib64/libc.so.6",
            "libm.so.6": "/usr/lib64/libm.so.6",
            "libz.so.1": "/usr/lib64/libz.so.1",
            "libssl_custom.so.1.1": "/usr/local/lib/libssl_custom.so.1.1",
        }

    def resolve_library(self, lib_name: str, rpath: str = None, runpath: str = None, ld_library_path: str = None):
        print(f"  {BOLD}Memulai pencarian shared object:{RESET} {MAGENTA}{lib_name}{RESET}")
        time.sleep(0.15)

        # 1. RPATH (jika RUNPATH tidak diset)
        if rpath and not runpath:
            print(f"  {DIM}1. Memeriksa DT_RPATH: {rpath}{RESET}")
            for p in rpath.split(":"):
                if p in self.virtual_fs and lib_name in self.virtual_fs[p]:
                    return f"{p}/{lib_name}", "DT_RPATH"

        # 2. LD_LIBRARY_PATH
        if ld_library_path:
            print(f"  {DIM}2. Memeriksa $LD_LIBRARY_PATH: {ld_library_path}{RESET}")
            for p in ld_library_path.split(":"):
                if p in self.virtual_fs and lib_name in self.virtual_fs[p]:
                    return f"{p}/{lib_name}", "LD_LIBRARY_PATH"
        else:
            print(f"  {DIM}2. $LD_LIBRARY_PATH kosong/tidak didefinisikan.{RESET}")

        # 3. RUNPATH
        if runpath:
            print(f"  {DIM}3. Memeriksa DT_RUNPATH: {runpath}{RESET}")
            for p in runpath.split(":"):
                if p in self.virtual_fs and lib_name in self.virtual_fs[p]:
                    return f"{p}/{lib_name}", "DT_RUNPATH"

        # 4. /etc/ld.so.cache
        print(f"  {DIM}4. Mencari di /etc/ld.so.cache (ldconfig binary index)...{RESET}")
        if lib_name in self.ld_so_cache:
            return self.ld_so_cache[lib_name], "/etc/ld.so.cache"

        # 5. Default Paths
        default_paths = ["/lib64", "/usr/lib64"]
        print(f"  {DIM}5. Mencari di Trusted System Paths: {', '.join(default_paths)}{RESET}")
        for p in default_paths:
            if p in self.virtual_fs and lib_name in self.virtual_fs[p]:
                return f"{p}/{lib_name}", "System Default"

        return None, "NOT FOUND"

    def simulate_ldd(self, binary_name: str, needed_libs: list, ld_library_path: str = None, runpath: str = None):
        print(f"{BOLD}Analisis Dependency Binary (Simulasi ldd {binary_name}):{RESET}")
        print(f"{DIM}{'-' * 60}{RESET}")
        all_resolved = True
        for lib in needed_libs:
            path, source = self.resolve_library(lib, runpath=runpath, ld_library_path=ld_library_path)
            if path:
                print(f"    {GREEN}✔{RESET} {lib} => {CYAN}{path}{RESET} ({YELLOW}via {source}{RESET})")
            else:
                print(f"    {RED}✘{RESET} {lib} => {RED}not found{RESET} (Error: undefined library)")
                all_resolved = False
            time.sleep(0.1)
        print(f"{DIM}{'-' * 60}{RESET}")
        if all_resolved:
            print(f"  Status Linking: {GREEN}{BOLD}READY EXECUTION{RESET}\n")
        else:
            print(f"  Status Linking: {RED}{BOLD}ERROR (Missing Shared Objects - exit code 127){RESET}\n")
        return all_resolved

class PackageManagerSimulator:
    """
    Simulasi Dependency Graph Resolver berbasis Directed Acyclic Graph (DAG)
    dan deteksi Circular Dependency serta urutan instalasi (Topological Sort).
    """

    def __init__(self):
        # Package repository: {package_name: [dependencies]}
        self.repo = {
            "nginx": ["nginx-core", "libssl", "libpcre3", "libc6"],
            "nginx-core": ["libc6", "libz"],
            "libssl": ["libc6", "libcrypto"],
            "libcrypto": ["libc6"],
            "libpcre3": ["libc6"],
            "libz": ["libc6"],
            "libc6": [],
            "mariadb-server": ["mariadb-client", "libaio1", "libc6"],
            "mariadb-client": ["libncurses6", "libc6"],
            "libncurses6": ["libc6"],
            "libaio1": ["libc6"],
            # Kasus circular dependency untuk lab
            "pkg-a": ["pkg-b"],
            "pkg-b": ["pkg-c"],
            "pkg-c": ["pkg-a"],
        }
        self.installed = set(["libc6"])

    def resolve_dependencies(self, target_pkg: str):
        print(f"{BOLD}Menghitung graph dependensi untuk:{RESET} {CYAN}{target_pkg}{RESET}")
        if target_pkg not in self.repo:
            print(f"  {RED}Error: Paket '{target_pkg}' tidak ditemukan di repository APT/RPM.{RESET}")
            return None

        # DFS dengan cycle detection
        visited = set()
        in_stack = set()
        install_order = []
        has_cycle = False
        cycle_nodes = []

        def dfs(node, path):
            nonlocal has_cycle
            if has_cycle:
                return
            visited.add(node)
            in_stack.add(node)
            path.append(node)

            for dep in self.repo.get(node, []):
                if dep in in_stack:
                    has_cycle = True
                    idx = path.index(dep)
                    cycle_nodes.extend(path[idx:] + [dep])
                    return
                if dep not in visited:
                    dfs(dep, path)

            in_stack.remove(node)
            path.pop()
            install_order.append(node)

        dfs(target_pkg, [])

        if has_cycle:
            cycle_str = f" {YELLOW}->{RESET} ".join([f"{RED}{n}{RESET}" for n in cycle_nodes])
            print(f"  {RED}{BOLD}FATAL DEPENDENCY ERROR:{RESET} Terdeteksi Circular Dependency!")
            print(f"  Rantai siklus: {cycle_str}")
            return None

        return install_order

    def simulate_install(self, target_pkg: str):
        plan = self.resolve_dependencies(target_pkg)
        if not plan:
            return False

        to_install = [p for p in plan if p not in self.installed]
        print(f"\n{BOLD}Rencana Eksekusi Instalasi (Topological Order):{RESET}")
        for i, pkg in enumerate(to_install, 1):
            print(f"  {BLUE}{i:02d}.{RESET} Unpacking & Setting up {GREEN}{pkg}{RESET}")
            time.sleep(0.12)
            self.installed.add(pkg)

        print(f"\n{GREEN}{BOLD}Instalasi '{target_pkg}' Berhasil Tanpa Kerusakan Dependensi!{RESET}\n")
        return True

def run_interactive_lab():
    print_header("LAB SIMULASI: LINUX DYNAMIC LINKING & PACKAGE RESOLUTION")
    linker = DynamicLinkerSimulator()
    pkg_mgr = PackageManagerSimulator()

    while True:
        print(f"{BOLD}Pilih Modul Praktikum:{RESET}")
        print(f"  {CYAN}1.{RESET} Simulasi 'ldd' & Linker Search Path Resolution (Skenario Normal)")
        print(f"  {CYAN}2.{RESET} Simulasi Missing Library & Perbaikan dengan $LD_LIBRARY_PATH")
        print(f"  {CYAN}3.{RESET} Simulasi Pembaruan Cache ldconfig (/etc/ld.so.cache)")
        print(f"  {CYAN}4.{RESET} Simulasi APT/DPKG Dependency Resolution (Nginx Stack)")
        print(f"  {CYAN}5.{RESET} Simulasi Deteksi Circular Dependency Kegagalan Paket")
        print(f"  {RED}0.{RESET} Keluar")
        
        choice = input(f"\n{BOLD}{YELLOW}Masukkan pilihan [0-5]: {RESET}").strip()

        if choice == "1":
            print_step(1, "Simulasi Resolusi Pustaka Standar (/usr/bin/curl)")
            needed = ["libc.so.6", "libz.so.1", "libssl_custom.so.1.1"]
            linker.simulate_ldd("/usr/bin/curl", needed)

        elif choice == "2":
            print_step(2, "Simulasi Aplikasi Internal Custom (/opt/app/bin/crm)")
            needed = ["libc.so.6", "libdbconnector.so.2", "libcryptoutils.so.1"]
            print(f"{YELLOW}--- Percobaan 1: Tanpa environment khusus ---{RESET}")
            linker.simulate_ldd("/opt/app/bin/crm", needed)

            print(f"{YELLOW}--- Percobaan 2: Menyuntikkan LD_LIBRARY_PATH ---{RESET}")
            fixed_env = "/opt/internal/lib:/custom/app/lib"
            print(f"{BOLD}Exporting:{RESET} {CYAN}export LD_LIBRARY_PATH={fixed_env}{RESET}\n")
            linker.simulate_ldd("/opt/app/bin/crm", needed, ld_library_path=fixed_env)

        elif choice == "3":
            print_step(3, "Simulasi Registrasi Pustaka Baru ke /etc/ld.so.cache")
            new_lib = "libpayment_gateway.so.3"
            target_dir = "/usr/local/lib"
            print(f"1. Menempatkan {MAGENTA}{new_lib}{RESET} di {CYAN}{target_dir}{RESET}")
            linker.virtual_fs.setdefault(target_dir, []).append(new_lib)
            
            print(f"2. Memeriksa sebelum eksekusi ldconfig:")
            linker.simulate_ldd("payment_daemon", [new_lib, "libc.so.6"])

            print(f"3. Menjalankan {BOLD}sudo ldconfig -v{RESET} untuk rebuild cache binary...")
            time.sleep(0.3)
            linker.ld_so_cache[new_lib] = f"{target_dir}/{new_lib}"
            print(f"   {GREEN}✔ Cache diperbarui: {new_lib} terpetakan ke {target_dir}/{new_lib}{RESET}\n")

            print(f"4. Memeriksa setelah ldconfig:")
            linker.simulate_ldd("payment_daemon", [new_lib, "libc.so.6"])

        elif choice == "4":
            print_step(4, "Simulasi APT Package Dependency Tree Resolution")
            pkg_mgr.simulate_install("nginx")

        elif choice == "5":
            print_step(5, "Simulasi Kegagalan Siklus Paket Dependensi (Deadlock)")
            pkg_mgr.simulate_install("pkg-a")

        elif choice == "0":
            print(f"\n{GREEN}Lab selesai. Terima kasih telah mempraktikkan konsep Linux Core Foundations!{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}\n")

if __name__ == "__main__":
    try:
        run_interactive_lab()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Lab dihentikan oleh pengguna.{RESET}\n")
        sys.exit(0)
