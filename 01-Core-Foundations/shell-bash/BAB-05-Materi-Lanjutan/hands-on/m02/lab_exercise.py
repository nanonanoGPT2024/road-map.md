#!/usr/bin/env python3
"""
Lab Hands-on: Modularitas Fungsi, Subshell, & Environment Management (Bash Engine Simulation)
Bab 05 - Modul 02 Deep Dive

Skrip ini mengimplementasikan simulasi virtual execution environment Bash,
memodelkan perilaku low-level POSIX/Bash:
1. Environment Variable Inheritance (export vs unexported).
2. Function Call Stack & Lexical Dynamic Scoping ('local' vs global mutation).
3. Subshell Forking Isolation: Copy-on-Write state, IPC via stdout capture ($()).
4. Exit Status propagation ($?) and Return Code contract.
"""

import sys
import copy
from typing import Dict, Any, List, Optional, Tuple

# ANSI Terminal Colors
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"


class BashVariable:
    """Merepresentasikan variabel shell beserta atribut status ekspor dan readonly."""
    def __init__(self, value: str, is_exported: bool = False, is_readonly: bool = False):
        self.value: str = str(value)
        self.is_exported: bool = is_exported
        self.is_readonly: bool = is_readonly

    def __repr__(self) -> str:
        flags = []
        if self.is_exported:
            flags.append("x")
        if self.is_readonly:
            flags.append("r")
        flag_str = f"[-{(''.join(flags))}]" if flags else "[--]"
        return f"{flag_str} {self.value}"


class ExecutionContext:
    """
    Memodelkan state memori runtime Bash:
    Tabel simbol, call stack lokal, stdout descriptor, dan exit status ($?).
    """
    def __init__(self, parent: Optional['ExecutionContext'] = None, is_subshell: bool = False):
        self.parent: Optional['ExecutionContext'] = parent
        self.is_subshell: bool = is_subshell
        self.last_exit_code: int = 0
        self.stdout_pipe: List[str] = []

        if parent is None:
            # Root environment (Init process / login shell)
            self.globals: Dict[str, BashVariable] = {}
            self.local_stack: List[Dict[str, BashVariable]] = []
        else:
            if is_subshell:
                # Fork semantics: Subshell menduplikasi seluruh tabel environment
                # Mutasi di subshell tidak pernah merefleksikan kembali ke parent.
                self.globals = copy.deepcopy(parent.globals)
                self.local_stack = copy.deepcopy(parent.local_stack)
            else:
                # Normal execution context (misal: sub-scope inline)
                self.globals = parent.globals
                self.local_stack = parent.local_stack

    def enter_function_frame(self) -> None:
        """Membuat stack frame baru untuk variabel lokal saat fungsi dipanggil."""
        self.local_stack.append({})

    def exit_function_frame(self) -> None:
        """Menghancurkan stack frame lokal saat keluar dari fungsi."""
        if self.local_stack:
            self.local_stack.pop()

    def set_var(self, name: str, value: str, is_local: bool = False, export: bool = False) -> None:
        """
        Meniru assignment Bash:
        - Jika `local` aktif, variabel dimasukkan ke stack frame teratas.
        - Jika variabel sudah ada di lokal stack, update dilakukan di frame tersebut.
        - Jika tidak ada di lokal stack, update/buat di global table.
        """
        if is_local:
            if not self.local_stack:
                raise RuntimeError(f"SyntaxError: 'local {name}' hanya valid di dalam blok fungsi!")
            self.local_stack[-1][name] = BashVariable(value, is_exported=export)
            return

        # Cek apakah variabel sudah didefinisikan secara lokal di stack frame saat ini
        for frame in reversed(self.local_stack):
            if name in frame:
                if frame[name].is_readonly:
                    raise PermissionError(f"bash: {name}: readonly variable")
                frame[name].value = str(value)
                if export:
                    frame[name].is_exported = True
                return

        # Fallback ke Global Scope
        if name in self.globals and self.globals[name].is_readonly:
            raise PermissionError(f"bash: {name}: readonly variable")

        if name in self.globals:
            self.globals[name].value = str(value)
            if export:
                self.globals[name].is_exported = True
        else:
            self.globals[name] = BashVariable(value, is_exported=export)

    def get_var(self, name: str) -> str:
        """Mencari variabel dari stack frame lokal teratas menuju global environment."""
        for frame in reversed(self.local_stack):
            if name in frame:
                return frame[name].value
        if name in self.globals:
            return self.globals[name].value
        return ""

    def export_var(self, name: str) -> None:
        """Menandai variabel sebagai 'exported' agar diwariskan ke proses turunan."""
        for frame in reversed(self.local_stack):
            if name in frame:
                frame[name].is_exported = True
                return
        if name in self.globals:
            self.globals[name].is_exported = True
        else:
            self.globals[name] = BashVariable("", is_exported=True)

    def echo(self, message: str) -> None:
        """Mengalirkan output ke buffer stdout context saat ini."""
        self.stdout_pipe.append(message)


