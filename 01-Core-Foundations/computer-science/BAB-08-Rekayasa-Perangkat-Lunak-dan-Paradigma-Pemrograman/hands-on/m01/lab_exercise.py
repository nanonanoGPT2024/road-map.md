#!/usr/bin/env python3
"""
Laboratorium Mandiri: Computer Science - Materi Lanjutan (BAB-08)
Fokus: Simulasi Distributed Consensus (Raft-like Leader Election & Log Replication)
       serta Virtual Memory Page Replacement (LRU & Page Fault Tracker).

Eksekusi:
    python3 lab_exercise.py
"""

import sys
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ==============================================================================
# ANSI Color Codes & UI Helper
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

def cprint(text: str, color: str = Color.WHITE, bold: bool = False, end: str = "\n"):
    prefix = Color.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Color.RESET}", end=end)

def header(title: str):
    print("\n" + "=" * 68)
    cprint(f"  {title.upper()}", Color.CYAN, bold=True)
    print("=" * 68)

# ==============================================================================
# BAGIAN 1: SIMULASI DISTRIBUTED CONSENSUS (RAFT-LIKE SIMULATOR)
# ==============================================================================
class NodeRole:
    FOLLOWER = "Follower"
    CANDIDATE = "Candidate"
    LEADER = "Leader"

@dataclass
class LogEntry:
    term: int
    index: int
    command: str

@dataclass
class RaftNode:
    node_id: int
    current_term: int = 0
    voted_for: Optional[int] = None
    log: List[LogEntry] = field(default_factory=list)
    role: str = NodeRole.FOLLOWER
    is_alive: bool = True
    votes_received: int = 0

