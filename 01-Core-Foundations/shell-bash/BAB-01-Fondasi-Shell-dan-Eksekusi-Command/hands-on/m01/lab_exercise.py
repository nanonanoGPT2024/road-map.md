#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Shell & Eksekusi Command (BAB-01)
Interaktif, edukatif, dan mandiri dengan visualisasi ANSI terminal.
Mencakup:
1. Anatomi Command Line & Tokenisasi
2. Ordo Resolusi Command (Alias -> Keyword -> Function -> Builtin -> PATH)
3. Simulasi Siklus Fork-Exec & Exit Codes
4. Simulasi File Descriptors (FD 0, 1, 2) & Redirection
"""

import os
import sys
import time
import shutil

# --- ANSI Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
  SIMULATOR FONDASI SHELL & EKSEKUSI COMMAND (BAB-01)
  Hands-On Lab: Command Anatomy, Resolution Order, Fork-Exec & Redirection
======================================================================{CLR_RESET}
"""
    print(banner)


def pause():
    input(f"\n{CLR_YELLOW}[Tekan ENTER untuk melanjutkan...]{CLR_RESET}")


# --- MODUL 1: Anatomi Command & Tokenisasi ---
def demo_command_anatomy():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== LAB 1: Anatomi Command & Tokenisasi Bash ==={CLR_RESET}")
    print("Bash mengurai command line menjadi token: Command, Options/Flags, Arguments, dan Operator.")

    sample_cmd = input(
        f"\nMasukkan command contoh (Default: {CLR_GREEN}ls -la --color=auto /var/log{CLR_RESET}): "
    ).strip()
    if not sample_cmd:
        sample_cmd = "ls -la --color=auto /var/log"

    tokens = sample_cmd.split()
    cmd = tokens[0] if tokens else ""
    short_flags = [t for t in tokens[1:] if t.startswith("-") and not t.startswith("--")]
    long_opts = [t for t in tokens[1:] if t.startswith("--")]
    args = [t for t in tokens[1:] if not t.startswith("-")]

    print(f"\n{CLR_BOLD}Analisis Tokenisasi Command:{CLR_RESET}")
    print(f"  {CLR_WHITE}String Mentah :{CLR_RESET} {sample_cmd}")
    print(f"  {CLR_GREEN}Executable/Cmd:{CLR_RESET} {cmd}")
    print(f"  {CLR_YELLOW}Short Flags   :{CLR_RESET} {short_flags}")
    print(f"  {CLR_CYAN}Long Options  :{CLR_RESET} {long_opts}")
    print(f"  {CLR_MAGENTA}Positional Arg:{CLR_RESET} {args}")

    print(f"\n{CLR_WHITE}Peran Parsing Bash:{CLR_RESET}")
    print("  1. Memisahkan string berdasarkan Whitespace IFS (Internal Field Separator).")
    print("  2. Memeriksa karakter quote ('...', \"...\") untuk mempertahankan spasi.")
    print("  3. Menyerahkan argumen ke tabel argv[] program target.")
    pause()


# --- MODUL 2: Resolusi Command (Lookup Order) ---
def demo_command_resolution():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== LAB 2: Ordo Resolusi Command Bash (type -a) ==={CLR_RESET}")
    print("Bash mencari eksekutor dengan urutan prioritas ketat:")
    print(f"  {CLR_GREEN}1. Alias{CLR_RESET} -> {CLR_YELLOW}2. Reserved Keyword{CLR_RESET} -> {CLR_CYAN}3. Shell Function{CLR_RESET} -> {CLR_MAGENTA}4. Shell Builtin{CLR_RESET} -> {CLR_WHITE}5. External Executable ($PATH){CLR_RESET}\n")

    # Mock database shell
    aliases = {"ll": "ls -l", "grep": "grep --color=auto"}
    keywords = {"if", "then", "else", "fi", "for", "while", "do", "done", "case", "esac"}
    functions = {"my_helper": "() { echo 'function demo'; }", "deploy": "() { echo 'deploying...'; }"}
    builtins = {"cd", "echo", "pwd", "exit", "export", "type", "alias", "read", "kill", "source"}

    target = input(f"Ketik command untuk uji lookup (contoh: cd, ll, for, python3, ls): ").strip()
    if not target:
        target = "cd"

    found_levels = []

    # 1. Alias
    if target in aliases:
        found_levels.append((1, "Alias", f"aliased to `{aliases[target]}`"))
    # 2. Keyword
    if target in keywords:
        found_levels.append((2, "Reserved Keyword", "merupakan struktur kontrol gramatikal shell"))
    # 3. Function
    if target in functions:
        found_levels.append((3, "Shell Function", functions[target]))
    # 4. Builtin
    if target in builtins:
        found_levels.append((4, "Shell Builtin", "dieksekusi langsung di memori proses shell tanpa fork()"))
    # 5. External Path
    ext_path = shutil.which(target)
    if ext_path:
        found_levels.append((5, "External Binary", f"ditemukan di disk pada path {ext_path}"))

    print(f"\n{CLR_BOLD}Hasil Pencarian Resolusi untuk `{target}`:{CLR_RESET}")
    if not found_levels:
        print(f"  {CLR_RED}[X] Command `{target}` tidak ditemukan (exit code 127: command not found).{CLR_RESET}")
    else:
        winner = found_levels[0]
        for priority, kind, desc in found_levels:
            marker = f"{CLR_GREEN}* AKTIF (MENANG){CLR_RESET}" if priority == winner[0] else f"{CLR_WHITE}- TERTINDIH{CLR_RESET}"
            print(f"  Tingkat {priority} [{kind:16}]: {marker} -> {desc}")

        print(f"\n{CLR_GREEN}Kesimpulan:{CLR_RESET} Jika dieksekusi, Bash akan menjalankan varian: {CLR_BOLD}{winner[1]}{CLR_RESET}")
    pause()


