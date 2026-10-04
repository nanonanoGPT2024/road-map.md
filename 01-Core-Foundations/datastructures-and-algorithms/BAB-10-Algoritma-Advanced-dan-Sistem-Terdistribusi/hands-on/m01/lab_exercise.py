#!/usr/bin/env python3
"""
Lab Exercise M01: Algoritma Advanced & Fondasi Sistem Terdistribusi
BAB 10: Algoritma Advanced dan Sistem Terdistribusi

Topik Simulasi Interaktif:
 1. Consistent Hashing Ring (dengan Virtual Nodes & Partisi Data)
 2. Vector Clocks (Deteksi Kausalitas & Konkurensi Distributed Events)
 3. Simulasi Konsensus 2-Phase Commit (2PC) Distributed Transaction

Standar: Python 3 Runnable, Zero-dependency eksternal, ANSI color terminal output.
"""

import hashlib
import bisect
import time
import sys
from typing import Dict, List, Tuple, Optional

# --- ANSI Color Codes ---
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
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE}  === {title.upper()} ===  {RESET}\n")


def print_success(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{RESET}")


def print_info(msg: str) -> None:
    print(f"{CYAN}ℹ {msg}{RESET}")


def print_warn(msg: str) -> None:
    print(f"{YELLOW}⚠ {msg}{RESET}")


def print_error(msg: str) -> None:
    print(f"{RED}✗ {msg}{RESET}")


# =====================================================================
# 1. CONSISTENT HASHING RING DENGAN VIRTUAL NODES
# =====================================================================

class ConsistentHashRing:
    """
    Implementasi Consistent Hash Ring dengan virtual nodes untuk
    distribusi beban merata dan minimalisasi data migration saat re-sharding.
    """
    def __init__(self, virtual_replicas: int = 3):
        self.virtual_replicas = virtual_replicas
        self.ring: List[int] = []  # Sorted list of hash tokens
        self.ring_map: Dict[int, str] = {}  # token -> physical node_id
        self.nodes: set = set()

    def _hash(self, key: str) -> int:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)  # Gunakan 32-bit hex untuk ring sederhana

    def add_node(self, node_id: str) -> None:
        if node_id in self.nodes:
            return
        self.nodes.add(node_id)
        for i in range(self.virtual_replicas):
            vnode_key = f"{node_id}#vnode-{i}"
            token = self._hash(vnode_key)
            idx = bisect.bisect(self.ring, token)
            self.ring.insert(idx, token)
            self.ring_map[token] = node_id

    def remove_node(self, node_id: str) -> None:
        if node_id not in self.nodes:
            return
        self.nodes.remove(node_id)
        tokens_to_remove = []
        for i in range(self.virtual_replicas):
            vnode_key = f"{node_id}#vnode-{i}"
            token = self._hash(vnode_key)
            tokens_to_remove.append(token)
        for token in tokens_to_remove:
            idx = bisect.bisect_left(self.ring, token)
            if idx < len(self.ring) and self.ring[idx] == token:
                del self.ring[idx]
            self.ring_map.pop(token, None)

    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None
        token = self._hash(key)
        idx = bisect.bisect(self.ring, token)
        if idx == len(self.ring):
            idx = 0  # Wrap around the ring
        return self.ring_map[self.ring[idx]]

    def get_distribution(self, keys: List[str]) -> Dict[str, List[str]]:
        dist: Dict[str, List[str]] = {node: [] for node in self.nodes}
        for k in keys:
            target = self.get_node(k)
            if target:
                dist[target].append(k)
        return dist


