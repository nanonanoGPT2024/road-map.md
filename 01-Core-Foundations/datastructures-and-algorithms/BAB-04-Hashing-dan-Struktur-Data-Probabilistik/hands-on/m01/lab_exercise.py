#!/usr/bin/env python3
"""
Lab Exercise M01: Fondasi Hashing & Struktur Data Probabilistik (Bloom Filter)
BAB-04: Hashing dan Struktur Data Probabilistik
"""

import sys
import math
import hashlib
import time

# ==============================================================================
# ANSI Color Codes & UI Helpers
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"

def banner():
    print(f"{Color.CYAN}{Color.BOLD}" + "="*70)
    print("  LAB INTERAKTIF: HASHING & PROBABILISTIC DATA STRUCTURES (M01)")
    print("  BAB-04: Separate Chaining, Linear Probing, & Bloom Filter Demo")
    print("="*70 + f"{Color.RESET}")

# ==============================================================================
# Bagian 1: Hash Table dengan Separate Chaining & Linear Probing
# ==============================================================================
class ChainedHashTable:
    """Implementasi Hash Table sederhana dengan Separate Chaining."""
    def __init__(self, capacity=7):
        self.capacity = capacity
        self.buckets = [[] for _ in range(capacity)]
        self.size = 0

    def _hash(self, key: str) -> int:
        # Horner's polynomial hashing modulo capacity
        h = 0
        for char in str(key):
            h = (h * 31 + ord(char)) % self.capacity
        return h

    def insert(self, key: str, value: str):
        idx = self._hash(key)
        bucket = self.buckets[idx]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                bucket[i] = (key, value)
                return
        bucket.append((key, value))
        self.size += 1

    def display(self):
        print(f"\n{Color.YELLOW}{Color.BOLD}--- Bucket Hash Table (Separate Chaining) [Capacity: {self.capacity}] ---{Color.RESET}")
        for idx, bucket in enumerate(self.buckets):
            chain_str = " -> ".join([f"[{k}: {v}]" for k, v in bucket]) if bucket else "EMPTY"
            color = Color.GREEN if bucket else Color.GRAY
            print(f"  Slot [{idx:02d}]: {color}{chain_str}{Color.RESET}")
        load_factor = self.size / self.capacity
        print(f"  {Color.WHITE}Total Item: {self.size} | Load Factor (α): {load_factor:.2f}{Color.RESET}\n")

class LinearProbingHashTable:
    """Implementasi Open Addressing (Linear Probing)."""
    def __init__(self, capacity=11):
        self.capacity = capacity
        self.table = [None] * capacity
        self.size = 0

    def _hash(self, key: str) -> int:
        h = 0
        for char in str(key):
            h = (h * 31 + ord(char)) % self.capacity
        return h

    def insert(self, key: str, value: str) -> int:
        if self.size >= self.capacity:
            raise OverflowError("Hash table penuh!")
        idx = self._hash(key)
        probes = 0
        while self.table[idx] is not None:
            if self.table[idx][0] == key:
                self.table[idx] = (key, value)
                return probes
            idx = (idx + 1) % self.capacity
            probes += 1
        self.table[idx] = (key, value)
        self.size += 1
        return probes

    def display(self):
        print(f"\n{Color.YELLOW}{Color.BOLD}--- Open Addressing Table (Linear Probing) [Capacity: {self.capacity}] ---{Color.RESET}")
        for idx, entry in enumerate(self.table):
            if entry is None:
                print(f"  Slot [{idx:02d}]: {Color.GRAY}[ EMPTY ]{Color.RESET}")
            else:
                k, v = entry
                orig = self._hash(k)
                offset = (idx - orig) % self.capacity
                disp_offset = f"{Color.RED}(+probed {offset}){Color.RESET}" if offset > 0 else f"{Color.GREEN}(exact slot){Color.RESET}"
                print(f"  Slot [{idx:02d}]: {Color.CYAN}[{k}: {v}]{Color.RESET} {disp_offset}")
        load_factor = self.size / self.capacity
        print(f"  {Color.WHITE}Total Item: {self.size} | Load Factor (α): {load_factor:.2f}{Color.RESET}\n")