# --- MODUL 3: Simulasi Fork & Exec Cycle ---
def demo_fork_exec():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== LAB 3: Siklus Hidup Proses (fork -> execve -> wait -> exit) ==={CLR_RESET}")
    parent_pid = os.getpid()
    print(f"Proses Shell Utama (Parent PID): {CLR_CYAN}{parent_pid}{CLR_RESET}")

    choice = input("\nJalankan simulasi eksekusi command eksternal (y/n)? [y]: ").strip().lower()
    if choice in ("", "y", "yes"):
        print(f"\n{CLR_YELLOW}[1] Shell memanggil fork()... menduplikasi address space.{CLR_RESET}")
        time.sleep(0.4)

        sim_child_pid = parent_pid + 42
        print(f"    --> Child process tercipta dengan PID: {CLR_GREEN}{sim_child_pid}{CLR_RESET} (PPID: {parent_pid})")
        time.sleep(0.4)

        print(f"{CLR_YELLOW}[2] Child memanggil execve('/usr/bin/uptime', argv, envp)...{CLR_RESET}")
        print("    --> Image memori child ditimpa oleh biner executable.")
        time.sleep(0.4)

        print(f"{CLR_YELLOW}[3] Parent shell menjalankan waitpid({sim_child_pid}) memblokir input prompt.{CLR_RESET}")
        time.sleep(0.6)

        # Real exec command safely to show real exit status
        exit_code = 0
        print(f"\n{CLR_WHITE}--- Output Proses Anak ---{CLR_RESET}")
        res = os.system("date")
        exit_code = res >> 8
        print(f"{CLR_WHITE}---------------------------{CLR_RESET}")

        print(f"\n{CLR_YELLOW}[4] Child selesai terminate. Exit code status: {CLR_GREEN}{exit_code}{CLR_RESET}")
        print(f"    Parent shell menangkap sinyal SIGCHLD, memperbarui variabel $? = {exit_code}, dan membuka prompt kembali.")
    pause()


# --- MODUL 4: Simulasi File Descriptor & Redirection ---
def demo_redirection():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== LAB 4: File Descriptors (0, 1, 2) & I/O Redirection ==={CLR_RESET}")
    print("Tabel File Descriptor default setiap proses:")
    print(f"  {CLR_CYAN}FD 0 (stdin){CLR_RESET}  : Standar Input  (Keyboard/Pipe)")
    print(f"  {CLR_GREEN}FD 1 (stdout){CLR_RESET} : Standar Output (Layar Terminal)")
    print(f"  {CLR_RED}FD 2 (stderr){CLR_RESET} : Standar Error  (Layar Terminal)")

    print(f"\n{CLR_BOLD}Simulasi Operator Redirection:{CLR_RESET}")
    ops = [
        ("cmd > file.txt", "Tutup FD 1 terminal, buka file.txt mode truncate (O_WRONLY|O_CREAT|O_TRUNC) pada FD 1"),
        ("cmd >> file.txt", "Tutup FD 1 terminal, buka file.txt mode append (O_APPEND) pada FD 1"),
        ("cmd 2> err.log", "Biarkan FD 1 ke terminal, alihkan FD 2 ke file err.log"),
        ("cmd > out.log 2>&1", "Arahkan FD 1 ke file out.log, lalu duplikasi FD 2 merujuk ke FD 1 via dup2()"),
        ("cmd < input.txt", "Tutup FD 0 terminal, buka input.txt sebagai sumber pembacaan FD 0"),
    ]

    for op, desc in ops:
        print(f"  {CLR_YELLOW}{op:20}{CLR_RESET} -> {desc}")

    print(f"\n{CLR_MAGENTA}Simulasi Interaktif dup2():{CLR_RESET}")
    user_choice = input("Pilih pengalihan stream (1=stdout_only, 2=stderr_to_file, 3=both): ").strip()
    if user_choice == "2":
        print(f"{CLR_GREEN}[OK]{CLR_RESET} dup2(fileno('err.log'), 2) dieksekusi sebelum execve(). Stderr kini terisolasi.")
    elif user_choice == "3":
        print(f"{CLR_GREEN}[OK]{CLR_RESET} stdout dan stderr disatukan ke target berkas yang sama.")
    else:
        print(f"{CLR_GREEN}[OK]{CLR_RESET} Mode standar: FD 1 dan FD 2 tetap tertaut ke TTY perangkat pengguna.")
    pause()


