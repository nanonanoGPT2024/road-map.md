#!/usr/bin/env python3
"""
Lab Hands-on: Shell-Bash Chapter 08 - Interaktivitas, Argument Parsing, & CLI Interface Design.
Simulasi Arsitektur POSIX/GNU Argument Lexer, State Machine Parser, dan Interactive Prompt Engine.
"""

import sys
import os
import re
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field

# ==========================================
# Terminal ANSI Color & Styling Definitions
# ==========================================
class Style:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

@dataclass
class OptionRule:
    """Mendefinisikan spesifikasi opsi CLI (mirip getopts/GNU getopt_long)."""
    short_opt: Optional[str]
    long_opt: Optional[str]
    has_arg: bool          # True jika membutuhkan argumen lanjutan
    arg_name: str = "VAL"
    description: str = ""
    default: Any = None

class POSIXArgParser:
    """
    State Machine Parser yang mengimplementasikan aturan sintaks utilitas POSIX.1-2017
    dan ekstensi GNU getopt_long (e.g., flag bundling '-xvf', inline value '--opt=val',
    dan end-of-options '--').
    """

    def __init__(self, program_name: str):
        self.program_name = program_name
        self.rules: Dict[str, OptionRule] = {}
        self.parsed_options: Dict[str, Any] = {}
        self.positional_args: List[str] = []

    def add_option(self, short_opt: Optional[str], long_opt: Optional[str],
                   has_arg: bool = False, arg_name: str = "VAL",
                   description: str = "", default: Any = None) -> None:
        """Mendaftarkan aturan flag CLI ke parser dictionary."""
        rule = OptionRule(short_opt, long_opt, has_arg, arg_name, description, default)
        if short_opt:
            self.rules[f"-{short_opt}"] = rule
        if long_opt:
            self.rules[f"--{long_opt}"] = rule
        if default is not None:
            canonical_name = long_opt or short_opt
            self.parsed_options[canonical_name] = default

    def _get_canonical_name(self, rule: OptionRule) -> str:
        return rule.long_opt if rule.long_opt else (rule.short_opt or "unknown")

    def parse(self, argv: List[str]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Melakukan eksekusi state-machine scanning pada daftar argument token.
        Menghasilkan dictionary opsi yang diekstrak dan list positional arguments ($1, $2, ...).
        """
        self.parsed_options.clear()
        self.positional_args.clear()
        
        idx = 0
        end_of_flags = False

        while idx < len(argv):
            token = argv[idx]

            # Jika sudah ketemu '--', sisa token mutlak menjadi positional args
            if end_of_flags:
                self.positional_args.append(token)
                idx += 1
                continue

            if token == "--":
                end_of_flags = True
                idx += 1
                continue

            # Handler: Long Option (--option atau --option=value)
            if token.startswith("--") and len(token) > 2:
                if "=" in token:
                    flag_part, inline_val = token.split("=", 1)
                    if flag_part not in self.rules:
                        raise ValueError(f"Opsi tidak dikenali: {flag_part}")
                    rule = self.rules[flag_part]
                    if not rule.has_arg:
                        raise ValueError(f"Opsi {flag_part} tidak menerima argumen!")
                    self.parsed_options[self._get_canonical_name(rule)] = inline_val
                else:
                    if token not in self.rules:
                        raise ValueError(f"Opsi tidak dikenali: {token}")
                    rule = self.rules[token]
                    if rule.has_arg:
                        idx += 1
                        if idx >= len(argv):
                            raise ValueError(f"Opsi {token} membutuhkan parameter nilai!")
                        self.parsed_options[self._get_canonical_name(rule)] = argv[idx]
                    else:
                        self.parsed_options[self._get_canonical_name(rule)] = True
                idx += 1
                continue

            # Handler: Short Option Bundling (-a, -xzf, -oFILE, -o FILE)
            if token.startswith("-") and len(token) > 1:
                sub_idx = 1
                while sub_idx < len(token):
                    char = token[sub_idx]
                    lookup = f"-{char}"
                    if lookup not in self.rules:
                        raise ValueError(f"Opsi pendek tidak valid: -{char}")
                    rule = self.rules[lookup]

                    if rule.has_arg:
                        # Value nempel langsung di short opt (misal: -p8080)
                        if sub_idx + 1 < len(token):
                            val = token[sub_idx + 1:]
                            self.parsed_options[self._get_canonical_name(rule)] = val
                            break
                        # Value ada di token berikutnya (misal: -p 8080)
                        else:
                            idx += 1
                            if idx >= len(argv):
                                raise ValueError(f"Opsi -{char} membutuhkan argumen nilai!")
                            self.parsed_options[self._get_canonical_name(rule)] = argv[idx]
                            break
                    else:
                        # Standalone boolean flag dalam bundle
                        self.parsed_options[self._get_canonical_name(rule)] = True
                    sub_idx += 1
                idx += 1
                continue

            # Standalone positional argument
            self.positional_args.append(token)
            idx += 1

        return self.parsed_options, self.positional_args


class BashInteractiveIO:
    """
    Simulasi subsistem interaktif terminal:
    Meniru behaviour Bash 'read -p', sanitasi input, regex constraint, dan yes/no prompts.
    """

    @staticmethod
    def prompt_text(prompt: str, default: Optional[str] = None, regex_pattern: Optional[str] = None,
                    max_attempts: int = 3, simulated_inputs: Optional[List[str]] = None) -> str:
        """Meminta input teks dengan validasi format dan toleransi retry."""
        full_prompt = f"{Style.CYAN}?{Style.RESET} {prompt}"
        if default:
            full_prompt += f" {Style.DIM}[default: {default}]{Style.RESET}"
        full_prompt += ": "

        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            print(full_prompt, end="", flush=True)
            
            # Mendukung simulasi input terprogram atau membaca stdin nyata
            if simulated_inputs is not None and len(simulated_inputs) > 0:
                raw_input = simulated_inputs.pop(0)
                print(f"{Style.YELLOW}{raw_input}{Style.RESET}")
            else:
                raw_input = sys.stdin.readline().rstrip("\r\n")

            value = raw_input.strip() if raw_input.strip() else (default or "")

            if not value and default is None:
                print(f"{Style.RED}  [Error] Input tidak boleh kosong! (Percobaan {attempts}/{max_attempts}){Style.RESET}")
                continue

            if regex_pattern and not re.match(regex_pattern, value):
                print(f"{Style.RED}  [Error] Pola tidak cocok dengan '{regex_pattern}'! (Percobaan {attempts}/{max_attempts}){Style.RESET}")
                continue

            return value

        raise TimeoutError(f"Gagal memvalidasi input setelah {max_attempts} percobaan.")

    @staticmethod
    def prompt_confirm(prompt: str, default_yes: bool = False,
                       simulated_inputs: Optional[List[str]] = None) -> bool:
        """Membuat konfirmasi biner interaktif [Y/n] atau [y/N]."""
        suffix = "[Y/n]" if default_yes else "[y/N]"
        full_prompt = f"{Style.MAGENTA}?{Style.RESET} {prompt} {Style.BOLD}{suffix}{Style.RESET}: "
        
        print(full_prompt, end="", flush=True)
        if simulated_inputs is not None and len(simulated_inputs) > 0:
            val = simulated_inputs.pop(0)
            print(f"{Style.YELLOW}{val}{Style.RESET}")
        else:
            val = sys.stdin.readline().strip().lower()

        if not val:
            return default_yes
        return val in ("y", "yes", "true", "1")


def run_cli_parser_tests():
    """Menjalankan automated test harness untuk POSIX/GNU arg parsing engine."""
    print(f"\n{Style.BOLD}{Style.BLUE}=== [1/2] BENCHMARK & HARNESS: POSIX/GNU ARGUMENT PARSER ==={Style.RESET}\n")

    parser = POSIXArgParser("sysadmin-deploy")
    parser.add_option("v", "verbose", has_arg=False, description="Tingkatkan verbositas log")
    parser.add_option("f", "force", has_arg=False, description="Abaikan dependensi konflik")
    parser.add_option("o", "output", has_arg=True, arg_name="PATH", description="File target output")
    parser.add_option("e", "env", has_arg=True, arg_name="ENV_NAME", description="Target deployment env", default="staging")
    parser.add_option(None, "dry-run", has_arg=False, description="Simulasikan proses tanpa mutasi sistem")

    test_cases = [
        {
            "name": "Single & Short-Bundling dengan Value Inline (-vf -o/opt/app)",
            "args": ["-vf", "-o/opt/app", "cluster-alpha", "cluster-beta"]
        },
        {
            "name": "GNU Long Flags dengan Equals Syntax (--output=/var/log/deploy.log --dry-run)",
            "args": ["--verbose", "--output=/var/log/deploy.log", "--dry-run", "target-node"]
        },
        {
            "name": "End-of-Options Boundary Delimiter (--) Menghalangi Flag Injection",
            "args": ["-v", "--", "-weird-filename.tar.gz", "--force"]
        }
    ]

    for idx, tc in enumerate(test_cases, 1):
        print(f"{Style.BOLD}Test Case #{idx}: {tc['name']}{Style.RESET}")
        print(f"  {Style.DIM}Invocations: {tc['args']}{Style.RESET}")
        start_time = time.perf_counter()
        opts, pos = parser.parse(tc["args"])
        elapsed = (time.perf_counter() - start_time) * 1_000_000

        print(f"  {Style.GREEN}✓ Parsed Options   :{Style.RESET} {opts}")
        print(f"  {Style.GREEN}✓ Positional ($@)  :{Style.RESET} {pos}")
        print(f"  {Style.CYAN}✓ Parsing Latency  :{Style.RESET} {elapsed:.2f} µs\n")


def run_interactive_simulation():
    """Mensimulasikan flow wizard interaktif shell administration."""
    print(f"{Style.BOLD}{Style.BLUE}=== [2/2] SIMULASI INTERACTIVE PROMPT ENGINE (Bash 'read' Pipeline) ==={Style.RESET}\n")

    mock_keystrokes = [
        "192.168.1.999",      # Format IP invalid (gagal regex)
        "10.0.4.15",          # Format valid
        "8443",               # Custom port
        "db-user-core",       # Username
        "yes"                 # Konfirmasi eksekusi
    ]

    print(f"{Style.DIM}Memulai simulasi sesi I/O terminal terstruktur...{Style.RESET}\n")

    # Prompt IP Target dengan validasi IPv4 Regex
    ip_target = BashInteractiveIO.prompt_text(
        prompt="Masukkan Host IP Target Node",
        default="127.0.0.1",
        regex_pattern=r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
        simulated_inputs=mock_keystrokes
    )

    # Prompt Port dengan Default Value
    port = BashInteractiveIO.prompt_text(
        prompt="Port Service Listener",
        default="443",
        regex_pattern=r"^\d{2,5}$",
        simulated_inputs=mock_keystrokes
    )

    # Prompt Operator Identity
    operator = BashInteractiveIO.prompt_text(
        prompt="Operator ID Identifier",
        default="admin",
        simulated_inputs=mock_keystrokes
    )

    # Confirmation Gate
    confirmed = BashInteractiveIO.prompt_confirm(
        prompt=f"Terapkan konfigurasi ke endpoint {ip_target}:{port}?",
        default_yes=False,
        simulated_inputs=mock_keystrokes
    )

    print(f"\n{Style.BOLD}--- Status Ringkasan Eksekusi ---{Style.RESET}")
    print(f"Endpoint Node : {Style.CYAN}{ip_target}:{port}{Style.RESET}")
    print(f"Operator      : {Style.YELLOW}{operator}{Style.RESET}")
    print(f"Disetujui     : {Style.GREEN if confirmed else Style.RED}{confirmed}{Style.RESET}")

    if confirmed:
        print(f"{Style.GREEN}-> State machine menerapkan perubahan konfigurasi secara aman.{Style.RESET}")
    else:
        print(f"{Style.RED}-> Eksekusi dibatalkan oleh pengguna.{Style.RESET}")


def main():
    print(f"{Style.BOLD}{Style.WHITE}=================================================================={Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE} LAB: BASH CLI DESIGN, ARGUMENT PARSING & INTERACTIVITY ENGINE    {Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE}=================================================================={Style.RESET}")
    
    run_cli_parser_tests()
    run_interactive_simulation()

    print(f"\n{Style.GREEN}{Style.BOLD}[✓] Seluruh modul verifikasi CLI & Argument Parser selesai dieksekusi.{Style.RESET}\n")


if __name__ == "__main__":
    main()