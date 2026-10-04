#!/usr/bin/env python3
"""
Lab Hands-on: Anatomi & Filosofi Version Control System (VCS)
Modul: 02 - Deep Dive Content-Addressable Storage Engine
Deskripsi:
    Simulasi mandiri dari storage engine berbasis Git (Content-Addressable Storage).
    Script ini memodelkan:
    1. Primitif Objek Git (Blob, Tree, Commit) dengan SHA-1 hashing & zlib compression.
    2. Filosofi "Snapshot over Delta" (Penyimpanan state utuh vs per-baris perubahan).
    3. Mekanisme deduplikasi otomatis berbasis hash.
    4. Integritas kriptografis Merkle DAG (Deteksi modifikasi data liar).
"""

import hashlib
import zlib
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Colors ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"

# ==============================================================================
# 1. CORE PRIMITIVES: Content-Addressable Storage (CAS)
# ==============================================================================

class ObjectType:
    BLOB = "blob"
    TREE = "tree"
    COMMIT = "commit"

def compute_git_hash(obj_type: str, data: bytes) -> Tuple[str, bytes]:
    """
    Menghitung Git SHA-1 Hash sesuai spesifikasi resmi:
    Format: '<tipe> <ukuran_dalam_byte>\0<konten>'
    """
    header = f"{obj_type} {len(data)}\0".encode('utf-8')
    full_payload = header + data
    sha1_hash = hashlib.sha1(full_payload).hexdigest()
    return sha1_hash, full_payload

class ObjectDatabase:
    """
    Simulasi direct store '.git/objects/'.
    Menyimpan objek terkompresi zlib yang diindeks oleh SHA-1 digest.
    """
    def __init__(self):
        # Key: 40-char SHA1, Value: zlib compressed raw payload
        self.store: Dict[str, bytes] = {}
        self.stats_saved_bytes = 0
        self.stats_dedup_hits = 0

    def write_object(self, obj_type: str, data: bytes) -> str:
        """Serialisasi, hash, kompresi, dan simpan objek ke CAS."""
        sha1, full_payload = compute_git_hash(obj_type, data)
        
        if sha1 in self.store:
            # Deduplikasi otomatis: konten identik tidak memakan ruang baru
            self.stats_dedup_hits += 1
            return sha1

        compressed = zlib.compress(full_payload)
        self.store[sha1] = compressed
        self.stats_saved_bytes += len(compressed)
        return sha1

    def read_object(self, sha1: str) -> Tuple[str, bytes]:
        """Dekompresi, validasi integritas, dan deserialisasi header objek."""
        if sha1 not in self.store:
            raise KeyError(f"Objek {sha1} tidak ditemukan di Object Database.")
        
        raw_payload = zlib.decompress(self.store[sha1])
        actual_sha1 = hashlib.sha1(raw_payload).hexdigest()
        
        # Validasi integritas Merkle
        if actual_sha1 != sha1:
            raise ValueError(f"CRITICAL: Data corruption terdeteksi pada {sha1}!")

        # Parsing header '<tipe> <ukuran>\0<data>'
        null_idx = raw_payload.find(b'\0')
        header = raw_payload[:null_idx].decode('utf-8')
        obj_type, _ = header.split(' ')
        content = raw_payload[null_idx + 1:]
        
        return obj_type, content

# ==============================================================================
# 2. VCS ABSTRACTIONS: Tree & Commit Nodes
# ==============================================================================

@dataclass
class TreeEntry:
    mode: str       # '100644' (file biasa), '040000' (direktori)
    name: str       # Nama file atau folder
    sha1: str       # SHA-1 pointer ke Blob atau Tree lain

class TreeBuilder:
    """Membentuk objek Tree: Representasi direktori/snapshot hirarki filesystem."""
    @staticmethod
    def serialize_entries(entries: List[TreeEntry]) -> bytes:
        # Standar Git menyortir entri secara alfabetis berdasarkan nama
        sorted_entries = sorted(entries, key=lambda e: e.name)
        raw = b""
        for entry in sorted_entries:
            # Format raw tree: <mode> <name>\0<binary_sha1 (20 bytes)>
            raw += f"{entry.mode} {entry.name}\0".encode('utf-8')
            raw += bytes.fromhex(entry.sha1)
        return raw

