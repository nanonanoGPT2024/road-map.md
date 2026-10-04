#!/usr/bin/env python3
"""
BAB-05 Materi Lanjutan: Computer Science Interactive Laboratory
Topik Fondasi Inti:
1. Distributed Systems: Lamport Logical Clocks & Causality
2. Consensus Protocol: Raft Leader Election & Heartbeat Simulation
3. Memory Architecture: MESI Cache Coherence Protocol Simulator
"""

import sys
import time
import random
from typing import Dict, List, Tuple

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{YELLOW} [CS LAB] {title.center(56)} {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}\n")

def pause_step(prompt: str = "Tekan [Enter] untuk melanjutkan...") -> None:
    try:
        input(f"{DIM}{prompt}{RESET}")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{YELLOW}Kembali ke menu utama.{RESET}")

# ------------------------------------------------------------------------------
# 1. Lamport Logical Clocks & Vector Clocks
# ------------------------------------------------------------------------------
class LamportProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.clock = 0

    def local_event(self) -> int:
        self.clock += 1
        return self.clock

    def send_message(self) -> int:
        self.clock += 1
        return self.clock

    def receive_message(self, sent_clock: int) -> int:
        self.clock = max(self.clock, sent_clock) + 1
        return self.clock

def run_lamport_simulation() -> None:
    print_header("Simulasi Lamport Logical Clocks (Kausalitas Terdistribusi)")
    print(f"{WHITE}Dalam sistem terdistribusi tanpa shared clock fisik,")
    print(f"Lamport Clock memastikan urutan 'happens-before' (->).{RESET}\n")

    nodes = [LamportProcess(i) for i in range(3)]
    for i, n in enumerate(nodes):
        print(f"  {BLUE}Node {i}{RESET}: Clock awal = {n.clock}")

    print(f"\n{BOLD}Skenario Eksekusi Event Terdistribusi:{RESET}")
    events = [
        ("local", 0, "Komputasi data lokal"),
        ("send", 0, 1, "Mengirim sync message ke Node 1"),
        ("local", 2, "Logging log transaksi independen"),
        ("send", 1, 2, "Mengirim update state ke Node 2"),
        ("local", 1, "Garbage collection internal"),
    ]

    for step, event in enumerate(events, 1):
        time.sleep(0.3)
        if event[0] == "local":
            _, node_id, desc = event
            clk = nodes[node_id].local_event()
            print(f"  [{step}] {GREEN}EVENT LOKAL{RESET} di Node {node_id}: {desc}")
            print(f"      -> Clock Node {node_id} sekarang: {BOLD}{clk}{RESET}")
        elif event[0] == "send":
            _, src, dst, desc = event
            sent_clk = nodes[src].send_message()
            print(f"  [{step}] {YELLOW}KIRIM PESAN{RESET} (Node {src} -> Node {dst}): {desc}")
            print(f"      -> Node {src} send clock: {sent_clk}")
            recv_clk = nodes[dst].receive_message(sent_clk)
            print(f"      -> Node {dst} menerima pesan, update clock: max({nodes[dst].clock - 1}, {sent_clk}) + 1 = {BOLD}{recv_clk}{RESET}")

    print(f"\n{BOLD}Status Akhir Clock Lamport:{RESET}")
    for n in nodes:
        print(f"  Node {n.pid}: Clock = {BOLD}{GREEN}{n.clock}{RESET}")
    print(f"\n{DIM}Prinsip: a -> b mengimplikasikan C(a) < C(b).{RESET}\n")
    pause_step()

# ------------------------------------------------------------------------------
# 2. Raft Consensus Simulator (Leader Election)
# ------------------------------------------------------------------------------
class RaftNode:
    FOLLOWER = "Follower"
    CANDIDATE = "Candidate"
    LEADER = "Leader"

    def __init__(self, node_id: int):
        self.node_id = node_id
        self.role = self.FOLLOWER
        self.term = 0
        self.voted_for = None
        self.alive = True

