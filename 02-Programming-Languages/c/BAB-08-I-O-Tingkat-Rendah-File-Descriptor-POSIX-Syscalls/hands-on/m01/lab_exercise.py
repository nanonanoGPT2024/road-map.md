#!/usr/bin/env python3
"""
Lab Exercise: Simulasi & Eksplorasi Low-Level POSIX I/O & File Descriptors
Modul 01 - C Low-Level I/O (open, read, write, lseek, close, dup2)

Program ini mendemonstrasikan cara kerja internal File Descriptor (FD) Table,
Open File Table, v-node/inode, serta pemanggilan low-level system call (POSIX).
"""

import os
import sys
import time
import tempfile

# ANSI Color Codes
class Colors:
    HEADER    = '\033[95m'
    BLUE      = '\033[94m'
    CYAN      = '\033[96m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    RED       = '\033[91m'
    BOLD      = '\033[1m'
    DIM       = '\033[2m'
    UNDERLINE = '\033[4m'
    RESET     = '\033[0m'

def print_banner():
    print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}  LAB INTERAKTIF: LOW-LEVEL I/O & FILE DESCRIPTOR POSIX SYSTEM CALLS {Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.DIM}Mempelajari tabel FD proses, open(), read(), write(), lseek(), dup2(){Colors.RESET}\n")

def demo_fd_table_concept():
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[1] KONSEP ARSITEKTUR KERNEL: FD TABLE -> OPEN FILE TABLE -> INODE{Colors.RESET}")
    print(f"{Colors.DIM}----------------------------------------------------------------------{Colors.RESET}")
    
    diagram = f"""
{Colors.GREEN}Process PCB (Per-Process)       Kernel Memory (System-Wide)       Filesystem Disk{Colors.RESET}
+-----------------------+     +-------------------------------+   +--------------+
|   FD Table (Array)    |     |    Open File Description      |   | Inode/v-node |
|-----------------------|     |-------------------------------|   |--------------|
| 0 -> [stdin (RO)]     |---->| File A: offset=0, flags=O_RDONLY|-->| Inode #1024  |
| 1 -> [stdout (WO)]    |     | File B: offset=42, flags=O_RDWR |-->| Inode #2048  |
| 2 -> [stderr (WO)]    |     +-------------------------------+   +--------------+
| 3 -> [file.txt (RW)]  |-------------^ (Berbagi offset & status)
| 4 -> [dup(3)]         |-------------^ (Hasil dup2 berbagi pointer struct file)
+-----------------------+
"""
    print(diagram)
    print(f"{Colors.CYAN}Poin Kunci:{Colors.RESET}")
    print(f" 1. {Colors.BOLD}FD (File Descriptor){Colors.RESET}: Bilangan integer non-negatif indeks array per proses.")
    print(f" 2. {Colors.BOLD}Open File Description{Colors.RESET}: Struktur kernel menyimpan file status, offset, ref-count.")
    print(f" 3. {Colors.BOLD}dup/dup2{Colors.RESET}: Menduplikasi slot FD untuk menunjuk ke struct file yang sama.")
    input(f"\n{Colors.DIM}Tekan [Enter] untuk melanjutkan ke simulasi syscall...{Colors.RESET}")