# ==============================================================================
# Bagian 2: Probabilistic Structure - Bloom Filter
# ==============================================================================
class BloomFilter:
    """
    Bloom Filter menggunakan k-hash functions yang diturunkan dari
    salt hashing MD5 & SHA-256 secara deterministik.
    """
    def __init__(self, expected_items: int = 20, false_positive_rate: float = 0.05):
        self.n = expected_items
        self.p = false_positive_rate
        # Rumus optimal m (ukuran bit array) dan k (banyaknya hash function)
        self.m = int(- (self.n * math.log(self.p)) / (math.log(2) ** 2))
        self.k = int((self.m / self.n) * math.log(2))
        self.bit_array = [0] * self.m
        self.items_added = 0

    def _hashes(self, item: str):
        indices = []
        for i in range(self.k):
            # Kirim salt indeks untuk mensimulasikan k-independent hash functions
            seed = f"{item}:{i}".encode('utf-8')
            digest = hashlib.sha256(seed).hexdigest()
            idx = int(digest, 16) % self.m
            indices.append(idx)
        return indices

    def add(self, item: str):
        indices = self._hashes(item)
        for idx in indices:
            self.bit_array[idx] = 1
        self.items_added += 1

    def contains(self, item: str) -> bool:
        indices = self._hashes(item)
        for idx in indices:
            if self.bit_array[idx] == 0:
                return False  # Pasti tidak ada (No False Negatives)
        return True          # Mungkin ada (Possible False Positive)

    def current_theoretical_fpr(self) -> float:
        # FPR = (1 - e^(-k * n / m))^k
        if self.m == 0:
            return 1.0
        exponent = - (self.k * self.items_added) / self.m
        return (1.0 - math.exp(exponent)) ** self.k

    def display_bitset(self):
        print(f"\n{Color.MAGENTA}{Color.BOLD}--- Visualisasi Bit Array Bloom Filter [Size m={self.m}, k={self.k}] ---{Color.RESET}")
        chunks = [self.bit_array[i:i+40] for i in range(0, self.m, 40)]
        for chunk_idx, chunk in enumerate(chunks):
            chunk_str = "".join([f"{Color.GREEN}1{Color.RESET}" if b == 1 else f"{Color.GRAY}0{Color.RESET}" for b in chunk])
            start_bit = chunk_idx * 40
            end_bit = min(start_bit + 39, self.m - 1)
            print(f"  Bit [{start_bit:03d}..{end_bit:03d}]: {chunk_str}")
        ones = sum(self.bit_array)
        density = (ones / self.m) * 100
        print(f"  {Color.WHITE}Bit Aktif (1s): {ones}/{self.m} ({density:.1f}% density)")
        print(f"  Items dimuat: {self.items_added} | Target FPR: {self.p*100:.2f}% | Teoretis FPR: {self.current_theoretical_fpr()*100:.2f}%{Color.RESET}\n")

# ==============================================================================
# Alur Demo Interaktif
# ==============================================================================
def demo_hash_tables():
    print(f"\n{Color.CYAN}{Color.BOLD}[1] Simulasi Hash Collision: Separate Chaining vs Linear Probing{Color.RESET}")
    print("Menyiapkan dataset sample yang memicu collision...")
    
    sample_data = [
        ("alpha", "192.168.1.1"),
        ("beta",  "192.168.1.2"),
        ("charlie", "192.168.1.3"),
        ("delta", "192.168.1.4"),
        ("echo",  "192.168.1.5"),
        ("foxtrot", "192.168.1.6"),
    ]

    sc = ChainedHashTable(capacity=5)
    lp = LinearProbingHashTable(capacity=7)

    for k, v in sample_data:
        sc.insert(k, v)
        probes = lp.insert(k, v)
        print(f"  -> Disisipkan {Color.BOLD}'{k}'{Color.RESET}: Chaining Hash={sc._hash(k)}, LP Probes={probes}")

    sc.display()
    lp.display()

