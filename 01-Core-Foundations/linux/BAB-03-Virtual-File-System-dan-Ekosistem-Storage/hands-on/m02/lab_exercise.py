#!/usr/bin/env python3
"""
Lab Hands-on: Virtual File System (VFS), Storage, dan Blok I/O
Kategori: 01-Core-Foundations | Bab 03 - Modul 02 Deep Dive

Script ini memodelkan arsitektur sub-sistem storage Linux dari user-space
hingga physical sector level:
 1. VFS Layer (vfs_inode, vfs_dentry, struct file, file_operations)
 2. Page Cache Subsystem (Dirty page tracking, Writeback daemon simulation)
 3. Block I/O Layer (bio request construction, Elevator / SCAN scheduler, request merging)
 4. Disk Driver Mock (LBA addressing, seek-time calculation, sector-level I/O)
"""

import sys
import time
import math
from typing import Dict, List, Optional, Tuple

# --- ANSI Formatting Constants ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"

PAGE_SIZE = 4096       # Linux standard 4KB memory page
SECTOR_SIZE = 512      # Classical 512-byte disk sector
SECTORS_PER_PAGE = PAGE_SIZE // SECTOR_SIZE


class Bio:
    """
    Representasi dari struct bio (Block I/O).
    Membawa deskripsi I/O request dari Page Cache / VFS ke block layer.
    """
    def __init__(self, rw: str, sector_start: int, sector_count: int, buffer: bytearray):
        self.rw = rw  # 'READ' atau 'WRITE'
        self.sector_start = sector_start
        self.sector_count = sector_count
        self.buffer = buffer
        self.completed = False

    def can_merge(self, other: 'Bio') -> bool:
        """Mengecek apakah request contiguous dan bisa dimerge (bio merging)."""
        return (self.rw == other.rw and
                (self.sector_start + self.sector_count == other.sector_start))

    def merge(self, other: 'Bio') -> None:
        """Menggabungkan dua contiguous request menjadi satu segment I/O tunggal."""
        self.sector_count += other.sector_count
        self.buffer.extend(other.buffer)


class BlockDevice:
    """
    Mock Driver Perangkat Blok / Disk Kontroler.
    Menyimpan block raw dan melacak head-movement seek distance.
    """
    def __init__(self, total_sectors: int = 65536):
        self.total_sectors = total_sectors
        self.storage: Dict[int, bytearray] = {}
        self.head_position = 0
        self.total_seek_distance = 0

    def submit_bio(self, bio: Bio) -> None:
        """Mengeksekusi bio pada LBA storage."""
        seek = abs(self.head_position - bio.sector_start)
        self.total_seek_distance += seek
        self.head_position = bio.sector_start + bio.sector_count

        if bio.rw == 'WRITE':
            for i in range(bio.sector_count):
                sec = bio.sector_start + i
                offset = i * SECTOR_SIZE
                chunk = bio.buffer[offset:offset + SECTOR_SIZE]
                self.storage[sec] = bytearray(chunk.ljust(SECTOR_SIZE, b'\0'))
        elif bio.rw == 'READ':
            bio.buffer = bytearray()
            for i in range(bio.sector_count):
                sec = bio.sector_start + i
                bio.buffer.extend(self.storage.get(sec, bytearray(SECTOR_SIZE)))

        bio.completed = True


class ElevatorScheduler:
    """
    Implementasi I/O Scheduler (Elevator/SCAN & Bio Request Merging).
    Mencegah head thrashing dengan mengurutkan dan menggabungkan sektor contiguous.
    """
    def __init__(self, block_dev: BlockDevice):
        self.block_dev = block_dev
        self.queue: List[Bio] = []

    def insert_request(self, bio: Bio) -> None:
        # Coba LLR / contiguous merge dengan request terakhir jika memungkinkan
        if self.queue and self.queue[-1].can_merge(bio):
            self.queue[-1].merge(bio)
            print(f"  {CLR_CYAN}[Block Layer]{CLR_RESET} Merged Bio contiguous: "
                  f"Sector {bio.sector_start} merged into prev request.")
        else:
            self.queue.append(bio)

    def dispatch_all(self, sort_elevator: bool = True) -> int:
        """
        Dispatch request ke disk.
        Jika sort_elevator aktif: diurutkan berdasarkan LBA ascending (Elevator SCAN).
        """
        if not self.queue:
            return 0

        initial_count = len(self.queue)
        if sort_elevator:
            # Sort ascending berdasarkan LBA sektor awal (Elevator sweep)
            self.queue.sort(key=lambda b: b.sector_start)

        while self.queue:
            bio = self.queue.pop(0)
            self.block_dev.submit_bio(bio)

        return initial_count


