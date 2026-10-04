#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktivitas, Argument Parsing & CLI Design (Bash Foundation)
BAB-08: Interaktivitas, Argument Parsing, dan CLI Design

Skrip ini mereplikasi mekanisme internal bash dalam menangani:
1. Positional Parameters ($0, $1..$N, $#, $@, $*) dan mekanisme `shift`
2. Parsing Flag & Opsi ala Bash Built-in `getopts` (short flags & flags with arguments)
3. Subcommand routing (pola CLI modern seperti Docker / Git / kubectl)
4. Interaktivitas terminal (read -p, read -s/silent masking, read -t/timeout, confirm prompt)
5. ANSI Color Palette & Terminal Styling standar POSIX CLI
"""

import sys
import time
import getpass
from typing import List, Dict, Tuple, Optional, Any

# ==========================================
# 1. ANSI Color & Terminal Styling Constants
# ==========================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground Colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background Colors
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def print_banner():
    banner = f"""{Style.CYAN}{Style.BOLD}
========================================================================
   BASH FOUNDATION SIMULATOR: BAB-08 CLI DESIGN & INTERACTIVITY
========================================================================{Style.RESET}"""
    print(banner)

def log_info(msg: str):
    print(f"{Style.BLUE}[INFO]{Style.RESET} {msg}")

def log_success(msg: str):
    print(f"{Style.GREEN}[SUCCESS]{Style.RESET} {msg}")

def log_warn(msg: str):
    print(f"{Style.YELLOW}[WARN]{Style.RESET} {msg}")

def log_error(msg: str):
    print(f"{Style.RED}{Style.BOLD}[ERROR]{Style.RESET} {msg}")

# ==========================================
# 2. Simulasi Positional Parameters & Shift
# ==========================================
class BashPositionalSimulator:
    """
    Simulasi variabel bawaan Bash:
    $0 = Nama script
    $1..$n = Parameter posisi
    $# = Total jumlah parameter
    $@ / $* = Kumpulan semua parameter
    shift = Menggeser pointer parameter ($2 jadi $1, $# berkurang 1)
    """
    def __init__(self, script_name: str, args: List[str]):
        self.script_name = script_name
        self.params = list(args)
        self.initial_count = len(args)

    def status(self) -> str:
        param_list_repr = " ".join([f'"{p}"' for p in self.params]) if self.params else "<empty>"
        return (f"[$# = {len(self.params)}] "
                f"[$0 = {self.script_name}] "
                f"[$1 = {self.params[0] if self.params else '<unset>'}] "
                f"[$@ = {param_list_repr}]")

    def shift(self, n: int = 1) -> Optional[str]:
        if not self.params:
            return None
        shifted = []
        for _ in range(min(n, len(self.params))):
            shifted.append(self.params.pop(0))
        return shifted[0] if len(shifted) == 1 else str(shifted)

# ==========================================
# 3. Simulasi Bash 'getopts' Engine
# ==========================================
class BashGetoptsSimulator:
    """
    Simulasi built-in `getopts "vhf:o:" opt`:
    - Karakter tanpa ':' adalah boolean switch (-v, -h)
    - Karakter dengan ':' memerlukan argumen tambahan (-f filename, -o out)
    - Menyimpan nilai ke OPTARG dan indeks ke OPTIND
    """
    def __init__(self, optstring: str, args: List[str]):
        self.optstring = optstring
        self.args = list(args)
        self.optind = 0
        self.optarg: Optional[str] = None
        self.optopt: Optional[str] = None
        self.parsed_flags: Dict[str, Any] = {}

    def parse(self) -> Dict[str, Any]:
        spec: Dict[str, bool] = {}
        i = 0
        while i < len(self.optstring):
            opt_char = self.optstring[i]
            if opt_char == ':':
                i += 1
                continue
            requires_arg = (i + 1 < len(self.optstring) and self.optstring[i + 1] == ':')
            spec[opt_char] = requires_arg
            i += 1

        idx = 0
        while idx < len(self.args):
            arg = self.args[idx]
            if not arg.startswith('-') or arg == '-':
                break  # Berhenti jika menemui non-flag atau positional arg
            if arg == '--':
                idx += 1
                break  # Tanda akhir flags ala POSIX standard

            # Penanganan combined short flags (e.g., -vh atau -f myfile)
            char_idx = 1
            while char_idx < len(arg):
                opt = arg[char_idx]
                if opt not in spec:
                    self.optopt = opt
                    log_error(f"getopts: illegal option -- {opt}")
                    self.parsed_flags['?'] = opt
                    char_idx += 1
                    continue

                requires_arg = spec[opt]
                if requires_arg:
                    # Cek sisa karakter dalam argument yang sama (-fValue) atau argumen berikutnya (-f Value)
                    remaining_in_arg = arg[char_idx + 1:]
                    if remaining_in_arg:
                        self.optarg = remaining_in_arg
                        self.parsed_flags[opt] = self.optarg
                        char_idx = len(arg)  # Habiskan argumen ini
                    else:
                        idx += 1
                        if idx < len(self.args):
                            self.optarg = self.args[idx]
                            self.parsed_flags[opt] = self.optarg
                        else:
                            log_error(f"getopts: option requires an argument -- {opt}")
                            self.parsed_flags[':'] = opt
                    break
                else:
                    self.parsed_flags[opt] = True
                    char_idx += 1
            idx += 1

        self.optind = idx
        return self.parsed_flags

# ==========================================
# 4. Simulasi Bash 'read' Interaktif
# ==========================================
class BashReadSimulator:
    """
    Simulasi fitur perintah bawaan Bash `read`:
    - `read -p "prompt"`: Prompt dengan teks kustom
    - `read -s`: Silent input (menyembunyikan input kata sandi)
    - `read -n 1`: Membaca single-character (e.g. konfirmasi [y/N])
    - Default value fallback jika input kosong
    """
    @staticmethod
    def prompt(prompt_text: str, default: Optional[str] = None) -> str:
        default_hint = f" [{Style.CYAN}{default}{Style.RESET}]" if default else ""
        sys.stdout.write(f"{Style.BOLD}{prompt_text}{default_hint}: {Style.RESET}")
        sys.stdout.flush()
        try:
            val = sys.stdin.readline()
            if not val:
                return default or ""
            val = val.strip()
            return val if val else (default or "")
        except (KeyboardInterrupt, EOFError):
            print()
            return default or ""

    @staticmethod
    def prompt_secret(prompt_text: str) -> str:
        sys.stdout.write(f"{Style.BOLD}{prompt_text}: {Style.RESET}")
        sys.stdout.flush()
        try:
            val = getpass.getpass(prompt="")
            return val
        except (KeyboardInterrupt, EOFError):
            print()
            return ""

    @staticmethod
    def confirm(prompt_text: str, default_yes: bool = False) -> bool:
        hint = "[Y/n]" if default_yes else "[y/N]"
        sys.stdout.write(f"{Style.YELLOW}{prompt_text} {hint}: {Style.RESET}")
        sys.stdout.flush()
        try:
            answer = sys.stdin.readline().strip().lower()
            if not answer:
                return default_yes
            return answer in ("y", "yes", "ya")
        except (KeyboardInterrupt, EOFError):
            print()
            return False

# ==========================================
# 5. CLI Controller & Help Menu
# ==========================================
def print_help():
    help_text = f"""
{Style.BOLD}PENGGUNAAN:{Style.RESET}
    python3 lab_exercise.py [SUBCOMMAND] [OPTIONS]

{Style.BOLD}SUBCOMMANDS TERSEDIA:{Style.RESET}
    {Style.GREEN}demo-positional{Style.RESET}   Simulasi penggeseran positional parameter ($1..$N dan `shift`)
    {Style.GREEN}demo-getopts{Style.RESET}      Simulasi parsing flag bergaya Bash getopts
    {Style.GREEN}demo-interactive{Style.RESET}  Simulasi pembacaan input user interaktif (read -p, read -s)
    {Style.GREEN}all{Style.RESET}               Menjalankan seluruh rangkaian demo secara berurutan

{Style.BOLD}OPSI GETOPTS (Contoh: -v, -h, -f <file>, -u <user>):{Style.RESET}
    -v          Mode verbose (output detail)
    -h          Tampilkan bantuan ini
    -f <path>   Tentukan file target
    -u <name>   Tentukan nama operator

{Style.BOLD}CONTOH PENGGUNAAN:{Style.RESET}
    python3 lab_exercise.py demo-positional argumen_satu argumen_dua argumen_tiga
    python3 lab_exercise.py demo-getopts -v -f /var/log/syslog -u admin
    python3 lab_exercise.py demo-interactive
"""
    print(help_text)

def run_positional_demo(args: List[str]):
    print(f"\n{Style.MAGENTA}{Style.BOLD}=== SIMULASI 1: POSITIONAL PARAMETERS & SHIFT ==={Style.RESET}")
    sample_args = args if args else ["alpha.txt", "beta.conf", "gamma.log", "delta.json"]
    sim = BashPositionalSimulator(script_name="deploy_service.sh", args=sample_args)
    
    log_info(f"Kondisi Awal: {sim.status()}")
    step = 1
    while sim.params:
        time.sleep(0.1)
        shifted = sim.shift()
        print(f"  {Style.YELLOW}--> [Langkah {step}] Eksekusi 'shift 1':{Style.RESET} membuang '{shifted}'")
        log_info(f"State Baru  : {sim.status()}")
        step += 1
    log_success("Seluruh parameter telah habis diproses via loop 'while [ $# -gt 0 ]'.")

def run_getopts_demo(raw_args: List[str]):
    print(f"\n{Style.MAGENTA}{Style.BOLD}=== SIMULASI 2: GETOPTS PARSER ENGINE ==={Style.RESET}")
    test_args = raw_args if raw_args else ["-v", "-f", "/etc/nginx/nginx.conf", "-u", "sysadmin", "extra_pos1"]
    optstring = "vhf:u:"
    log_info(f"Format Optstring: '{optstring}' (v,h: boolean; f,u: butuh argumen)")
    log_info(f"Input Argumen   : {' '.join(test_args)}")
    
    parser = BashGetoptsSimulator(optstring, test_args)
    parsed = parser.parse()
    
    print(f"\n{Style.BOLD}Hasil Parsing Flag:{Style.RESET}")
    for k, v in parsed.items():
        print(f"  - Flag {Style.CYAN}-{k}{Style.RESET} => {Style.GREEN}{v}{Style.RESET}")
    
    remaining_pos = test_args[parser.optind:]
    print(f"  - Parameter Non-Flag Tersisa ($@ setelah OPTIND): {remaining_pos}")
    log_success("Parsing getopts selesai tanpa error fatal.")

def run_interactive_demo():
    print(f"\n{Style.MAGENTA}{Style.BOLD}=== SIMULASI 3: INTERAKTIVITAS & BASH READ ==={Style.RESET}")
    
    username = BashReadSimulator.prompt("Masukkan Username Sistem", default="devops_user")
    log_info(f"Username tercatat: {Style.GREEN}{username}{Style.RESET}")
    
    secret = BashReadSimulator.prompt_secret("Masukkan Token API Rahasia (read -s simulasi)")
    masked = "*" * len(secret) if secret else "<kosong>"
    log_info(f"Secret masking check: {Style.GREEN}{masked}{Style.RESET}")
    
    do_deploy = BashReadSimulator.confirm("Apakah Anda yakin ingin memicu deploy ke production?", default_yes=False)
    if do_deploy:
        log_warn("Memicu deployment ke cluster production...")
        for i in range(1, 4):
            time.sleep(0.1)
            print(f"  {Style.CYAN}[Deploying phase {i}/3] Sinkronisasi konfigurasi...{Style.RESET}")
        log_success("Deploy sukses diselesaikan!")
    else:
        log_info("Deploy dibatalkan oleh pengguna (Safe Exit).")

def main():
    print_banner()
    raw_args = sys.argv[1:]
    
    if not raw_args or "-h" in raw_args or "--help" in raw_args:
        print_help()
        # Jika dijalankan tanpa argumen dalam test runner, jalankan demo ringkas
        if not raw_args:
            print(f"{Style.YELLOW}Tidak ada argumen diberikan. Menjalankan mode demo lengkap...{Style.RESET}")
            run_positional_demo([])
            run_getopts_demo([])
            print(f"\n{Style.BLUE}Mode interaktif dilewati pada eksekusi otomatis. Jalankan: python3 lab_exercise.py demo-interactive{Style.RESET}")
        return

    subcmd = raw_args[0]
    subcmd_args = raw_args[1:]

    if subcmd == "demo-positional":
        run_positional_demo(subcmd_args)
    elif subcmd == "demo-getopts":
        run_getopts_demo(subcmd_args)
    elif subcmd == "demo-interactive":
        run_interactive_demo()
    elif subcmd == "all":
        run_positional_demo([])
        run_getopts_demo([])
        run_interactive_demo()
    else:
        log_error(f"Subcommand tidak dikenal: '{subcmd}'")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