def demo_consistent_hashing() -> None:
    header("Simulasi Consistent Hashing Ring")
    ring = ConsistentHashRing(virtual_replicas=4)
    initial_nodes = ["storage-node-A", "storage-node-B", "storage-node-C"]
    for n in initial_nodes:
        ring.add_node(n)
        print_info(f"Node fisik ditambahkan: {BOLD}{n}{RESET} (4 virtual tokens)")

    sample_keys = [
        "user:101:profile", "user:202:settings", "session:abc889",
        "order:99201", "invoice:4401", "cart:user_771",
        "cache:home_feed", "product:sku_9019", "image:thumb_552"
    ]

    print(f"\n{BOLD}{YELLOW}Distribusi Kunci Awal (3 Nodes):{RESET}")
    dist1 = ring.get_distribution(sample_keys)
    for node, keys in dist1.items():
        print(f"  {MAGENTA}● {node:<18}{RESET} -> {GREEN}{len(keys):>2} keys{RESET}: {keys}")

    print(f"\n{BOLD}{CYAN}>> Melakukan Scale-Out: Menambahkan 'storage-node-D'...{RESET}")
    ring.add_node("storage-node-D")

    dist2 = ring.get_distribution(sample_keys)
    print(f"\n{BOLD}{YELLOW}Distribusi Kunci Setelah Penambahan Node-D:{RESET}")
    migrated_count = 0
    for k in sample_keys:
        old_node = next(n for n, keys in dist1.items() if k in keys)
        new_node = ring.get_node(k)
        if old_node != new_node:
            migrated_count += 1
            print(f"  {YELLOW}MIGRASI:{RESET} Key '{k}' berpindah dari [{old_node}] -> [{GREEN}{new_node}{RESET}]")
        else:
            print(f"  {DIM}STABIL :{RESET} Key '{k}' tetap di [{old_node}]")

    print(f"\n{BOLD}Total kunci:{RESET} {len(sample_keys)} | {BOLD}Kunci yang berpindah:{RESET} {migrated_count} "
          f"({(migrated_count / len(sample_keys)) * 100:.1f}%)")
    print_success("Consistent Hashing membatasi migrasi data hanya ke node baru tanpa rehashing total!")


# =====================================================================
# 2. VECTOR CLOCKS (LOGICAL CLOCK & EVENT ORDERING)
# =====================================================================

class VectorClock:
    """
    Vector Clock melacak kausalitas dalam sistem terdistribusi tanpa shared clock fisik.
    """
    def __init__(self, node_id: str, all_nodes: List[str]):
        self.node_id = node_id
        self.clock: Dict[str, int] = {n: 0 for n in all_nodes}

    def tick(self) -> None:
        self.clock[self.node_id] += 1

    def send_event(self) -> Dict[str, int]:
        self.tick()
        return dict(self.clock)

    def receive_event(self, remote_clock: Dict[str, int]) -> None:
        self.tick()
        for node, time_val in remote_clock.items():
            self.clock[node] = max(self.clock.get(node, 0), time_val)

    @staticmethod
    def compare(vc1: Dict[str, int], vc2: Dict[str, int]) -> str:
        """
        Mengembalikan hubungan:
        'HAPPENED_BEFORE' (vc1 -> vc2),
        'HAPPENED_AFTER' (vc2 -> vc1),
        'IDENTICAL', atau
        'CONCURRENT' (konflik / parallel)
        """
        le = all(vc1.get(k, 0) <= vc2.get(k, 0) for k in set(vc1) | set(vc2))
        ge = all(vc1.get(k, 0) >= vc2.get(k, 0) for k in set(vc1) | set(vc2))

        if le and ge:
            return "IDENTICAL"
        if le:
            return "HAPPENED_BEFORE (vc1 -> vc2)"
        if ge:
            return "HAPPENED_AFTER (vc2 -> vc1)"
        return "CONCURRENT (Conflict/Split-Brain)"


def demo_vector_clocks() -> None:
    header("Simulasi Vector Clocks & Deteksi Kausalitas")
    nodes = ["NodeA", "NodeB", "NodeC"]
    vc_a = VectorClock("NodeA", nodes)
    vc_b = VectorClock("NodeB", nodes)
    vc_c = VectorClock("NodeC", nodes)

    print_info("State Awal: Semua vector clock = [0, 0, 0]")

    print(f"\n{BOLD}Langkah 1:{RESET} NodeA melakukan local event (misal write database)")
    vc_a.tick()
    print(f"  NodeA: {GREEN}{vc_a.clock}{RESET}")

    print(f"\n{BOLD}Langkah 2:{RESET} NodeA mengirim pesan sinkronisasi ke NodeB")
    msg_a_to_b = vc_a.send_event()
    vc_b.receive_event(msg_a_to_b)
    print(f"  NodeA clock (setelah send)   : {GREEN}{vc_a.clock}{RESET}")
    print(f"  NodeB clock (setelah receive): {BLUE}{vc_b.clock}{RESET}")

    rel1 = VectorClock.compare(vc_a.clock, vc_b.clock)
    print(f"  Kausalitas NodeA vs NodeB     : {BOLD}{YELLOW}{rel1}{RESET}")

    print(f"\n{BOLD}Langkah 3:{RESET} NodeC melakukan concurrent local write secara independen")
    vc_c.tick()
    print(f"  NodeC clock: {MAGENTA}{vc_c.clock}{RESET}")

    rel2 = VectorClock.compare(vc_b.clock, vc_c.clock)
    print(f"  Kausalitas NodeB vs NodeC     : {BOLD}{RED}{rel2}{RESET}")
    print_warn("Terdeteksi CONCURRENT! Data di NodeB dan NodeC dibuat tanpa pengetahuan satu sama lain.")
    print_info("Sistem terdistribusi (seperti DynamoDB/Riak) butuh strategi LWW atau Conflict Resolution.")


