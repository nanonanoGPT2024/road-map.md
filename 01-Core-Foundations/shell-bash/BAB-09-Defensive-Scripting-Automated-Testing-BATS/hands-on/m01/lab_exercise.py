#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Defensive Scripting & Automated Testing (BATS) Simulator
Modul 01 - Shell-Bash Core Foundations: BAB 09
Simulasi interaktif konsep defensif Bash: set -euo pipefail, trap/cleanup,
safe file locks (flock), parameter expansion defensif, dan mini-BATS testing engine.
"""

import sys
import os
import time
import tempfile
import shutil
from typing import Callable, List, Tuple

# ANSI Terminal Color Palette
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BG_DARK = "\033[40m"

def print_banner():
    banner = f"""
{TermColor.CYAN}{TermColor.BOLD}========================================================================
 LAB SIMULATOR: BAB 09 - DEFENSIVE SCRIPTING & BATS AUTOMATED TESTING
 Interactive Shell Safety Engine & Assertion Framework (Python 3)
========================================================================{TermColor.RESET}
"""
    print(banner)

class BashEnvironmentSimulator:
    """Simulasi eksekusi Bash dengan opsi defensif (set -euo pipefail) dan trap handler."""

    def __init__(self):
        self.set_e = False
        self.set_u = False
        self.set_pipefail = False
        self.variables = {"USER": "engineer", "PORT": "8080"}
        self.trap_actions = []
        self.temp_files = []

    def set_strict_mode(self, enabled: bool):
        self.set_e = enabled
        self.set_u = enabled
        self.set_pipefail = enabled
        status = f"{TermColor.GREEN}ENABLED (set -euo pipefail){TermColor.RESET}" if enabled else f"{TermColor.RED}DISABLED (default lenient bash){TermColor.RESET}"
        print(f"[*] Strict Mode: {status}")

    def register_trap(self, signal: str, callback: Callable):
        self.trap_actions.append((signal, callback))
        print(f"{TermColor.YELLOW}[TRAP REGISTERED]{TermColor.RESET} Signal: {signal} -> Handler disiapkan.")

    def run_trap_cleanup(self):
        print(f"\n{TermColor.MAGENTA}[TRAP TRIGGERED]{TermColor.RESET} Mengeksekusi penanganan sinyal & cleanup atomic...")
        for sig, cb in reversed(self.trap_actions):
            cb()
        self.trap_actions.clear()

    def get_var(self, name: str, default: str = None) -> str:
        if name in self.variables:
            return self.variables[name]
        if self.set_u:
            raise KeyError(f"Defensive Error (set -u): Variabel '${name}' belum diinisialisasi (unbound variable)!")
        return default if default is not None else ""

    def simulate_pipeline(self, exit_codes: List[int]) -> int:
        """Simulasi return code pipa perintah cmd1 | cmd2 | cmd3"""
        print(f"[*] Pipeline step exit codes: {exit_codes}")
        if self.set_pipefail:
            # Mengambil kode exit non-nol terakhir di pipeline
            failed = [c for c in exit_codes if c != 0]
            final_code = failed[-1] if failed else 0
        else:
            # Default Bash hanya mengecek elemen terakhir
            final_code = exit_codes[-1]
        return final_code

class MiniBatsRunner:
    """Simulasi framework test otomatis BATS (Bash Automated Testing System)."""

    def __init__(self):
        self.tests: List[Tuple[str, Callable[[], None]]] = []
        self.setup_fn = None
        self.teardown_fn = None

    def setup(self, fn: Callable[[], None]):
        self.setup_fn = fn

    def teardown(self, fn: Callable[[], None]):
        self.teardown_fn = fn

    def test(self, description: str):
        def decorator(fn: Callable[[], None]):
            self.tests.append((description, fn))
            return fn
        return decorator

    def run(self):
        print(f"\n{TermColor.BOLD}{TermColor.BLUE}=== MENJALANKAN TEST SUITE BATS (TAP 13 Format) ==={TermColor.RESET}")
        print(f"1..{len(self.tests)}")
        passed = 0
        failed = 0
        start_time = time.time()

        for idx, (desc, fn) in enumerate(self.tests, 1):
            if self.setup_fn:
                self.setup_fn()
            
            test_success = True
            error_msg = ""
            try:
                fn()
            except AssertionError as e:
                test_success = False
                error_msg = str(e)
            except Exception as e:
                test_success = False
                error_msg = f"Unexpected Error: {e}"
            finally:
                if self.teardown_fn:
                    self.teardown_fn()

            if test_success:
                passed += 1
                print(f"{TermColor.GREEN}ok {idx} - {desc}{TermColor.RESET}")
            else:
                failed += 1
                print(f"{TermColor.RED}not ok {idx} - {desc}{TermColor.RESET}")
                print(f"  {TermColor.RED}# Failure: {error_msg}{TermColor.RESET}")

        duration = time.time() - start_time
        summary_color = TermColor.GREEN if failed == 0 else TermColor.RED
        print(f"\n{summary_color}{TermColor.BOLD}Test Result: {passed} passed, {failed} failed in {duration:.4f}s{TermColor.RESET}")
        return failed == 0

def demo_strict_mode_and_pipefail():
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}--- SCENARIO 1: Perbedaan Bash Default vs set -euo pipefail ---{TermColor.RESET}")
    env = BashEnvironmentSimulator()
    
    # 1. Unbound variable test
    print(f"\n{TermColor.BOLD}Test A: Unbound Variable ($TARGET_DIR){TermColor.RESET}")
    env.set_strict_mode(False)
    val = env.get_var("TARGET_DIR")
    print(f"Lenient: TARGET_DIR bernilai '{val}' (Berbahaya jika `rm -rf /${'{TARGET_DIR}'}`)!")
    
    env.set_strict_mode(True)
    try:
        val = env.get_var("TARGET_DIR")
    except KeyError as err:
        print(f"Strict: {TermColor.RED}[DITANGKAP]{TermColor.RESET} {err}")

    # 2. Pipefail test
    print(f"\n{TermColor.BOLD}Test B: Pipeline Failure Detection (cat error.log | grep critical | wc -l){TermColor.RESET}")
    mock_pipeline = [1, 0, 0]  # cat gagal (1), tapi wc berhasil (0)
    
    env.set_strict_mode(False)
    code_default = env.simulate_pipeline(mock_pipeline)
    print(f"Lenient result code: {code_default} (Pipa dianggap SUKSES karena perintah terakhir 0!)")
    
    env.set_strict_mode(True)
    code_strict = env.simulate_pipeline(mock_pipeline)
    print(f"Strict result code: {TermColor.RED}{code_strict}{TermColor.RESET} (Pipa terdeteksi GAGAL karena ada perintah non-nol!)")

def demo_trap_atomic_cleanup():
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}--- SCENARIO 2: Trap Pattern & Atomic Temporary File Cleanup ---{TermColor.RESET}")
    env = BashEnvironmentSimulator()
    temp_dir = tempfile.mkdtemp(prefix="lab_bab09_")
    secret_scratch = os.path.join(temp_dir, "atomic_payload.tmp")
    
    with open(secret_scratch, "w") as f:
        f.write("temporary_production_credential_token=xyz123")
    print(f"[*] File sementara dibuat di: {secret_scratch}")

    def cleanup_handler():
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"{TermColor.GREEN}[CLEANUP SUCCESS]{TermColor.RESET} Folder scratch {temp_dir} dibersihkan secara aman.")

    env.register_trap("EXIT", cleanup_handler)
    print("[*] Melakukan kalkulasi skrip...")
    time.sleep(0.3)
    # Simulasi interupsi atau skrip selesai
    env.run_trap_cleanup()
    print(f"[*] Verifikasi eksistensi disk: {os.path.exists(temp_dir)} (Harus False)")

def demo_mini_bats():
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}--- SCENARIO 3: BATS Automated Testing Simulation ---{TermColor.RESET}")
    runner = MiniBatsRunner()

    context = {}

    @runner.setup
    def setup_fixture():
        context["env"] = BashEnvironmentSimulator()
        context["env"].set_strict_mode(True)

    @runner.teardown
    def teardown_fixture():
        context.clear()

    @runner.test("Verifikasi variabel wajib DATABASE_URL terdeteksi jika kosong")
    def test_missing_env():
        env: BashEnvironmentSimulator = context["env"]
        try:
            _ = env.get_var("DATABASE_URL")
            raise AssertionError("Seharusnya melempar KeyError untuk variabel unbound")
        except KeyError:
            pass

    @runner.test("Verifikasi parameter expansion default ${PORT:-3000}")
    def test_default_parameter():
        env: BashEnvironmentSimulator = context["env"]
        val = env.get_var("PORT", default="3000")
        assert val == "8080", f"Expected 8080, got {val}"

    @runner.test("Verifikasi pipefail menangkap error di tahap awal pipeline")
    def test_pipefail_detection():
        env: BashEnvironmentSimulator = context["env"]
        status = env.simulate_pipeline([127, 0])
        assert status == 127, f"Expected 127, got {status}"

    runner.run()

def interactive_menu():
    while True:
        print_banner()
        print(f"{TermColor.BOLD}Menu Simulasi Lab:{TermColor.RESET}")
        print("  1. Simulasi Strict Mode (`set -euo pipefail`) vs Lenient Bash")
        print("  2. Simulasi Signal Trap Handler & Atomic Cleanup")
        print("  3. Jalankan BATS Testing Engine (Automated Spec Assertions)")
        print("  4. Jalankan Semua Skenario Sekaligus (All-in-One Benchmark)")
        print("  5. Keluar")
        
        choice = input(f"\n{TermColor.CYAN}Pilih opsi [1-5]: {TermColor.RESET}").strip()
        if choice == "1":
            demo_strict_mode_and_pipefail()
        elif choice == "2":
            demo_trap_atomic_cleanup()
        elif choice == "3":
            demo_mini_bats()
        elif choice == "4":
            demo_strict_mode_and_pipefail()
            demo_trap_atomic_cleanup()
            demo_mini_bats()
        elif choice == "5" or choice.lower() in ("q", "exit"):
            print(f"\n{TermColor.GREEN}Lab selesai. Tetap terapkan defensive scripting di produksi!{TermColor.RESET}\n")
            break
        else:
            print(f"{TermColor.RED}Pilihan tidak valid, silakan coba lagi.{TermColor.RESET}")
        
        input(f"\n{TermColor.DIM}Tekan [Enter] untuk kembali ke menu...{TermColor.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        print_banner()
        demo_strict_mode_and_pipefail()
        demo_trap_atomic_cleanup()
        demo_mini_bats()
    else:
        interactive_menu()