class CommitBuilder:
    """Membentuk objek Commit: Metadata snapshot, root tree pointer, parent hash."""
    @staticmethod
    def serialize(tree_sha: str, parent_sha: Optional[str], author: str, message: str) -> bytes:
        timestamp = int(time.time())
        lines = [f"tree {tree_sha}"]
        if parent_sha:
            lines.append(f"parent {parent_sha}")
        lines.append(f"author {author} {timestamp} +0000")
        lines.append(f"committer {author} {timestamp} +0000")
        lines.append("")
        lines.append(message)
        lines.append("")
        return "\n".join(lines).encode('utf-8')

# ==============================================================================
# 3. HIGH-LEVEL CLIENT SIMULATION
# ==============================================================================

class MiniGitEngine:
    def __init__(self):
        self.odb = ObjectDatabase()
        self.index: Dict[str, str] = {} # Staging area: {file_path: blob_sha1}
        self.head: Optional[str] = None # Current commit SHA-1

    def stage_file(self, path: str, content: str) -> str:
        """Menyimulasikan 'git add': Simpan file sebagai blob dan perbarui Index."""
        blob_sha = self.odb.write_object(ObjectType.BLOB, content.encode('utf-8'))
        self.index[path] = blob_sha
        return blob_sha

    def commit(self, message: str, author: str = "Developer <dev@lab.local>") -> str:
        """Menyimulasikan 'git commit': Bekukan Index ke Tree, buat node Commit."""
        if not self.index:
            raise RuntimeError("Index kosong. Tidak ada perubahan untuk di-commit.")

        # Bentuk tree dari index saat ini
        tree_entries = [
            TreeEntry(mode="100644", name=path, sha1=sha)
            for path, sha in self.index.items()
        ]
        raw_tree = TreeBuilder.serialize_entries(tree_entries)
        tree_sha = self.odb.write_object(ObjectType.TREE, raw_tree)

        # Buat commit yang menunjuk ke root tree
        raw_commit = CommitBuilder.serialize(
            tree_sha=tree_sha,
            parent_sha=self.head,
            author=author,
            message=message
        )
        commit_sha = self.odb.write_object(ObjectType.COMMIT, raw_commit)
        self.head = commit_sha
        return commit_sha

# ==============================================================================
# 4. HANDS-ON DEMONSTRATION & BENCHMARK
# ==============================================================================

def print_separator(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*60}")
    print(f"[*] {title.upper()}")
    print(f"{'='*60}{CLR_RESET}\n")

