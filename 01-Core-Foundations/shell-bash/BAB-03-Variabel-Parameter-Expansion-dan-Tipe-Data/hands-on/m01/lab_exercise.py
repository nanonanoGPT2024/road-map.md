#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Parameter Expansion & Tipe Data Shell/Bash
BAB 03 - Variabel, Parameter Expansion, dan Tipe Data
"""

import sys
import re
import time

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
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================{RESET}
{MAGENTA}{BOLD}       LAB INTERAKTIF: BASH PARAMETER EXPANSION & VARIABLE ENGINE       {RESET}
{CYAN}{BOLD}       Modul M01 - BAB 03: Variabel, Expansion, Array & Tipe Data       {RESET}
{CYAN}{BOLD}========================================================================{RESET}
"""
    print(banner)


class BashSimulator:
    def __init__(self):
        # Environment simulation state
        self.variables = {
            "APP_ENV": "production",
            "CONFIG_FILE": "/etc/nginx/conf.d/app.conf",
            "USER_NAME": "developer_ops",
            "LOG_PATH": "app_backend_2026_10_05.log",
            "UNSET_VAR": None,
            "EMPTY_VAR": "",
            "TAGS": "linux:bash:devops:automation",
            "PROJECT": "kilo-platform",
        }
        self.arrays = {
            "SERVERS": ["web01", "web02", "db01", "redis01"],
        }
        self.score = 0
        self.total_tests = 0

    def print_var_table(self):
        print(f"\n{BOLD}{YELLOW}[+] Current Simulated Environment State:{RESET}")
        print(f"{CYAN}+--------------------+------------------------------------------+{RESET}")
        print(f"{CYAN}| Variable Name      | Current Value                            |{RESET}")
        print(f"{CYAN}+--------------------+------------------------------------------+{RESET}")
        for k, v in self.variables.items():
            val_display = "(unset)" if v is None else f'"{v}"'
            print(f"| {GREEN}{k:<18}{RESET} | {WHITE}{val_display:<40}{RESET} |")
        for k, arr in self.arrays.items():
            arr_display = f"({' '.join(arr)})"
            print(f"| {GREEN}{k:<18}{RESET} | {WHITE}{arr_display:<40}{RESET} |")
        print(f"{CYAN}+--------------------+------------------------------------------+{RESET}\n")

    def eval_expansion(self, expression: str) -> str:
        """
        Simulate Bash parameter expansion mechanics:
        - ${#var} -> length
        - ${var:-default} -> use default if unset/empty
        - ${var:=default} -> assign default if unset/empty
        - ${var:+alt} -> alternative if set and not empty
        - ${var:offset} or ${var:offset:len} -> substring
        - ${var#pattern} / ${var##pattern} -> strip prefix
        - ${var%pattern} / ${var%%pattern} -> strip suffix
        - ${var/pattern/replace} / ${var//pattern/replace} -> replace
        - ${var^^} / ${var,,} -> uppercase / lowercase
        - ${#arr[@]} -> array length
        """
        expr = expression.strip()
        if not (expr.startswith("${") and expr.endswith("}")):
            if expr.startswith("$") and expr[1:] in self.variables:
                val = self.variables[expr[1:]]
                return "" if val is None else val
            return expr

        inner = expr[2:-1]

        # Array length ${#arr[@]}
        if inner.startswith("#") and inner.endswith("[@]"):
            arr_name = inner[1:-3]
            if arr_name in self.arrays:
                return str(len(self.arrays[arr_name]))
            return "0"

        # String length ${#var}
        if inner.startswith("#"):
            var_name = inner[1:]
            val = self.variables.get(var_name)
            return "0" if val is None else str(len(val))

        # Case modification: ${var^^} or ${var,,}
        if inner.endswith("^^"):
            var_name = inner[:-2]
            val = self.variables.get(var_name, "") or ""
            return val.upper()
        if inner.endswith(",,"):
            var_name = inner[:-2]
            val = self.variables.get(var_name, "") or ""
            return val.lower()

        # Regex replacement ${var/pattern/repl} or ${var//pattern/repl}
        repl_match = re.match(r"^([A-Za-z0-9_]+)(/{1,2})([^/]*)(?:/(.*))?$", inner)
        if repl_match:
            var_name, slash, pattern, replacement = repl_match.groups()
            replacement = replacement if replacement is not None else ""
            val = self.variables.get(var_name, "") or ""
            regex_pat = re.escape(pattern)
            if slash == "//":
                return re.sub(regex_pat, replacement, val)
            else:
                return re.sub(regex_pat, replacement, val, count=1)

        # Prefix stripping ${var#pattern} or ${var##pattern}
        if "#" in inner:
            if "##" in inner:
                var_name, pat = inner.split("##", 1)
                val = self.variables.get(var_name, "") or ""
                # Greedy prefix
                regex_pat = "^" + re.escape(pat).replace(r"\*", ".*")
                match = re.search(regex_pat, val)
                if match:
                    return val[match.end():]
                return val
            else:
                var_name, pat = inner.split("#", 1)
                val = self.variables.get(var_name, "") or ""
                # Non-greedy prefix
                regex_pat = "^" + re.escape(pat).replace(r"\*", ".*?")
                match = re.search(regex_pat, val)
                if match:
                    return val[match.end():]
                return val

        # Suffix stripping ${var%pattern} or ${var%%pattern}
        if "%" in inner:
            if "%%" in inner:
                var_name, pat = inner.split("%%", 1)
                val = self.variables.get(var_name, "") or ""
                # Greedy suffix
                regex_pat = re.escape(pat).replace(r"\*", ".*") + "$"
                match = re.search(regex_pat, val)
                if match:
                    return val[:match.start()]
                return val
            else:
                var_name, pat = inner.split("%", 1)
                val = self.variables.get(var_name, "") or ""
                # Non-greedy suffix
                regex_pat = re.escape(pat).replace(r"\*", ".*?") + "$"
                match = re.search(regex_pat, val)
                if match:
                    return val[:match.start()]
                return val

        # Default fallback: ${var:-default}
        if ":-" in inner:
            var_name, default_val = inner.split(":-", 1)
            val = self.variables.get(var_name)
            return default_val if (val is None or val == "") else val

        # Default assign: ${var:=default}
        if ":=" in inner:
            var_name, default_val = inner.split(":=", 1)
            val = self.variables.get(var_name)
            if val is None or val == "":
                self.variables[var_name] = default_val
                return default_val
            return val

        # Alternative: ${var:+alt}
        if ":+" in inner:
            var_name, alt_val = inner.split(":+", 1)
            val = self.variables.get(var_name)
            return alt_val if (val is not None and val != "") else ""

        # Substring slicing: ${var:offset:length} or ${var:offset}
        slice_match = re.match(r"^([A-Za-z0-9_]+):(-?\d+)(?::(-?\d+))?$", inner)
        if slice_match:
            var_name, offset_s, len_s = slice_match.groups()
            val = self.variables.get(var_name, "") or ""
            offset = int(offset_s)
            if len_s is not None:
                length = int(len_s)
                return val[offset:offset + length]
            return val[offset:]

        # Normal variable retrieval
        return self.variables.get(inner, "") or ""


