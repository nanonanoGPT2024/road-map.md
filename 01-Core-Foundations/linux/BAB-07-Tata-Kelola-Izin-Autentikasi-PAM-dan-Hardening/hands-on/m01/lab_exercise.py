#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Tata Kelola Izin, PAM, dan Hardening Linux
BAB-07-Tata-Kelola-Izin-Autentikasi-PAM-dan-Hardening
Kategori: Linux Core Foundations
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple

# Kode Warna ANSI Terminal
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
BG_DARK = "\033[40m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
  SIMULASI LINUX SECURITY LAB: TATA KELOLA IZIN, PAM & HARDENING
  BAB-07: Foundations of Linux Authentication, Authorization & Security
======================================================================{RESET}
"""
    print(banner)


# -----------------------------------------------------------------------------
# 1. SIMULASI PERMISSION RESOLVER (DAC, OCTAL, SPECIAL BITS)
# -----------------------------------------------------------------------------
def decode_permissions(octal_str: str) -> Tuple[str, List[str]]:
    """Menerjemahkan 3 atau 4 digit oktal menjadi format symbolic string rwxrwxrwx & special bits."""
    if len(octal_str) == 3:
        octal_str = "0" + octal_str

    if len(octal_str) != 4 or not octal_str.isdigit():
        raise ValueError("Mode oktal harus 3 atau 4 digit angka (0-7).")

    special = int(octal_str[0])
    u = int(octal_str[1])
    g = int(octal_str[2])
    o = int(octal_str[3])

    for digit in [special, u, g, o]:
        if not (0 <= digit <= 7):
            raise ValueError("Setiap digit oktal harus di rentang 0-7.")

    def parse_triplet(val: int) -> List[str]:
        r = "r" if (val & 4) else "-"
        w = "w" if (val & 2) else "-"
        x = "x" if (val & 1) else "-"
        return [r, w, x]

    user_bits = parse_triplet(u)
    group_bits = parse_triplet(g)
    other_bits = parse_triplet(o)

    notes = []

    # SUID (4) pada user execute
    if special & 4:
        user_bits[2] = "s" if user_bits[2] == "x" else "S"
        notes.append("SUID (Set User ID) aktif: binary dieksekusi dengan EUID pemilik berkas.")

    # SGID (2) pada group execute
    if special & 2:
        group_bits[2] = "s" if group_bits[2] == "x" else "S"
        notes.append("SGID (Set Group ID) aktif: dieksekusi dengan EGID grup / file baru mewarisi grup.")

    # Sticky Bit (1) pada other execute
    if special & 1:
        other_bits[2] = "t" if other_bits[2] == "x" else "T"
        notes.append("Sticky Bit aktif (biasa di /tmp): hanya pemilik atau root yang dapat menghapus berkas.")

    symbolic = "".join(user_bits + group_bits + other_bits)
    return symbolic, notes


def run_permission_lab():
    print(f"\n{YELLOW}{BOLD}[MODUL 1: DAC & SPECIAL PERMISSIONS CALCULATOR]{RESET}")
    print("Menganalisis mode berkas oktal (contoh: 755, 4755, 2775, 1777).")
    val = input(f"{WHITE}Masukkan nilai oktal permission (contoh: 4755): {RESET}").strip()
    if not val:
        val = "4755"

    try:
        symbolic, notes = decode_permissions(val)
        norm_octal = val.zfill(4)
        print(f"\n{GREEN}{BOLD}Hasil Dekode Permission:{RESET}")
        print(f"  Mode Oktal : {BOLD}{norm_octal}{RESET}")
        print(f"  Symbolic   : {CYAN}{BOLD}-{symbolic}{RESET}")
        print(f"  Owner (u)  : {symbolic[0:3]}")
        print(f"  Group (g)  : {symbolic[3:6]}")
        print(f"  Other (o)  : {symbolic[6:9]}")

        if notes:
            print(f"\n{MAGENTA}{BOLD}Special Security Bits Terdeteksi:{RESET}")
            for note in notes:
                print(f"  {YELLOW}*{RESET} {note}")
        else:
            print(f"  {DIM}Tidak ada Special Bit (SUID/SGID/Sticky) aktif.{RESET}")

        # Contoh Umask Calculation
        print(f"\n{BLUE}[Kalkulator Default Creation Mask (umask)]{RESET}")
        umask_input = input(f"{WHITE}Masukkan umask server (default 022): {RESET}").strip() or "022"
        um = int(umask_input, 8)
        file_base = 0o666
        dir_base = 0o777
        res_file = file_base & (~um)
        res_dir = dir_base & (~um)
        print(f"  Default File (666 & ~{umask_input}) -> {oct(res_file)[2:].zfill(3)}")
        print(f"  Default Dir  (777 & ~{umask_input}) -> {oct(res_dir)[2:].zfill(3)}")

    except Exception as e:
        print(f"{RED}Error:{RESET} {e}")


# -----------------------------------------------------------------------------
# 2. SIMULASI PAM (PLUGGABLE AUTHENTICATION MODULES) EVALUATION ENGINE
# -----------------------------------------------------------------------------
@dataclass
class PAMRule:
    control: str  # required, requisite, sufficient, optional
    module: str
    result_mock: bool  # True (SUCCESS) or False (FAIL)
    description: str


def simulate_pam_stack(rules: List[PAMRule]) -> Tuple[bool, List[str]]:
    """
    Simulasi alur evaluasi PAM stack Linux:
    - required: jika gagal, catat gagal tapi lanjutkan evaluasi stack berikutnya.
    - requisite: jika gagal, LANGSUNG terminasi (abort) stack dengan kegagalan.
    - sufficient: jika sukses dan belum ada kegagalan sebelumnya, LANGSUNG terminate dengan sukses.
    - optional: hasil tidak berpengaruh kecuali modul tunggal.
    """
    logs = []
    overall_failure = False

    for idx, rule in enumerate(rules, start=1):
        status_text = f"{GREEN}SUCCESS{RESET}" if rule.result_mock else f"{RED}FAILURE{RESET}"
        logs.append(f"Langkah {idx}: [{rule.control:<10}] {rule.module:<20} -> {status_text} ({rule.description})")

        if rule.control == "requisite":
            if not rule.result_mock:
                overall_failure = True
                logs.append(f"  {RED}{BOLD}>> REQUISITE FAILED: Evaluasi stack dihentikan seketika (Aborted).{RESET}")
                return False, logs

        elif rule.control == "required":
            if not rule.result_mock:
                overall_failure = True
                logs.append(f"  {YELLOW}>> REQUIRED FAILED: Kegagalan dicatat, namun stack tetap dilanjutkan.{RESET}")

        elif rule.control == "sufficient":
            if rule.result_mock and not overall_failure:
                logs.append(f"  {GREEN}{BOLD}>> SUFFICIENT PASSED: Tidak ada error sebelumnya, akses LANGSUNG diberikan.{RESET}")
                return True, logs
            elif not rule.result_mock:
                logs.append(f"  {DIM}>> SUFFICIENT GAGAL: Diabaikan jika ada aturan fallback lain.{RESET}")

        elif rule.control == "optional":
            logs.append(f"  {DIM}>> OPTIONAL: Pengaruh informasional.{RESET}")

    final_decision = not overall_failure
    return final_decision, logs


def run_pam_lab():
    print(f"\n{YELLOW}{BOLD}[MODUL 2: PAM STACK EVALUATION ENGINE (/etc/pam.d/system-auth)]{RESET}")
    print("Menganalisis bagaimana control-flag (required, requisite, sufficient) mempengaruhi keputusan autentikasi.\n")

    print("Pilih Skenario Autentikasi:")
    print("1. Password benar, tapi faillock (tally) terpicu (Requisite Fail)")
    print("2. Biometrik / MFA sukses di awal (Sufficient Pass)")
    print("3. Password salah pada modul PAM standar (Required Fail)")

    choice = input(f"{WHITE}Pilihan Anda (1-3): {RESET}").strip()

    if choice == "1":
        stack = [
            PAMRule("requisite", "pam_faillock.so", False, "Mengecek percobaan brute force limit"),
            PAMRule("sufficient", "pam_unix.so", True, "Verifikasi /etc/shadow"),
            PAMRule("required", "pam_permit.so", True, "Final rule permit"),
        ]
    elif choice == "2":
        stack = [
            PAMRule("requisite", "pam_faillock.so", True, "Pre-auth check ok"),
            PAMRule("sufficient", "pam_fido2.so", True, "Hardware security key terverifikasi"),
            PAMRule("required", "pam_unix.so", False, "Fallback password unix tidak perlu dieksekusi"),
        ]
    else:
        stack = [
            PAMRule("required", "pam_env.so", True, "Load environment variabel"),
            PAMRule("requisite", "pam_faillock.so", True, "Lockout check ok"),
            PAMRule("required", "pam_unix.so", False, "Kata sandi hash tidak cocok"),
            PAMRule("required", "pam_deny.so", False, "Enforce denial fallback"),
        ]

    success, logs = simulate_pam_stack(stack)
    print("\n--- Proses Evaluasi Stack Kernel/PAM ---")
    for log in logs:
        print(log)

    print("-" * 50)
    if success:
        print(f"Keputusan Akhir: {GREEN}{BOLD}PAM_SUCCESS (Akses Diberikan){RESET}\n")
    else:
        print(f"Keputusan Akhir: {RED}{BOLD}PAM_AUTH_ERR / PAM_PERM_DENIED (Akses Ditolak){RESET}\n")


# -----------------------------------------------------------------------------
# 3. LINUX HARDENING & COMPLIANCE AUDITOR
# -----------------------------------------------------------------------------
@dataclass
class AuditItem:
    parameter: str
    current_value: str
    recommended_value: str
    passed: bool
    remediation: str


def run_hardening_audit():
    print(f"\n{YELLOW}{BOLD}[MODUL 3: LINUX SECURITY HARDENING & CIS BENCHMARK AUDITOR]{RESET}")
    print("Memeriksa konfigurasi umum server Linux terhadap postur keamanan standar.")

    checks = [
        AuditItem("PermitRootLogin (/etc/ssh/sshd_config)", "yes", "no", False, "Ubah 'PermitRootLogin no' di sshd_config"),
        AuditItem("PasswordAuthentication (SSH)", "yes", "no", False, "Terapkan SSH Key Auth only"),
        AuditItem("/etc/shadow Permissions", "0640", "0000 atau 0640 (root:shadow)", True, "chmod 0640 /etc/shadow"),
        AuditItem("fs.protected_hardlinks (sysctl)", "1", "1", True, "sysctl -w fs.protected_hardlinks=1"),
        AuditItem("fs.protected_symlinks (sysctl)", "1", "1", True, "sysctl -w fs.protected_symlinks=1"),
        AuditItem("kernel.randomize_va_space (ASLR)", "2", "2", True, "sysctl -w kernel.randomize_va_space=2"),
        AuditItem("Default System Umask (/etc/login.defs)", "002", "027", False, "Set 'UMASK 027' di /etc/login.defs"),
    ]

    passed_count = 0
    total = len(checks)

    print("\n" + f"{'PARAMETER':<40} | {'STATUS':<10} | {'REKOMENDASI':<20}")
    print("-" * 75)

    for item in checks:
        if item.passed:
            status_str = f"{GREEN}PASS{RESET}"
            passed_count += 1
        else:
            status_str = f"{RED}FAIL{RESET}"

        print(f"{item.parameter:<40} | {status_str:<19} | {item.recommended_value}")
        if not item.passed:
            print(f"  {YELLOW}-> Perbaikan:{RESET} {item.remediation}")

    score = int((passed_count / total) * 100)
    print("\n" + "=" * 50)
    color = GREEN if score >= 80 else (YELLOW if score >= 50 else RED)
    print(f"Skor Kepatuhan Hardening: {color}{BOLD}{score}% ({passed_count}/{total} Lolos){RESET}")
    print("=" * 50 + "\n")


# -----------------------------------------------------------------------------
# 4. SKENARIO TANTANGAN PRIVILEGE ESCALATION INTERAKTIF
# -----------------------------------------------------------------------------
def run_privilege_challenge():
    print(f"\n{YELLOW}{BOLD}[MODUL 4: ANALISIS KERENTANAN MISKONFIGURASI IZIN & SUDO]{RESET}")
    print("Periksa entri sudoers dan permission berikut untuk menemukan celah keamanan:")
    print(f"{CYAN}Tipe Entri:{RESET} developer ALL=(ALL) NOPASSWD: /usr/bin/find")
    print(f"{CYAN}Tipe File :{RESET} -rwsr-xr-x 1 root root /usr/local/bin/backup-tool\n")

    print("Pertanyaan:")
    print("1. Mengapa mengizinkan 'find' via NOPASSWD sudo sangat berbahaya?")
    print("2. Apa arti flag '-rwsr-xr-x' pada backup-tool?")

    ans = input(f"\n{WHITE}Ketik 'eval' untuk melihat penjelasan security engineer: {RESET}").strip()
    if ans.lower() == "eval" or True:
        print(f"\n{GREEN}{BOLD}[TEMUAN AUDIT KEAMANAN]{RESET}")
        print(f"1. {RED}Bahaya Binary 'find' pada sudoers:{RESET}")
        print("   Binary 'find' memiliki flag '-exec'. Penyerang dapat menjalankan shell root:")
        print(f"   {BOLD}$ sudo find . -exec /bin/sh \\; -quit{RESET} -> Menghasilkan Root Shell seketika.")
        print(f"2. {RED}Bahaya SUID root pada binary kustom:{RESET}")
        print("   Flag 's' pada user (SUID) membuat script/binary dijalankan dengan privilege penuh root.")
        print("   Jika program tersebut memanggil command tanpa absolute path (relatif), penyerang")
        print("   dapat memanipulasi $PATH untuk menyuntikkan binary berbahaya (Path Hijacking).")


# -----------------------------------------------------------------------------
# MAIN CLI LOOP
# -----------------------------------------------------------------------------
def main():
    while True:
        print_banner()
        print("Pilih modul laboratorium:")
        print(f"  {CYAN}1.{RESET} Kalkulator & Analisis Permission (DAC, Octal, SUID, SGID, Sticky, Umask)")
        print(f"  {CYAN}2.{RESET} Simulasi Mesin Evaluasi PAM Stack (/etc/pam.d/)")
        print(f"  {CYAN}3.{RESET} Audit Hardening & Parameter Keamanan Linux (CIS Benchmark)")
        print(f"  {CYAN}4.{RESET} Analisis Kerentanan SUID & Sudo Misconfiguration")
        print(f"  {CYAN}5.{RESET} Jalankan Seluruh Pengujian Otomatis")
        print(f"  {RED}0.{RESET} Keluar")

        pilihan = input(f"\n{WHITE}Masukkan pilihan [0-5]: {RESET}").strip()

        if pilihan == "1":
            run_permission_lab()
        elif pilihan == "2":
            run_pam_lab()
        elif pilihan == "3":
            run_hardening_audit()
        elif pilihan == "4":
            run_privilege_challenge()
        elif pilihan == "5":
            print(f"\n{CYAN}Menjalankan uji otomatis seluruh komponen...{RESET}")
            time.sleep(0.3)
            decode_permissions("4755")
            simulate_pam_stack([PAMRule("required", "pam_unix.so", True, "Test ok")])
            run_hardening_audit()
            print(f"{GREEN}{BOLD}Semua simulasi berhasil dijalankan secara terpadu!{RESET}\n")
        elif pilihan == "0":
            print(f"\n{GREEN}Selesai. Terima kasih telah menggunakan Linux Security Lab.{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    main()
