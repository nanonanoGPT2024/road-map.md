#!/usr/bin/env python3
"""
Lab Exercise: Elasticsearch Data Tiering & Index Lifecycle Management (ILM) Simulation
BAB-08: Data Tiering & ILM Architecture
"""

import sys
import time
from typing import Dict, List, Optional

# ANSI Color Codes for Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def print_banner():
    banner = f"""{Color.CYAN}{Color.BOLD}
================================================================================
* ELASTICSEARCH DATA TIERING & INDEX LIFECYCLE MANAGEMENT (ILM) LAB SIMULATION *
* Architecture: Hot -> Warm -> Cold -> Frozen -> Delete                        *
================================================================================{Color.RESET}"""
    print(banner)

class SimulatedIndex:
    def __init__(self, name: str, generation: int):
        self.name = name
        self.generation = generation
        self.age_days = 0.0
        self.doc_count = 0
        self.size_mb = 0.0
        self.primary_shards = 2
        self.replica_shards = 1
        self.segments_per_shard = 8
        self.phase = "hot"
        self.is_write_index = True
        self.is_readonly = False
        self.tier_preference = "data_hot"
        self.searchable_snapshot = False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "phase": self.phase,
            "age_days": round(self.age_days, 1),
            "doc_count": self.doc_count,
            "size_mb": round(self.size_mb, 2),
            "shards": f"{self.primary_shards}p / {self.replica_shards}r",
            "segments": self.segments_per_shard,
            "tier": self.tier_preference,
            "readonly": self.is_readonly,
            "snapshot": self.searchable_snapshot,
            "write_target": self.is_write_index
        }

