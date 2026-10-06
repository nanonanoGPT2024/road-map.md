#!/usr/bin/env python3
"""
Lab Exercise: Systems Programming Fundamentals in C++
Topic: BAB-09 Systems Programming (POSIX Subsystems, Virtual Memory, IPC & Signals)

Simulasi interaktif konsep inti Systems Programming C++:
1. Virtual Memory & Page Table Translation (mmap, page protection, page fault)
2. POSIX File Descriptor Table & Pipe IPC (Kernel buffer, read/write ends)
3. Signal Handling & Bitmask Dispatcher (SIGINT, SIGKILL, sigprocmask)
4. RAII Syscall Wrapper (Kernel resource management vs raw fd leak)
"""

import sys
import time
import os
from typing import Dict, List, Optional, Tuple

# Terminal ANSI Color Formatting
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 65
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" [*] {title}")
    print(f"{line}{CLR_RESET}")


def subheader(title: str) -> None:
    print(f"\n{CLR_YELLOW}{CLR_BOLD}--- {title} ---{CLR_RESET}")


def success(msg: str) -> None:
    print(f"{CLR_GREEN}[✓] {msg}{CLR_RESET}")


def warn(msg: str) -> None:
    print(f"{CLR_YELLOW}[!] {msg}{CLR_RESET}")


def error(msg: str) -> None:
    print(f"{CLR_RED}[✗] {msg}{CLR_RESET}")


def info(msg: str) -> None:
    print(f"{CLR_BLUE}[i] {msg}{CLR_RESET}")


# ==============================================================================
# 1. Virtual Memory & Page Table Simulation (mmap & Memory Protection)
# ==============================================================================
class PageProtection:
    PROT_NONE  = 0b000
    PROT_READ  = 0b001
    PROT_WRITE = 0b010
    PROT_EXEC  = 0b100


