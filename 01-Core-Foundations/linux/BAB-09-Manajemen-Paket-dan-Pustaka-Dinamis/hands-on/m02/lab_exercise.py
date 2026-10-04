#!/usr/bin/env python3
"""
Lab Hands-on: Dynamic Linker & Runtime Loader Emulation (ld-linux.so deep dive)
Topik: 01-Core-Foundations / Bab 09: Dynamic Libraries & Linker Architecture

Deskripsi:
Skrip ini mensimulasikan mekanisme internal runtime dynamic linker Linux (ld.so),
mencakup:
1. Parsing metadata ELF Dynamic Section (DT_NEEDED, DT_SONAME, DT_RPATH).
2. Algoritma resolusi path pustaka (RPATH -> LD_LIBRARY_PATH -> ld.so.cache -> Default paths).
3. Pembuatan cache soname dinamis (replika mekanisme /sbin/ldconfig).
4. Relokasi Global Offset Table (GOT) dan simulasi Lazy vs Eager binding (PLT trampolines).
5. Deteksi konflik ABI / missing symbol versioning.
"""

import sys
import time
from typing import Dict, List, Optional, Tuple, Set


# --- ANSI Color Formatting Utilities ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# --- Data Structures: ELF & Shared Object Models ---
class SharedLibrary:
    """Merepresentasikan file Shared Object (.so) di filesystem."""
    def __init__(
        self,
        filepath: str,
        soname: str,
        exported_symbols: Dict[str, str],
        needed: Optional[List[str]] = None,
        abi_version: str = "1.0",
    ):
        self.filepath = filepath
        self.soname = soname
        self.exported_symbols = exported_symbols  # {symbol_name: virtual_address}
        self.needed = needed or []               # DT_NEEDED dependencies
        self.abi_version = abi_version


class ElfExecutable:
    """Merepresentasikan file ELF binary executable."""
    def __init__(
        self,
        name: str,
        needed: List[str],
        imported_symbols: List[str],
        rpath: Optional[str] = None,
    ):
        self.name = name
        self.needed = needed                     # DT_NEEDED entries
        self.imported_symbols = imported_symbols # Symbol references requiring GOT relocation
        self.rpath = rpath                       # DT_RPATH / DT_RUNPATH


# --- Simulated Filesystem & Loader Context ---
class MockVFS:
    """Filesystem virtual untuk menampung pustaka dinamis."""
    def __init__(self):
        self.files: Dict[str, SharedLibrary] = {}

    def install_library(self, lib: SharedLibrary):
        self.files[lib.filepath] = lib

    def exists(self, path: str) -> bool:
        return path in self.files

    def get(self, path: str) -> Optional[SharedLibrary]:
        return self.files.get(path)