class ILMEngine:
    def __init__(self):
        # ILM Policy Configuration Thresholds
        self.policy_name = "logs-lifecycle-policy"
        self.rollover_max_docs = 10000
        self.rollover_max_size_mb = 50.0
        self.rollover_max_age_days = 7.0
        
        self.warm_min_age_days = 7.0
        self.cold_min_age_days = 30.0
        self.frozen_min_age_days = 90.0
        self.delete_min_age_days = 180.0

        # Cluster state
        self.alias_name = "logs-app"
        self.generation_counter = 1
        self.indices: List[SimulatedIndex] = []
        
        # Initialize primary write index
        first_index = SimulatedIndex(f"logs-app-{self.generation_counter:06d}", self.generation_counter)
        self.indices.append(first_index)

    @property
    def write_index(self) -> Optional[SimulatedIndex]:
        for idx in self.indices:
            if idx.is_write_index:
                return idx
        return None

    def ingest_logs(self, batch_docs: int = 2500, doc_avg_bytes: int = 1200):
        target = self.write_index
        if not target:
            print(f"{Color.RED}[!] Error: Tidak ada active write index pada alias '{self.alias_name}'.{Color.RESET}")
            return

        added_size_mb = (batch_docs * doc_avg_bytes) / (1024 * 1024)
        target.doc_count += batch_docs
        target.size_mb += added_size_mb
        target.segments_per_shard += 2  # New flush/refresh creates Lucene segments

        print(f"{Color.GREEN}[+] Berhasil menginjeksi {batch_docs:,} dokumen (~{added_size_mb:.2f} MB) ke index '{target.name}'.{Color.RESET}")
        print(f"    Total Dokumen: {target.doc_count:,} | Ukuran Index: {target.size_mb:.2f} MB | Segmen: {target.segments_per_shard}/shard")

    def advance_time(self, days: float):
        for idx in self.indices:
            idx.age_days += days
        print(f"{Color.YELLOW}[>>] Waktu cluster dimajukan +{days} hari.{Color.RESET}")

    def evaluate_ilm_policy(self):
        print(f"\n{Color.BOLD}{Color.MAGENTA}--- Mengevaluasi ILM Policy '{self.policy_name}' ---{Color.RESET}")
        actions_taken = 0
        indices_to_delete = []

        for idx in list(self.indices):
            # Phase 1: HOT Phase Evaluation
            if idx.phase == "hot":
                if idx.is_write_index:
                    rollover_needed = False
                    reason = ""
                    if idx.doc_count >= self.rollover_max_docs:
                        rollover_needed = True
                        reason = f"Doc count ({idx.doc_count}) >= {self.rollover_max_docs}"
                    elif idx.size_mb >= self.rollover_max_size_mb:
                        rollover_needed = True
                        reason = f"Size ({idx.size_mb:.2f} MB) >= {self.rollover_max_size_mb} MB"
                    elif idx.age_days >= self.rollover_max_age_days:
                        rollover_needed = True
                        reason = f"Age ({idx.age_days:.1f}d) >= {self.rollover_max_age_days}d"

                    if rollover_needed:
                        actions_taken += 1
                        print(f"{Color.CYAN}[ACTION: ROLLOVER]{Color.RESET} Target: '{idx.name}' | Alasan: {reason}")
                        idx.is_write_index = False
                        
                        # Buat index generasi berikutnya
                        self.generation_counter += 1
                        new_idx_name = f"logs-app-{self.generation_counter:06d}"
                        new_index = SimulatedIndex(new_idx_name, self.generation_counter)
                        self.indices.append(new_index)
                        print(f"    {Color.GREEN}* Index baru '{new_idx_name}' dibuat sebagai write_index.{Color.RESET}")
                        print(f"    * Alias '{self.alias_name}' dialihkan (is_write_index=True pada {new_idx_name}).")

                # Transisi dari Hot ke Warm
                if not idx.is_write_index and idx.age_days >= self.warm_min_age_days:
                    actions_taken += 1
                    print(f"{Color.YELLOW}[ACTION: MIGRATE TO WARM]{Color.RESET} Index: '{idx.name}' (Umur: {idx.age_days:.1f}d)")
                    idx.phase = "warm"
                    idx.tier_preference = "data_warm,data_hot"
                    # ILM Warm Actions: Shrink & ForceMerge
                    print(f"    * ForceMerge: Menggabungkan {idx.segments_per_shard} segmen -> 1 segmen (max_num_segments=1)")
                    idx.segments_per_shard = 1
                    print(f"    * Shrink Shard: Menurunkan primary shard dari {idx.primary_shards} -> 1")
                    idx.primary_shards = 1
                    idx.is_readonly = True
                    print(f"    * Index diset readonly: True")

            # Phase 2: WARM Phase Evaluation
            elif idx.phase == "warm":
                if idx.age_days >= self.cold_min_age_days:
                    actions_taken += 1
                    print(f"{Color.BLUE}[ACTION: MIGRATE TO COLD]{Color.RESET} Index: '{idx.name}' (Umur: {idx.age_days:.1f}d)")
                    idx.phase = "cold"
                    idx.tier_preference = "data_cold"
                    idx.replica_shards = 0
                    idx.searchable_snapshot = True
                    print(f"    * Menghilangkan local replica (replica count=0)")
                    print(f"    * Mount Searchable Snapshot: Penyimpanan utama dialihkan ke object store cache.")

            # Phase 3: COLD Phase Evaluation
            elif idx.phase == "cold":
                if idx.age_days >= self.frozen_min_age_days:
                    actions_taken += 1
                    print(f"{Color.WHITE}[ACTION: MIGRATE TO FROZEN]{Color.RESET} Index: '{idx.name}' (Umur: {idx.age_days:.1f}d)")
                    idx.phase = "frozen"
                    idx.tier_preference = "data_frozen"
                    print(f"    * Partially mounted searchable snapshot diaktifkan.")
                    print(f"    * Local disk cache diminimalkan (Zero-replica, pure blob retrieval).")

            # Phase 4: FROZEN Phase Evaluation
            elif idx.phase == "frozen":
                if idx.age_days >= self.delete_min_age_days:
                    actions_taken += 1
                    print(f"{Color.RED}[ACTION: DELETE]{Color.RESET} Index: '{idx.name}' (Umur: {idx.age_days:.1f}d >= {self.delete_min_age_days}d)")
                    print(f"    * Menghapus index dan membersihkan snapshot referensi dari storage cluster.")
                    indices_to_delete.append(idx)

        for del_idx in indices_to_delete:
            self.indices.remove(del_idx)

        if actions_taken == 0:
            print(f"{Color.WHITE}Semua index berada pada status optimal sesuai lifecycle age masing-masing. Tidak ada aksi yang dieksekusi.{Color.RESET}")
        else:
            print(f"{Color.GREEN}Evaluasi selesai: {actions_taken} aksi lifecycle berhasil diterapkan.{Color.RESET}")

    def display_cluster_state(self):
        print(f"\n{Color.BOLD}{Color.WHITE}=== CLUSTER DATA TIERS & INDICES STATUS ==={Color.RESET}")
        header = f"{'Index Name':<20} | {'Phase':<7} | {'Age (d)':<7} | {'Docs':<8} | {'Size(MB)':<9} | {'Shards':<8} | {'Tier Pref':<15} | {'Write'}"
        print(f"{Color.BG_DARK}{Color.WHITE}{header}{Color.RESET}")
        print("-" * len(header))

        for idx in self.indices:
            color = Color.WHITE
            if idx.phase == "hot":
                color = Color.GREEN
            elif idx.phase == "warm":
                color = Color.YELLOW
            elif idx.phase == "cold":
                color = Color.BLUE
            elif idx.phase == "frozen":
                color = Color.CYAN

            write_badge = f"{Color.BOLD}{Color.GREEN}ACTIVE{Color.RESET}" if idx.is_write_index else f"{Color.RED}NO{Color.RESET}"
            row = (
                f"{color}{idx.name:<20}{Color.RESET} | "
                f"{color}{idx.phase.upper():<7}{Color.RESET} | "
                f"{idx.age_days:<7.1f} | "
                f"{idx.doc_count:<8,d} | "
                f"{idx.size_mb:<9.2f} | "
                f"{idx.primary_shards}p/{idx.replica_shards}r ({idx.segments_per_shard}seg) | "
                f"{idx.tier_preference:<15} | "
                f"{write_badge}"
            )
            print(row)

    def display_policy_config(self):
        print(f"\n{Color.BOLD}{Color.YELLOW}=== KONFIGURASI ILM POLICY: {self.policy_name} ==={Color.RESET}")
        print(f"{Color.GREEN}1. Hot Phase:{Color.RESET}")
        print(f"   - Min Index Age: 0d (Immediate)")
        print(f"   - Rollover Conditions: max_docs={self.rollover_max_docs:,}, max_size={self.rollover_max_size_mb}MB, max_age={self.rollover_max_age_days}d")
        print(f"   - Hardware: Fast NVMe SSDs, High CPU/RAM, Tier Node: 'data_hot'")
        print(f"{Color.YELLOW}2. Warm Phase:{Color.RESET}")
        print(f"   - Min Index Age: {self.warm_min_age_days}d")
        print(f"   - Actions: Read-Only=True, Shrink Shards=1, ForceMerge Segments=1")
        print(f"   - Hardware: Standard SSD/HDD, Tier Node: 'data_warm'")
        print(f"{Color.BLUE}3. Cold Phase:{Color.RESET}")
        print(f"   - Min Index Age: {self.cold_min_age_days}d")
        print(f"   - Actions: Searchable Snapshot Mount, Replicas=0")
        print(f"   - Hardware: Low-cost storage / Object store cache, Tier Node: 'data_cold'")
        print(f"{Color.CYAN}4. Frozen Phase:{Color.RESET}")
        print(f"   - Min Index Age: {self.frozen_min_age_days}d")
        print(f"   - Actions: Partially mounted searchable snapshot, Minimal heap overhead")
        print(f"   - Hardware: Object Store (AWS S3, MinIO, GCS), Tier Node: 'data_frozen'")
        print(f"{Color.RED}5. Delete Phase:{Color.RESET}")
        print(f"   - Min Index Age: {self.delete_min_age_days}d")
        print(f"   - Actions: Delete index automatically")