def run_raft_simulation() -> None:
    print_header("Simulasi Raft Consensus (Leader Election & Heartbeat)")
    nodes = [RaftNode(i) for i in range(5)]
    current_term = 1

    print(f"{WHITE}Inisialisasi Cluster 5 Nodes (Quorum = 3):{RESET}")
    for n in nodes:
        print(f"  Node {n.node_id}: {CYAN}{n.role}{RESET} (Term: {n.term})")

    print(f"\n{YELLOW}[1] Follower Node 0 mendeteksi Election Timeout!{RESET}")
    candidate = nodes[0]
    candidate.role = RaftNode.CANDIDATE
    candidate.term = current_term
    candidate.voted_for = candidate.node_id
    votes = 1
    print(f"  Node {candidate.node_id} menjadi {BOLD}{MAGENTA}CANDIDATE{RESET} (Term {candidate.term}).")
    print(f"  Node {candidate.node_id} memberi vote untuk dirinya sendiri (Votes: {votes}/5).")

    print(f"\n{YELLOW}[2] Mengirim RequestVote RPC ke peers...{RESET}")
    for peer in nodes[1:]:
        time.sleep(0.2)
        if peer.alive and peer.voted_for is None:
            peer.voted_for = candidate.node_id
            peer.term = candidate.term
            votes += 1
            print(f"  Peers Node {peer.node_id}: {GREEN}Granted Vote{RESET} ke Node {candidate.node_id}")

    print(f"\n{BOLD}Hasil Perhitungan Vote: {votes}/5{RESET}")
    if votes >= 3:
        candidate.role = RaftNode.LEADER
        print(f"  {BOLD}{GREEN}MAJORITAS TERCAPAI (>= 3)! Node {candidate.node_id} resmi menjadi LEADER.{RESET}")
    
    print(f"\n{YELLOW}[3] Leader Node {candidate.node_id} mengirim Heartbeat (AppendEntries)...{RESET}")
    for peer in nodes[1:]:
        print(f"  -> Heartbeat diterima oleh Node {peer.node_id} (Role: {peer.role}, Term: {peer.term})")

    print(f"\n{RED}[4] Skenario Partisi Jaringan: Node {candidate.node_id} (Leader) mengalami CRASH!{RESET}")
    candidate.alive = False
    print(f"  Node {candidate.node_id} Down.")
    time.sleep(0.3)
    
    new_candidate = nodes[2]
    new_term = current_term + 1
    new_candidate.role = RaftNode.CANDIDATE
    new_candidate.term = new_term
    new_candidate.voted_for = new_candidate.node_id
    new_votes = 1
    print(f"  Node {new_candidate.node_id} mendeteksi missing heartbeat, memulai election Term {new_term}.")

    for peer in [nodes[1], nodes[3], nodes[4]]:
        peer.voted_for = new_candidate.node_id
        peer.term = new_term
        new_votes += 1
    
    print(f"  Node {new_candidate.node_id} mendapatkan {new_votes} vote dari node aktif.")
    new_candidate.role = RaftNode.LEADER
    print(f"  {BOLD}{GREEN}Node {new_candidate.node_id} terpilih sebagai NEW LEADER (Term {new_term}).{RESET}\n")
    pause_step()

# ------------------------------------------------------------------------------
# 3. MESI Cache Coherence Protocol Simulator
# ------------------------------------------------------------------------------
class MESICacheLine:
    # Status MESI
    MODIFIED = "Modified (M)"
    EXCLUSIVE = "Exclusive (E)"
    SHARED = "Shared (S)"
    INVALID = "Invalid (I)"

    def __init__(self, core_id: int):
        self.core_id = core_id
        self.state = self.INVALID
        self.data = None