class DynamicLinker:
    """
    Simulator runtime linker (ld-linux-x86-64.so.2).
    Mengimplementasikan spesifikasi pencarian pustaka dan relokasi GOT/PLT.
    """
    def __init__(self, vfs: MockVFS):
        self.vfs = vfs
        self.default_paths = ["/lib64", "/usr/lib64"]
        self.ld_so_cache: Dict[str, str] = {}  # Map soname -> full path
        self.ld_library_path: List[str] = []
        self.loaded_libraries: Dict[str, SharedLibrary] = {}
        self.got: Dict[str, str] = {}          # Global Offset Table {symbol: target_address}
        self.plt: Dict[str, bool] = {}         # Procedure Linkage Table status {symbol: resolved_flag}

    def run_ldconfig(self, directories: List[str]):
        """
        Simulasi /sbin/ldconfig: Memindai direktori pustaka standar, membaca SONAME,
        dan menyusun cache biner (/etc/ld.so.cache).
        """
        print(f"{Colors.CYAN}[ldconfig]{Colors.RESET} Memperbarui /etc/ld.so.cache...")
        self.ld_so_cache.clear()
        for directory in directories:
            for path, lib in self.vfs.files.items():
                if path.startswith(directory.rstrip("/") + "/"):
                    self.ld_so_cache[lib.soname] = lib.filepath
                    print(f"  {Colors.DIM}-> Cache mapped: {lib.soname} => {lib.filepath}{Colors.RESET}")
        print(f"{Colors.GREEN}[ldconfig] Cache selesai dibangun ({len(self.ld_so_cache)} entri).{Colors.RESET}\n")

    def _resolve_library_path(self, soname: str, rpath: Optional[str]) -> Tuple[Optional[str], str]:
        """
        Algoritma pencarian pustaka dinamis sesuai urutan prioritas glibc/Linux:
        1. DT_RPATH / DT_RUNPATH (jika disematkan dalam binary)
        2. LD_LIBRARY_PATH (variabel lingkungan)
        3. /etc/ld.so.cache
        4. Jalur sistem default (/lib64, /usr/lib64)
        """
        # Prioritas 1: DT_RPATH
        if rpath:
            for p in rpath.split(":"):
                candidate = f"{p.rstrip('/')}/{soname}"
                if self.vfs.exists(candidate):
                    return candidate, "DT_RPATH"

        # Prioritas 2: LD_LIBRARY_PATH
        for p in self.ld_library_path:
            candidate = f"{p.rstrip('/')}/{soname}"
            if self.vfs.exists(candidate):
                return candidate, "LD_LIBRARY_PATH"

        # Prioritas 3: ld.so.cache
        if soname in self.ld_so_cache:
            candidate = self.ld_so_cache[soname]
            if self.vfs.exists(candidate):
                return candidate, "/etc/ld.so.cache"

        # Prioritas 4: Sistem default
        for p in self.default_paths:
            candidate = f"{p.rstrip('/')}/{soname}"
            if self.vfs.exists(candidate):
                return candidate, "DEFAULT_SYSTEM_PATH"

        return None, "NOT_FOUND"

    def load_dependencies(self, binary: ElfExecutable, eager_binding: bool = False) -> bool:
        """
        Memuat seluruh dependensi rekursif (DT_NEEDED) dan memetakan relokasi simbol.
        """
        print(f"{Colors.BOLD}{Colors.HEADER}=== Memulai Pemuatan Binary: {binary.name} ==={Colors.RESET}")
        print(f"Binding Mode : {'LD_BIND_NOW (Eager)' if eager_binding else 'Lazy Binding (Default)'}")
        print(f"LD_LIBRARY_PATH: {':'.join(self.ld_library_path) if self.ld_library_path else '(kosong)'}")
        print(f"Binary RPATH   : {binary.rpath or '(none)'}\n")

        queue = list(binary.needed)
        visited_sonames: Set[str] = set()

        while queue:
            needed_soname = queue.pop(0)
            if needed_soname in visited_sonames:
                continue

            resolved_path, source = self._resolve_library_path(needed_soname, binary.rpath)
            
            if not resolved_path:
                print(f"{Colors.RED}[FATAL ERROR] Tidak dapat menemukan pustaka bersama: '{needed_soname}'!{Colors.RESET}")
                print(f"              Status: Resolusi gagal di seluruh path hierarki.\n")
                return False

            lib = self.vfs.get(resolved_path)
            self.loaded_libraries[lib.soname] = lib
            visited_sonames.add(needed_soname)

            print(f"  {Colors.GREEN}[LOADED]{Colors.RESET} {needed_soname} -> {lib.filepath} (via {Colors.YELLOW}{source}{Colors.RESET})")

            # Memasukkan dependensi sekunder pustaka (DT_NEEDED milik library itu sendiri)
            for sub_dep in lib.needed:
                if sub_dep not in visited_sonames:
                    queue.append(sub_dep)

        # Inisialisasi PLT & GOT
        for sym in binary.imported_symbols:
            self.plt[sym] = False
            self.got[sym] = "0x00000000"  # Pointer awal menunjuk kembali ke resolver PLT

        if eager_binding:
            print(f"\n{Colors.CYAN}[LD_BIND_NOW] Melakukan relokasi GOT secara instan untuk seluruh simbol...{Colors.RESET}")
            for sym in binary.imported_symbols:
                if not self._relocate_symbol(sym):
                    return False

        print(f"{Colors.GREEN}[SUCCESS] Seluruh dependensi berhasil dimuat ke memori virtual.{Colors.RESET}\n")
        return True

    def _relocate_symbol(self, symbol_name: str) -> bool:
        """Mencari simbol di memori pustaka yang telah dimuat dan memperbarui GOT."""
        for lib in self.loaded_libraries.values():
            if symbol_name in lib.exported_symbols:
                resolved_addr = lib.exported_symbols[symbol_name]
                self.got[symbol_name] = resolved_addr
                self.plt[symbol_name] = True
                print(f"  {Colors.DIM}[GOT Relocation] Symbol '{symbol_name}' resolved to {resolved_addr} ({lib.soname}){Colors.RESET}")
                return True

        print(f"{Colors.RED}[LINK ERROR] Simbol tak terdefinisi (Undefined Reference): '{symbol_name}'{Colors.RESET}")
        return False

    def execute_symbol(self, symbol_name: str):
        """Simulasi eksekusi fungsi binary yang memicu lazy binding melalui PLT/GOT."""
        print(f"{Colors.BOLD}--> Binary mengeksekusi panggilan fungsi: '{symbol_name}()'{Colors.RESET}")

        if not self.plt.get(symbol_name, False):
            print(f"    {Colors.YELLOW}[Lazy Binding Triggered]{Colors.RESET} Simbol belum di-resolve. PLT memanggil runtime dynamic resolver...")
            time.sleep(0.05)  # Simulasi overhead dynamic lookup
            if not self._relocate_symbol(symbol_name):
                print(f"    {Colors.RED}[SIGSEGV/ABRT] Segmentation fault saat runtime dynamic relocation!{Colors.RESET}\n")
                return
            print(f"    {Colors.GREEN}[Lazy Binding Completed]{Colors.RESET} GOT di-patch. Pemanggilan berikutnya akan langsung melompat tanpa overhead.")
        else:
            print(f"    {Colors.GREEN}[Direct GOT Jump]{Colors.RESET} Simbol telah ter-resolve di alamat {self.got[symbol_name]}. Zero-overhead dispatch.")

        print(f"    {Colors.CYAN}Eksekusi fungsi '{symbol_name}' berhasil selesai.{Colors.RESET}\n")