def run_auto_lifecycle_demo(engine: ILMEngine):
    print(f"\n{Color.BOLD}{Color.CYAN}>>> MEMULAI SIMULASI END-TO-END AUTOMATIC LIFECYCLE <<<{Color.RESET}")
    steps = [
        ("Tahap 1: Ingest traffic log awal ke Hot Tier", lambda: engine.ingest_logs(4000, 1500)),
        ("Tahap 2: Ingest traffic tambahan hingga tembus batas Rollover", lambda: engine.ingest_logs(7000, 1500)),
        ("Tahap 3: Trigger evaluasi ILM untuk Rollover Hot Tier", lambda: engine.evaluate_ilm_policy()),
        ("Tahap 4: Simulasi berjalannya waktu 10 hari (+10d) untuk memicu Warm Phase", lambda: engine.advance_time(10)),
        ("Tahap 5: Ingest data baru ke write-index baru sambil memproses Warm transition", lambda: (engine.ingest_logs(3000), engine.evaluate_ilm_policy())),
        ("Tahap 6: Majukan waktu 35 hari (+35d) untuk transisi Cold Tier", lambda: engine.advance_time(35)),
        ("Tahap 7: Evaluasi ILM untuk Cold Phase (Searchable Snapshot)", lambda: engine.evaluate_ilm_policy()),
        ("Tahap 8: Majukan waktu 60 hari (+60d) untuk transisi Frozen Tier", lambda: engine.advance_time(60)),
        ("Tahap 9: Evaluasi ILM untuk Frozen Phase", lambda: engine.evaluate_ilm_policy()),
        ("Tahap 10: Majukan waktu 100 hari (+100d) untuk retensi Delete Phase", lambda: engine.advance_time(100)),
        ("Tahap 11: Evaluasi ILM untuk Eksekusi Purge/Delete", lambda: engine.evaluate_ilm_policy()),
    ]

    for title, action in steps:
        print(f"\n{Color.BOLD}{Color.WHITE}------------------------------------------------------------{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}[SIMULASI] {title}{Color.RESET}")
        action()
        time.sleep(0.3)
    
    print(f"\n{Color.BOLD}{Color.GREEN}=== Hasil Akhir Cluster Setelah Siklus ILM Penuh ==={Color.RESET}")
    engine.display_cluster_state()