# --- KUIS / EVALUASI MANDIRI CEPAT ---
def mini_challenge():
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}=== QUICK CHALLENGE: Uji Pemahaman BAB-01 ==={CLR_RESET}")
    questions = [
        {
            "q": "Mengapa command 'cd' harus diimplementasikan sebagai Shell Builtin dan bukan executable external di /bin/cd?",
            "opts": [
                "A. Karena executable binary lebih lambat dari skrip Bash",
                "B. Karena proses anak (child) tidak dapat mengubah current working directory proses induk (parent)",
                "C. Karena kernel Linux melarang pemanggilan fork() untuk navigasi folder",
            ],
            "ans": "B",
            "exp": "Sifat POSIX: proses anak memiliki copy memori sendiri. Jika 'cd' adalah biner eksternal, fork() akan dibuat, child berganti direktori, lalu terminate tanpa mengubah direktori shell utama Anda.",
        },
        {
            "q": "Manakah urutan lookup yang benar jika sebuah nama bertabrakan antara Builtin dan Alias?",
            "opts": [
                "A. Alias menang dan dieksekusi lebih dulu daripada Builtin",
                "B. Builtin selalu menang karena tertanam di binary shell",
                "C. Shell berhenti dengan error 'Ambiguous command resolution'",
            ],
            "ans": "A",
            "exp": "Ordo lookup Bash: Alias dievaluasi di tahap paling awal sebelum reservasi kata kunci, fungsi, dan builtin.",
        },
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{CLR_BOLD}Pertanyaan {idx}:{CLR_RESET} {item['q']}")
        for opt in item["opts"]:
            print(f"  {opt}")
        ans = input(f"Jawaban Anda (A/B/C): ").strip().upper()
        if ans == item["ans"]:
            print(f"{CLR_GREEN}[BENAR]{CLR_RESET} {item['exp']}")
            score += 1
        else:
            print(f"{CLR_RED}[SALAH]{CLR_RESET} Jawaban tepat adalah {item['ans']}. Penjelasan: {item['exp']}")

    print(f"\n{CLR_BOLD}Skor Akhir Challenge:{CLR_RESET} {score}/{len(questions)}")
    pause()


def main():
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        print_banner()
        print(f"{CLR_BOLD}Pilih Menu Simulasi Lab:{CLR_RESET}")
        print("  1. Anatomi Command Line & Token Parsing")
        print("  2. Command Resolution Lookup Order (type -a simulation)")
        print("  3. Siklus Hidup Proses (fork, exec, wait, exit status)")
        print("  4. File Descriptors & Redirection Engine (0, 1, 2, dup2)")
        print("  5. Mini Challenge & Pemahaman Konseptual")
        print("  0. Keluar")

        choice = input(f"\n{CLR_GREEN}Masukkan pilihan (0-5): {CLR_RESET}").strip()
        if choice == "1":
            demo_command_anatomy()
        elif choice == "2":
            demo_command_resolution()
        elif choice == "3":
            demo_fork_exec()
        elif choice == "4":
            demo_redirection()
        elif choice == "5":
            mini_challenge()
        elif choice == "0":
            print(f"\n{CLR_CYAN}Terima kasih telah menjalankan hands-on lab fondasi shell!{CLR_RESET}\n")
            sys.exit(0)
        else:
            print(f"{CLR_RED}Pilihan tidak valid.{CLR_RESET}")
            time.sleep(0.8)


if __name__ == "__main__":
    main()