class RaftCluster:
    def __init__(self, node_count: int = 5):
        self.nodes: Dict[int, RaftNode] = {
            i: RaftNode(node_id=i) for i in range(1, node_count + 1)
        }
        self.active_leader: Optional[int] = None

    def display_status(self):
        cprint("\n[Status Klaster Konsensus]", Color.YELLOW, bold=True)
        print(f"{'Node ID':<10} | {'Status':<12} | {'Role':<12} | {'Term':<8} | {'Log Count':<10}")
        print("-" * 62)
        for nid, node in self.nodes.items():
            status_str = f"{Color.GREEN}UP{Color.RESET}" if node.is_alive else f"{Color.RED}DOWN{Color.RESET}"
            role_color = (
                Color.CYAN if node.role == NodeRole.LEADER
                else Color.YELLOW if node.role == NodeRole.CANDIDATE
                else Color.WHITE
            )
            role_str = f"{role_color}{node.role:<12}{Color.RESET}"
            print(f"Node-{nid:<5} | {status_str:<21} | {role_str} | {node.current_term:<8} | {len(node.log):<10}")
        print("-" * 62)

    def trigger_election(self, candidate_id: int):
        candidate = self.nodes.get(candidate_id)
        if not candidate or not candidate.is_alive:
            cprint(f"[!] Node {candidate_id} sedang nonaktif, tidak dapat memulai pemilu.", Color.RED)
            return

        candidate.role = NodeRole.CANDIDATE
        candidate.current_term += 1
        candidate.voted_for = candidate_id
        candidate.votes_received = 1
        
        cprint(f"\n[*] Node-{candidate_id} memicu Pemilihan Pemimpin (Term {candidate.current_term})...", Color.MAGENTA, bold=True)
        time.sleep(0.3)

        quorum = (len(self.nodes) // 2) + 1
        alive_nodes = [n for n in self.nodes.values() if n.is_alive and n.node_id != candidate_id]

        for peer in alive_nodes:
            # Grant vote if peer hasn't voted in this term and term is acceptable
            if peer.voted_for is None or peer.current_term < candidate.current_term:
                peer.current_term = candidate.current_term
                peer.voted_for = candidate_id
                peer.role = NodeRole.FOLLOWER
                candidate.votes_received += 1
                cprint(f"    -> Node-{peer.node_id} memberikan suara ke Node-{candidate_id}", Color.GREEN)
            else:
                cprint(f"    -> Node-{peer.node_id} MENOLAK suara ke Node-{candidate_id}", Color.RED)

        cprint(f"\nHasil Suara: {candidate.votes_received} / {len(self.nodes)} (Quorum minimal: {quorum})", Color.WHITE, bold=True)
        if candidate.votes_received >= quorum:
            candidate.role = NodeRole.LEADER
            self.active_leader = candidate_id
            cprint(f"[+] SUKSES: Node-{candidate_id} resmi menjadi LEADER baru klaster!\n", Color.GREEN, bold=True)
        else:
            candidate.role = NodeRole.FOLLOWER
            candidate.voted_for = None
            cprint(f"[-] GAGAL: Quorum tidak terpenuhi. Node-{candidate_id} kembali menjadi FOLLOWER.\n", Color.YELLOW)

    def replicate_log(self, command: str):
        if not self.active_leader or not self.nodes[self.active_leader].is_alive:
            cprint("[!] Tidak ada Leader aktif! Replikasi instruksi dibatalkan.", Color.RED, bold=True)
            return

        leader = self.nodes[self.active_leader]
        entry = LogEntry(term=leader.current_term, index=len(leader.log) + 1, command=command)
        leader.log.append(entry)
        
        cprint(f"\n[LEADER Node-{leader.node_id}] Menerima Instruksi '{command}' (Index={entry.index}, Term={entry.term})", Color.CYAN, bold=True)
        cprint("    Memulai proses 2-Phase Commit / AppendEntries...", Color.DIM)

        ack_count = 1
        quorum = (len(self.nodes) // 2) + 1

        for peer in self.nodes.values():
            if peer.node_id != leader.node_id and peer.is_alive:
                peer.log.append(entry)
                peer.current_term = leader.current_term
                ack_count += 1
                cprint(f"    [ACK] Node-{peer.node_id} berhasil mereplikasi log index {entry.index}", Color.GREEN)

        if ack_count >= quorum:
            cprint(f"[COMMIT] Instruksi '{command}' telah dikomit secara konsisten oleh mayoritas ({ack_count} nodes).\n", Color.GREEN, bold=True)
        else:
            cprint(f"[ROLLBACK] Gagal mencapai quorum ({ack_count}/{len(self.nodes)}). Log rawan split-brain!\n", Color.RED, bold=True)

    def toggle_node(self, node_id: int):
        node = self.nodes.get(node_id)
        if not node:
            return
        node.is_alive = not node.is_alive
        status = "HIDUP" if node.is_alive else "MATI (CRASHED)"
        color = Color.GREEN if node.is_alive else Color.RED
        cprint(f"[*] Node-{node_id} sekarang {status}", color, bold=True)
        if not node.is_alive and self.active_leader == node_id:
            cprint(f"[!] PERINGATAN: Leader Node-{node_id} mengalami kegagalan/crash!", Color.RED, bold=True)
            node.role = NodeRole.FOLLOWER
            self.active_leader = None

# ==============================================================================
# BAGIAN 2: SIMULASI VIRTUAL MEMORY (PAGE REPLACEMENT LRU)
# ==============================================================================
class VirtualMemoryManager:
    def __init__(self, frame_capacity: int = 3):
        self.capacity = frame_capacity
        self.frames: List[int] = []
        self.access_order: List[int] = []
        self.page_faults = 0
        self.hits = 0

    def access_page(self, page_id: int) -> Tuple[bool, Optional[int]]:
        """
        Mengakses halaman memori.
        Return: (is_page_fault, evicted_page)
        """
        if page_id in self.frames:
            self.hits += 1
            # Perbarui posisi di LRU history
            self.access_order.remove(page_id)
            self.access_order.append(page_id)
            return (False, None)

        # Page Fault terjadi
        self.page_faults += 1
        evicted = None

        if len(self.frames) >= self.capacity:
            # Ambil halaman yang paling lama tidak digunakan (LRU)
            evicted = self.access_order.pop(0)
            self.frames.remove(evicted)

        self.frames.append(page_id)
        self.access_order.append(page_id)
        return (True, evicted)

    def run_trace(self, reference_string: List[int]):
        cprint("\n[Simulasi Paging Memori Virtual - Algoritma LRU]", Color.YELLOW, bold=True)
        cprint(f"Kapasitas Bingkai Fisik (RAM Frames): {self.capacity}", Color.CYAN)
        cprint(f"Rentetan Alamat Referensi (Page Sequence): {reference_string}\n", Color.DIM)

        print(f"{'Page Ref':<10} | {'Status':<14} | {'Isi Frame RAM':<20} | {'Evicted'}")
        print("-" * 60)

        for page in reference_string:
            is_fault, evicted = self.access_page(page)
            if is_fault:
                status_str = f"{Color.RED}PAGE FAULT{Color.RESET}"
                evicted_str = f"Page {evicted}" if evicted is not None else "-"
            else:
                status_str = f"{Color.GREEN}CACHE HIT{Color.RESET}  "
                evicted_str = "-"

            frames_str = f"[{', '.join(str(f) for f in self.frames)}]"
            print(f"{page:<10} | {status_str:<23} | {frames_str:<20} | {evicted_str}")
            time.sleep(0.15)

        print("-" * 60)
        total = self.page_faults + self.hits
        hit_ratio = (self.hits / total * 100) if total > 0 else 0
        cprint(f"Total Akses: {total} | Fault: {self.page_faults} | Hit: {self.hits} | Hit Ratio: {hit_ratio:.1f}%\n", Color.WHITE, bold=True)

# ==============================================================================
# MENU UTAMA & RUNNER INTERAKTIF
# ==============================================================================
def run_interactive_lab():
    cluster = RaftCluster(node_count=5)
    
    while True:
        header("Sistem Laboratorium Terpadu: Computer Science Lanjutan")
        print(" 1. [Konsensus] Tampilkan Status Klaster Node")
        print(" 2. [Konsensus] Picu Pemilihan Leader (Election)")
        print(" 3. [Konsensus] Replikasi Data Log ke Klaster")
        print(" 4. [Konsensus] Simulasi Kerusakan / Pemulihan Node (Crash / Recover)")
        print(" 5. [Memori]    Jalankan Simulasi Virtual Memory LRU Paging")
        print(" 6. [Batch]     Jalankan Seluruh Test Otomatis")
        print(" 0. Keluar")
        print("-" * 68)

        choice = input(f"{Color.BOLD}Pilih menu (0-6): {Color.RESET}").strip()

        if choice == "1":
            cluster.display_status()
        elif choice == "2":
            cluster.display_status()
            try:
                nid = int(input(f"Pilih ID Node kandidat (1-5): ").strip())
                cluster.trigger_election(nid)
            except ValueError:
                cprint("[!] Masukkan ID angka yang valid.", Color.RED)
        elif choice == "3":
            cmd = input("Masukkan perintah log (misal: 'SET x=42'): ").strip()
            if cmd:
                cluster.replicate_log(cmd)
            else:
                cprint("[!] Perintah tidak boleh kosong.", Color.RED)
        elif choice == "4":
            try:
                nid = int(input("Pilih ID Node untuk toggle UP/DOWN (1-5): ").strip())
                cluster.toggle_node(nid)
            except ValueError:
                cprint("[!] Masukkan ID angka yang valid.", Color.RED)
        elif choice == "5":
            vmm = VirtualMemoryManager(frame_capacity=3)
            default_trace = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1]
            custom = input(f"Gunakan reference string default ({default_trace})? [Y/n]: ").strip().lower()
            if custom == 'n':
                raw = input("Masukkan nomor page dipisahkan spasi (cth: 1 2 3 4 1 2): ").strip()
                trace = [int(x) for x in raw.split() if x.isdigit()]
            else:
                trace = default_trace
            vmm.run_trace(trace)
        elif choice == "6":
            run_automated_verification()
        elif choice == "0":
            cprint("\nTerima kasih telah menyelesaikan modul laboratorium lanjutan!\n", Color.GREEN, bold=True)
            break
        else:
            cprint("[!] Pilihan tidak dikenali.", Color.RED)

def run_automated_verification():
    header("Verifikasi Otomatis: Algoritma Konsensus & Memori")
    cprint("[*] 1. Pengujian Pemilihan Leader Raft...", Color.CYAN)
    cluster = RaftCluster(5)
    cluster.trigger_election(1)
    assert cluster.active_leader == 1, "Leader harus terdaftar di node 1"
    assert cluster.nodes[1].role == NodeRole.LEADER

    cprint("[*] 2. Pengujian Replikasi Konsisten Quorum...", Color.CYAN)
    cluster.replicate_log("TX_INIT_STATE")
    assert len(cluster.nodes[1].log) == 1
    assert cluster.nodes[2].log[0].command == "TX_INIT_STATE"

    cprint("[*] 3. Pengujian Toleransi Partisi Jaringan...", Color.CYAN)
    cluster.toggle_node(1) # Kill leader
    assert cluster.active_leader is None
    cluster.trigger_election(2) # Node 2 becomes leader
    assert cluster.active_leader == 2

    cprint("[*] 4. Pengujian LRU Cache Eviction...", Color.CYAN)
    vmm = VirtualMemoryManager(frame_capacity=3)
    # [1, 2, 3] -> page 4 triggers eviction of 1
    vmm.access_page(1)
    vmm.access_page(2)
    vmm.access_page(3)
    is_fault, evicted = vmm.access_page(4)
    assert is_fault is True
    assert evicted == 1
    assert vmm.frames == [2, 3, 4]

    cprint("\n[V] SEMUA UJI VERIFIKASI BERHASIL 100% LOLOS!\n", Color.GREEN, bold=True)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_automated_verification()
    else:
        run_interactive_lab()