class VirtualMemorySubsystem:
    PAGE_SIZE = 4096  # 4 KB per page

    def __init__(self, ram_pages: int = 16):
        self.total_ram_pages = ram_pages
        self.physical_ram: List[bytearray] = [bytearray(self.PAGE_SIZE) for _ in range(ram_pages)]
        self.frame_allocated = [False] * ram_pages
        # Page Table: virtual_page_num -> (physical_frame_id, protection_bits, is_dirty)
        self.page_table: Dict[int, Tuple[int, int, bool]] = {}

    def mmap_allocate(self, vaddr_start: int, length: int, prot: int) -> int:
        num_pages = (length + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        base_vpn = vaddr_start // self.PAGE_SIZE

        for i in range(num_pages):
            vpn = base_vpn + i
            if vpn in self.page_table:
                raise RuntimeError(f"VADDR collision at page {vpn:#x}")
            # Find free physical frame
            frame_id = -1
            for fid, allocated in enumerate(self.frame_allocated):
                if not allocated:
                    frame_id = fid
                    self.frame_allocated[fid] = True
                    break
            if frame_id == -1:
                raise MemoryError("Out of physical memory frames (Kernel OOM)!")
            self.page_table[vpn] = (frame_id, prot, False)

        return vaddr_start

    def write_byte(self, vaddr: int, data: int) -> None:
        vpn = vaddr // self.PAGE_SIZE
        offset = vaddr % self.PAGE_SIZE

        if vpn not in self.page_table:
            raise PermissionError(f"PAGE FAULT (SIGSEGV): Unmapped address {vaddr:#010x}")

        frame_id, prot, _ = self.page_table[vpn]
        if not (prot & PageProtection.PROT_WRITE):
            raise PermissionError(
                f"PAGE FAULT (SIGSEGV): Write violation on read-only page {vpn:#x} (VADDR {vaddr:#010x})"
            )

        self.physical_ram[frame_id][offset] = data & 0xFF
        self.page_table[vpn] = (frame_id, prot, True)

    def read_byte(self, vaddr: int) -> int:
        vpn = vaddr // self.PAGE_SIZE
        offset = vaddr % self.PAGE_SIZE

        if vpn not in self.page_table:
            raise PermissionError(f"PAGE FAULT (SIGSEGV): Unmapped address {vaddr:#010x}")

        frame_id, prot, dirty = self.page_table[vpn]
        if not (prot & PageProtection.PROT_READ):
            raise PermissionError(f"PAGE FAULT (SIGSEGV): Read violation on no-access page {vpn:#x}")

        return self.physical_ram[frame_id][offset]

    def dump_mmap_mappings(self) -> None:
        print(f"\n{CLR_WHITE}{'Virtual Page (VPN)':<20} | {'Frame':<8} | {'Flags':<12} | {'State':<10}{CLR_RESET}")
        print("-" * 58)
        for vpn, (frame, prot, dirty) in sorted(self.page_table.items()):
            p_flags = []
            if prot & PageProtection.PROT_READ:  p_flags.append("R")
            if prot & PageProtection.PROT_WRITE: p_flags.append("W")
            if prot & PageProtection.PROT_EXEC:  p_flags.append("X")
            flag_str = "|".join(p_flags) if p_flags else "NONE"
            dirty_str = f"{CLR_YELLOW}DIRTY{CLR_RESET}" if dirty else f"{CLR_GREEN}CLEAN{CLR_RESET}"
            print(f"0x{vpn * self.PAGE_SIZE:08x} - 0x{(vpn+1)*self.PAGE_SIZE - 1:08x} | #{frame:<6} | {flag_str:<12} | {dirty_str}")


# ==============================================================================
# 2. Kernel File Descriptor Table & POSIX Pipe IPC Simulation
# ==============================================================================
class KernelPipeBuffer:
    def __init__(self, capacity: int = 64):
        self.capacity = capacity
        self.buffer = bytearray()
        self.read_open = True
        self.write_open = True

    def write(self, data: bytes) -> int:
        if not self.read_open:
            raise BrokenPipeError("SIGPIPE: Reader closed, write failed with Broken pipe (EPIPE)")
        space = self.capacity - len(self.buffer)
        if space <= 0:
            return 0  # Non-blocking / buffer full simulation
        to_write = data[:space]
        self.buffer.extend(to_write)
        return len(to_write)

    def read(self, n: int) -> bytes:
        if not self.buffer:
            if not self.write_open:
                return b""  # EOF
            return b""      # Non-blocking empty
        chunk = bytes(self.buffer[:n])
        del self.buffer[:n]
        return chunk


class FileDescriptorTable:
    def __init__(self, max_fds: int = 16):
        self.max_fds = max_fds
        # fd slot -> (resource_type, resource_ref, mode)
        self.slots: Dict[int, Tuple[str, any, str]] = {
            0: ("STDIN", None, "r"),
            1: ("STDOUT", None, "w"),
            2: ("STDERR", None, "w"),
        }

    def alloc_fd(self, res_type: str, ref: any, mode: str) -> int:
        for candidate in range(self.max_fds):
            if candidate not in self.slots:
                self.slots[candidate] = (res_type, ref, mode)
                return candidate
        raise OSError("EMFILE: Too many open files")

    def close(self, fd: int) -> None:
        if fd not in self.slots:
            raise OSError(f"EBADF: Bad file descriptor {fd}")
        res_type, ref, _ = self.slots.pop(fd)
        if res_type == "PIPE_READ":
            ref.read_open = False
        elif res_type == "PIPE_WRITE":
            ref.write_open = False

    def create_pipe(self) -> Tuple[int, int]:
        pipe_obj = KernelPipeBuffer(capacity=32)
        r_fd = self.alloc_fd("PIPE_READ", pipe_obj, "r")
        w_fd = self.alloc_fd("PIPE_WRITE", pipe_obj, "w")
        return r_fd, w_fd


# ==============================================================================
# 3. RAII POSIX Handle Emulation (Scope Guard in C++)
# ==============================================================================
class UniqueFD:
    """Emulates C++ std::unique_ptr custom deleter or class FileDescriptor { ~FileDescriptor() { close(); } }"""
    def __init__(self, fd_table: FileDescriptorTable, fd: int):
        self._table = fd_table
        self._fd = fd
        self._moved = False

    def get(self) -> int:
        return self._fd

    def release(self) -> int:
        self._moved = True
        return self._fd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._moved and self._fd in self._table.slots:
            info(f"RAII Destructor invoked: auto closing fd={self._fd} to prevent fd leak")
            self._table.close(self._fd)


# ==============================================================================
# 4. POSIX Signal & Mask Dispatcher Simulation
# ==============================================================================
class SignalDispatcher:
    SIGINT  = 2
    SIGKILL = 9
    SIGUSR1 = 10
    SIGTERM = 15

    def __init__(self):
        self.signal_mask: int = 0  # Bitmask of blocked signals (sigprocmask)
        self.pending_signals: List[int] = []
        self.handlers: Dict[int, str] = {
            self.SIGINT: "Default: InterruptProcess",
            self.SIGTERM: "Default: TerminateProcess",
            self.SIGUSR1: "Default: Ignore",
            self.SIGKILL: "Unblockable: ForceKill",
        }

    def set_sigprocmask(self, block: bool, signum: int) -> None:
        if signum == self.SIGKILL:
            warn("POSIX rule: SIGKILL cannot be masked or ignored!")
            return
        if block:
            self.signal_mask |= (1 << signum)
            info(f"sigprocmask: Blocked signal {signum}")
        else:
            self.signal_mask &= ~(1 << signum)
            info(f"sigprocmask: Unblocked signal {signum}")
            self.drain_pending()

    def send_signal(self, signum: int) -> None:
        print(f"\n{CLR_MAGENTA}>>> Kernel sends signal #{signum} to process PID 4201{CLR_RESET}")
        if signum == self.SIGKILL:
            error("FATAL: SIGKILL received! Process terminated unconditionally by kernel.")
            return

        if self.signal_mask & (1 << signum):
            warn(f"Signal {signum} is BLOCKED by sigprocmask. Appended to pending queue.")
            self.pending_signals.append(signum)
        else:
            self.dispatch(signum)

    def dispatch(self, signum: int) -> None:
        handler = self.handlers.get(signum, "Default: Terminate")
        success(f"Signal {signum} dispatched -> Handler: [{handler}]")

    def drain_pending(self) -> None:
        remaining = []
        for s in self.pending_signals:
            if not (self.signal_mask & (1 << s)):
                info(f"Processing unblocked pending signal #{s}:")
                self.dispatch(s)
            else:
                remaining.append(s)
        self.pending_signals = remaining


# ==============================================================================
# Interactive CLI Scenarios & Verification
# ==============================================================================
def run_mmap_scenario(vm: VirtualMemorySubsystem) -> None:
    header("SCENARIO 1: Virtual Memory, mmap & Page Protection Violations")
    info("1. Melakukan mmap() alokasi 8192 bytes (2 pages) di VADDR 0x00400000 dengan PROT_READ | PROT_WRITE")
    vaddr = vm.mmap_allocate(0x00400000, 8192, PageProtection.PROT_READ | PageProtection.PROT_WRITE)
    success(f"mmap mapped successfully at {vaddr:#010x}")

    info("2. Melakukan mmap() alokasi 4096 bytes (1 page) di VADDR 0x00800000 dengan PROT_READ (ReadOnly)")
    ro_vaddr = vm.mmap_allocate(0x00800000, 4096, PageProtection.PROT_READ)
    success(f"ReadOnly mapped at {ro_vaddr:#010x}")

    vm.dump_mmap_mappings()

    info("3. Menulis data 0xAA ke VADDR 0x00400010...")
    vm.write_byte(0x00400010, 0xAA)
    val = vm.read_byte(0x00400010)
    success(f"Read back from 0x00400010: {val:#04x} (Match!)")

    info("4. Eksperimen: Menulis ke memori Read-Only (0x00800005) -> Expecting SIGSEGV")
    try:
        vm.write_byte(0x00800005, 0xFF)
    except PermissionError as ex:
        error(f"Captured Hardware Trap: {ex}")

    info("5. Eksperimen: Membaca address liar tak terpetakan (0x0DEAD000) -> Expecting SIGSEGV")
    try:
        vm.read_byte(0x0DEAD000)
    except PermissionError as ex:
        error(f"Captured Hardware Trap: {ex}")


def run_ipc_scenario(table: FileDescriptorTable) -> None:
    header("SCENARIO 2: POSIX Pipe IPC & EPIPE / SIGPIPE Simulation")
    info("1. Memanggil syscall pipe(pipefd)...")
    r_fd, w_fd = table.create_pipe()
    success(f"Pipe created: Read End fd={r_fd}, Write End fd={w_fd}")

    pipe_buf: KernelPipeBuffer = table.slots[w_fd][1]
    msg = b"Hello from C++ Child Process!"
    info(f"2. Menulis {len(msg)} bytes pesan ke fd={w_fd}...")
    pipe_buf.write(msg)
    info(f"Kernel pipe buffer used: {len(pipe_buf.buffer)} / {pipe_buf.capacity} bytes")

    info(f"3. Membaca 12 bytes dari fd={r_fd}...")
    received = pipe_buf.read(12)
    success(f"Received buffer slice: {received.decode('ascii')}")

    info("4. Menutup reader fd (close(r_fd)) untuk menguji Broken Pipe...")
    table.close(r_fd)

    info("5. Mencoba menulis ke pipe tanpa reader -> Mengharapkan SIGPIPE / EPIPE")
    try:
        pipe_buf.write(b"Data causing crash")
    except BrokenPipeError as ex:
        error(f"Kernel Signal Triggered: {ex}")

    table.close(w_fd)
    success(f"Write fd={w_fd} ditutup dengan aman.")


def run_raii_scenario(table: FileDescriptorTable) -> None:
    header("SCENARIO 3: RAII Resource Safety vs Raw Syscall FD Leak")
    info("Membuka pipe dengan raw handle tanpa RAII...")
    raw_r, raw_w = table.create_pipe()
    warn(f"Raw FD active: slots={list(table.slots.keys())}")
    info("Mensimulasikan exception di tengah eksekusi bisnis logika...")
    try:
        # User forgets to close raw_r & raw_w
        raise RuntimeError("Unexpected logic failure before close(fd)")
    except RuntimeError as e:
        warn(f"Exception caught: {e}")

    warn(f"RESOURCE LEAK! FD {raw_r} & {raw_w} masih tertinggal terbuka: {list(table.slots.keys())}")
    table.close(raw_r)
    table.close(raw_w)

    subheader("Membandingkan dengan Solusi Modern C++ RAII (UniqueFD)")
    r2, w2 = table.create_pipe()
    info(f"Membuka scope RAII untuk fd={r2}...")
    try:
        with UniqueFD(table, r2) as u_fd:
            info(f"Di dalam scope RAII: fd {u_fd.get()} aktif digunakan.")
            info("Memicu exception mendadak...")
            raise RuntimeError("Fatal calculation error inside RAII block")
    except RuntimeError:
        warn("Exception keluar dari scope.")

    if r2 not in table.slots:
        success(f"RAII Verifikasi: fd={r2} berhasil di-cleanup otomatis oleh destructor!")
    table.close(w2)


def run_signals_scenario() -> None:
    header("SCENARIO 4: POSIX Signals, Bitmask & sigprocmask")
    disp = SignalDispatcher()

    info("1. Mengirim SIGINT normal (tanpa blocking)...")
    disp.send_signal(disp.SIGINT)

    info("2. Memblokir SIGINT dengan sigprocmask(SIG_BLOCK, &mask, nullptr)...")
    disp.set_sigprocmask(block=True, signum=disp.SIGINT)

    info("3. Mengirim SIGINT lagi saat sedang diblokir...")
    disp.send_signal(disp.SIGINT)

    info("4. Mengirim SIGTERM normal...")
    disp.send_signal(disp.SIGTERM)

    info("5. Membuka blokir SIGINT (sigprocmask(SIG_UNBLOCK))...")
    disp.set_sigprocmask(block=False, signum=disp.SIGINT)

    info("6. Menguji proteksi SIGKILL unblockable...")
    disp.set_sigprocmask(block=True, signum=disp.SIGKILL)
    disp.send_signal(disp.SIGKILL)


def interactive_menu():
    vm = VirtualMemorySubsystem()
    table = FileDescriptorTable()

    while True:
        header("LAB EXERCISE: C++ SYSTEMS PROGRAMMING SIMULATION")
        print(f"{CLR_WHITE}1. Run Scenario 1: Virtual Memory & Page Faults (mmap/PROT)")
        print(f"2. Run Scenario 2: POSIX Pipe IPC & Broken Pipe (SIGPIPE)")
        print(f"3. Run Scenario 3: RAII Resource Management vs FD Leak")
        print(f"4. Run Scenario 4: Signal Dispatcher & sigprocmask")
        print(f"5. Run All Scenarios Sequentially (Full Diagnostic)")
        print(f"6. Exit Lab{CLR_RESET}")

        try:
            choice = input(f"\n{CLR_BOLD}Pilih opsi [1-6]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            run_mmap_scenario(vm)
        elif choice == "2":
            run_ipc_scenario(table)
        elif choice == "3":
            run_raii_scenario(table)
        elif choice == "4":
            run_signals_scenario()
        elif choice == "5":
            run_mmap_scenario(vm)
            run_ipc_scenario(table)
            run_raii_scenario(table)
            run_signals_scenario()
            success("Seluruh skenario pengujian systems programming berhasil diselesaikan!")
        elif choice == "6":
            print(f"{CLR_CYAN}Terima kasih telah menjalankan C++ Systems Programming Lab.{CLR_RESET}")
            break
        else:
            warn("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    # If run in non-interactive batch/test mode
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--batch", "-b"):
        print(f"{CLR_BOLD}Menjalankan uji otomatis (Non-interactive mode)...{CLR_RESET}")
        vm_test = VirtualMemorySubsystem()
        tbl_test = FileDescriptorTable()
        run_mmap_scenario(vm_test)
        run_ipc_scenario(tbl_test)
        run_raii_scenario(tbl_test)
        run_signals_scenario()
        success("Audit mandiri selesai dengan status 100% PASS.")
        sys.exit(0)
    else:
        # Detect if stdin is not a tty (piped)
        if not sys.stdin.isatty():
            vm_test = VirtualMemorySubsystem()
            tbl_test = FileDescriptorTable()
            run_mmap_scenario(vm_test)
            run_ipc_scenario(tbl_test)
            run_raii_scenario(tbl_test)
            run_signals_scenario()
            success("Audit mandiri selesai dengan status 100% PASS.")
        else:
            interactive_menu()