def run_interactive_evaluator(sim: BashSimulator):
    print(f"\n{BOLD}{BG_BLUE}=== MODE 1: LIVE PARAMETER EXPANSION PLAYGROUND ==={RESET}")
    print(f"{DIM}Ketik ekspresi parameter expansion (contoh: ${{CONFIG_FILE##*/}} atau ${{APP_ENV^^}}).")
    print(f"Ketik 'vars' untuk lihat variabel, 'help' untuk daftar sintaks, atau 'back' untuk kembali.{RESET}\n")

    while True:
        try:
            cmd = input(f"{BOLD}{GREEN}bash-sim$ {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue
        if cmd.lower() in ("back", "exit", "quit"):
            break
        elif cmd.lower() == "vars":
            sim.print_var_table()
        elif cmd.lower() == "help":
            print(f"""
{YELLOW}{BOLD}Daftar Sintaks Parameter Expansion yang Didukung:{RESET}
  {CYAN}${{#var}}{RESET}              -> Hitung panjang karakter string
  {CYAN}${{var:-default}}{RESET}      -> Gunakan default jika var kosong/unset
  {CYAN}${{var:=default}}{RESET}      -> Assign default ke var jika kosong/unset
  {CYAN}${{var:+alternate}}{RESET}    -> Tampilkan alternate hanya jika var bernilai
  {CYAN}${{var:offset:length}}{RESET}  -> Substring slicing dari offset
  {CYAN}${{var#pattern}}{RESET}        -> Hapus prefix terpendek (non-greedy)
  {CYAN}${{var##pattern}}{RESET}       -> Hapus prefix terpanjang (greedy)
  {CYAN}${{var%pattern}}{RESET}        -> Hapus suffix terpendek (non-greedy)
  {CYAN}${{var%%pattern}}{RESET}       -> Hapus suffix terpanjang (greedy)
  {CYAN}${{var/pattern/repl}}{RESET}  -> Ganti kecocokan pertama
  {CYAN}${{var//pattern/repl}}{RESET} -> Ganti semua kecocokan (global)
  {CYAN}${{var^^}}{RESET}             -> Konversi ke HURUF BESAR (uppercase)
  {CYAN}${{var,,}}{RESET}             -> Konversi ke huruf kecil (lowercase)
  {CYAN}${{#SERVERS[@]}}{RESET}        -> Jumlah elemen array SERVERS
            """)
        else:
            result = sim.eval_expansion(cmd)
            print(f"{BOLD}{WHITE}=> {GREEN}{result}{RESET}")


def run_challenge_quiz(sim: BashSimulator):
    print(f"\n{BOLD}{BG_GREEN}=== MODE 2: BASH PARAMETER EXPANSION CHALLENGE (10 SOAL) ==={RESET}")
    print(f"{DIM}Uji pemahaman Anda terhadap evaluasi parameter expansion shell bash.{RESET}\n")

    challenges = [
        {
            "q": "Ekspresi untuk mengambil basename nama file dari CONFIG_FILE ('app.conf'):",
            "expected": "${CONFIG_FILE##*/}",
            "hint": "Gunakan greedy prefix removal (##) dengan pattern */",
            "eval_target": "app.conf"
        },
        {
            "q": "Ekspresi untuk mengambil direktori dari CONFIG_FILE ('/etc/nginx/conf.d'):",
            "expected": "${CONFIG_FILE%/*}",
            "hint": "Gunakan non-greedy suffix removal (%) dengan pattern /*",
            "eval_target": "/etc/nginx/conf.d"
        },
        {
            "q": "Ekspresi untuk mengubah APP_ENV menjadi huruf besar ('PRODUCTION'):",
            "expected": "${APP_ENV^^}",
            "hint": "Gunakan case expansion ^^",
            "eval_target": "PRODUCTION"
        },
        {
            "q": "Ekspresi untuk mendapatkan panjang karakter dari USER_NAME ('developer_ops'):",
            "expected": "${#USER_NAME}",
            "hint": "Prefix tanda pagar # di depan nama variabel",
            "eval_target": "13"
        },
        {
            "q": "Ekspresi untuk fallback UNSET_VAR ke nilai default 'development':",
            "expected": "${UNSET_VAR:-development}",
            "hint": "Gunakan operator :-",
            "eval_target": "development"
        },
        {
            "q": "Ekspresi untuk mengganti semua separator ':' di TAGS dengan spasi ' ':",
            "expected": "${TAGS//:/ }",
            "hint": "Gunakan double slash // untuk global replace",
            "eval_target": "linux bash devops automation"
        },
        {
            "q": "Ekspresi untuk mengambil tahun '2026' dari LOG_PATH ('app_backend_2026_10_05.log') via slice:",
            "expected": "${LOG_PATH:12:4}",
            "hint": "Gunakan slice :offset:length (offset index ke-12, panjang 4 karakter)",
            "eval_target": "2026"
        },
        {
            "q": "Ekspresi untuk menghapus ekstensi file '.log' dari LOG_PATH:",
            "expected": "${LOG_PATH%.log}",
            "hint": "Gunakan suffix removal % dengan ekstensi .log",
            "eval_target": "app_backend_2026_10_05"
        },
        {
            "q": "Ekspresi untuk mengambil jumlah elemen dari array SERVERS:",
            "expected": "${#SERVERS[@]}",
            "hint": "Sintaks array length: ${#SERVERS[@]}",
            "eval_target": "4"
        },
        {
            "q": "Ekspresi untuk mengubah USER_NAME menjadi lowercase ('developer_ops'):",
            "expected": "${USER_NAME,,}",
            "hint": "Gunakan case expansion ,,",
            "eval_target": "developer_ops"
        }
    ]

    score = 0
    total = len(challenges)

    for i, ch in enumerate(challenges, 1):
        print(f"{BOLD}{CYAN}Soal {i}/{total}:{RESET} {WHITE}{ch['q']}{RESET}")
        user_input = input(f"{YELLOW}Jawaban Anda: {RESET}").strip()
        evaluated_val = sim.eval_expansion(user_input)

        if user_input == ch["expected"] or evaluated_val == ch["eval_target"]:
            print(f"{GREEN}{BOLD}[BENAR]{RESET} Output Bash: '{evaluated_val}'\n")
            score += 1
        else:
            print(f"{RED}{BOLD}[SALAH]{RESET} Input Anda menghasilkan: '{evaluated_val}'")
            print(f"{DIM}Petunjuk: {ch['hint']}")
            print(f"Jawaban referensi: {BOLD}{ch['expected']}{RESET} -> '{ch['eval_target']}'\n")

    print(f"{BOLD}====================================================={RESET}")
    print(f"Skor Akhir Anda: {BOLD}{score}/{total}{RESET} ({score/total*100:.1f}%)")
    if score == total:
        print(f"{GREEN}{BOLD}Luar Biasa! Anda menguasai Parameter Expansion Bash tingkat mahir!{RESET}\n")
    elif score >= 7:
        print(f"{YELLOW}{BOLD}Bagus! Pemahaman parameter expansion Anda sudah solid.{RESET}\n")
    else:
        print(f"{RED}{BOLD}Perlu latihan lebih giat pada operator pattern stripping & slicing.{RESET}\n")


def main():
    sim = BashSimulator()
    print_banner()
    sim.print_var_table()

    while True:
        print(f"{BOLD}MENU PILIHAN LAB:{RESET}")
        print(f"  {CYAN}1.{RESET} Playground Evaluator Interaktif (Eksplorasi Ekspresi Bebas)")
        print(f"  {CYAN}2.{RESET} Tantangan Mandiri (10 Soal Interaktif)")
        print(f"  {CYAN}3.{RESET} Tampilkan Ulang Tabel Variabel & Environment")
        print(f"  {CYAN}4.{RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}{YELLOW}Pilih opsi [1-4]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Sampai jumpa di modul hands-on berikutnya!{RESET}")
            sys.exit(0)

        if choice == "1":
            run_interactive_evaluator(sim)
        elif choice == "2":
            run_challenge_quiz(sim)
        elif choice == "3":
            sim.print_var_table()
        elif choice == "4":
            print(f"\n{GREEN}{BOLD}[OK] Sesi lab selesai. Selamat belajar Bash scripting!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 1-4.{RESET}\n")


if __name__ == "__main__":
    main()