def main():
    print_banner()
    engine = ILMEngine()

    # Jika dieksekusi secara non-interaktif (contoh: piping atau automated test)
    if not sys.stdin.isatty():
        print(f"{Color.YELLOW}[*] Non-interactive mode terdeteksi. Menjalankan demonstrasi otomatis lengkap...{Color.RESET}")
        engine.display_policy_config()
        run_auto_lifecycle_demo(engine)
        return

    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}PILIHAN MENU SIMULASI ILM:{Color.RESET}")
        print(f"  {Color.GREEN}1{Color.RESET}. Tampilkan Status Cluster & Data Tiers")
        print(f"  {Color.GREEN}2{Color.RESET}. Tampilkan Konfigurasi ILM Policy")
        print(f"  {Color.GREEN}3{Color.RESET}. Ingest Batch Log Dokumen ke Active Write Index")
        print(f"  {Color.GREEN}4{Color.RESET}. Evaluasi ILM Step Checker (Transisi Lifecycle)")
        print(f"  {Color.GREEN}5{Color.RESET}. Majukan Waktu Simulasi (+7 hari)")
        print(f"  {Color.GREEN}6{Color.RESET}. Majukan Waktu Simulasi (+30 hari)")
        print(f"  {Color.CYAN}7{Color.RESET}. Jalankan Demo Otomatis End-to-End Lifecycle")
        print(f"  {Color.RED}0{Color.RESET}. Keluar")
        
        try:
            choice = input(f"{Color.BOLD}Pilih opsi [0-7]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Program dihentikan.{Color.RESET}")
            break

        if choice == "1":
            engine.display_cluster_state()
        elif choice == "2":
            engine.display_policy_config()
        elif choice == "3":
            try:
                raw_count = input(f"Masukkan jumlah dokumen (default 3000): ").strip()
                count = int(raw_count) if raw_count else 3000
                engine.ingest_logs(batch_docs=count)
            except ValueError:
                print(f"{Color.RED}Input angka tidak valid.{Color.RESET}")
        elif choice == "4":
            engine.evaluate_ilm_policy()
        elif choice == "5":
            engine.advance_time(7.0)
        elif choice == "6":
            engine.advance_time(30.0)
        elif choice == "7":
            run_auto_lifecycle_demo(engine)
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan simulasi ILM Elasticsearch.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")

if __name__ == "__main__":
    main()