def demo_posix_syscalls():
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[2] PRAKTEK LANGSUNG: open(), write(), lseek(), read(), close(){Colors.RESET}")
    print(f"{Colors.DIM}----------------------------------------------------------------------{Colors.RESET}")
    
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, "posix_lab_test.txt")

    print(f"{Colors.BLUE}[*] Membuka/Membuat file dengan open() O_CREAT | O_RDWR | O_TRUNC...{Colors.RESET}")
    time.sleep(0.5)
    
    # Flags setara: O_CREAT | O_RDWR | O_TRUNC dengan mode 0644
    flags = os.O_CREAT | os.O_RDWR | os.O_TRUNC
    mode = 0o644
    fd = os.open(filepath, flags, mode)
    print(f"  {Colors.GREEN}✓ File dibuka! Mendapatkan File Descriptor (FD) = {Colors.BOLD}{fd}{Colors.RESET}")
    print(f"  {Colors.DIM}(Catatan: FD standard: 0=stdin, 1=stdout, 2=stderr. FD terendah yang bebas dialokasikan){Colors.RESET}\n")

    # Syscall write()
    data = b"ABCDEFGHIJ0123456789"
    print(f"{Colors.BLUE}[*] Menulis {len(data)} byte ke FD {fd} via write() syscall...{Colors.RESET}")
    bytes_written = os.write(fd, data)
    print(f"  {Colors.GREEN}✓ Berhasil menulis {bytes_written} byte data: '{data.decode()}'{Colors.RESET}")
    print(f"  {Colors.DIM}Posisi current offset kernel sekarang berada di byte {bytes_written}.{Colors.RESET}\n")

    # Syscall lseek()
    print(f"{Colors.BLUE}[*] Memanipulasi file offset via lseek()...{Colors.RESET}")
    # SEEK_SET: Geser ke byte 10
    pos1 = os.lseek(fd, 10, os.SEEK_SET)
    print(f"  {Colors.GREEN}✓ lseek(fd, 10, SEEK_SET) -> Offset sekarang: {pos1}{Colors.RESET}")
    
    # Read dari offset 10
    read_buf = os.read(fd, 5)
    print(f"  {Colors.GREEN}✓ os.read(fd, 5) membaca: '{read_buf.decode()}'{Colors.RESET}")
    
    # SEEK_CUR: Geser mundur 3 byte dari posisi saat ini
    pos2 = os.lseek(fd, -3, os.SEEK_CUR)
    print(f"  {Colors.GREEN}✓ lseek(fd, -3, SEEK_CUR) -> Offset kembali ke: {pos2}{Colors.RESET}")
    read_buf2 = os.read(fd, 8)
    print(f"  {Colors.GREEN}✓ os.read(fd, 8) membaca: '{read_buf2.decode()}'{Colors.RESET}\n")

    # Syscall close()
    print(f"{Colors.BLUE}[*] Menutup file descriptor via close()...{Colors.RESET}")
    os.close(fd)
    print(f"  {Colors.GREEN}✓ os.close({fd}) berhasil. Slot FD {fd} dibebaskan kembali ke kernel.{Colors.RESET}")
    
    # Cleanup file sementara
    if os.path.exists(filepath):
        os.remove(filepath)
    input(f"\n{Colors.DIM}Tekan [Enter] untuk melanjutkan ke simulasi dup2() & I/O Redirection...{Colors.RESET}")

def demo_dup2_redirection():
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[3] SIMULASI DUP2() & I/O REDIRECTION (stdout -> file){Colors.RESET}")
    print(f"{Colors.DIM}----------------------------------------------------------------------{Colors.RESET}")
    print(f"Konsep dasar implementasi redirection shell (contoh: 'ls > output.txt') di C:")
    print(f"{Colors.CYAN}  int file_fd = open(\"output.txt\", O_WRONLY | O_CREAT, 0644);\n  dup2(file_fd, STDOUT_FILENO); // STDOUT_FILENO (1) kini menunjuk ke output.txt\n  close(file_fd);{Colors.RESET}\n")

    temp_dir = tempfile.gettempdir()
    redirect_log = os.path.join(temp_dir, "redirect_output.log")
    
    print(f"{Colors.BLUE}[*] Menduplikasi stdout asli (FD 1) untuk backup...{Colors.RESET}")
    saved_stdout_fd = os.dup(1)
    print(f"  {Colors.GREEN}✓ Saved stdout FD = {saved_stdout_fd}{Colors.RESET}")

    log_fd = os.open(redirect_log, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o644)
    print(f"{Colors.BLUE}[*] Membuka log file (FD = {log_fd}), kemudian dup2(log_fd, 1)...{Colors.RESET}")
    
    # Redirect FD 1 ke file
    os.dup2(log_fd, 1)
    
    # Pesan ini masuk ke file, bukan terminal!
    sys.stdout.write("--- INI PESAN YANG DI-REDIRECT KE DALAM FILE VIA DUP2 ---\n")
    sys.stdout.write("Baris kedua log: Syscall level redirection bekerja sempurna!\n")
    sys.stdout.flush()

    # Kembalikan FD 1 ke terminal
    os.dup2(saved_stdout_fd, 1)
    os.close(saved_stdout_fd)
    os.close(log_fd)

    print(f"{Colors.GREEN}✓ stdout berhasil dikembalikan ke terminal!{Colors.RESET}")
    print(f"{Colors.BLUE}[*] Membaca isi file hasil redirection:{Colors.RESET}")
    with open(redirect_log, 'r') as f:
        for line in f:
            print(f"    {Colors.DIM}| {line.strip()}{Colors.RESET}")
            
    if os.path.exists(redirect_log):
        os.remove(redirect_log)
    input(f"\n{Colors.DIM}Tekan [Enter] untuk masuk ke Kuis Tantangan Interaktif...{Colors.RESET}")

