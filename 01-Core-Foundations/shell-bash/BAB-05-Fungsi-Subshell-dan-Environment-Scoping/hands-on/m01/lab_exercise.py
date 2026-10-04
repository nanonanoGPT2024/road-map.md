#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Konsep Fondasi Bash Scoping & Subshell
BAB-05: Fungsi, Subshell, dan Environment Scoping
Python 3 Runnable Mandiri (Standar Library Only)
"""

import sys
import os
import copy
import time
from typing import Dict, Any, Optional

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RESET = "\033[0m"


class BashEnvironmentSimulator:
    """
    Simulasi memori variabel Bash: Shell Variables vs Exported (Env) Variables
    dan penanganan scoping (Global, Function Local, Subshell Isolation).
    """

    def __init__(self, name: str = "Parent Shell (PID: 1000)"):
        self.name = name
        self.shell_vars: Dict[str, str] = {}
        self.exported_vars: Dict[str, str] = {}
        self.exit_code: int = 0

    def set_var(self, name: str, value: str, export: bool = False):
        self.shell_vars[name] = value
        if export:
            self.exported_vars[name] = value

    def export_var(self, name: str):
        if name in self.shell_vars:
            self.exported_vars[name] = self.shell_vars[name]
        else:
            self.shell_vars[name] = ""
            self.exported_vars[name] = ""

    def get_var(self, name: str) -> Optional[str]:
        return self.shell_vars.get(name)

    def spawn_subshell(self, name: str = "Subshell `(...)` (PID: 1001)") -> "BashEnvironmentSimulator":
        """
        Subshell menyalin seluruh shell variables dan env variables (fork copy-on-write).
        Mutasi di subshell tidak berdampak ke parent.
        """
        child = BashEnvironmentSimulator(name)
        child.shell_vars = copy.deepcopy(self.shell_vars)
        child.exported_vars = copy.deepcopy(self.exported_vars)
        return child

    def spawn_subprocess(self, name: str = "Subprocess (External Bin) (PID: 1002)") -> "BashEnvironmentSimulator":
        """
        Subprocess HANYA mewarisi variabel yang di-export (Environment Variables).
        Shell variables biasa (unexported) hilang.
        """
        child = BashEnvironmentSimulator(name)
        child.shell_vars = copy.deepcopy(self.exported_vars)
        child.exported_vars = copy.deepcopy(self.exported_vars)
        return child


def print_banner():
    print(f"{CYAN}{BOLD}===================================================================={RESET}")
    print(f"{GREEN}{BOLD}      LAB SIMULASI INTERAKTIF: BASH SCOPING, SUBSHELL & EXPORT       {RESET}")
    print(f"{YELLOW}          BAB-05: Fungsi, Subshell, dan Environment Scoping           {RESET}")
    print(f"{CYAN}{BOLD}===================================================================={RESET}")


def demo_function_local_vs_global():
    print(f"\n{BOLD}{MAGENTA}[1] SIMULASI: Global Variables vs Local Variables dalam Fungsi{RESET}")
    print("Kode bash representatif:")
    print(f"{BLUE}  TARGET_APP='v1.0'  # Global\n"
          f"  my_func() {{\n"
          f"      local INNER_VAR='private'\n"
          f"      TARGET_APP='v2.0' # Mengubah global tanpa 'local'!\n"
          f"  }}{RESET}")

    parent = BashEnvironmentSimulator("Main Script")
    parent.set_var("TARGET_APP", "v1.0")
    print(f"\n{YELLOW}-> Kondisi Awal:{RESET}")
    print(f"   TARGET_APP = '{parent.get_var('TARGET_APP')}'")

    print(f"\n{CYAN}-> Mengeksekusi 'my_func()' di mana TARGET_APP ditimpa tanpa deklarasi local...{RESET}")
    # Local scope frame
    local_frame = {"INNER_VAR": "private"}
    # Global side-effect
    parent.set_var("TARGET_APP", "v2.0")

    print(f"{GREEN}[OK] Eksekusi fungsi selesai.{RESET}")
    print(f"   Akses $INNER_VAR dari parent shell: {RED}{repr(parent.get_var('INNER_VAR'))}{RESET} (Out of scope / kosong)")
    print(f"   Akses $TARGET_APP dari parent shell: {RED}{parent.get_var('TARGET_APP')}{RESET} (Terkontaminasi karena lupa keyword 'local')")
    print(f"{BOLD}{YELLOW}=> Kesimpulan: Selalu gunakan `local var_name=...` dalam fungsi bash!{RESET}\n")


def demo_subshell_isolation():
    print(f"\n{BOLD}{MAGENTA}[2] SIMULASI: Isolasi Lingkungan Subshell `( ... )` vs `{{ ...; }}`{RESET}")
    print("Kode bash representatif:")
    print(f"{BLUE}  CONFIG_MODE='production'\n"
          f"  ( \n"
          f"      CONFIG_MODE='staging'\n"
          f"      cd /tmp\n"
          f"      echo \"Inside subshell: $CONFIG_MODE\"\n"
          f"  )\n"
          f"  echo \"Outside subshell: $CONFIG_MODE\"{RESET}")

    parent = BashEnvironmentSimulator("Parent Shell")
    parent.set_var("CONFIG_MODE", "production")

    print(f"\n{YELLOW}-> Parent Shell Awal:{RESET} CONFIG_MODE = '{parent.get_var('CONFIG_MODE')}'")
    print(f"{CYAN}-> Melakukan fork subshell via tanda kurung ( ... )...{RESET}")

    subshell = parent.spawn_subshell()
    subshell.set_var("CONFIG_MODE", "staging")
    print(f"   {GREEN}[Subshell PID 1001]{RESET} CONFIG_MODE diubah menjadi '{subshell.get_var('CONFIG_MODE')}'")

    print(f"{CYAN}-> Subshell exit dengan code 0. Kembali ke Parent Shell...{RESET}")
    print(f"   {GREEN}[Parent Shell]{RESET} CONFIG_MODE tetap = '{parent.get_var('CONFIG_MODE')}'")
    print(f"{BOLD}{YELLOW}=> Kesimpulan: Subshell berjalan di proses child terpisah (fork). Perubahan env/cd hilang saat subshell selesai!{RESET}\n")


def demo_export_inheritance():
    print(f"\n{BOLD}{MAGENTA}[3] SIMULASI: Export vs Unexported Variables ke Subprocess{RESET}")
    print("Kode bash representatif:")
    print(f"{BLUE}  LOCAL_SECRET='rahasia_shell'\n"
          f"  export API_TOKEN='xyz-12345'\n"
          f"  python3 child_script.py{RESET}")

    parent = BashEnvironmentSimulator("Parent Terminal")
    parent.set_var("LOCAL_SECRET", "rahasia_shell", export=False)
    parent.set_var("API_TOKEN", "xyz-12345", export=True)

    print(f"\n{YELLOW}-> Status di Parent Shell:{RESET}")
    print(f"   LOCAL_SECRET = '{parent.get_var('LOCAL_SECRET')}' (export = False)")
    print(f"   API_TOKEN    = '{parent.get_var('API_TOKEN')}' (export = True)")

    print(f"\n{CYAN}-> Menjalankan subprocess biner eksternal...{RESET}")
    child_proc = parent.spawn_subprocess()

    print(f"   {BLUE}[Subprocess Environment Check]:{RESET}")
    print(f"   - LOCAL_SECRET terlihat? : {RED}{child_proc.get_var('LOCAL_SECRET')}{RESET} (None/Tidak diwariskan)")
    print(f"   - API_TOKEN terlihat?    : {GREEN}{child_proc.get_var('API_TOKEN')}{RESET} (Diwariskan via environ!)")
    print(f"{BOLD}{YELLOW}=> Kesimpulan: Subprocess hanya mewarisi variabel bertanda `export`. Variabel biasa hanya ada di memori shell lokal.{RESET}\n")


def interactive_quiz():
    print(f"\n{BOLD}{MAGENTA}[4] KUIS INTERAKTIF: Uji Pemahaman Fondasi Bash Scoping{RESET}")
    questions = [
        {
            "q": "Manakah konstruksi yang TIDAK membuat subshell baru?",
            "options": [
                "A. ( cd /var/log && ls )",
                "B. { cd /var/log; ls; }",
                "C. ps aux | grep bash",
                "D. $(date +%s)"
            ],
            "ans": "B",
            "explain": "Tanda kurung kurawal `{ ...; }` adalah Group Command yang dieksekusi di current shell context!"
        },
        {
            "q": "Di dalam fungsi Bash, apa efek `return 1` vs `exit 1`?",
            "options": [
                "A. Keduanya sama persis mematikan script utama.",
                "B. `return 1` menghentikan fungsi dan set $?=1; `exit 1` membunuh seluruh proses shell.",
                "C. `return` hanya boleh digunakan di subshell.",
                "D. `exit` tidak mengubah status code $?."
            ],
            "ans": "B",
            "explain": "`return` keluar dari stack fungsi saat ini, sedangkan `exit` menterminasi shell pengimpornya."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{BOLD}{CYAN}Soal {idx}:{RESET} {item['q']}")
        for opt in item["options"]:
            print(f"   {opt}")

        try:
            user_choice = input(f"{YELLOW}Jawaban Anda (A/B/C/D) [atau 's' lewati]: {RESET}").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{BLUE}[Dibatalkan]{RESET}")
            return
        if user_choice == item["ans"]:
            print(f"{GREEN}[BENAR]{RESET} {item['explain']}")
            score += 1
        elif user_choice == "S":
            print(f"{BLUE}[DILEWATI]{RESET}")
        else:
            print(f"{RED}[SALAH]{RESET} Jawaban tepat adalah {item['ans']}. {item['explain']}")

    print(f"\n{BOLD}{GREEN}Skor Kuis Anda: {score}/{len(questions)}{RESET}\n")


def main():
    print_banner()
    while True:
        print(f"{BOLD}Pilih Modul Lab:{RESET}")
        print("  1. Simulasi Local vs Global Variable dalam Fungsi")
        print("  2. Simulasi Isolasi Lingkungan Subshell ( ... )")
        print("  3. Simulasi Pewarisan Lingkungan (export vs unexport)")
        print("  4. Kuis Evaluasi Mandiri Scoping & Subshell")
        print("  5. Jalankan Semua Simulasi Otomatis")
        print("  0. Keluar")

        try:
            choice = input(f"\n{CYAN}Masukkan pilihan (0-5): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREEN}Lab dihentikan. Sampai jumpa!{RESET}")
            break
        if choice == "1":
            demo_function_local_vs_global()
        elif choice == "2":
            demo_subshell_isolation()
        elif choice == "3":
            demo_export_inheritance()
        elif choice == "4":
            interactive_quiz()
        elif choice == "5":
            demo_function_local_vs_global()
            demo_subshell_isolation()
            demo_export_inheritance()
            interactive_quiz()
        elif choice in ("0", "exit", "quit"):
            print(f"{GREEN}Lab selesai. Selamat belajar!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}\n")


if __name__ == "__main__":
    main()