# --- Demonstration & Scenario Runner ---
def setup_environment() -> Tuple[MockVFS, DynamicLinker]:
    vfs = MockVFS()

    # 1. Pustaka Kriptografi v1.1 (Standard ABI)
    vfs.install_library(SharedLibrary(
        filepath="/usr/lib64/libcrypto.so.1.1",
        soname="libcrypto.so.1.1",
        exported_symbols={"CRYPTO_create_ctx": "0x7f88a00110", "SHA256_Digest": "0x7f88a00180"},
        abi_version="1.1"
    ))

    # 2. Pustaka SSL v1.1 bergantung pada libcrypto.so.1.1
    vfs.install_library(SharedLibrary(
        filepath="/usr/lib64/libssl.so.1.1",
        soname="libssl.so.1.1",
        exported_symbols={"SSL_CTX_new": "0x7f88b00210", "SSL_connect": "0x7f88b00290"},
        needed=["libcrypto.so.1.1"],
        abi_version="1.1"
    ))

    # 3. Custom internal lib yang diletakkan di direktori non-standar vendor (/opt/custom/lib)
    vfs.install_library(SharedLibrary(
        filepath="/opt/vendor/lib/libtelemetry.so.1",
        soname="libtelemetry.so.1",
        exported_symbols={"telemetry_send": "0x7f88c00500"},
        abi_version="1.0"
    ))

    # 4. Pustaka SSL v3.0 (Incompatible ABI bump, missing old symbols)
    vfs.install_library(SharedLibrary(
        filepath="/usr/lib64/libssl.so.3.0",
        soname="libssl.so.3",
        exported_symbols={"SSL_CTX_new_v2": "0x7f88d00900"}, # Simbol lama hilang/diubah
        abi_version="3.0"
    ))

    linker = DynamicLinker(vfs)
    return vfs, linker