# =====================================================================
# 3. DUA-PHASE COMMIT (2PC) DISTRIBUTED TRANSACTION
# =====================================================================

class Participant:
    def __init__(self, name: str, will_fail: bool = False):
        self.name = name
        self.will_fail = will_fail
        self.status = "INIT"

    def prepare(self) -> bool:
        if self.will_fail:
            self.status = "ABORTED"
            return False
        self.status = "PREPARED"
        return True

    def commit(self) -> None:
        if self.status == "PREPARED":
            self.status = "COMMITTED"

    def abort(self) -> None:
        self.status = "ABORTED"


def run_2pc_simulation(scenario: str) -> None:
    header(f"Simulasi Two-Phase Commit (2PC) - Skenario: {scenario}")
    participants = [
        Participant("DB-Accounts", will_fail=False),
        Participant("DB-Inventory", will_fail=(scenario == "FAILURE")),
        Participant("DB-AuditLog", will_fail=False)
    ]

    print(f"{BOLD}[FASE 1: PREPARE / VOTING]{RESET}")
    votes = {}
    for p in participants:
        ok = p.prepare()
        votes[p.name] = ok
        if ok:
            print(f"  [{GREEN}VOTE YES{RESET}] {p.name} siap dan mengunci resource.")
        else:
            print(f"  [{RED}VOTE NO {RESET}] {p.name} GAGAL mengunci resource/validasi disk.")

    all_agreed = all(votes.values())

    print(f"\n{BOLD}[FASE 2: COMMIT / ABORT DECISION]{RESET}")
    if all_agreed:
        print_success("Koordinator memutuskan: GLOBAL COMMIT!")
        for p in participants:
            p.commit()
            print(f"  {GREEN}●{RESET} {p.name} status akhir: {BOLD}{p.status}{RESET}")
    else:
        print_error("Koordinator memutuskan: GLOBAL ABORT (Rollback) demi konsistensi atomik!")
        for p in participants:
            p.abort()
            print(f"  {RED}●{RESET} {p.name} status akhir: {BOLD}{p.status}{RESET}")


# =====================================================================
# MAIN RUNNER & INTERACTIVE CLI
# =====================================================================

def show_menu() -> None:
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{WHITE}  BAB 10: ALGORITMA ADVANCED & DISTRIBUTED SYSTEMS LAB{RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}")
    print(f" {BOLD}1.{RESET} Consistent Hashing Ring (Scale-Out & Data Placement)")
    print(f" {BOLD}2.{RESET} Vector Clocks (Causality & Concurrent Event Ordering)")
    print(f" {BOLD}3.{RESET} 2-Phase Commit (2PC) - Skenario Sukses (Global Commit)")
    print(f" {BOLD}4.{RESET} 2-Phase Commit (2PC) - Skenario Gagal (Global Rollback)")
    print(f" {BOLD}5.{RESET} Jalankan Seluruh Demonstrasi (Automated Full Suite)")
    print(f" {BOLD}0.{RESET} Keluar")
    print(f"{CYAN}------------------------------------------------------{RESET}")


def run_full_suite() -> None:
    demo_consistent_hashing()
    demo_vector_clocks()
    run_2pc_simulation("SUCCESS")
    run_2pc_simulation("FAILURE")
    print_success("\nSemua demonstrasi modul fondasi distributed system selesai dieksekusi!\n")


def main() -> None:
    # Jika dijalankan non-interaktif atau dengan argumen CLI
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "run"):
        run_full_suite()
        return

    # Mode Interaktif
    while True:
        try:
            show_menu()
            choice = input(f"{BOLD}Pilih menu [0-5]: {RESET}").strip()
            if choice == "1":
                demo_consistent_hashing()
            elif choice == "2":
                demo_vector_clocks()
            elif choice == "3":
                run_2pc_simulation("SUCCESS")
            elif choice == "4":
                run_2pc_simulation("FAILURE")
            elif choice == "5":
                run_full_suite()
            elif choice in ("0", "q", "exit"):
                print(f"\n{GREEN}Lab selesai. Selamat belajar arsitektur sistem terdistribusi!{RESET}\n")
                break
            else:
                print_warn("Pilihan tidak valid, silakan ketik angka 0-5.")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan oleh pengguna.{RESET}\n")
            break


if __name__ == "__main__":
    main()