def interactive_quiz():
    print(f"\n{Colors.YELLOW}{Colors.BOLD}[4] KUIS TANTANGAN INTERAKTIF FILE DESCRIPTORS{Colors.RESET}")
    print(f"{Colors.DIM}----------------------------------------------------------------------{Colors.RESET}")

    questions = [
        {
            "q": "Berapakah nilai standar file descriptor untuk stdin, stdout, dan stderr secara berurutan?",
            "opts": ["A) 1, 2, 3", "B) 0, 1, 2", "C) -1, 0, 1", "D) 3, 4, 5"],
            "ans": "B",
            "explain": "Standard POSIX mendefinisikan 0=stdin, 1=stdout, 2=stderr."
        },
        {
            "q": "Apa yang terjadi pada file offset ketika dua proses membuka file yang sama menggunakan open() secara terpisah?",
            "opts": [
                "A) Berbagi offset yang sama di kernel",
                "B) Memiliki entry Open File terpisah dan file offset independen",
                "C) Salah satu proses akan mengalami EBUSY error",
                "D) Offset otomatis di-reset ke akhir file (EOF)"
            ],
            "ans": "B",
            "explain": "Setiap pemanggilan open() independen membuat entry baru pada kernel Open File Table dengan offset masing-masing."
        },
        {
            "q": "Syscall manakah yang digunakan untuk mengkloning FD ke slot integer spesifik (misal ke slot 1 / stdout)?",
            "opts": ["A) clone()", "B) fork()", "C) dup2()", "D) fcntl(F_GETFL)"],
            "ans": "C",
            "explain": "dup2(oldfd, newfd) menutup newfd jika terbuka, lalu menduplikasi oldfd ke newfd secara atomik."
        }
    ]

    score = 0
    for i, item in enumerate(questions, 1):
        print(f"\n{Colors.BOLD}Pertanyaan {i}:{Colors.RESET} {item['q']}")
        for opt in item['opts']:
            print(f"  {opt}")
        
        user_ans = ""
        while user_ans not in ["A", "B", "C", "D"]:
            try:
                user_ans = input(f"{Colors.CYAN}Jawaban Anda (A/B/C/D): {Colors.RESET}").strip().upper()
            except (EOFError, KeyboardInterrupt):
                print("\nKeluar dari kuis.")
                return

        if user_ans == item['ans']:
            print(f"{Colors.GREEN}✓ Benar!{Colors.RESET} {item['explain']}")
            score += 1
        else:
            print(f"{Colors.RED}✗ Salah.{Colors.RESET} Jawaban benar adalah {item['ans']}. {item['explain']}")

    print(f"\n{Colors.BOLD}Hasil Akhir Kuis:{Colors.RESET} {score}/{len(questions)} Benar")
    if score == len(questions):
        print(f"{Colors.GREEN}{Colors.BOLD}Sempurna! Anda memahami konsep fondasi Low-Level POSIX I/O!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}Bagus! Terus pelajari modul dan ulangi eksperimen ini.{Colors.RESET}")

def main():
    while True:
        print_banner()
        print(f"{Colors.BOLD}Menu Eksperimen:{Colors.RESET}")
        print(f"  {Colors.CYAN}1.{Colors.RESET} Konsep Arsitektur: FD Table -> Open File Table -> Inode")
        print(f"  {Colors.CYAN}2.{Colors.RESET} Eksekusi Syscalls: open, write, lseek, read, close")
        print(f"  {Colors.CYAN}3.{Colors.RESET} Simulasi dup2() & I/O Redirection")
        print(f"  {Colors.CYAN}4.{Colors.RESET} Kuis Tantangan Interaktif")
        print(f"  {Colors.CYAN}5.{Colors.RESET} Jalankan Seluruh Demo Secara Berurutan")
        print(f"  {Colors.CYAN}0.{Colors.RESET} Keluar")
        
        try:
            choice = input(f"\n{Colors.BOLD}Pilih opsi [0-5]: {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSampai jumpa!")
            break

        if choice == '1':
            demo_fd_table_concept()
        elif choice == '2':
            demo_posix_syscalls()
        elif choice == '3':
            demo_dup2_redirection()
        elif choice == '4':
            interactive_quiz()
        elif choice == '5':
            demo_fd_table_concept()
            demo_posix_syscalls()
            demo_dup2_redirection()
            interactive_quiz()
        elif choice == '0':
            print(f"{Colors.GREEN}Terima kasih telah menggunakan lab simulasi POSIX I/O!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid, silakan coba lagi.{Colors.RESET}")
            time.sleep(1)

if __name__ == "__main__":
    main()
