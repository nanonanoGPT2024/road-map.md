#!/usr/bin/env python3
"""
Lab Exercise: Hands-On Computer Science (BAB 07 - Materi Lanjutan)
Topik: Simulasi Konsensus Terdistribusi & Replikasi Log (Raft Consensus Algorithm)

Modul ini mensimulasikan konsep tingkat lanjut Computer Science:
1. Distributed Systems & Consensus Problem (CAP Theorem, Split-Brain mitigation)
2. State Machine Replication (SMR)
3. Leader Election, Term epoch, and Quorum Voting
4. Heartbeat propagation & Fault Detection
"""

import sys
import time
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# --- ANSI Terminal Color Palette ---
class Colors:
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
    BG_BLUE = "\033[44m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


class NodeRole(Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"


@dataclass
class LogEntry:
    term: int
    index: int
    command: str
    committed: bool = False


@dataclass
class RaftNode:
    node_id: int
    role: NodeRole = NodeRole.FOLLOWER
    current_term: int = 0
    voted_for: Optional[int] = None
    log: List[LogEntry] = field(default_factory=list)
    commit_index: int = 0
    is_alive: bool = True
    votes_received: int = 0

    def reset_election_timeout(self):
        # Timeout random untuk mencegah split-vote berulang (Raft spec)
        self.election_timeout = random.uniform(1.5, 3.0)
        self.last_heartbeat = time.time()

    def __post_init__(self):
        self.reset_election_timeout()


class RaftClusterSimulator:
    def __init__(self, cluster_size: int = 5):
        self.cluster_size = cluster_size
        self.nodes: Dict[int, RaftNode] = {
            i: RaftNode(node_id=i) for i in range(1, cluster_size + 1)
        }
        self.quorum = (cluster_size // 2) + 1
        self.current_leader: Optional[int] = None

    def print_banner(self):
        print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")
        print(f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}   SIMULATOR KONSENSUS DISTRIBUSI (RAFT ALGORITHM) - ADVANCED CS     {Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")
        print(f"{Colors.DIM}Node Aktif: {self.cluster_size} Node | Quorum Minimal: {self.quorum} Node{Colors.RESET}\n")

    def display_cluster_state(self):
        print(f"\n{Colors.BOLD}{Colors.WHITE}--- STATUS KLASTER (Term Snapshot) ---{Colors.RESET}")
        header = f"{'Node ID':<10} | {'Status':<12} | {'Role':<12} | {'Term':<6} | {'Commit Idx':<10} | {'Log Count':<10}"
        print(f"{Colors.DIM}{'-' * len(header)}{Colors.RESET}")
        print(f"{Colors.BOLD}{header}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * len(header)}{Colors.RESET}")

        for node_id, node in self.nodes.items():
            status_str = f"{Colors.GREEN}ALIVE{Colors.RESET}" if node.is_alive else f"{Colors.RED}OFFLINE{Colors.RESET}"
            
            if node.role == NodeRole.LEADER:
                role_str = f"{Colors.MAGENTA}{Colors.BOLD}{node.role.value}{Colors.RESET}"
            elif node.role == NodeRole.CANDIDATE:
                role_str = f"{Colors.YELLOW}{node.role.value}{Colors.RESET}"
            else:
                role_str = f"{Colors.CYAN}{node.role.value}{Colors.RESET}"

            row = (
                f"Node-{node.node_id:<5} | "
                f"{status_str:<21} | "
                f"{role_str:<21} | "
                f"{node.current_term:<6} | "
                f"{node.commit_index:<10} | "
                f"{len(node.log):<10}"
            )
            print(row)
        print(f"{Colors.DIM}{'-' * len(header)}{Colors.RESET}\n")

    def run_election(self, candidate_id: int):
        candidate = self.nodes[candidate_id]
        if not candidate.is_alive:
            print(f"{Colors.RED}[!] Node-{candidate_id} sedang OFFLINE, tidak bisa memulai pemilihan.{Colors.RESET}")
            return

        candidate.role = NodeRole.CANDIDATE
        candidate.current_term += 1
        candidate.voted_for = candidate_id
        candidate.votes_received = 1  # Memilih dirinya sendiri

        print(f"{Colors.YELLOW}[*] Node-{candidate_id} memulai Pemilihan (Election) untuk Term {candidate.current_term}!{Colors.RESET}")
        time.sleep(0.4)

        # Request Vote ke semua peer yang hidup
        for node_id, peer in self.nodes.items():
            if node_id == candidate_id or not peer.is_alive:
                continue

            # Logika konsensus Raft: update term jika calon memiliki term lebih tinggi
            if candidate.current_term > peer.current_term:
                peer.current_term = candidate.current_term
                peer.role = NodeRole.FOLLOWER
                peer.voted_for = None

            # Vote diberikan jika belum memilih di term ini atau memilih calon yang sama
            if peer.voted_for is None or peer.voted_for == candidate_id:
                peer.voted_for = candidate_id
                candidate.votes_received += 1
                print(f"    -> Node-{peer.node_id} memberikan {Colors.GREEN}VOTE (+1){Colors.RESET} untuk Node-{candidate_id}")
            else:
                print(f"    -> Node-{peer.node_id} {Colors.RED}MENOLAK{Colors.RESET} vote untuk Node-{candidate_id}")

        print(f"\n{Colors.BOLD}Hasil Voting:{Colors.RESET} Diperoleh {candidate.votes_received}/{self.cluster_size} suara (Quorum: {self.quorum})")
        
        if candidate.votes_received >= self.quorum:
            candidate.role = NodeRole.LEADER
            self.current_leader = candidate_id
            print(f"{Colors.BG_GREEN}{Colors.WHITE}{Colors.BOLD} [SUCCESS] Node-{candidate_id} terpilih sebagai LEADER baru untuk Term {candidate.current_term}! {Colors.RESET}\n")
            
            # Leader baru mengirim heartbeat instan
            self.broadcast_heartbeat()
        else:
            candidate.role = NodeRole.FOLLOWER
            print(f"{Colors.YELLOW}[!] Quorum tidak tercapai. Pemilihan gagal, Node-{candidate_id} kembali jadi FOLLOWER.{Colors.RESET}\n")

    def broadcast_heartbeat(self):
        if self.current_leader is None or not self.nodes[self.current_leader].is_alive:
            print(f"{Colors.RED}[!] Tidak ada Leader aktif untuk memancarkan heartbeat.{Colors.RESET}")
            return

        leader = self.nodes[self.current_leader]
        print(f"{Colors.MAGENTA}[HEARTBEAT]{Colors.RESET} Leader (Node-{leader.node_id}) menyiarkan denyut periodik (AppendEntries)...")

        for node_id, peer in self.nodes.items():
            if node_id != leader.node_id and peer.is_alive:
                peer.role = NodeRole.FOLLOWER
                peer.current_term = leader.current_term
                peer.reset_election_timeout()
        print(f"    -> Seluruh follower yang hidup mengakui otoritas Leader.")

    def client_replicate_command(self, command: str):
        if self.current_leader is None or not self.nodes[self.current_leader].is_alive:
            print(f"{Colors.RED}[ERROR] Klien gagal mengirim transaksi! Tidak ada Leader yang memimpin.{Colors.RESET}")
            return

        leader = self.nodes[self.current_leader]
        new_index = len(leader.log) + 1
        entry = LogEntry(term=leader.current_term, index=new_index, command=command)
        leader.log.append(entry)

        print(f"\n{Colors.CYAN}[CLIENT REQUEST]{Colors.RESET} Klien mengirim perintah '{Colors.BOLD}{command}{Colors.RESET}' ke Leader (Node-{leader.node_id})")
        print(f"[*] Leader mencatat ke uncommitted log [Index: {new_index}, Term: {entry.term}]")
        time.sleep(0.3)

        # Replikasi ke followers
        replicated_count = 1  # Leader itu sendiri
        for node_id, peer in self.nodes.items():
            if node_id == leader.node_id or not peer.is_alive:
                continue
            peer_entry = LogEntry(term=entry.term, index=entry.index, command=entry.command)
            peer.log.append(peer_entry)
            replicated_count += 1
            print(f"    -> Log direplikasi ke Node-{node_id}")

        print(f"[*] Replikasi berhasil pada {replicated_count}/{self.cluster_size} node.")

        # Komitmen jika quorum terpenuhi
        if replicated_count >= self.quorum:
            entry.committed = True
            leader.commit_index = new_index
            for node in self.nodes.values():
                if node.is_alive and len(node.log) >= new_index:
                    node.log[new_index - 1].committed = True
                    node.commit_index = new_index
            print(f"{Colors.GREEN}{Colors.BOLD}[COMMITTED]{Colors.RESET} Perintah '{command}' telah dikomit secara permanen ke State Machine!")
        else:
            print(f"{Colors.RED}[FAILED]{Colors.RESET} Gagal mencapai Quorum. Log belum dikomit (Split-Brain safe).")

    def toggle_node_partition(self, node_id: int):
        if node_id not in self.nodes:
            print(f"{Colors.RED}[!] Node ID tidak valid.{Colors.RESET}")
            return

        node = self.nodes[node_id]
        node.is_alive = not node.is_alive
        status = "HIDUP" if node.is_alive else "MATI / TERISOLASI"
        print(f"\n{Colors.YELLOW}[NETWORK PARTITION] Node-{node_id} sekarang {status}.{Colors.RESET}")

        if not node.is_alive and self.current_leader == node_id:
            print(f"{Colors.BG_RED}{Colors.WHITE} [ALERT] LEADER CRASHED! Kluster kehilangan pemimpin! {Colors.RESET}")
            self.current_leader = None

    def trigger_auto_demo(self):
        print(f"\n{Colors.BOLD}{Colors.WHITE}=== MEMULAI SKENARIO OTOMATIS: LEADER ELECTION & REPLIKASI ==={Colors.RESET}")
        time.sleep(0.5)
        
        # 1. Election
        self.run_election(candidate_id=1)
        self.display_cluster_state()
        time.sleep(1)

        # 2. Append Entries
        self.client_replicate_command("SET user:101 = 'Alice'")
        self.client_replicate_command("SET balance:101 = 500000")
        self.display_cluster_state()
        time.sleep(1)

        # 3. Leader Crash Simulation
        print(f"\n{Colors.YELLOW}--- Simulasi Kegagalan Jaringan: Crash Leader (Node-1) ---{Colors.RESET}")
        self.toggle_node_partition(1)
        self.display_cluster_state()
        time.sleep(1)

        # 4. Failover Election
        print(f"{Colors.CYAN}--- Failover Otomatis: Node-2 Mendeteksi Heartbeat Timeout ---{Colors.RESET}")
        self.run_election(candidate_id=2)
        self.client_replicate_command("SET user:102 = 'Bob'")
        self.display_cluster_state()

        print(f"{Colors.GREEN}{Colors.BOLD}[DEMO SELESAI] Konsep Konsensus & Fault Tolerance Berhasil Diuji.{Colors.RESET}\n")


def interactive_menu():
    sim = RaftClusterSimulator(cluster_size=5)
    sim.print_banner()

    while True:
        print(f"{Colors.BOLD}Menu Eksperimen:{Colors.RESET}")
        print("1. Tampilkan Status Kluster & Log")
        print("2. Picu Pemilihan Pemimpin (Trigger Election)")
        print("3. Kirim Transaksi Klien (Replicate Command)")
        print("4. Kirim Heartbeat Leader")
        print("5. Simulasi Gangguan Node (Kill/Recover Node)")
        print("6. Jalankan Full Demo Otomatis (Failover & Log Replication)")
        print("0. Keluar")

        try:
            choice = input(f"\n{Colors.CYAN}Pilih opsi [0-6]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            sim.display_cluster_state()
        elif choice == "2":
            try:
                c_id = int(input("Masukkan Node ID yang menjadi kandidat (1-5): "))
                sim.run_election(c_id)
            except ValueError:
                print(f"{Colors.RED}[!] Input harus angka numerik.{Colors.RESET}")
        elif choice == "3":
            cmd = input("Masukkan perintah state machine (contoh: SET saldo = 100): ").strip()
            if cmd:
                sim.client_replicate_command(cmd)
        elif choice == "4":
            sim.broadcast_heartbeat()
        elif choice == "5":
            try:
                n_id = int(input("Masukkan Node ID yang ingin di-toggle statusnya (1-5): "))
                sim.toggle_node_partition(n_id)
            except ValueError:
                print(f"{Colors.RED}[!] Input harus angka numerik.{Colors.RESET}")
        elif choice == "6":
            sim.trigger_auto_demo()
        elif choice == "0":
            print(f"{Colors.GREEN}Simulator selesai. Terima kasih.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}[!] Pilihan tidak dikenali.{Colors.RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan argumen '--demo', langsung jalankan skenario tanpa menunggu input
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        simulator = RaftClusterSimulator(cluster_size=5)
        simulator.print_banner()
        simulator.trigger_auto_demo()
    else:
        interactive_menu()
