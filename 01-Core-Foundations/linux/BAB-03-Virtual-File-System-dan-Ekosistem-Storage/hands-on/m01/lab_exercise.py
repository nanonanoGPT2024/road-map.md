#!/usr/bin/env python3
"""
Lab Exercise: Virtual File System (VFS) & Linux Storage Ecosystem
BAB-03: Virtual File System dan Ekosistem Storage

Simulasi interaktif arsitektur internal Linux VFS:
- Superblock, Inode, Dentry, dan File Object (struct file)
- Alokasi Data Block & Inode Table
- Hard Links vs Symbolic (Soft) Links
- File Descriptor (fd) table per process
- Mount Points & Virtual Filesystems (procfs/sysfs)
"""

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Codes untuk visualisasi terminal
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_BLUE = "\033[44m"


# ==============================================================================
# Model Struktur Data VFS & Storage
# ==============================================================================
@dataclass
class Inode:
    ino: int
    mode: str           # "file", "dir", "symlink"
    size: int
    nlink: int
    blocks: List[int] = field(default_factory=list)
    target_path: Optional[str] = None  # Khusus symlink

@dataclass
class Dentry:
    name: str
    inode_nr: int
    parent: Optional['Dentry'] = None
    children: Dict[str, 'Dentry'] = field(default_factory=dict)

@dataclass
class FileHandle:
    fd: int
    inode_nr: int
    offset: int
    flags: str          # "r", "w", "rw"