class Page:
    """Representasi struct page dalam Page Cache."""
    def __init__(self, index: int):
        self.index = index
        self.data = bytearray(PAGE_SIZE)
        self.dirty = False
        self.valid = False


class Inode:
    """
    Representasi struct inode pada VFS.
    Menyimpan metadata file dan memetakan page index ke LBA block sector.
    """
    _ino_counter = 1000

    def __init__(self, mode: str = "file"):
        Inode._ino_counter += 1
        self.i_ino = Inode._ino_counter
        self.i_mode = mode
        self.i_size = 0
        self.i_blocks = 0
        # Mapping: logical page index -> sector LBA awal pada block device
        self.block_map: Dict[int, int] = {}
        # Page cache resident pages
        self.page_cache: Dict[int, Page] = {}

    def allocate_page_lba(self, page_idx: int) -> int:
        """Mengalokasikan LBA fisik untuk page logis jika belum terpetakan."""
        if page_idx not in self.block_map:
            # Alokasi deterministic pseudo-LBA berdasarkan inode dan page index
            lba = (self.i_ino * 64 + page_idx * SECTORS_PER_PAGE) % 60000
            self.block_map[page_idx] = lba
            self.i_blocks += SECTORS_PER_PAGE
        return self.block_map[page_idx]


class Dentry:
    """Representasi struct dentry (Directory Entry Cache) pada VFS."""
    def __init__(self, name: str, inode: Optional[Inode] = None, parent: Optional['Dentry'] = None):
        self.d_name = name
        self.d_inode = inode
        self.d_parent = parent
        self.d_subdirs: Dict[str, 'Dentry'] = {}


class File:
    """Representasi struct file (Open File Descriptor context)."""
    def __init__(self, dentry: Dentry, flags: str = "r"):
        self.f_dentry = dentry
        self.f_pos = 0  # Offset pointer
        self.f_flags = flags