def demo_bloom_filter():
    print(f"\n{Color.CYAN}{Color.BOLD}[2] Simulasi Bloom Filter (Deteksi Keanggotaan & False Positive){Color.RESET}")
    bf = BloomFilter(expected_items=10, false_positive_rate=0.10)
    print(f"Bloom Filter dikonfigurasi: m={bf.m} bits, k={bf.k} hash functions untuk 10 items target (FPR 10%).")

    whitelist = ["user_alice", "user_bob", "user_charlie", "user_david", "user_eva"]
    print(f"\nMenambahkan elemen ke whitelist:")
    for user in whitelist:
        bf.add(user)
        print(f"  {Color.GREEN}+ Ditambahkan:{Color.RESET} {user}")

    bf.display_bitset()

    print(f"{Color.YELLOW}Menguji Keanggotaan (Membership Query):{Color.RESET}")
    test_queries = [
        "user_alice",      # Ada di whitelist
        "user_bob",        # Ada di whitelist
        "user_unknown_1",  # Tidak ada
        "user_unknown_2",  # Tidak ada
        "user_attacker_x", # Tidak ada
        "user_eva"         # Ada di whitelist
    ]

    for q in test_queries:
        exists = bf.contains(q)
        is_actual = q in whitelist
        if exists and is_actual:
            status = f"{Color.GREEN}[TRUE POSITIVE]{Color.RESET} Terdeteksi Ada (Akurat)"
        elif exists and not is_actual:
            status = f"{Color.RED}[FALSE POSITIVE]{Color.RESET} Dilaporkan Ada padahal Tidak Ada!"
        elif not exists and not is_actual:
            status = f"{Color.BLUE}[TRUE NEGATIVE]{Color.RESET} Pasti Tidak Ada (Definitif)"
        else:
            status = f"{Color.RED}[ERROR/IMPOSSIBLE]{Color.RESET} False Negative (Harusnya mustahil di Bloom Filter)"
        
        print(f"  Query: {q:<18} -> Hasil: {status}")

def demo_false_positive_benchmark():
    print(f"\n{Color.CYAN}{Color.BOLD}[3] Uji Empiris Rasio False Positive Bloom Filter (10.000 Percobaan){Color.RESET}")
    n_items = 200
    bf = BloomFilter(expected_items=n_items, false_positive_rate=0.05)
    
    # Isi dengan 200 elemen dummy
    for i in range(n_items):
        bf.add(f"member_node_{i}")

    # Uji 10.000 elemen asing
    test_count = 10000
    fp_count = 0
    for i in range(test_count):
        fake_key = f"stranger_query_{i}"
        if bf.contains(fake_key):
            fp_count += 1

    empirical_rate = (fp_count / test_count) * 100
    theoretical_rate = bf.current_theoretical_fpr() * 100

    print(f"  Jumlah Bit (m)        : {bf.m} bits ({bf.m / 8:.1f} bytes)")
    print(f"  Hash Functions (k)    : {bf.k}")
    print(f"  Items Dimasukkan (n)  : {n_items}")
    print(f"  Percobaan Elemen Asing: {test_count}")
    print(f"  False Positives Ditemukan: {Color.RED}{fp_count}{Color.RESET}")
    print(f"  Empirical FPR         : {Color.YELLOW}{empirical_rate:.2f}%{Color.RESET}")
    print(f"  Theoretical FPR       : {Color.GREEN}{theoretical_rate:.2f}%{Color.RESET}")

def main():
    banner()
    while True:
        print(f"{Color.BOLD}PILIH MENU SIMULASI:{Color.RESET}")
        print(" [1] Collision Handling: Separate Chaining & Linear Probing")
        print(" [2] Bloom Filter Membership Test & Bitset Visualization")
        print(" [3] Benchmark Empiris False Positive Rate (10.000 Queri)")
        print(" [4] Jalankan Semua Demo Sekaligus")
        print(" [0] Keluar")
        
        try:
            choice = input(f"\n{Color.WHITE}Masukkan pilihan [0-4]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar program.")
            sys.exit(0)

        if choice == "1":
            demo_hash_tables()
        elif choice == "2":
            demo_bloom_filter()
        elif choice == "3":
            demo_false_positive_benchmark()
        elif choice == "4":
            demo_hash_tables()
            demo_bloom_filter()
            demo_false_positive_benchmark()
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan Lab M01! Selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-4.{Color.RESET}")
        
        print("\n" + "-"*70 + "\n")

if __name__ == "__main__":
    # Jika dijalankan dengan argumen --auto atau non-interaktif, jalankan demo 4
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "--auto", "-a"):
        banner()
        demo_hash_tables()
        demo_bloom_filter()
        demo_false_positive_benchmark()
    else:
        main()