def main():
    print(f"{Colors.BOLD}{Colors.CYAN}======================================================================{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}    LAB DEEP DIVE: SISTEM LINKING DINAMIS, SONAME & RUNTIME LOADER    {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}======================================================================{Colors.RESET}\n")

    vfs, linker = setup_environment()

    # --- Skenario 1: Rekonstruksi ld.so.cache (ldconfig) ---
    print(f"{Colors.BOLD}[SKENARIO 1] Eksekusi ldconfig untuk Mengindeks Shared Libraries{Colors.RESET}")
    linker.run_ldconfig(directories=["/lib64", "/usr/lib64"])

    # --- Skenario 2: Pemuatan Standar dengan Lazy Binding ---
    print(f"{Colors.BOLD}[SKENARIO 2] Pemuatan Binary Webserver (Lazy Binding Default){Colors.RESET}")
    web_server = ElfExecutable(
        name="nginx_mock",
        needed=["libssl.so.1.1"],
        imported_symbols=["SSL_CTX_new", "SSL_connect"]
    )

    if linker.load_dependencies(web_server, eager_binding=False):
        # Eksekusi fungsi pertama: memicu lazy binding
        linker.execute_symbol("SSL_CTX_new")
        # Eksekusi fungsi yang sama kedua kali: bypass dynamic linker lookup (fast path)
        linker.execute_symbol("SSL_CTX_new")

    # --- Skenario 3: Penanganan Path Khusus dengan LD_LIBRARY_PATH vs RPATH ---
    print(f"{Colors.BOLD}[SKENARIO 3] Resolusi Path Non-Standar (/opt/vendor/lib){Colors.RESET}")
    vendor_app = ElfExecutable(
        name="analytics_agent",
        needed=["libtelemetry.so.1"],
        imported_symbols=["telemetry_send"]
    )

    print("Percobaan 1: Tanpa konfigurasi path tambahan...")
    linker_test1 = DynamicLinker(vfs)
    linker_test1.run_ldconfig(directories=["/usr/lib64"])
    linker_test1.load_dependencies(vendor_app)

    print("Percobaan 2: Menyediakan LD_LIBRARY_PATH=/opt/vendor/lib...")
    linker_test2 = DynamicLinker(vfs)
    linker_test2.ld_library_path = ["/opt/vendor/lib"]
    if linker_test2.load_dependencies(vendor_app):
        linker_test2.execute_symbol("telemetry_send")

    # --- Skenario 4: Eager Binding (LD_BIND_NOW=1) & ABI Breakage Check ---
    print(f"{Colors.BOLD}[SKENARIO 4] Kegagalan Simbol & ABI Breakage pada LD_BIND_NOW=1{Colors.RESET}")
    broken_app = ElfExecutable(
        name="legacy_service",
        needed=["libssl.so.3"], # Terhubung ke ABI baru v3.0 padahal butuh simbol v1.1
        imported_symbols=["SSL_CTX_new"]
    )

    linker_test3 = DynamicLinker(vfs)
    linker_test3.run_ldconfig(directories=["/usr/lib64"])
    success = linker_test3.load_dependencies(broken_app, eager_binding=True)

    if not success:
        print(f"{Colors.RED}[DIAGNOSA KERNEL/LOADER] Aplikasi 'legacy_service' ditolak oleh runtime loader!{Colors.RESET}")
        print("Penyebab: libssl.so.3 mengalami perubahan SONAME dan mematahkan ABI Backward-Compatibility.")
        print("Solusi  : Pasang pustaka kompatibilitas (misal: compat-openssl11) atau rebuild binary.\n")


if __name__ == "__main__":
    main()