class VirtualFileSystem:
    """
    VFS Engine: Menyediakan abstraksi POSIX file operations, Page Cache handling,
    dan jembatan I/O flush ke Block Layer.
    """
    def __init__(self, scheduler: ElevatorScheduler):
        self.scheduler = scheduler
        self.root_dentry = Dentry("/")
        self.root_dentry.d_inode = Inode(mode="dir")
        self.cache_hits = 0
        self.cache_misses = 0

    def lookup(self, path: str) -> Optional[Dentry]:
        """Resolusi path dentry (dcache lookup)."""
        tokens = [t for t in path.strip("/").split("/") if t]
        curr = self.root_dentry
        for token in tokens:
            if token not in curr.d_subdirs:
                return None
            curr = curr.d_subdirs[token]
        return curr

    def create_file(self, path: str) -> Dentry:
        """Alokasi dentry dan inode baru (vfs_create)."""
        tokens = [t for t in path.strip("/").split("/") if t]
        filename = tokens[-1]
        parent = self.root_dentry

        # Sederhana: file ditaruh di root directory
        inode = Inode(mode="file")
        dentry = Dentry(filename, inode, parent)
        parent.d_subdirs[filename] = dentry
        return dentry

    def write(self, file_desc: File, data: bytes) -> int:
        """
        vfs_write(): Menulis data ke Page Cache.
        Halaman ditandai 'dirty' tanpa langsung memicu synchronous block I/O.
        """
        inode = file_desc.f_dentry.d_inode
        bytes_written = 0
        total_len = len(data)

        while bytes_written < total_len:
            page_idx = file_desc.f_pos // PAGE_SIZE
            offset_in_page = file_desc.f_pos % PAGE_SIZE
            chunk_size = min(total_len - bytes_written, PAGE_SIZE - offset_in_page)

            # Temukan atau buat Page di Page Cache
            if page_idx not in inode.page_cache:
                inode.page_cache[page_idx] = Page(page_idx)
                inode.allocate_page_lba(page_idx)

            page = inode.page_cache[page_idx]
            # Copy data ke page buffer
            chunk = data[bytes_written:bytes_written + chunk_size]
            page.data[offset_in_page:offset_in_page + chunk_size] = chunk
            page.dirty = True
            page.valid = True

            file_desc.f_pos += chunk_size
            bytes_written += chunk_size

            if file_desc.f_pos > inode.i_size:
                inode.i_size = file_desc.f_pos

        return bytes_written

    def read(self, file_desc: File, length: int) -> bytes:
        """
        vfs_read(): Membaca data melalui Page Cache.
        Jika page tidak ada (cache miss), dibaca dari Block Device via bio read.
        """
        inode = file_desc.f_dentry.d_inode
        bytes_read = 0
        read_buffer = bytearray()
        target_len = min(length, max(0, inode.i_size - file_desc.f_pos))

        while bytes_read < target_len:
            page_idx = file_desc.f_pos // PAGE_SIZE
            offset_in_page = file_desc.f_pos % PAGE_SIZE
            chunk_size = min(target_len - bytes_read, PAGE_SIZE - offset_in_page)

            # Cek Page Cache
            if page_idx in inode.page_cache and inode.page_cache[page_idx].valid:
                self.cache_hits += 1
                page = inode.page_cache[page_idx]
            else:
                self.cache_misses += 1
                # Page fault / cache miss -> Alokasi page & submit read bio
                lba = inode.allocate_page_lba(page_idx)
                page = Page(page_idx)
                bio = Bio(rw='READ', sector_start=lba, sector_count=SECTORS_PER_PAGE, buffer=bytearray())
                self.scheduler.insert_request(bio)
                self.scheduler.dispatch_all(sort_elevator=False)
                page.data = bio.buffer
                page.valid = True
                inode.page_cache[page_idx] = page

            read_buffer.extend(page.data[offset_in_page:offset_in_page + chunk_size])
            file_desc.f_pos += chunk_size
            bytes_read += chunk_size

        return bytes(read_buffer)

    def sync_inode(self, inode: Inode) -> int:
        """
        Simulasi kworker writeback daemon (fsync / sync).
        Mengumpulkan dirty page, membangun struct bio, dan push ke elevator scheduler.
        """
        flushed_pages = 0
        for page_idx, page in sorted(inode.page_cache.items()):
            if page.dirty:
                lba = inode.block_map[page_idx]
                bio = Bio(rw='WRITE', sector_start=lba, sector_count=SECTORS_PER_PAGE,
                          buffer=bytearray(page.data))
                self.scheduler.insert_request(bio)
                page.dirty = False
                flushed_pages += 1
        return flushed_pages