class VFSSimulator:
    def __init__(self, total_blocks: int = 64, block_size: int = 4096):
        self.block_size = block_size
        self.total_blocks = total_blocks
        self.free_blocks = [True] * total_blocks
        self.storage_pool: Dict[int, str] = {}
        self.inodes: Dict[int, Inode] = {}
        self.next_inode = 1
        self.fd_table: Dict[int, FileHandle] = {}
        self.next_fd = 3  # 0, 1, 2 reserved untuk stdin/out/err

        # Inisialisasi Root Dentry & Inode
        root_inode = self._alloc_inode(mode="dir", size=4096)
        self.root_dentry = Dentry(name="/", inode_nr=root_inode.ino)
        self.current_dentry = self.root_dentry

        # Simulasi Mount Pseudo-FS
        self.mounts: Dict[str, str] = {
            "/": "ext4 (rw,relatime)",
            "/proc": "proc (rw,nosuid,nodev,noexec)",
            "/sys": "sysfs (rw,nosuid,nodev,noexec)"
        }

    def _alloc_blocks(self, count: int) -> List[int]:
        allocated = []
        for i in range(self.total_blocks):
            if self.free_blocks[i]:
                self.free_blocks[i] = False
                allocated.append(i)
                if len(allocated) == count:
                    break
        if len(allocated) < count:
            # Rollback alokasi parsial
            for b in allocated:
                self.free_blocks[b] = True
            raise IOError("Disk Full: Tidak cukup data block yang tersedia!")
        return allocated

    def _free_blocks(self, blocks: List[int]):
        for b in blocks:
            self.free_blocks[b] = True
            self.storage_pool.pop(b, None)

    def _alloc_inode(self, mode: str, size: int = 0) -> Inode:
        ino = self.next_inode
        self.next_inode += 1
        inode = Inode(ino=ino, mode=mode, size=size, nlink=1)
        self.inodes[ino] = inode
        return inode

    def create_file(self, filename: str, content: str) -> Tuple[int, Inode]:
        if filename in self.current_dentry.children:
            raise FileExistsError(f"File '{filename}' sudah ada pada dentry saat ini.")

        data_bytes = content.encode('utf-8')
        size = len(data_bytes)
        needed_blocks = max(1, (size + self.block_size - 1) // self.block_size)
        blocks = self._alloc_blocks(needed_blocks)

        inode = self._alloc_inode(mode="file", size=size)
        inode.blocks = blocks

        # Simpan payload ke block simulasi
        for idx, blk in enumerate(blocks):
            chunk = content[idx * self.block_size : (idx + 1) * self.block_size]
            self.storage_pool[blk] = chunk

        child_dentry = Dentry(name=filename, inode_nr=inode.ino, parent=self.current_dentry)
        self.current_dentry.children[filename] = child_dentry
        return inode.ino, inode

    def create_hardlink(self, target_name: str, link_name: str):
        if target_name not in self.current_dentry.children:
            raise FileNotFoundError(f"Target '{target_name}' tidak ditemukan.")
        if link_name in self.current_dentry.children:
            raise FileExistsError(f"Nama link '{link_name}' sudah terpakai.")

        target_dentry = self.current_dentry.children[target_name]
        inode = self.inodes[target_dentry.inode_nr]
        if inode.mode == "dir":
            raise PermissionError("Hard link ke direktori dilarang oleh kernel Linux (mencegah cyclic directory loops).")

        inode.nlink += 1
        link_dentry = Dentry(name=link_name, inode_nr=inode.ino, parent=self.current_dentry)
        self.current_dentry.children[link_name] = link_dentry

    def create_symlink(self, target_path: str, link_name: str):
        if link_name in self.current_dentry.children:
            raise FileExistsError(f"Nama link '{link_name}' sudah terpakai.")

        inode = self._alloc_inode(mode="symlink", size=len(target_path))
        inode.target_path = target_path
        link_dentry = Dentry(name=link_name, inode_nr=inode.ino, parent=self.current_dentry)
        self.current_dentry.children[link_name] = link_dentry

    def unlink(self, filename: str):
        if filename not in self.current_dentry.children:
            raise FileNotFoundError(f"File '{filename}' tidak ditemukan.")

        dentry = self.current_dentry.children.pop(filename)
        inode = self.inodes[dentry.inode_nr]
        inode.nlink -= 1

        # Jika link count habis dan tidak ada file descriptor aktif, deallokasi inode & blocks
        if inode.nlink == 0:
            active_opens = any(h.inode_nr == inode.ino for h in self.fd_table.values())
            if not active_opens:
                self._free_blocks(inode.blocks)
                self.inodes.pop(inode.ino, None)

    def open_file(self, filename: str, flags: str = "r") -> int:
        if filename not in self.current_dentry.children:
            raise FileNotFoundError(f"File '{filename}' tidak ditemukan.")

        dentry = self.current_dentry.children[filename]
        inode = self.inodes[dentry.inode_nr]

        # Resolusi Symlink jika ada
        if inode.mode == "symlink":
            target = inode.target_path or ""
            if target not in self.current_dentry.children:
                raise FileNotFoundError(f"Dangling symlink: target '{target}' tidak ditemukan.")
            dentry = self.current_dentry.children[target]
            inode = self.inodes[dentry.inode_nr]

        fd = self.next_fd
        self.next_fd += 1
        self.fd_table[fd] = FileHandle(fd=fd, inode_nr=inode.ino, offset=0, flags=flags)
        return fd

    def close_file(self, fd: int):
        if fd not in self.fd_table:
            raise ValueError(f"Bad File Descriptor: fd {fd} tidak valid.")
        handle = self.fd_table.pop(fd)
        inode = self.inodes.get(handle.inode_nr)
        if inode and inode.nlink == 0:
            # Bersihkan inode tertunda jika semua fd ditutup
            active_opens = any(h.inode_nr == inode.ino for h in self.fd_table.values())
            if not active_opens:
                self._free_blocks(inode.blocks)
                self.inodes.pop(inode.ino, None)


# ==============================================================================
# Antarmuka Visualisasi Terminal ANSI
# ==============================================================================
def clear_screen():
    print("\033[2J\033[H", end="")

def banner():
    print(f"{Color.CYAN}{Color.BOLD}" + "=" * 70)
    print("   VIRTUAL FILE SYSTEM (VFS) & STORAGE ECOSYSTEM INTERACTIVE LAB")
    print("   Arsitektur Kernel Linux: Inode, Dentry, Block Bitmap & FDs")
    print("=" * 70 + f"{Color.RESET}")

def render_vfs_state(vfs: VFSSimulator):
    print(f"\n{Color.BOLD}{Color.YELLOW}[1] MOUNT POINTS TABLE (VFS Superblock Abstraction):{Color.RESET}")
    for mnt, fstype in vfs.mounts.items():
        print(f"  {Color.GREEN}{mnt:<10}{Color.RESET} -> filesystem: {Color.WHITE}{fstype}{Color.RESET}")

    print(f"\n{Color.BOLD}{Color.YELLOW}[2] DENTRY TREE (Hierarki Direktori '/') & INODE BINDINGS:{Color.RESET}")
    if not vfs.current_dentry.children:
        print(f"  {Color.WHITE}(Direktori kosong){Color.RESET}")
    for name, dentry in vfs.current_dentry.children.items():
        ino = vfs.inodes.get(dentry.inode_nr)
        if ino:
            mode_badge = f"{Color.BG_BLUE} {ino.mode.upper()} {Color.RESET}"
            extra = f"-> {ino.target_path}" if ino.mode == "symlink" else f"blocks={ino.blocks}"
            print(f"  * Dentry: {Color.BOLD}{name:<16}{Color.RESET} Inode: {Color.CYAN}#{ino.ino:<3}{Color.RESET} "
                  f"Links: {Color.MAGENTA}{ino.nlink:<2}{Color.RESET} {mode_badge} Size: {ino.size}B {extra}")

    print(f"\n{Color.BOLD}{Color.YELLOW}[3] OPEN FILE TABLE (Kernel Process FD Table):{Color.RESET}")
    if not vfs.fd_table:
        print(f"  {Color.WHITE}(Tidak ada file yang sedang terbuka oleh proses){Color.RESET}")
    for fd, handle in vfs.fd_table.items():
        print(f"  * fd: {Color.RED}{fd}{Color.RESET} -> Inode: #{handle.inode_nr} | Offset: {handle.offset} | Mode: '{handle.flags}'")

    print(f"\n{Color.BOLD}{Color.YELLOW}[4] STORAGE BLOCK BITMAP (Ext4 / Physical Block Layer):{Color.RESET}")
    used_blocks = sum(1 for f in vfs.free_blocks if not f)
    total = vfs.total_blocks
    bar = ""
    for idx, free in enumerate(vfs.free_blocks):
        if idx > 0 and idx % 16 == 0:
            bar += "\n  "
        bar += f"{Color.GREEN}.{Color.RESET} " if free else f"{Color.RED}X{Color.RESET} "
    print(f"  Kapasitas: {used_blocks}/{total} Blocks Terpakai ({used_blocks * vfs.block_size} bytes)")
    print(f"  [ . = Bebas | X = Terisi ]\n  {bar}")


# ==============================================================================
# Menu Interaktif Lab
# ==============================================================================
def print_menu():
    print(f"\n{Color.CYAN}{Color.BOLD}--- PILIHAN OPERASI LAB ---{Color.RESET}")
    print(f"[{Color.GREEN}1{Color.RESET}] Buat File Baru (write dentry + alloc inode + alloc blocks)")
    print(f"[{Color.GREEN}2{Color.RESET}] Buat Hard Link (ln target link) -> Uji Inode Refcount")
    print(f"[{Color.GREEN}3{Color.RESET}] Buat Symbolic Link (ln -s target link) -> Pointer Inode")
    print(f"[{Color.GREEN}4{Color.RESET}] Buka File (sys_open -> dapatkan File Descriptor)")
    print(f"[{Color.GREEN}5{Color.RESET}] Tutup File (sys_close fd)")
    print(f"[{Color.GREEN}6{Color.RESET}] Hapus File (sys_unlink) -> Lihat perilaku Inode & Block deallocation")
    print(f"[{Color.GREEN}7{Color.RESET}] Eksperimen Khusus: 'Unlink saat FD masih terbuka' (Linux Lazy Deletion)")
    print(f"[{Color.GREEN}8{Color.RESET}] Jalankan Verifikasi Otomatis (Self-Test Suite)")
    print(f"[{Color.RED}0{Color.RESET}] Keluar dari Lab")


def run_lazy_deletion_experiment(vfs: VFSSimulator):
    print(f"\n{Color.MAGENTA}{Color.BOLD}=== EKSPERIMEN: LINUX LAZY DELETION (Unlink Open File) ==={Color.RESET}")
    print("Skenario dunia nyata: Log file dihapus ('rm app.log'), namun disk tetap penuh")
    print("karena daemon aplikasi masih memegang open file descriptor!")
    time.sleep(1)

    filename = "database.log"
    vfs.create_file(filename, "A" * 8192)
    print(f"{Color.GREEN}[+] Dibuat '{filename}' (mengalokasikan 2 blocks).{Color.RESET}")

    fd = vfs.open_file(filename, "r")
    print(f"{Color.GREEN}[+] File dibuka oleh daemon -> Mendapatkan FD: {fd}.{Color.RESET}")

    print(f"{Color.YELLOW}[*] Menjalankan unlink('{filename}')...{Color.RESET}")
    vfs.unlink(filename)
    print(f"{Color.CYAN}[i] Status setelah unlink:{Color.RESET}")
    print(f"    - Nama '{filename}' hilang dari Dentry direktori.")
    print(f"    - Inode nlink menjadi 0.")
    print(f"    - Namun blok data BELUM dilepaskan karena process FD {fd} masih aktif!")
    
    render_vfs_state(vfs)
    input(f"\n{Color.WHITE}Tekan Enter untuk mensimulasikan process close(fd {fd}) atau daemon mati...{Color.RESET}")
    vfs.close_file(fd)
    print(f"{Color.GREEN}[+] FD {fd} ditutup -> Kernel sekarang melepaskan blok penyimpanan ke bitmap!{Color.RESET}")


def run_self_tests(vfs: VFSSimulator):
    print(f"\n{Color.CYAN}{Color.BOLD}=== MENJALANKAN SELF-TEST SUITE VFS & STORAGE ==={Color.RESET}")
    # Test 1: Inode sharing on Hard Link
    test_vfs = VFSSimulator()
    ino1, _ = test_vfs.create_file("test1.txt", "Linux Kernel Core")
    test_vfs.create_hardlink("test1.txt", "test1_hl.txt")
    assert test_vfs.inodes[ino1].nlink == 2, "Test 1 Gagal: nlink harus 2"
    print(f" {Color.GREEN}✔ PASS{Color.RESET}: Hard link berbagi Inode dan menaikkan nlink ke 2.")

    # Test 2: Symlink memiliki Inode berbeda
    test_vfs.create_symlink("test1.txt", "test1_sl.txt")
    sl_dentry = test_vfs.current_dentry.children["test1_sl.txt"]
    assert sl_dentry.inode_nr != ino1, "Test 2 Gagal: symlink harus memiliki Inode baru"
    assert test_vfs.inodes[sl_dentry.inode_nr].mode == "symlink"
    print(f" {Color.GREEN}✔ PASS{Color.RESET}: Symlink membuat inode terpisah dengan mode 'symlink'.")

    # Test 3: Block deallocation setelah nlink = 0
    test_vfs.unlink("test1.txt")
    assert test_vfs.inodes[ino1].nlink == 1, "Test 3 Gagal: nlink harus tersisa 1"
    test_vfs.unlink("test1_hl.txt")
    assert ino1 not in test_vfs.inodes, "Test 3 Gagal: Inode harus dibersihkan setelah nlink 0"
    print(f" {Color.GREEN}✔ PASS{Color.RESET}: Data block dan Inode dilepas sempurna saat refcount habis.")
    print(f"{Color.GREEN}{Color.BOLD}SEMUA PENGUJIAN INTI VFS SUKSES!{Color.RESET}\n")


def main():
    vfs = VFSSimulator(total_blocks=64, block_size=4096)

    # Inisialisasi awal beberapa file untuk demonstrasi
    vfs.create_file("kernel.img", "ELF-BOOTLOADER-DATA")
    vfs.create_file("config.sys", "vfs.max_inodes=65536")

    # Jika dijalankan secara non-interaktif atau mode CI/Headless
    if not sys.stdin.isatty():
        banner()
        render_vfs_state(vfs)
        run_self_tests(vfs)
        print(f"{Color.GREEN}Eksekusi headless selesai dengan sukses.{Color.RESET}")
        return

    while True:
        clear_screen()
        banner()
        render_vfs_state(vfs)
        print_menu()

        try:
            choice = input(f"\n{Color.BOLD}Pilih opsi [0-8]: {Color.RESET}").strip()
            if choice == "0":
                print(f"\n{Color.CYAN}Keluar dari simulator VFS. Terima kasih!{Color.RESET}")
                break

            elif choice == "1":
                fname = input("Nama file: ").strip()
                content = input("Konten teks file: ")
                if fname:
                    vfs.create_file(fname, content)
                    print(f"{Color.GREEN}File '{fname}' berhasil dibuat!{Color.RESET}")

            elif choice == "2":
                target = input("Nama file target: ").strip()
                link = input("Nama hard link: ").strip()
                vfs.create_hardlink(target, link)
                print(f"{Color.GREEN}Hard link '{link}' -> '{target}' berhasil dibuat!{Color.RESET}")

            elif choice == "3":
                target = input("Target path symlink: ").strip()
                link = input("Nama symlink: ").strip()
                vfs.create_symlink(target, link)
                print(f"{Color.GREEN}Symlink '{link}' -> '{target}' berhasil dibuat!{Color.RESET}")

            elif choice == "4":
                fname = input("Nama file yang ingin dibuka: ").strip()
                flag = input("Mode open (r/w/rw) [default: r]: ").strip() or "r"
                fd = vfs.open_file(fname, flag)
                print(f"{Color.GREEN}File dibuka! Process mendapatkan file descriptor fd = {fd}{Color.RESET}")

            elif choice == "5":
                fd_str = input("Masukkan FD yang ingin ditutup: ").strip()
                if fd_str.isdigit():
                    vfs.close_file(int(fd_str))
                    print(f"{Color.GREEN}File descriptor {fd_str} berhasil ditutup.{Color.RESET}")

            elif choice == "6":
                fname = input("Nama file/link yang ingin di-unlink: ").strip()
                vfs.unlink(fname)
                print(f"{Color.GREEN}Dentry '{fname}' berhasil di-unlink.{Color.RESET}")

            elif choice == "7":
                run_lazy_deletion_experiment(vfs)

            elif choice == "8":
                run_self_tests(vfs)

            else:
                print(f"{Color.RED}Pilihan tidak valid!{Color.RESET}")

            input(f"\n{Color.WHITE}Tekan Enter untuk melanjutkan...{Color.RESET}")

        except Exception as err:
            print(f"\n{Color.RED}{Color.BOLD}[ERROR]: {err}{Color.RESET}")
            input(f"\n{Color.WHITE}Tekan Enter untuk melanjutkan...{Color.RESET}")


if __name__ == "__main__":
    main()