def run_mesi_simulation() -> None:
    print_header("Simulasi MESI Cache Coherence (Multi-Core Snooping)")
    print(f"{WHITE}MESI Protocol menjaga konsistensi L1/L2 cache antar Core:")
    print(f"  - {BOLD}M{RESET}: Dirty, hanya di core ini, berbeda dari RAM")
    print(f"  - {BOLD}E{RESET}: Clean, hanya di core ini, sama dengan RAM")
    print(f"  - {BOLD}S{RESET}: Clean, direplikasi di multi-core, sama dengan RAM")
    print(f"  - {BOLD}I{RESET}: Data usang/invalid{RESET}\n")

    cores = [MESICacheLine(i) for i in range(4)]
    address_x_val = 100

    def print_cores():
        status_line = " | ".join([f"Core {c.core_id}: {MAGENTA if 'M' in c.state else (GREEN if 'E' in c.state else (CYAN if 'S' in c.state else RED))}{c.state}{RESET} (Val={c.data})" for c in cores])
        print(f"  {status_line}")

    print(f"{BOLD}Kondisi Awal:{RESET}")
    print_cores()

    print(f"\n{YELLOW}[Langkah 1] Core 0 melakukan READ pada Addr(X):{RESET}")
    cores[0].state = MESICacheLine.EXCLUSIVE
    cores[0].data = address_x_val
    print("  -> BusRd dikirim. Tidak ada core lain yang punya data. State Core 0 = EXCLUSIVE")
    print_cores()

    print(f"\n{YELLOW}[Langkah 2] Core 1 melakukan READ pada Addr(X):{RESET}")
    cores[0].state = MESICacheLine.SHARED
    cores[1].state = MESICacheLine.SHARED
    cores[1].data = address_x_val
    print("  -> BusRd didengar oleh Core 0. Data di-share. State Core 0 & Core 1 = SHARED")
    print_cores()

    print(f"\n{YELLOW}[Langkah 3] Core 1 melakukan WRITE pada Addr(X) (Nilai baru = 250):{RESET}")
    cores[1].data = 250
    cores[1].state = MESICacheLine.MODIFIED
    cores[0].state = MESICacheLine.INVALID
    cores[0].data = None
    print("  -> BusUpd / Invalidation signal dikirim oleh Core 1.")
    print("  -> Core 0 meng-invalidasi cache line-nya! State Core 1 = MODIFIED, Core 0 = INVALID")
    print_cores()

    print(f"\n{YELLOW}[Langkah 4] Core 2 membaca Addr(X):{RESET}")
    print("  -> Core 1 mendeteksi Read Miss dari Core 2, melakukan Flush data 250 ke Main Memory & Core 2.")
    cores[1].state = MESICacheLine.SHARED
    cores[2].state = MESICacheLine.SHARED
    cores[2].data = 250
    print_cores()

    print(f"\n{GREEN}Konsistensi memori berhasil dipertahankan tanpa data race!{RESET}\n")
    pause_step()

# ------------------------------------------------------------------------------
# Main Interactive Menu
# ------------------------------------------------------------------------------
def main():
    while True:
        print_header("LAB KOMPUTASI LANJUTAN (BAB-05 Computer Science)")
        print(f"{WHITE}Pilih simulasi konsep arsitektur & komputasi lanjutan:{RESET}\n")
        print(f"  {BOLD}1.{RESET} {CYAN}Lamport Logical Clocks{RESET} (Distributed Event Ordering)")
        print(f"  {BOLD}2.{RESET} {YELLOW}Raft Consensus Algorithm{RESET} (Leader Election & Failure)")
        print(f"  {BOLD}3.{RESET} {MAGENTA}MESI Cache Coherence Protocol{RESET} (Multi-core Hardware)")
        print(f"  {BOLD}4.{RESET} {GREEN}Jalankan Semua Simulasi Secara Berurutan{RESET}")
        print(f"  {BOLD}0.{RESET} {RED}Keluar dari Lab{RESET}\n")

        try:
            choice = input(f"{BOLD}Masukkan opsi [0-4]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan oleh user.{RESET}")
            break

        if choice == "1":
            run_lamport_simulation()
        elif choice == "2":
            run_raft_simulation()
        elif choice == "3":
            run_mesi_simulation()
        elif choice == "4":
            run_lamport_simulation()
            run_raft_simulation()
            run_mesi_simulation()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah bereksperimen di Hands-on Lab BAB-05!{RESET}\n")
            break
        else:
            print(f"{RED}Opsi tidak valid, silakan coba lagi.{RESET}\n")
            time.sleep(0.5)

if __name__ == "__main__":
    main()