def main():
    print(f"{CLR_BOLD}{CLR_GREEN}=== [LAB] VFS, Page Cache, dan Sub-Sistem Blok I/O Linux ==={CLR_RESET}\n")

    # Inisialisasi Device & Layers
    disk = BlockDevice()
    scheduler = ElevatorScheduler(disk)
    vfs = VirtualFileSystem(scheduler)

    # 1. Alokasi VFS Inode & Dentry
    print(f"{CLR_BOLD}{CLR_YELLOW}[Step 1] Inisialisasi VFS Inode & Dentry Cache{CLR_RESET}")
    dentry_app = vfs.create_file("database.db")
    inode_app = dentry_app.d_inode
    print(f"  VFS Path     : /{dentry_app.d_name}")
    print(f"  Alloc Inode  : ino={inode_app.i_ino} (mode={inode_app.i_mode})")

    # 2. Write Pipeline: Buffered Write ke Page Cache
    print(f"\n{CLR_BOLD}{CLR_YELLOW}[Step 2] Buffered Write (vfs_write) ke Page Cache{CLR_RESET}")
    fd = File(dentry_app, flags="w")

    # Siapkan data non-trivial multi-page (10 KB = ~2.5 halaman 4KB)
    payload_size = 10240
    dummy_data = bytearray((i % 256 for i in range(payload_size)))
    vfs.write(fd, dummy_data)

    print(f"  Ukuran payload : {payload_size} bytes")
    print(f"  Offset File    : {fd.f_pos} bytes")
    print(f"  Inode size     : {inode_app.i_size} bytes")
    print(f"  Cached Pages   : {len(inode_app.page_cache)} halaman dialokasikan")
    for idx, page in inode_app.page_cache.items():
        print(f"    Page #{idx}: Dirty={CLR_RED}{page.dirty}{CLR_RESET}, "
              f"Mapped to LBA Sector={inode_app.block_map[idx]}")

    print(f"  Status Disk    : Belum ada blok tertulis pada disk fisik (Deferred I/O).")

    # 3. Writeback Simulation: Merging & Elevator Scheduling
    print(f"\n{CLR_BOLD}{CLR_YELLOW}[Step 3] Flush/Writeback Daemon (Bio Construction & Merging){CLR_RESET}")
    flushed = vfs.sync_inode(inode_app)
    print(f"  Dirty pages flushed : {flushed}")
    print(f"  Scheduled Bio Queue : {len(scheduler.queue)} unified request(s) siap kirim")

    # Tampilkan request sebelum dispatch
    for bio in scheduler.queue:
        print(f"    -> Bio: Op={bio.rw}, Start LBA={bio.sector_start}, "
              f"Sectors={bio.sector_count} ({bio.sector_count * SECTOR_SIZE} bytes)")

    # Dispatch elevator ke Mock Block Device
    dispatched = scheduler.dispatch_all(sort_elevator=True)
    print(f"  Dispatched Bios     : {dispatched} request(s) dieksekusi oleh driver.")
    print(f"  Head seek distance  : {disk.total_seek_distance} sektor.")

    # 4. Read Pipeline: Cache Hit vs Cache Invalidation / Cold Read
    print(f"\n{CLR_BOLD}{CLR_YELLOW}[Step 4] Read Pipeline & Cache Hit Verification{CLR_RESET}")
    read_fd = File(dentry_app, flags="r")
    data_cached = vfs.read(read_fd, payload_size)
    print(f"  Read bytes      : {len(data_cached)}")
    print(f"  Cache Hits      : {CLR_GREEN}{vfs.cache_hits}{CLR_RESET}")
    print(f"  Cache Misses    : {vfs.cache_misses}")
    assert data_cached == dummy_data, "Data integrity error on Page Cache read!"

    # Invalidate Page Cache untuk mensimulasikan drop_caches / cold read
    print(f"\n{CLR_BOLD}{CLR_YELLOW}[Step 5] Cache Invalidation (echo 3 > /proc/sys/vm/drop_caches){CLR_RESET}")
    inode_app.page_cache.clear()
    print("  Page Cache purged dari memori!")

    read_fd_cold = File(dentry_app, flags="r")
    initial_seek = disk.total_seek_distance
    data_cold = vfs.read(read_fd_cold, payload_size)
    print(f"  Cold Read bytes : {len(data_cold)}")
    print(f"  Cache Hits      : {vfs.cache_hits}")
    print(f"  Cache Misses    : {CLR_RED}{vfs.cache_misses}{CLR_RESET} (Triggers Block Bio Read)")
    print(f"  Additional Seek : {disk.total_seek_distance - initial_seek} sektor")
    assert data_cold == dummy_data, "Data integrity error on Physical Disk read!"

    # Summary
    print(f"\n{CLR_BOLD}{CLR_GREEN}=== [SIMULASI SUKSES] Ringkasan Sub-Sistem Storage Linux ==={CLR_RESET}")
    print(f"  Total Sector Disk Terpakai : {len(disk.storage)} sektor ({len(disk.storage)*SECTOR_SIZE} B)")
    print(f"  Total Akumulasi Seek Disk  : {disk.total_seek_distance} sektor")
    print(f"  Status Data Integrity      : {CLR_GREEN}MATCH (100% Valid){CLR_RESET}\n")


if __name__ == "__main__":
    main()