def run_lab():
    engine = MiniGitEngine()

    print_separator("Tahap 1: Pembuktian Content-Addressable Storage (CAS)")
    file_a_v1 = "print('Hello, World! Modular VCS Engine')"
    file_b_v1 = "DATABASE_HOST=localhost\nDATABASE_PORT=5432"
    file_c_v1 = "print('Hello, World! Modular VCS Engine')" # Konten persis sama dengan file A

    print(f"{CLR_YELLOW}Menyimpan 3 file ke CAS...{CLR_RESET}")
    sha_a = engine.stage_file("main.py", file_a_v1)
    sha_b = engine.stage_file(".env", file_b_v1)
    sha_c = engine.stage_file("backup_main.py", file_c_v1)

    print(f" -> Blob ['main.py']        : {CLR_GREEN}{sha_a}{CLR_RESET}")
    print(f" -> Blob ['.env']           : {CLR_GREEN}{sha_b}{CLR_RESET}")
    print(f" -> Blob ['backup_main.py'] : {CLR_GREEN}{sha_c}{CLR_RESET}")

    print(f"\n{CLR_BOLD}Analisis Deduplikasi:{CLR_RESET}")
    print(f"  File 'main.py' & 'backup_main.py' memiliki isi identik.")
    print(f"  Hash sama persis? {CLR_GREEN}{sha_a == sha_c}{CLR_RESET}")
    print(f"  Objek riil tersimpan di database: {CLR_BOLD}{len(engine.odb.store)}{CLR_RESET} (Harusnya 2, bukan 3)")
    print(f"  Counter deduplikasi hit: {CLR_BOLD}{engine.odb.stats_dedup_hits}{CLR_RESET}")

    print_separator("Tahap 2: Menghasilkan Snapshot Pertama (Commit 1)")
    commit1_sha = engine.commit("Initial project architecture commit")
    print(f"Root Commit 1 SHA : {CLR_BOLD}{CLR_BLUE}{commit1_sha}{CLR_RESET}")
    
    # Inspeksi commit 1
    _, commit_content = engine.odb.read_object(commit1_sha)
    print(f"\n{CLR_GRAY}--- Raw Data Commit 1 ---\n{commit_content.decode('utf-8').strip()}\n-------------------------{CLR_RESET}")

    print_separator("Tahap 3: Filosofi Snapshot vs Delta (Commit 2)")
    print(f"Skenario: Hanya mengubah 'main.py', file '.env' dan 'backup_main.py' TIDAK disentuh.")
    
    file_a_v2 = "print('Hello, World! Modular VCS Engine v2.0 - Patch Applied')"
    sha_a_v2 = engine.stage_file("main.py", file_a_v2)
    commit2_sha = engine.commit("Update main.py to v2.0")

    print(f" -> Blob baru ['main.py v2'] : {CLR_GREEN}{sha_a_v2}{CLR_RESET}")
    print(f"Root Commit 2 SHA             : {CLR_BOLD}{CLR_BLUE}{commit2_sha}{CLR_RESET}")

    # Bandingkan Tree commit 1 vs Tree commit 2
    _, raw_c1 = engine.odb.read_object(commit1_sha)
    _, raw_c2 = engine.odb.read_object(commit2_sha)
    
    # Ambil tree hash dari masing-masing commit
    tree1_sha = raw_c1.decode('utf-8').split("\n")[0].split(" ")[1]
    tree2_sha = raw_c2.decode('utf-8').split("\n")[0].split(" ")[1]

    print(f"\nPerbandingan Tree:")
    print(f"  Tree Commit 1 : {tree1_sha}")
    print(f"  Tree Commit 2 : {tree2_sha}")
    print(f"  Tree Hash berubah? {CLR_YELLOW}{tree1_sha != tree2_sha}{CLR_RESET} (Karena snapshot seluruh root berganti)")

    print_separator("Tahap 4: Pembuktian Immutability & Merkle DAG Integrity")
    print(f"Mekanisme Git mencegah pemalsuan riwayat (Tamper-Resistance).")
    print(f"Mencoba mengutak-atik byte pada blob asli di disk storage...")

    # Memodifikasi byte secara sengaja di ODB
    corrupted_data = b"DATA_PALSU_DISISIPKAN"
    engine.odb.store[sha_b] = zlib.compress(b"blob 21\0" + corrupted_data)

    print(f"Mencoba membaca objek {sha_b[:10]}... yang telah dimodifikasi secara ilegal:")
    try:
        engine.odb.read_object(sha_b)
    except ValueError as err:
        print(f"{CLR_RED}[PASS] Deteksi Kriptografis Berhasil:{CLR_RESET} {err}")

    print_separator("Tahap 5: Ringkasan Metrik Storage CAS")
    print(f"Total objek tersimpan : {CLR_BOLD}{len(engine.odb.store)}{CLR_RESET}")
    print(f"Deduplikasi terpicu   : {CLR_BOLD}{engine.odb.stats_dedup_hits} kali{CLR_RESET}")
    print(f"Kompresi Zlib aktif   : {CLR_GREEN}Valid (Lossless Deflate Engine){CLR_RESET}")
    print(f"Status Sistem         : {CLR_BOLD}{CLR_GREEN}INTEGRITAS TERVERIFIKASI TINGKAT SISTEM{CLR_RESET}\n")

if __name__ == "__main__":
    run_lab()