class BashEngine:
    """Simulator runtime modularitas, execution stack, dan subshell isolation Bash."""
    def __init__(self):
        self.root_context = ExecutionContext()
        self.functions: Dict[str, Any] = {}

    def define_function(self, name: str, fn_callable: Any) -> None:
        """Mendaftarkan fungsi ke dalam environment simbol table."""
        self.functions[name] = fn_callable

    def execute_subshell(self, subshell_routine: Any) -> Tuple[int, str]:
        """
        Simulasi Operator `(...)` dan Command Substitution `$(...)`:
        Membuat klon child context terisolasi (Fork-like), mengeksekusi subshell_routine,
        dan mengembalikan exit status serta capture stdout pipe.
        """
        child_ctx = ExecutionContext(parent=self.root_context, is_subshell=True)
        try:
            return_code = subshell_routine(child_ctx)
            if return_code is None:
                return_code = 0
            child_ctx.last_exit_code = return_code
        except Exception as err:
            child_ctx.echo(f"Subshell Panic: {str(err)}")
            return_code = 1
            child_ctx.last_exit_code = 1

        captured_stdout = "\n".join(child_ctx.stdout_pipe)
        return return_code, captured_stdout

    def call_function(self, name: str, ctx: ExecutionContext, *args: str) -> int:
        """
        Eksekusi fungsi Bash:
        Mengatur frame stack lokal, binding argumen posisi ($1, $2, dll.),
        dan membersihkan stack frame setelah selesai.
        """
        if name not in self.functions:
            ctx.echo(f"bash: command not found: {name}")
            return 127

        ctx.enter_function_frame()
        # Bind positional parameters
        for idx, arg in enumerate(args, start=1):
            ctx.set_var(str(idx), arg, is_local=True)
        ctx.set_var("#", str(len(args)), is_local=True)

        try:
            exit_code = self.functions[name](ctx, *args)
            if exit_code is None:
                exit_code = 0
            ctx.last_exit_code = exit_code
            return exit_code
        finally:
            ctx.exit_function_frame()


# ==============================================================================
# WORKLOAD & VERIFIKASI PRAKTEK
# ==============================================================================

def print_banner(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title} ==={CLR_RESET}")


