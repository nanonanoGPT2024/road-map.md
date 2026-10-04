#!/usr/bin/env python3
"""
Lab Exercise: BAB-04 Logika Kontrol, Arithmetic, dan Exit Codes (Shell/Bash)
Simulasi Interaktif & Verifikasi Konsep Fondasi Bash dalam Python 3 Murni.
"""

import sys
import time
import os

# ANSI Color Codes untuk Terminal Styling
class Color:
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
    BG_RED = "\033[41m"


def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
========================================================================
   LAB SIMULASI INTERAKTIF: BASH CONTROL LOGIC & EXIT CODES (BAB 04)
========================================================================{Color.RESET}
{Color.DIM}Topik: Exit Codes ($?), Test/Double Brackets [[ ]], Arithmetic $(( )), 
       Short-circuit (&&, ||), dan Konstruk Kondisional (if/case){Color.RESET}
"""
    print(banner)


class BashExitCodeSimulator:
    """Simulasi eksekusi pipeline dan inspeksi exit code ($?)."""

    COMMON_EXIT_CODES = {
        0: "Success / No Error",
        1: "General catchall error",
        2: "Misuse of shell builtins (syntax/missing arg)",
        126: "Command invoked cannot execute (Permission problem)",
        127: "Command not found ($PATH lookup failed)",
        128: "Invalid exit argument",
        130: "Script terminated by Control-C (128 + 2 SIGINT)",
        137: "Fatal error signal 9 (128 + 9 SIGKILL / OOM Killer)",
        143: "Fatal error signal 15 (128 + 15 SIGTERM)",
    }

    def explain_code(self, code: int):
        explanation = self.COMMON_EXIT_CODES.get(code, "Custom/Application defined error code")
        color = Color.GREEN if code == 0 else Color.RED
        print(f"{Color.BOLD}Inspect $?:{Color.RESET} {color}{code} -> {explanation}{Color.RESET}")


class BashArithmeticEngine:
    """Simulasi evaluasi aritmatika Bash $(( ... )). Bash hanya mendukung integer!"""

    @staticmethod
    def evaluate(expression: str):
        print(f"\n{Color.YELLOW}[Bash Arithmetic $(( {expression} ))]{Color.RESET}")
        try:
            # Bash integer arithmetic truncates towards zero
            # Mengganti pembagian float python dengan floor/int division
            sanitized = expression.replace("/", "//")
            result = eval(sanitized, {"__builtins__": {}}, {})
            if isinstance(result, float):
                result = int(result)
            print(f"  {Color.BOLD}Ekspresi Bash :{Color.RESET} echo $(( {expression} ))")
            print(f"  {Color.BOLD}Hasil Integer :{Color.RESET} {Color.GREEN}{result}{Color.RESET}")
            return result
        except ZeroDivisionError:
            print(f"  {Color.RED}bash: division by 0 (error token is \"0\"){Color.RESET}")
            return None
        except Exception as e:
            print(f"  {Color.RED}bash: syntax error: {e}{Color.RESET}")
            return None


class BashConditionSimulator:
    """Simulasi logika evaluasi [[ ... ]] serta short-circuit execution."""

    @staticmethod
    def test_file_operators(filepath: str, operator: str) -> int:
        """Simulasi operator file bash: -f, -d, -e, -s"""
        exists = os.path.exists(filepath)
        if operator == "-e":
            ret = 0 if exists else 1
        elif operator == "-f":
            ret = 0 if (exists and os.path.isfile(filepath)) else 1
        elif operator == "-d":
            ret = 0 if (exists and os.path.isdir(filepath)) else 1
        elif operator == "-s":
            ret = 0 if (exists and os.path.getsize(filepath) > 0) else 1
        else:
            print(f"{Color.RED}Operator tidak dikenal: {operator}{Color.RESET}")
            return 2

        status_str = f"{Color.GREEN}TRUE (0){Color.RESET}" if ret == 0 else f"{Color.RED}FALSE (1){Color.RESET}"
        print(f"  [[ {operator} \"{filepath}\" ]] -> Exit Status: {status_str}")
        return ret

    @staticmethod
    def test_integer_comparison(a: int, op: str, b: int) -> int:
        """Simulasi operator integer: -eq, -ne, -lt, -le, -gt, -ge"""
        ops = {
            "-eq": a == b,
            "-ne": a != b,
            "-lt": a < b,
            "-le": a <= b,
            "-gt": a > b,
            "-ge": a >= b,
        }
        if op not in ops:
            print(f"{Color.RED}Operator tidak valid untuk bilangan integer: {op}{Color.RESET}")
            return 2
        
        is_true = ops[op]
        ret = 0 if is_true else 1
        res_color = Color.GREEN if is_true else Color.RED
        print(f"  [[ {a} {op} {b} ]] => Evaluasi: {res_color}{'BERHASIL (Exit 0)' if is_true else 'GAGAL (Exit 1)'}{Color.RESET}")
        return ret

    @staticmethod
    def test_string_operators(s: str, op: str) -> int:
        """Simulasi operator string: -z (empty), -n (not empty)"""
        if op == "-z":
            is_true = (len(s) == 0)
        elif op == "-n":
            is_true = (len(s) > 0)
        else:
            print(f"{Color.RED}Operator string tidak valid: {op}{Color.RESET}")
            return 2
        ret = 0 if is_true else 1
        label = "True (0)" if is_true else "False (1)"
        print(f"  [[ {op} \"{s}\" ]] => String len: {len(s)} -> {label}")
        return ret


def simulate_short_circuit():
    """Simulasi rantai operator logika Bash: CMD1 && CMD2 || CMD3"""
    print(f"\n{Color.CYAN}{Color.BOLD}=== SIMULASI SHORT-CIRCUIT EVALUATION (&& dan ||) ==={Color.RESET}")
    scenarios = [
        ("Kondisi Sukses: (Exit 0) && (Perintah Lanjut)", True, "backup.sh sukses", "kirim_notif.sh"),
        ("Kondisi Gagal: (Exit 1) && (Tidak Dieksekusi)", False, "backup.sh gagal", "kirim_notif.sh"),
        ("Kondisi Fallback: (Exit 1) || (Eksekusi Fallback)", False, "ping db_host gagal", "restart_db.sh"),
        ("Kondisi Skip Fallback: (Exit 0) || (Fallback Diabaikan)", True, "ping db_host sukses", "restart_db.sh"),
    ]

    for title, first_cmd_success, desc1, desc2 in scenarios:
        print(f"\n{Color.BOLD}Skenario:{Color.RESET} {title}")
        time.sleep(0.1)
        exit1 = 0 if first_cmd_success else 1
        print(f"  CMD 1: '{desc1}' -> Exit Code: {Color.GREEN if exit1 == 0 else Color.RED}{exit1}{Color.RESET}")
        
        if "&&" in title:
            if exit1 == 0:
                print(f"  Operator '&&': Kiri menghasilkan 0, mengeksekusi kanan: {Color.CYAN}'{desc2}'{Color.RESET}")
            else:
                print(f"  Operator '&&': Kiri menghasilkan {exit1} (!= 0), {Color.YELLOW}SHORT-CIRCUIT: Kanan diabaikan.{Color.RESET}")
        else: # ||
            if exit1 != 0:
                print(f"  Operator '||': Kiri gagal (exit {exit1}), mengeksekusi fallback: {Color.MAGENTA}'{desc2}'{Color.RESET}")
            else:
                print(f"  Operator '||': Kiri sukses (exit 0), {Color.YELLOW}SHORT-CIRCUIT: Fallback tidak diperlukan.{Color.RESET}")


def interactive_menu():
    sim_exit = BashExitCodeSimulator()
    sim_arith = BashArithmeticEngine()
    sim_cond = BashConditionSimulator()

    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}--- PILIHAN MODUL PRAKTIKUM ---{Color.RESET}")
        print("1. Eksplorasi Exit Codes Standar Linux ($?)")
        print("2. Uji Aritmatika Integer Bash $(( ekspresi ))")
        print("3. Uji Operator Kondisional [[ -eq, -ne, -lt, -gt ]]")
        print("4. Uji Operator String & File [[ -z, -n, -f, -d ]]")
        print("5. Jalankan Demo Short-Circuit Execution (&& / ||)")
        print("6. Keluar (exit 0)")

        try:
            choice = input(f"\n{Color.CYAN}Pilih menu [1-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Menerima sinyal keluar. Goodbye!{Color.RESET}")
            break

        if choice == "1":
            print(f"\n{Color.YELLOW}Daftar Exit Code Umum Bash:{Color.RESET}")
            for code in [0, 1, 2, 126, 127, 130, 137, 143]:
                sim_exit.explain_code(code)
            
            val = input(f"\n{Color.CYAN}Masukkan sembarang integer exit code (0-255) untuk diuji: {Color.RESET}").strip()
            if val.isdigit():
                sim_exit.explain_code(int(val))
            else:
                print(f"{Color.RED}Input harus berupa angka.{Color.RESET}")

        elif choice == "2":
            print(f"\n{Color.YELLOW}Contoh ekspresi valid: 10 + 5 * 2, (100 - 20) / 4, 17 % 5, 2**8{Color.RESET}")
            expr = input(f"{Color.CYAN}Masukkan ekspresi aritmatika: {Color.RESET}").strip()
            if expr:
                sim_arith.evaluate(expr)

        elif choice == "3":
            print(f"\n{Color.YELLOW}Uji komparasi integer bash [[ NUM1 OP NUM2 ]]{Color.RESET}")
            try:
                n1 = int(input("  Nilai A : ").strip())
                op = input("  Operator (-eq, -ne, -lt, -le, -gt, -ge): ").strip()
                n2 = int(input("  Nilai B : ").strip())
                sim_cond.test_integer_comparison(n1, op, n2)
            except ValueError:
                print(f"{Color.RED}Input bilangan harus valid.{Color.RESET}")

        elif choice == "4":
            print(f"\n{Color.YELLOW}Uji status string dan file:{Color.RESET}")
            txt = input("  Masukkan teks sembarang (atau tekan Enter untuk string kosong): ")
            sim_cond.test_string_operators(txt, "-z")
            sim_cond.test_string_operators(txt, "-n")

            test_path = input("\n  Masukkan path file/folder untuk dicek (contoh: /etc/passwd atau .): ").strip()
            if test_path:
                sim_cond.test_file_operators(test_path, "-e")
                sim_cond.test_file_operators(test_path, "-f")
                sim_cond.test_file_operators(test_path, "-d")

        elif choice == "5":
            simulate_short_circuit()

        elif choice == "6":
            print(f"{Color.GREEN}Selesai. Exit code: 0{Color.RESET}")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1-6.{Color.RESET}")


def run_automated_check():
    """Mode non-interaktif untuk automated CI/CD validation."""
    print(f"{Color.MAGENTA}[AUTOMATED CHECK MODE RUNNING]{Color.RESET}")
    engine = BashArithmeticEngine()
    assert engine.evaluate("10 + 20") == 30, "Aritmatika penjumlahan gagal"
    assert engine.evaluate("50 / 2") == 25, "Aritmatika pembagian integer gagal"

    cond = BashConditionSimulator()
    assert cond.test_integer_comparison(10, "-eq", 10) == 0
    assert cond.test_integer_comparison(5, "-gt", 10) == 1
    assert cond.test_string_operators("", "-z") == 0
    assert cond.test_string_operators("hello", "-n") == 0

    print(f"{Color.GREEN}[PASSED] Semua logika fondasi Bash valid dan terverifikasi.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        run_automated_check()
    else:
        print_banner()
        # Jika stdout bukan tty interaktif, jalankan automated check
        if not sys.stdin.isatty():
            run_automated_check()
            simulate_short_circuit()
        else:
            interactive_menu()
