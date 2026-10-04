#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Arsitektur Bash I/O Streams, File Descriptors & Navigasi
Kategori: 01-Core-Foundations | Bab: 02

Script ini mensimulasikan subsistem Linux kernel untuk manajemen file descriptor (FD),
tabel file terbuka (open file table), manipulasi I/O redirection (>, >>, <, 2>&1),
duplikasi file descriptor (dup2), serta mekanika direktori stack (pushd/popd).
"""

import sys
import io
import os
import time
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Colors & Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"
CLR_GRAY = "\033[90m"

def print_header(title: str):
    width = 75
    print(f"\n{CLR_BLUE}{'=' * width}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [LAB] {title.upper()}{CLR_RESET}")
    print(f"{CLR_BLUE}{'=' * width}{CLR_RESET}")

def print_substep(step: str, detail: str = ""):
    print(f"{CLR_YELLOW}➜ {CLR_BOLD}{step}{CLR_RESET} {CLR_GRAY}{detail}{CLR_RESET}")

def print_fd_table(fd_table: Dict[int, 'VirtualFileStream']):
    print(f"\n{CLR_GRAY}┌────┬──────────────────────┬──────────┬─────────────────────────────┐{CLR_RESET}")
    print(f"{CLR_GRAY}│{CLR_BOLD} FD {CLR_RESET}{CLR_GRAY}│ Target Type          │ Mode     │ Stream Resource / Buffer    │{CLR_RESET}")
    print(f"{CLR_GRAY}├────┼──────────────────────┼──────────┼─────────────────────────────┤{CLR_RESET}")
    for fd in sorted(fd_table.keys()):
        stream = fd_table[fd]
        res_name = stream.name if stream else "CLOSED"
        mode_str = stream.mode if stream else "---"
        buf_preview = stream.peek(20).replace("\n", "\\n") if stream else "---"
        res_type = stream.type_desc if stream else "UNALLOCATED"
        print(f"{CLR_GRAY}│{CLR_RESET} {fd:<2} {CLR_GRAY}│{CLR_RESET} {res_type:<20} {CLR_GRAY}│{CLR_RESET} {mode_str:<8} {CLR_GRAY}│{CLR_RESET} {buf_preview:<27} {CLR_GRAY}│{CLR_RESET}")
    print(f"{CLR_GRAY}└────┴──────────────────────┴──────────┴─────────────────────────────┘{CLR_RESET}\n")


class VirtualFileStream:
    """
    Representasi abstraksi 'struct file' di kernel Linux.
    Menyimpan buffer memori, pointer posisi (offset), hak akses, dan metadata.
    """
    def __init__(self, name: str, mode: str = "r", stream_type: str = "REGULAR_FILE"):
        self.name = name
        self.mode = mode
        self.type_desc = stream_type
        self.buffer = io.StringIO()
        self.closed = False

    def write(self, data: str) -> int:
        if self.closed:
            raise ValueError("EBADF: Bad file descriptor (stream is closed)")
        if "w" not in self.mode and "a" not in self.mode and "+" not in self.mode:
            raise PermissionError("EACCES: File descriptor is not writable")
        return self.buffer.write(data)

    def read(self) -> str:
        if self.closed:
            raise ValueError("EBADF: Bad file descriptor (stream is closed)")
        return self.buffer.getvalue()

    def peek(self, max_len: int = 20) -> str:
        val = self.buffer.getvalue()
        if len(val) > max_len:
            return val[:max_len] + "..."
        return val

    def close(self):
        self.closed = True


class ProcessContext:
    """
    Simulasi task_struct Linux yang mengelola:
    1. File Descriptor Table (FD 0: stdin, 1: stdout, 2: stderr, 3+: custom)
    2. Virtual VFS Working Directory (PWD) & Directory Stack (pushd/popd)
    """
    def __init__(self):
        self.cwd: str = "/home/developer"
        self.dir_stack: List[str] = []
        self.fd_table: Dict[int, Optional[VirtualFileStream]] = {}
        self.init_standard_streams()

    def init_standard_streams(self):
        """Inisialisasi stream standar (POSIX FD 0, 1, 2)"""
        self.fd_table[0] = VirtualFileStream("/dev/stdin", "r", "CHAR_DEV (TTY)")
        self.fd_table[1] = VirtualFileStream("/dev/stdout", "w", "CHAR_DEV (TTY)")
        self.fd_table[2] = VirtualFileStream("/dev/stderr", "w", "CHAR_DEV (TTY)")

    def allocate_fd(self, stream: VirtualFileStream, specific_fd: Optional[int] = None) -> int:
        """Kernel-like fd allocation: mengambil FD terendah yang kosong jika specific_fd None"""
        if specific_fd is not None:
            self.fd_table[specific_fd] = stream
            return specific_fd
        
        fd = 0
        while fd in self.fd_table and self.fd_table[fd] is not None:
            fd += 1
        self.fd_table[fd] = stream
        return fd

    def sys_close(self, fd: int):
        """Implementasi syscall close(fd)"""
        if fd not in self.fd_table or self.fd_table[fd] is None:
            raise OSError(f"EBADF: FD {fd} tidak valid untuk di-close")
        self.fd_table[fd].close()
        del self.fd_table[fd]

    def sys_dup2(self, oldfd: int, newfd: int) -> int:
        """
        Implementasi syscall dup2(oldfd, newfd).
        Jika newfd terbuka, newfd ditutup terlebih dahulu secara atomic,
        lalu merujuk ke 'struct file' yang sama dengan oldfd.
        """
        if oldfd not in self.fd_table or self.fd_table[oldfd] is None:
            raise OSError(f"EBADF: Sumber oldfd={oldfd} tidak valid")
        
        if oldfd == newfd:
            return newfd
        
        if newfd in self.fd_table and self.fd_table[newfd] is not None:
            self.fd_table[newfd].close()

        # Shared reference ke underlying stream
        self.fd_table[newfd] = self.fd_table[oldfd]
        return newfd

    def write_to_fd(self, fd: int, payload: str):
        """Syscall wrapper write(fd, buf, count)"""
        if fd not in self.fd_table or self.fd_table[fd] is None:
            raise OSError(f"{CLR_RED}EBADF: File Descriptor {fd} tidak terdaftar!{CLR_RESET}")
        self.fd_table[fd].write(payload)

    # --- Simulasi Shell Navigation & Stack ---
    def pushd(self, target_path: str):
        """Simulasi perintah built-in bash 'pushd'"""
        resolved = os.path.normpath(os.path.join(self.cwd, target_path))
        self.dir_stack.append(self.cwd)
        self.cwd = resolved
        return self.get_dirs()

    def popd(self) -> str:
        """Simulasi perintah built-in bash 'popd'"""
        if not self.dir_stack:
            raise IndexError("bash: popd: directory stack empty")
        self.cwd = self.dir_stack.pop()
        return self.get_dirs()

    def get_dirs(self) -> str:
        """Menampilkan representasi 'dirs -v'"""
        stack_repr = [self.cwd] + list(reversed(self.dir_stack))
        return " ".join(stack_repr)


def run_pipeline_simulation():
    """
    Simulasi komunikasi pipeline inter-process (IPC pipe)
    Konsep: Mengarahkan FD 1 process A ke FD 0 process B melalui buffer pipa kernel.
    """
    print_header("Simulasi Pipeline Linux Pipe Operator: [ cmdA | cmdB ]")
    
    # Kernel pipe buffer
    pipe_read_end = VirtualFileStream("pipe:[0042]", "r", "FIFO_PIPE")
    pipe_write_end = VirtualFileStream("pipe:[0042]", "w", "FIFO_PIPE")

    # Command A: Producer (Menghasilkan log data)
    print_substep("Process A (Producer)", "Menulis log ke standard output (FD 1 di-redirect ke Pipe Write-End)")
    log_entries = "WARN: Disk full\nERROR: DB Timeout\nINFO: Success\nERROR: Auth Fail\n"
    pipe_write_end.write(log_entries)
    print(f"{CLR_GREEN}Producer menulis {len(log_entries.splitlines())} baris ke Pipe.{CLR_RESET}")

    # Mentransfer data dari write buffer ke read buffer (mensimulasikan sirkular buffer kernel)
    pipe_read_end.buffer = pipe_write_end.buffer

    # Command B: Consumer (Simulasi grep 'ERROR')
    print_substep("Process B (Consumer)", "Membaca dari stdin (FD 0 terhubung ke Pipe Read-End) & filter 'ERROR'")
    raw_input = pipe_read_end.read()
    filtered = [line for line in raw_input.splitlines() if "ERROR" in line]

    print(f"{CLR_CYAN}Hasil Pemrosesan Pipe Consumer:{CLR_RESET}")
    for res in filtered:
        print(f"  {CLR_BOLD}{CLR_RED}✖ {res}{CLR_RESET}")


def main():
    ctx = ProcessContext()

    # =========================================================================
    # BAGIAN 1: Navigasi & Directory Stack Mechanics
    # =========================================================================
    print_header("1. Mekanika Navigasi Bash & Directory Stack (pushd/popd)")
    print(f"Awal Direktori PWD: {CLR_BOLD}{ctx.cwd}{CLR_RESET}")

    print_substep("pushd /var/log", "Pindah direktori sambil menyimpan PWD sebelumnya ke LIFO stack")
    ctx.pushd("/var/log")
    print(f"Current Stack: {CLR_CYAN}{ctx.get_dirs()}{CLR_RESET}")

    print_substep("pushd ../etc/nginx", "Resolusi path relatif terhadap PWD aktif")
    ctx.pushd("../etc/nginx")
    print(f"Current Stack: {CLR_CYAN}{ctx.get_dirs()}{CLR_RESET}")

    print_substep("popd", "Kembali ke path sebelumnya dari stack")
    ctx.popd()
    print(f"Current Stack: {CLR_CYAN}{ctx.get_dirs()}{CLR_RESET}")

    # =========================================================================
    # BAGIAN 2: Standar File Descriptor & Tabel FD Kernel
    # =========================================================================
    print_header("2. Arsitektur File Descriptor Standar (0, 1, 2)")
    print("Inisialisasi tabel FD awal untuk proses aktif:")
    print_fd_table(ctx.fd_table)

    # =========================================================================
    # BAGIAN 3: Redirection Operasional (stdout, stderr, append)
    # =========================================================================
    print_header("3. Redirection Operasional: stdout (>), append (>>), dan stderr (2>)")

    print_substep("Simulasi: command > output.log", "Membuka file baru, overwrite (TRUNC), ganti FD 1")
    file_out = VirtualFileStream("/tmp/output.log", "w", "REGULAR_FILE")
    ctx.allocate_fd(file_out, specific_fd=1)
    ctx.write_to_fd(1, "Baris 1: Aplikasi dimulai...\n")
    print_fd_table(ctx.fd_table)

    print_substep("Simulasi: command 2> error.log", "Membuka file error terpisah, ganti FD 2")
    file_err = VirtualFileStream("/tmp/error.log", "w", "REGULAR_FILE")
    ctx.allocate_fd(file_err, specific_fd=2)
    ctx.write_to_fd(2, "CRITICAL: Database connection failed on port 5432!\n")
    print_fd_table(ctx.fd_table)

    # =========================================================================
    # BAGIAN 4: Teknik Duplikasi FD: Merging Streams (2>&1)
    # =========================================================================
    print_header("4. Analisis Teknis Duplikasi Deskriptor: '2>&1'")
    print(f"{CLR_GRAY}Sintaks '2>&1' menginstruksikan kernel menduplikasi referensi FD 1 ke FD 2.{CLR_RESET}")
    print(f"{CLR_GRAY}Syscall: dup2(oldfd=1, newfd=2){CLR_RESET}")

    # Buat file gabungan
    combined_log = VirtualFileStream("/tmp/all_output.log", "w", "REGULAR_FILE")
    ctx.allocate_fd(combined_log, specific_fd=1)
    print_substep("Sebelum dup2", "FD 1 mengarah ke /tmp/all_output.log, FD 2 ke /tmp/error.log")
    
    # Eksekusi dup2
    ctx.sys_dup2(oldfd=1, newfd=2)
    print_substep("Setelah sys_dup2(1, 2)", "FD 2 sekarang merujuk ke memori buffer yang identik dengan FD 1")
    print_fd_table(ctx.fd_table)

    # Bukti modifikasi bersama
    ctx.write_to_fd(1, "[STDOUT] Operasi batch dimulai.\n")
    ctx.write_to_fd(2, "[STDERR] Peringatan: memory buffer hampir penuh.\n")

    print(f"{CLR_BOLD}Isi buffer gabungan (/tmp/all_output.log):{CLR_RESET}")
    print(f"{CLR_GREEN}{ctx.fd_table[1].read()}{CLR_RESET}")

    # =========================================================================
    # BAGIAN 5: Custom File Descriptors (exec 3> audit.log & 3>&-)
    # =========================================================================
    print_header("5. Alokasi Custom File Descriptor (exec 3> /var/audit.log)")
    audit_stream = VirtualFileStream("/var/audit.log", "w", "CUSTOM_FD_STREAM")
    fd_custom = ctx.allocate_fd(audit_stream, specific_fd=3)
    
    print_substep(f"Custom FD {fd_custom} dibuka", "Dialokasikan manual di luar batasan POSIX standar (0-2)")
    ctx.write_to_fd(3, "[AUDIT] User root mengakses subsystem pada tick " + str(int(time.time())) + "\n")
    print_fd_table(ctx.fd_table)

    print_substep("Menutup Custom FD (exec 3>&-)", "Syscall close(3) membebaskan slot pada FD table")
    ctx.sys_close(3)
    print_fd_table(ctx.fd_table)

    try:
        ctx.write_to_fd(3, "Mencoba menulis ke FD yang sudah tertutup...")
    except OSError as e:
        print(f"{CLR_YELLOW}Expected Error ditangkap:{CLR_RESET} {e}")

    # =========================================================================
    # BAGIAN 6: Simulasi Pipeline IPC
    # =========================================================================
    run_pipeline_simulation()

    print_header("Lab Selesai: Ringkasan Deep-Dive")
    print(f"""
{CLR_BOLD}Konsep Kunci yang Divalidasi:{CLR_RESET}
1. {CLR_CYAN}File Descriptor (FD){CLR_RESET} hanyalah integer indeks array proses ke virtual Open File Table kernel.
2. {CLR_CYAN}Redirection (> / <){CLR_RESET} mengubah mapping slot indeks FD menuju struct file objek baru.
3. {CLR_CYAN}Operator 2>&1{CLR_RESET} mengeksekusi syscall dup2(1, 2), menyamakan pointer file object.
4. {CLR_CYAN}Operator Pipe (|){CLR_RESET} menghubungkan FD 1 produser ke FD 0 konsumer via buffer ring kernel.
    """)

if __name__ == "__main__":
    main()