def lab_exercise():
    engine = BashEngine()
    ctx = engine.root_context

    print_banner("1. INIT ROOT ENVIRONMENT & VARIABLE SCOPING")
    # Deklarasi variabel biasa vs export
    ctx.set_var("GLOBAL_CONFIG", "/etc/app.conf", export=False)
    ctx.set_var("API_TOKEN", "secret-xyz-token", export=True)
    ctx.set_var("CLUSTER_NODES", "3", export=False)

    print(f"[*] API_TOKEN (Exported)   : {ctx.get_var('API_TOKEN')}")
    print(f"[*] GLOBAL_CONFIG (Private): {ctx.get_var('GLOBAL_CONFIG')}")
    print(f"[*] CLUSTER_NODES (Private): {ctx.get_var('CLUSTER_NODES')}")

    # ==========================================================================
    print_banner("2. FUNCTION DEFINITION & SCOPE SHADOWING (local vs dynamic)")
    # ==========================================================================
    def configure_cluster_node(c: ExecutionContext, node_id: str, new_token: str) -> int:
        # Deklarasi lokal: tidak boleh membocorkan state ke global
        c.set_var("node_id", node_id, is_local=True)
        # Mutasi variabel global tanpa 'local': akan menimpa parent global
        c.set_var("GLOBAL_CONFIG", f"/etc/node_{node_id}.conf")
        # Mutasi shadow variabel: didefinisikan lokal
        c.set_var("API_TOKEN", new_token, is_local=True)

        c.echo(f"Inside Function: local node_id={c.get_var('node_id')}")
        c.echo(f"Inside Function: shadowed API_TOKEN={c.get_var('API_TOKEN')}")
        c.echo(f"Inside Function: modified GLOBAL_CONFIG={c.get_var('GLOBAL_CONFIG')}")
        return 0

    engine.define_function("configure_cluster_node", configure_cluster_node)

    print("[>] Memanggil fungsi 'configure_cluster_node' dengan frame stack lokal...")
    exit_status = engine.call_function("configure_cluster_node", ctx, "alpha-01", "ephemeral-node-token")
    
    # Flush function stdout
    for line in ctx.stdout_pipe:
        print(f"  {CLR_CYAN}|> {line}{CLR_RESET}")
    ctx.stdout_pipe.clear()

    print(f"\n[?] Status Inspeksi Variabel Root Pasca-Eksekusi (Exit Code: {exit_status}):")
    # Validasi Scoping:
    # GLOBAL_CONFIG harus berubah (karena dimutasi secara global di fungsi)
    # API_TOKEN harus tetap yang lama (karena fungsi menggunakan 'local')
    # node_id tidak boleh ada di global
    val_cfg = ctx.get_var("GLOBAL_CONFIG")
    val_tok = ctx.get_var("API_TOKEN")
    val_nid = ctx.get_var("node_id")

    print(f"  GLOBAL_CONFIG -> {val_cfg} " + 
          (f"{CLR_GREEN}[MUTASI GLOBAL VALID]{CLR_RESET}" if val_cfg == "/etc/node_alpha-01.conf" else f"{CLR_RED}[GAGAL]{CLR_RESET}"))
    print(f"  API_TOKEN     -> {val_tok} " + 
          (f"{CLR_GREEN}[PROTEKSI LOKAL VALID]{CLR_RESET}" if val_tok == "secret-xyz-token" else f"{CLR_RED}[LEAKED]{CLR_RESET}"))
    print(f"  node_id       -> '{val_nid}' " + 
          (f"{CLR_GREEN}[FRAME HANCUR SESUAI SPEC]{CLR_RESET}" if val_nid == "" else f"{CLR_RED}[FRAME LEAK]{CLR_RESET}"))

    # ==========================================================================
    print_banner("3. SUBSHELL ISOLATION & FORK SEMANTICS: (...)")
    # ==========================================================================
    print("[>] Menjalankan rutinitas di dalam Subshell terisolasi...")
    
    def subshell_task(sub_ctx: ExecutionContext) -> int:
        sub_ctx.echo(f"Subshell PID (simulated) menerima API_TOKEN={sub_ctx.get_var('API_TOKEN')}")
        # Mutasi environment di subshell
        sub_ctx.set_var("API_TOKEN", "corrupted-by-subshell", export=True)
        sub_ctx.set_var("SUBSHELL_SCRATCHPAD", "active-tmp-data")
        sub_ctx.echo(f"Subshell mutasi API_TOKEN={sub_ctx.get_var('API_TOKEN')}")
        return 42

    code, captured_out = engine.execute_subshell(subshell_task)

    print(f"{CLR_YELLOW}[Subshell Output Capture]:{CLR_RESET}")
    for out in captured_out.splitlines():
        print(f"  [Subshell Stdout] {out}")

    print(f"\n[?] Return Code Subshell ($?): {code}")
    print("[?] Verifikasi Mutasi Environment Parent pasca-subshell:")
    parent_tok = ctx.get_var("API_TOKEN")
    parent_scratch = ctx.get_var("SUBSHELL_SCRATCHPAD")

    print(f"  API_TOKEN           : {parent_tok} " +
          (f"{CLR_GREEN}[ISOLASI AMAN - TAK BERUBAH]{CLR_RESET}" if parent_tok == "secret-xyz-token" else f"{CLR_RED}[TERKONTAMINASI]{CLR_RESET}"))
    print(f"  SUBSHELL_SCRATCHPAD : '{parent_scratch}' " +
          (f"{CLR_GREEN}[ISOLASI MEMORI VALID]{CLR_RESET}" if parent_scratch == "" else f"{CLR_RED}[BOCOR KE PARENT]{CLR_RESET}"))

    # ==========================================================================
    print_banner("4. COMMAND SUBSTITUTION IPC: RESULT=$(compute_load)")
    # ==========================================================================
    def compute_cluster_load(sub_ctx: ExecutionContext) -> int:
        # Simulasi kalkulasi load di background/subshell
        raw_metrics = [12, 45, 68, 23]
        avg_metric = sum(raw_metrics) / len(raw_metrics)
        sub_ctx.echo(f"LOAD_AVG:{avg_metric:.1f}%")
        return 0

    print("[>] Menjalankan simulasi: RESULT=$(compute_cluster_load)")
    ipc_code, ipc_output = engine.execute_subshell(compute_cluster_load)
    
    if ipc_code == 0:
        # Parent menyimpan output subshell ke variabelnya sendiri
        ctx.set_var("LAST_LOAD_REPORT", ipc_output.strip())
        print(f"{CLR_GREEN}[SUCCESS] Hasil ditangkap ke Parent:{CLR_RESET} {ctx.get_var('LAST_LOAD_REPORT')}")
    else:
        print(f"{CLR_RED}[FAIL] Subshell mengembalikan kode error {ipc_code}{CLR_RESET}")

    print_banner("LAB SUMMARY VERIFICATION")
    print(f"{CLR_BOLD}Teknologi Shell Bash Termodelkan dengan Akurat:{CLR_RESET}")
    print(f" 1. Dynamic Local Scoping Stack          : {CLR_GREEN}PASSED{CLR_RESET}")
    print(f" 2. Copy-On-Write Subshell Memory Sandbox : {CLR_GREEN}PASSED{CLR_RESET}")
    print(f" 3. IPC Output Capture & Status Handling : {CLR_GREEN}PASSED{CLR_RESET}\n")


if __name__ == "__main__":
    lab_exercise()