# Bab 02: Arsitektur Node, Jaringan Peer-to-Peer, & Mempool

## 1. Learning Objectives

Setelah menyelesaikan bab ini, Anda diharapkan mampu:
- **Menganalisis** arsitektur internal *blockchain node* (Execution Client, Consensus Client, Storage Engine, dan RPC Interface) serta peran fungsionalnya dalam ekosistem *autonomous agents*.
- **Mengimplementasikan** mekanisme *distributed hash table* (DHT) berbasis algoritma Kademlia dan protokol *gossip* (Gossipsub v1.1) untuk propagasi data transaksi.
- **Merekayasa** subsistem *Transaction Pool* (*Mempool*) berbasis memori performa tinggi yang dilengkapi *dynamic fee prioritization*, validasi *nonce sequencing*, mitigasi DoS, dan aturan *Replace-by-Fee* (RBF) EIP-1559.
- **Mendiagnosis** dan memitigasi serangan tingkat jaringan seperti *Eclipse Attacks*, *Sybil Attacks*, *Transaction Flooding*, dan anomali sinkronisasi state.
- **Membangun** pipeline injeksi transaksi deterministik untuk *autonomous agent* yang berinteraksi langsung dengan node privat guna meminimalkan latensi propagasi dan risiko *front-running/MEV*.

---

## 2. Concept Overview

Secara fundamental, sistem blockchain terdesentralisasi adalah sebuah *replicated state machine* yang disinkronkan melalui jaringan *peer-to-peer* (P2P) tanpa perantara tepercaya (*trustless*). Node merupakan unit komputasi otonom yang menjalankan protokol konsensus, memvalidasi transisi state, menyimpan riwayat buku besar, dan memelihara kolam transaksi sementara (*mempool*).

```
                      +-------------------------------------------------------+
                      |                      FULL NODE                        |
                      |                                                       |
                      |  +--------------------+      +---------------------+  |
                      |  |   Consensus Layer  | <--> |   Execution Layer   |  |
                      |  |    (CL / Engine)   | Engine|   (EL / EVM/State)  |  |
                      |  +--------------------+ API  +---------------------+  |
                      |         ^                             ^               |
                      |         | Discv5                      | P2P (devp2p)  |
                      +---------|-----------------------------|---------------+
                                |                             |
                                v                             v
                     [ P2P Consensus Mesh ]        [ P2P Execution Mesh ]
                     (Beacon Blocks/Attestations)  (Transactions / Blocks)
```

### Mental Model Subsistem Node
Node blockchain modern (khususnya pasca-Ethereum The Merge) mengadopsi arsitektur terpisah:
1. **Consensus Client (CL):** Mengelola konsensus Proof-of-Stake (PoS), pemilihan validator, komite atestasi, dan finalitas rantai (misal: Prysm, Lighthouse).
2. **Execution Client (EL):** Mengelola EVM (*Ethereum Virtual Machine*), eksekusi transaksi, pemeliharaan *state trie* (World State), kalkulasi *gas*, dan *mempool* (misal: Geth, Nethermind, Reth).
3. **Engine API:** Antarmuka JSON-RPC berbasis IPC/WebSocket terautentikasi (menggunakan shared secret HMAC-SHA256) yang menjembatani konsensus dan eksekusi.
4. **Peer-to-Peer (P2P) Engine:** Mengatur penemuan peer (*node discovery* via Kademlia/Discv5), pertukaran metadata, dan propagasi pesan melalui *gossip protocol*.
5. **Mempool (TxPool):** Area *staging* non-deterministik di dalam RAM (dengan opsi persistensi disk lokal) yang menampung transaksi yang valid secara kriptografis dan terverifikasi secara balance/nonce, namun belum dimasukkan ke dalam blok oleh *proposer/builder*.

Bagi *Autonomous AI Agents*, memahami batas latensi antara injeksi transaksi ke RPC lokal, propagasi *mempool*, dan penerimaan oleh *block builder* adalah faktor kritis yang menentukan apakah sebuah agen berhasil mengeksekusi arbitrase, likuidasi, atau pembaruan *state inference* tepat waktu.

---

## 3. Why It Matters: Implikasi untuk Enterprise & AI Agents

Pada sistem konvensional, transaksi dikirimkan ke server terpusat dengan antrean FIFO (*First-In, First-Out*). Pada arsitektur Web3 dan desentralisasi:
- **Kondisi Tanpa Batas Ruang Memori (Mempool Congestion):** Mempool memiliki batas alokasi memori fisik (default Geth: 4096 transaksi *executable*, 1024 *non-executable*). Ketika lonjakan volume terjadi, transaksi agen AI dapat ter-eviksi (*dropped*) jika penetapan gas fee statis atau sub-optimal.
- **Asymmetric Information & MEV (Maximal Extractable Value):** Transaksi yang disiarkan ke *public mempool* dapat dibaca oleh *Searcher Bot* lain. Jika sebuah AI Agent mengirimkan transaksi likuidasi atau arbitrase secara terbuka, bot MEV dapat melakukan *front-running* atau *sandwich attack* dengan membayar *priority fee* lebih tinggi, sehingga memotong potensi keuntungan agen tersebut.
- **Ketergantungan Infrastruktur RPC Publik:** Menggunakan penyedia RPC terkelola pihak ketiga (seperti Infura atau Alchemy) memperkenalkan latensi *network hop* tambahan (50–300 ms), *rate-limiting*, dan ketidakpastian status mempool. Autonomous agents tingkat enterprise wajib mengoperasikan *local private node* atau terhubung langsung ke jaringan *MEV-Boost / private relay* (Flashbots Protect, Eden, bloXroute) untuk memotong propagasi publik.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan jalur internal sebuah transaksi: mulai dari injeksi oleh agen otonom, masuk ke *Mempool Admission Controller*, divalidasi, disimpan di *TxPool Staging Queue*, disiarkan ke *P2P Gossip Network*, hingga ditarik oleh *Block Builder*.

```
 +-----------------------------------------------------------------------------------------------+
 |                                     NODE INTERNALS                                            |
 |                                                                                               |
 |  [ Autonomous Agent ]                                                                         |
 |          |                                                                                    |
 |   (1) eth_sendRawTransaction                                                                  |
 |          v                                                                                    |
 |  +-----------------------+      (2) Static Validation                                         |
 |  | JSON-RPC Server       | --------------------------------+                                  |
 |  +-----------------------+                                 |                                  |
 |                                                            v                                  |
 |  +-----------------------------------------------------------------------------------------+  |
 |  | MEMPOOL (TxPool)                                                                        |  |
 |  |                                                                                         |  |
 |  |   +-----------------------+                                                             |  |
 |  |   | Admission Controller  | <--- Checks: Byte-size, Signature (secp256k1),              |  |
 |  |   +-----------------------+              BaseFee >= MinFee, Nonce >= AccountNonce        |  |
 |  |               |                                                                         |  |
 |  |               v                                                                         |  |
 |  |   +-----------------------+        (Nonce Gap?)         +---------------------------+   |  |
 |  |   | Tx Validation Engine  | --------------------------> | Queued / Future Pool      |   |  |
 |  |   +-----------------------+                             | (Waiting for lower nonces)|   |  |
 |  |               | (Nonce == NextNonce)                    +---------------------------+   |  |
 |  |               v                                                       |                 |  |
 |  |   +-----------------------+                                           | (Promoted when  |  |
 |  |   | Pending / Executable  | <-----------------------------------------+  nonce arrived) |  |
 |  |   | Priority Queue (Heap) |                                                             |  |
 |  |   +-----------------------+                                                             |  |
 |  |          |         ^                                                                    |  |
 |  |          |         | (Eviction if memory full: Min-Heap by Tip/Gas)                     |  |
 |  +----------|---------|--------------------------------------------------------------------+  |
 |             |         |                                                                       |
 |             | (3) Propagate Valid Tx                                                          |
 |             v                                                                                 |
 |  +---------------------------------------------------------+                                  |
 |  | P2P Networking Layer (Libp2p / DevP2P)                  |                                  |
 |  |                                                         |                                  |
 |  |   +-------------------+       +---------------------+   |                                  |
 |  |   | Discovery Service |       | Gossipsub Router    |   |                                  |
 |  |   | (Discv5 / Kademlia|       | (Mesh Topologies)   |   |                                  |
 |  |   +-------------------+       +---------------------+   |                                  |
 |  +------------------------------------------|--------------+                                  |
 +---------------------------------------------|-------------------------------------------------+
                                               |
                               (4) Announce NewPooledTransactionHashes
                                               v
                             +-----------------------------------+
                             |     Peer Node / Block Builder     |
                             +-----------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Node Discovery via Kademlia DHT & Discv5
Penemuan *peer* pada jaringan terdesentralisasi tidak bergantung pada DNS terpusat, melainkan pada struktur *Distributed Hash Table* (DHT) berbasis Kademlia.

- **Metrik Jarak (XOR Metric):** Jarak logis antara dua node dengan Node ID $x$ dan $y$ didefinisikan sebagai:
  $$d(x, y) = x \oplus y$$
  Sifat operasi XOR ($\oplus$):
  - $d(x, y) = 0 \iff x = y$
  - $d(x, y) = d(y, x)$ (Simetris)
  - $d(x, z) \le d(x, y) \oplus d(y, z)$ (Pertidaksamaan Segitiga)

- **$k$-Buckets:** Node menyimpan informasi peer dalam daftar yang disebut $k$-buckets. Setiap bucket mencakup rentang jarak logis tertentu $[2^i, 2^{i+1}-1]$ untuk $0 \le i < 256$. Nilai $k$ (biasanya $k=16$) menentukan jumlah maksimum node yang disimpan per bucket. Struktur ini memastikan bahwa node memiliki informasi detail mengenai tetangga terdekat, namun tetap memiliki referensi eksponensial ke seluruh jaringan.

- **Prosedur Lookup Node:**
  1. Node penginisiasi memilih $\alpha$ (faktor konkurensi, default $\alpha=3$) node terdekat dari $k$-bucket lokalnya.
  2. Mengirimkan RPC `FIND_NODE` yang berisi target ID.
  3. Node penerima mengembalikan $k$ node terdekat ke target yang diketahuinya.
  4. Penginisiasi memperbarui daftar kandidat dan mengulangi proses hingga konvergen (tidak ditemukan node yang lebih dekat).

### 5.2 Gossipsub Protocol v1.1
Propagasi blok dan transaksi mengandalkan protokol *publish/subscribe* berbasis mesh (*Gossipsub*):
- **Mesh Construction:** Untuk setiap topik (misalnya, `tx/eth`), setiap node mempertahankan *mesh* lokal yang terdiri dari sejumlah peer berderajat $D$ (misal: $D_{\text{low}} = 6, D = 8, D_{\text{high}} = 12$).
- **Gossip Dissemination (IHAVE / IWANT):**
  - Alih-alih langsung mengirimkan *payload* transaksi lengkap ke seluruh koneksi (yang memboroskan bandwidth secara kuadratik $O(N^2)$), node menyiarkan metadata hash melalui pesan `IHAVE`.
  - Node yang belum memiliki transaksi tersebut akan merespons dengan pesan `IWANT` berbatas waktu (*timeout*).
  - Node pengirim kemudian mengirimkan *payload* penuh (`NewPooledTransactionHashes` $\rightarrow$ `GetPooledTransactions` $\rightarrow$ `PooledTransactions`).
- **Peer Scoring System:** Gossipsub v1.1 menerapkan sistem skoring peer dinamis multi-parameter:
  $$Score = w_1 P_1 + w_2 P_2 + w_3 P_3 + w_4 P_4$$
  Dimana $P_1$ adalah waktu keaktifan dalam mesh (*time in mesh*), $P_2$ adalah laju pengiriman pesan pertama yang valid (*first message deliveries*), $P_3$ adalah tingkat pesan redundan/usang, dan $P_4$ adalah penalti kegagalan validasi aplikasi (*internal validation failures*). Peer dengan skor di bawah ambang batas (*gossip threshold*) akan diabaikan (*pruned*), sedangkan peer di bawah *disconnect threshold* akan diputus koneksinya secara permanen guna mencegah *Gossip Flood Attacks*.

### 5.3 Arsitektur Internal Mempool & Life-Cycle Transaksi
Mempool bukanlah antrean tunggal sederhana, melainkan struktur data terbagi (*partitioned*):

1. **Pending Pool (Executable):**
   - Berisi transaksi yang *nonce*-nya berurutan langsung dari *current account state* di database trie.
   - Siap dieksekusi oleh EVM dan diurutkan menggunakan *priority queue* berdasarkan *Effective Gas Tip*:
     $$\text{EffectiveTip} = \min(\text{max\_priority\_fee\_per\_gas}, \text{max\_fee\_per\_gas} - \text{base\_fee})$$

2. **Queued Pool (Non-executable / Future):**
   - Berisi transaksi yang memiliki *nonce gap* (misal: state akun saat ini adalah nonce 5, tetapi transaksi yang masuk adalah nonce 7).
   - Transaksi akan ditahan di sini hingga transaksi dengan nonce 5 dan 6 diterima dan divalidasi.

3. **Mekanisme Replace-By-Fee (RBF):**
   - Transaksi yang sama (dari akun yang sama dengan nonce yang sama) dapat ditimpa jika dan hanya jika:
     $$\text{NewEffectiveTip} \ge \text{OldEffectiveTip} \times (1 + \text{BumpPercentage})$$
     Standar industri mengharuskan minimal kenaikan sebesar 10% hingga 12% untuk mengompensasi sumber daya komputasi dan bandwidth jaringan yang terbuang akibat *re-gossiping*.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem Mempool asynchronous dan terisolasi untuk arsitektur *Autonomous Agent*. Sistem ini mencakup verifikasi kriptografi transaksi, kontrol *admission*, pelacakan *nonce sequencing*, mekanisme penggusuran (*eviction*) berbasis heap prioritas, dan penggantian transaksi (RBF).

```python
"""
Core Engine: Production-Grade Blockchain Transaction Pool (Mempool)
Desain untuk Autonomous Agent Operations & Local Node Infrastructure.
"""

from __future__ import annotations
import asyncio
import dataclasses
import hashlib
import hmac
import time
from typing import Dict, List, Optional, Tuple, Set
import heapq
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TxEngine")


@dataclasses.dataclass(frozen=True)
class Transaction:
    sender: str
    nonce: int
    to: str
    value: int
    gas_limit: int
    max_fee_per_gas: int          # EIP-1559 Cap Fee
    max_priority_fee_per_gas: int # EIP-1559 Miner/Validator Tip
    payload: bytes
    signature: str                # Simulasi Hex signature (65 bytes ecdsa)
    timestamp: float = dataclasses.field(default_factory=time.time)

    @property
    def hash(self) -> str:
        """Kalkulasi identitas unik transaksi (TxHash) via SHA256 (representasi deterministik)."""
        preimage = (
            f"{self.sender}:{self.nonce}:{self.to}:{self.value}:"
            f"{self.gas_limit}:{self.max_fee_per_gas}:{self.max_priority_fee_per_gas}:"
            f"{self.payload.hex()}:{self.signature}"
        )
        return hashlib.sha256(preimage.encode("utf-8")).hexdigest()

    def calculate_effective_tip(self, current_base_fee: int) -> int:
        """Kalkulasi tip aktual yang didapat block builder berdasarkan EIP-1559."""
        if self.max_fee_per_gas < current_base_fee:
            return 0
        max_possible_tip = self.max_fee_per_gas - current_base_fee
        return min(self.max_priority_fee_per_gas, max_possible_tip)


class TxPoolFullError(Exception):
    """Dilempar saat kapasitas mempool penuh dan transaksi tidak memenuhi kriteria eviksi."""
    pass


class InvalidTransactionError(Exception):
    """Dilempar saat transaksi melanggar validasi statis/dinamis."""
    pass


class AccountState:
    """Mock interface representasi state trie lokal pada node."""
    def __init__(self, confirmed_nonce: int, confirmed_balance: int):
        self.confirmed_nonce = confirmed_nonce
        self.confirmed_balance = confirmed_balance


class Mempool:
    """
    Sub-komponen Transaction Pool dengan dynamic eviction,
    EIP-1559 compatibility, and deterministic nonce routing.
    """
    def __init__(
        self,
        max_capacity: int = 1000,
        price_bump_percentage: float = 0.10, # Minimal kenaikan tip 10% untuk RBF
    ):
        self._max_capacity = max_capacity
        self._price_bump_percentage = price_bump_percentage
        
        # Lock asynchronous untuk integritas state engine
        self._lock = asyncio.Lock()

        # Penyimpanan Transaksi: tx_hash -> Transaction
        self._all_txs: Dict[str, Transaction] = {}
        
        # Pengelompokan Nonce: sender -> {nonce -> Transaction}
        self._pending_txs: Dict[str, Dict[int, Transaction]] = {}
        self._queued_txs: Dict[str, Dict[int, Transaction]] = {}

        # Tracking Akun Global (State Terakhir Buku Besar)
        self._state_store: Dict[str, AccountState] = {}

    def set_account_state(self, address: str, nonce: int, balance: int) -> None:
        """Sinkronisasi state on-chain dasar dari execution engine."""
        self._state_store[address] = AccountState(confirmed_nonce=nonce, confirmed_balance=balance)

    def _get_account_nonce(self, address: str) -> int:
        state = self._state_store.get(address)
        return state.confirmed_nonce if state else 0

    def _get_account_balance(self, address: str) -> int:
        state = self._state_store.get(address)
        return state.confirmed_balance if state else 0

    def _verify_crypto_signature(self, tx: Transaction) -> bool:
        """
        Validasi integritas kriptografi signature.
        Catatan: Dalam implementasi riil, ini mengeksekusi secp256k1_ecdsa_recover.
        """
        if not tx.signature or len(tx.signature) < 64:
            return False
        # Simulasi validitas: digest sender + nonce harus cocok dengan signature mock
        expected = hmac.new(b"network-secret-key", f"{tx.sender}:{tx.nonce}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(tx.signature, expected)

    async def add_transaction(self, tx: Transaction, current_base_fee: int) -> Tuple[bool, str]:
        """
        Entry point utama untuk injeksi transaksi ke dalam node.
        Mengembalikan tuple (Status Keberhasilan, Alasan/TxHash).
        """
        async with self._lock:
            try:
                # 1. Static Validation
                self._validate_static(tx, current_base_fee)

                # 2. Dynamic State Validation (Balance & Nonce)
                account_nonce = self._get_account_nonce(tx.sender)
                account_balance = self._get_account_balance(tx.sender)

                if tx.nonce < account_nonce:
                    raise InvalidTransactionError(
                        f"Nonce {tx.nonce} kadaluarsa (state nonce: {account_nonce})"
                    )

                max_cost = tx.value + (tx.gas_limit * tx.max_fee_per_gas)
                if account_balance < max_cost:
                    raise InvalidTransactionError(
                        f"Saldo tidak memadai: Dibutuhkan {max_cost}, Tersedia {account_balance}"
                    )

                # 3. Handle Replace-By-Fee (RBF)
                if self._is_replacement(tx):
                    self._handle_replacement(tx, current_base_fee)
                    logger.info("Transkasi %s berhasil menggantikan transaksi sebelumnya (RBF).", tx.hash)
                    return True, tx.hash

                # 4. Check Capacity & Eviction Rule
                if len(self._all_txs) >= self._max_capacity:
                    evicted = self._try_evict_lowest_fee(tx, current_base_fee)
                    if not evicted:
                        raise TxPoolFullError("Mempool penuh. Tip gas transaksi baru terlalu rendah untuk eviksi.")

                # 5. Route to Pending or Queued
                self._route_transaction(tx, account_nonce)
                self._all_txs[tx.hash] = tx
                logger.info("Tx %s diterima. Sender: %s | Nonce: %d", tx.hash, tx.sender, tx.nonce)
                return True, tx.hash

            except (InvalidTransactionError, TxPoolFullError) as exc:
                logger.warning("Penolakan Transaksi: %s", str(exc))
                return False, str(exc)

    def _validate_static(self, tx: Transaction, current_base_fee: int) -> None:
        """Validasi statis intrinsik transaksi."""
        if tx.gas_limit < 21000:
            raise InvalidTransactionError("Gas limit di bawah batas intrinsik (21000)")
        if tx.max_fee_per_gas < current_base_fee:
            raise InvalidTransactionError(
                f"Max fee ({tx.max_fee_per_gas}) lebih rendah dari Base fee saat ini ({current_base_fee})"
            )
        if tx.max_priority_fee_per_gas > tx.max_fee_per_gas:
            raise InvalidTransactionError("Max Priority Fee melebihi Max Fee Per Gas")
        if not self._verify_crypto_signature(tx):
            raise InvalidTransactionError("Tanda tangan kriptografi tidak valid")

    def _is_replacement(self, tx: Transaction) -> bool:
        """Memeriksa apakah transaksi dengan nonce yang sama sudah ada di dalam pool."""
        sender_pending = self._pending_txs.get(tx.sender, {})
        sender_queued = self._queued_txs.get(tx.sender, {})
        return (tx.nonce in sender_pending) or (tx.nonce in sender_queued)

    def _handle_replacement(self, tx: Transaction, current_base_fee: int) -> None:
        """Evaluasi apakah transaksi baru memenuhi threshold kenaikan gas (RBF)."""
        sender_pool = (
            self._pending_txs.get(tx.sender) 
            if tx.nonce in self._pending_txs.get(tx.sender, {}) 
            else self._queued_txs.get(tx.sender)
        )
        assert sender_pool is not None
        old_tx = sender_pool[tx.nonce]

        min_tip = int(old_tx.calculate_effective_tip(current_base_fee) * (1.0 + self._price_bump_percentage))
        new_tip = tx.calculate_effective_tip(current_base_fee)

        if new_tip <= min_tip:
            raise InvalidTransactionError(
                f"RBF Ditolak: Tip baru ({new_tip}) harus minimal {self._price_bump_percentage*100}% "
                f"lebih tinggi dari tip lama ({min_tip})"
            )

        # Hapus transaksi lama
        del self._all_txs[old_tx.hash]
        sender_pool[tx.nonce] = tx
        self._all_txs[tx.hash] = tx

    def _route_transaction(self, tx: Transaction, current_account_nonce: int) -> None:
        """Menentukan apakah transaksi masuk ke antrean Pending atau Queued (karena nonce gap)."""
        sender = tx.sender
        if sender not in self._pending_txs:
            self._pending_txs[sender] = {}
        if sender not in self._queued_txs:
            self._queued_txs[sender] = {}

        # Nonce langsung berurutan dari blockchain state
        if tx.nonce == current_account_nonce:
            self._pending_txs[sender][tx.nonce] = tx
            self._promote_queued_nonces(sender, tx.nonce)
        elif tx.nonce > current_account_nonce:
            # Memeriksa kontinuitas nonce lokal di pending pool
            if (tx.nonce - 1) in self._pending_txs[sender]:
                self._pending_txs[sender][tx.nonce] = tx
                self._promote_queued_nonces(sender, tx.nonce)
            else:
                self._queued_txs[sender][tx.nonce] = tx
        else:
            raise InvalidTransactionError("Nonce berada di masa lampau")

    def _promote_queued_nonces(self, sender: str, highest_pending_nonce: int) -> None:
        """Memindahkan transaksi dari queued ke pending jika gap telah terpenuhi."""
        queued = self._queued_txs.get(sender, {})
        next_expected = highest_pending_nonce + 1

        while next_expected in queued:
            promoted_tx = queued.pop(next_expected)
            self._pending_txs[sender][next_expected] = promoted_tx
            logger.info("Tx %s dipromosikan dari Queued ke Pending Pool.", promoted_tx.hash)
            next_expected += 1

    def _try_evict_lowest_fee(self, candidate_tx: Transaction, current_base_fee: int) -> bool:
        """
        Logika penggusuran (Eviction):
        Mencari transaksi dengan effective tip paling rendah di seluruh antrean pool.
        Jika tip candidate_tx lebih tinggi, maka transaksi terendah akan di-evict.
        """
        if not self._all_txs:
            return False

        # Mencari transaksi dengan tip terendah
        lowest_tx: Optional[Transaction] = None
        lowest_tip = float("inf")

        for tx in self._all_txs.values():
            tip = tx.calculate_effective_tip(current_base_fee)
            if tip < lowest_tip:
                lowest_tip = tip
                lowest_tx = tx

        candidate_tip = candidate_tx.calculate_effective_tip(current_base_fee)
        if lowest_tx and candidate_tip > lowest_tip:
            # Drop lowest_tx
            self._remove_tx_by_hash(lowest_tx.hash)
            logger.warning("Eviction triggered: Tx %s dikeluarkan demi Tx baru.", lowest_tx.hash)
            return True
        return False

    def _remove_tx_by_hash(self, tx_hash: str) -> None:
        """Pembersihan internal saat eviksi atau finalisasi blok."""
        tx = self._all_txs.pop(tx_hash, None)
        if not tx:
            return

        if tx.sender in self._pending_txs and tx.nonce in self._pending_txs[tx.sender]:
            del self._pending_txs[tx.sender][tx.nonce]
        if tx.sender in self._queued_txs and tx.nonce in self._queued_txs[tx.sender]:
            del self._queued_txs[tx.sender][tx.nonce]

    def get_executable_batch(self, current_base_fee: int, max_batch_size: int = 100) -> List[Transaction]:
        """
        Dieksekusi oleh Block Proposer / Builder.
        Mengambil transaksi berurutan berdasarkan tip tertinggi dari Pending Pool.
        """
        candidates: List[Transaction] = []
        for sender, txs in self._pending_txs.items():
            for tx in txs.values():
                candidates.append(tx)

        # Urutkan berdasarkan tip tertinggi (descending)
        candidates.sort(key=lambda t: t.calculate_effective_tip(current_base_fee), reverse=True)
        return candidates[:max_batch_size]

    def dump_metrics(self) -> Dict[str, int]:
        """Metrik observabilitas pool."""
        pending_count = sum(len(pool) for pool in self._pending_txs.values())
        queued_count = sum(len(pool) for pool in self._queued_txs.values())
        return {
            "total_indexed": len(self._all_txs),
            "pending_count": pending_count,
            "queued_count": queued_count,
        }


# =====================================================================
# Verification and Demonstration Routine
# =====================================================================
async def main():
    logger.info("Inisialisasi Sandbox Mempool Node...")
    mempool = Mempool(max_capacity=3, price_bump_percentage=0.15)
    base_fee = 30  # Gwei equivalent integer

    # Setup state awal untuk akun agent
    agent_addr = "0xAgent007"
    mempool.set_account_state(agent_addr, nonce=0, balance=1_000_000)

    def generate_sig(sender: str, nonce: int) -> str:
        return hmac.new(b"network-secret-key", f"{sender}:{nonce}".encode(), hashlib.sha256).hexdigest()

    # 1. Masukkan Transaksi Normal Nonce 0
    tx0 = Transaction(
        sender=agent_addr,
        nonce=0,
        to="0xProtocolRouter",
        value=1000,
        gas_limit=50000,
        max_fee_per_gas=50,
        max_priority_fee_per_gas=10,
        payload=b"action=rebalance",
        signature=generate_sig(agent_addr, 0)
    )
    success, res = await mempool.add_transaction(tx0, base_fee)
    logger.info("Submission Tx0 Status: %s | Result: %s", success, res)

    # 2. Masukkan Transaksi Nonce Gap (Nonce 2, melewati Nonce 1) -> Masuk Queued Pool
    tx2 = Transaction(
        sender=agent_addr,
        nonce=2,
        to="0xProtocolRouter",
        value=2000,
        gas_limit=50000,
        max_fee_per_gas=60,
        max_priority_fee_per_gas=15,
        payload=b"action=liquidation",
        signature=generate_sig(agent_addr, 2)
    )
    success, res = await mempool.add_transaction(tx2, base_fee)
    logger.info("Submission Tx2 (Nonce Gap) Status: %s | Result: %s", success, res)

    logger.info("Mempool Metrics Saat Ini: %s", mempool.dump_metrics())

    # 3. Masukkan Transaksi Nonce 1 -> Harus memicu promosi otomatis Tx2 ke Pending
    tx1 = Transaction(
        sender=agent_addr,
        nonce=1,
        to="0xProtocolRouter",
        value=1500,
        gas_limit=50000,
        max_fee_per_gas=55,
        max_priority_fee_per_gas=12,
        payload=b"action=approve",
        signature=generate_sig(agent_addr, 1)
    )
    await mempool.add_transaction(tx1, base_fee)
    logger.info("Metrics Setelah Tx1 (Promosi Tx2): %s", mempool.dump_metrics())

    # 4. Pengujian RBF (Replace-By-Fee) pada Nonce 1
    # Tip lama: min(12, 55-30) = 12. Diperlukan kenaikan >= 15% (tip > 13.8)
    # Coba RBF dengan tip baru = 13 (Gagal)
    tx1_fail_rbf = Transaction(
        sender=agent_addr,
        nonce=1,
        to="0xProtocolRouter",
        value=1500,
        gas_limit=50000,
        max_fee_per_gas=55,
        max_priority_fee_per_gas=13,
        payload=b"action=approve_faster",
        signature=generate_sig(agent_addr, 1)
    )
    success, reason = await mempool.add_transaction(tx1_fail_rbf, base_fee)
    logger.info("RBF Rendah Status (Expected False): %s | Alasan: %s", success, reason)

    # Coba RBF dengan tip baru = 20 (Berhasil)
    tx1_success_rbf = Transaction(
        sender=agent_addr,
        nonce=1,
        to="0xProtocolRouter",
        value=1500,
        gas_limit=50000,
        max_fee_per_gas=70,
        max_priority_fee_per_gas=20,
        payload=b"action=approve_flashbots",
        signature=generate_sig(agent_addr, 1)
    )
    success, reason = await mempool.add_transaction(tx1_success_rbf, base_fee)
    logger.info("RBF Valid Status (Expected True): %s | TxHash: %s", success, reason)

    # 5. Uji Kapasitas dan Penggusuran (Eviction)
    # Kapasitas = 3. Isi saat ini: tx0 (tip 10), tx1_success_rbf (tip 20), tx2 (tip 15).
    # Buat akun lain dan kirim tx dengan tip sangat tinggi (tip 40)
    external_addr = "0xExternalAgent"
    mempool.set_account_state(external_addr, nonce=0, balance=500_000)
    tx_whale = Transaction(
        sender=external_addr,
        nonce=0,
        to="0xVault",
        value=5000,
        gas_limit=50000,
        max_fee_per_gas=100,
        max_priority_fee_per_gas=40,
        payload=b"action=flash_arbitrage",
        signature=generate_sig(external_addr, 0)
    )
    success, reason = await mempool.add_transaction(tx_whale, base_fee)
    logger.info("Whale Transaction Eviction Test: %s | Result: %s", success, reason)
    logger.info("Final Pool Metrics: %s", mempool.dump_metrics())

    # Ekstraksi batch untuk blok
    executable_block = mempool.get_executable_batch(current_base_fee=base_fee)
    logger.info("Transaksi yang masuk ke blok (Sorted by Tip):")
    for idx, tx in enumerate(executable_block):
        logger.info("  Index [%d] Hash: %s... | Tip: %d", idx, tx.hash[:12], tx.calculate_effective_tip(base_fee))


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Pada level infrastruktur terdistribusi, kegagalan jaringan dan transaksi memunculkan skenario kritis berikut:

| Skenario Kerusakan | Akar Masalah | Mekanisme Deteksi | Mitigasi Node & Agent Level |
| :--- | :--- | :--- | :--- |
| **Nonce Gaps Stalling** | Agen mengirim Tx dengan Nonce $N+2$, tetapi Tx dengan Nonce $N+1$ di-drop di tingkat P2P. | Transaksi tersendat di `Queued Pool` tanpa batas waktu; transaksi selanjutnya terblokir. | Agen mengimplementasikan *heartbeat watch* yang memeriksa `txpool_content`. Jika dalam batas waktu $T$ tidak tervalidasi, kirimkan transaksi *noop* (0 ETH ke diri sendiri) dengan Nonce $N+1$. |
| **Transaction Invalidation via State Drift** | Saldo on-chain akun berkurang akibat eksekusi kontrak pintar lain sebelum transaksi dieksekusi. | Node melempar error `insufficient funds for gas * price + value` saat transaksi ditarik ke pending pool. | Node langsung membuang transaksi tersebut dari mempool saat header blok baru tiba. Agen harus melacak *virtual pending balance*. |
| **Eclipse Attack (P2P)** | Penyerang mengisolasi node korban dengan mengisi seluruh koneksi TCP masuk/keluar menggunakan IP berbahaya. | Node tidak menerima blok baru, $k$-bucket hanya berisi IP dari satu subnet / ASN yang sama. | Menerapkan *peer diversity constraints*: batasi koneksi maksimal per `/16` IPv4 subnet, gunakan protokol *peer exchange* terenkripsi (Discv5), pertahankan koneksi *static bootnode* tepercaya. |
| **Mempool Bloat / DoS** | Aktor jahat membanjiri jaringan dengan jutaan transaksi bertip nol atau minimum fee. | Penggunaan RAM node melesat melampaui ambang batas fisik (OOM Killer). | Tetapkan batas ketat alokasi memori fisik untuk mempool (`--txpool.totalslots`), serta naikkan kriteria minimum *gas price acceptance* secara dinamis saat memori menipis. |
| **Transaction Underpriced Replacement** | Agen mencoba mempercepat transaksi dengan mengirimkan hash baru tetapi menaikkan gas tip di bawah persentase ambang batas (misal hanya +2%). | Node merespons dengan pesan JSON-RPC: `replacement transaction underpriced`. | Agen harus memprogram kalkulasi bump secara matematis: $\text{Fee}_{\text{new}} \ge \lceil \text{Fee}_{\text{old}} \times 1.12 \rceil$. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap keputusan perancangan node dan perutean transaksi memiliki kompromi arsitektural:

```
                  ARSITEKTUR TRANSMISI TRANSAKSI
                               |
        +----------------------+----------------------+
        |                                             |
   Public Mempool                              Private Relay (MEV-Boost/PBS)
   (P2P Gossip Network)                        (Direct RPC Bundles)
        |                                             |
  [Kelebihan]                                   [Kelebihan]
  - Sangat Terdesentralisasi                    - Kebal Sandwitch/Front-running
  - Ketersediaan Tinggi (Fault Tolerant)        - Eksekusi 0-latensi ke Proposer
  - Tanpa Izin (Permissionless)                 - Jaminan Revert Tidak Bayar Gas
        |                                             |
  [Kekurangan]                                  [Kekurangan]
  - Rawan MEV Searcher & Arbitrage Exploitation - Sentralisasi Relay Relatif Tinggi
  - Latensi Propagasi Lebih Lambat (1-3 dtk)    - Ketergantungan pada Proposer Terpilih
  - Biaya Gas Terbuang Jika Revert              - Sensor Transaksi Potensial
```

### 1. In-Memory Mempool vs. Persistent Disk Storage
- **In-Memory (Geth/Reth Default):** Akses berkecepatan mikrodetik ($\mu s$) untuk pencarian dan pembaruan antrean. Kelemahannya: saat node me-restart, seluruh transaksi non-konfirmasi akan hilang dari pool lokal dan harus ditangkap kembali melalui gossip peer.
- **Persistent Disk (BadgerDB/RocksDB Log):** Mempertahankan transaksi saat restart. Kelemahannya: menulis ke disk pada setiap transmisi gossip P2P memperlambat performa I/O node dan memperpendek masa pakai SSD enterprise melalui *write amplification*.

### 2. Full P2P Propagation vs. Private Bundles (PBS / Proposer-Builder Separation)
Bagi autonomous agent yang menjalankan kalkulasi bernilai tinggi, menggunakan *Public Mempool* menghadirkan risiko *information leakage*. Menggunakan *Private RPC Relay* (seperti Flashbots MEV-Share) menjamin bahwa transaksi tidak akan disiarkan ke P2P publik, melainkan langsung diteruskan ke *Block Builder*. Komprominya adalah jika builder tersebut tidak terpilih untuk memproduksi blok berikutnya, penyelesaian transaksi dapat tertunda selama beberapa slot.

---

## 9. Best Practices & Standar Industri

1. **Deterministic Nonce Management pada Multi-Agent Systems:**
   Hindari pemanggilan metode `eth_getTransactionCount` dengan tag `"latest"` pada setiap transaksi. Ini menimbulkan *race condition* jika beberapa thread agen mengirim transaksi secara bersamaan. Solusinya: bangun *in-memory Atomic Nonce Counter* terpusat pada service gateway agen yang mengelola status `"pending"`.

2. **Peer Scoring Tuning (DevP2P/Libp2p):**
   Pada jaringan privat atau sub-jaringan konsorsium, konfigurasi `--txpool.pricelimit` ke tingkat rasional untuk menghindari *spam*. Berikan whitelist (`--net.static-nodes`) pada node sesama kluster agen guna memastikan transmisi *zero-hop* tanpa filter gossip.

3. **Circuit Breaking & Gas Cap Safeguards:**
   Sertakan pengaman dinamis pada kode agen:
   - Tentukan `MaxPriorityFeePerGas` maksimal yang tidak boleh dilewati sekalipun terjadi persaingan lelang gas (*gas war*).
   - Terapkan mekanisme pembatalan darurat (*self-cancellation*) jika transaksi macet lebih dari $K$ blok melalui pengiriman transaksi zero-value ber-nonce identik dengan gas tip tinggi.

4. **Konektivitas RPC Tingkat Produksi:**
   Hindari penggunaan HTTP Polling untuk memonitor status transaksi. Gunakan koneksi murni **WebSocket (`ws://`)** atau **IPC socket (`.ipc`)** berbasis antrean event streaming (`eth_subscribe` dengan opsi `newPendingTransactions`).

---

## 10. Hands-on Lab Exercise

### Deskripsi Lab
Dalam lab ini, Anda akan mempraktikkan proses observasi dan manipulasi mempool lokal node:
1. Menjalankan node pengujian berbasis kontainer lokal.
2. Memonitor *pending transactions* secara langsung melalui protokol WebSocket.
3. Mensimulasikan *nonce gap lockup* pada autonomous agent.
4. Mengeksekusi intervensi transaksi menggunakan teknik *Replace-By-Fee (RBF)*.

### Langkah 1: Jalankan Local Mock Devnet (Anvil / Hardhat)
Buka terminal dan jalankan Anvil (bagian dari Foundry toolkit) dengan mengaktifkan pelacakan transaksi:
```bash
anvil --block-time 5 --port 8545
```
*Anvil mengeksekusi blok baru setiap 5 detik, memberikan jendela waktu visual untuk mengamati mempool.*

### Langkah 2: Script Observasi Mempool Real-time
Simpan kode berikut sebagai `mempool_watcher.py` dan jalankan pada terminal terpisah:
```python
import asyncio
import json
import websockets

async def watch_mempool():
    uri = "ws://127.0.0.1:8545"
    async with websockets.connect(uri) as ws:
        # Subscribe ke transaksi pending
        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_subscribe",
            "params": ["newPendingTransactions"]
        }
        await ws.send(json.dumps(subscribe_msg))
        response = await ws.recv()
        print(f"[Watcher Connected] Subscription ID: {response}")

        while True:
            try:
                msg = await ws.recv()
                tx_data = json.loads(msg)
                tx_hash = tx_data.get("params", {}).get("result")
                print(f"[Mempool Catch] Pending Tx Terdeteksi: {tx_hash}")
            except Exception as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    asyncio.run(watch_mempool())
```

### Langkah 3: Eksekusi Skenario Nonce-Lock & Solusi RBF
Jalankan script Python berikut (`agent_tx_rescue.py`) untuk memicu kondisi kegagalan dan memperbaikinya:
```python
import time
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
account = w3.eth.accounts[0] # Menggunakan funded test account
target_addr = w3.eth.accounts[1]

current_nonce = w3.eth.get_transaction_count(account, "latest")
print(f"Starting Nonce: {current_nonce}")

# 1. Simulasikan Nonce Gap: Kirim transaksi dengan Nonce + 1 secara sengaja
gap_tx = {
    'from': account,
    'to': target_addr,
    'value': w3.to_wei(0.1, 'ether'),
    'gas': 21000,
    'maxFeePerGas': w3.to_wei(20, 'gwei'),
    'maxPriorityFeePerGas': w3.to_wei(2, 'gwei'),
    'nonce': current_nonce + 1,
    'chainId': 31337
}
tx_hash_gap = w3.eth.send_transaction(gap_tx)
print(f"Tx Nonce Gap Terkirim (Stuck di Queued Pool): {tx_hash_gap.hex()}")

# 2. Kirim transaksi dengan Nonce yang tertinggal dengan Fee Rendah
slow_tx = {
    'from': account,
    'to': target_addr,
    'value': w3.to_wei(0.05, 'ether'),
    'gas': 21000,
    'maxFeePerGas': w3.to_wei(15, 'gwei'),
    'maxPriorityFeePerGas': w3.to_wei(1, 'gwei'),
    'nonce': current_nonce,
    'chainId': 31337
}
tx_hash_slow = w3.eth.send_transaction(slow_tx)
print(f"Tx Lambat Terkirim (Pending Pool): {tx_hash_slow.hex()}")

# 3. Lakukan RBF: Percepat transaksi Nonce saat ini dengan kenaikan Tip signifikan
time.sleep(1) # Tunggu sejenak sebelum menimpa
speedup_tx = {
    'from': account,
    'to': target_addr,
    'value': w3.to_wei(0.05, 'ether'),
    'gas': 21000,
    'maxFeePerGas': w3.to_wei(50, 'gwei'),           # Bump fee
    'maxPriorityFeePerGas': w3.to_wei(10, 'gwei'),     # Bump tip > 10%
    'nonce': current_nonce,                          # Nonce yang sama
    'chainId': 31337
}
tx_hash_speedup = w3.eth.send_transaction(speedup_tx)
print(f"RBF Speedup Tx Berhasil Terkirim: {tx_hash_speedup.hex()}")

# Tunggu konfirmasi blok
receipt = w3.eth.wait_for_transaction_receipt(tx_hash_speedup)
print(f"[Konfirmasi Sukses] Dimasukkan pada Blok: {receipt.blockNumber}")
```

### Evaluasi Lab
- Periksa konsol `mempool_watcher.py`: Verifikasi bahwa hash transaksi yang masuk sesuai dengan urutan pengiriman.
- Amati log Anvil: Pastikan transaksi RBF menggantikan hash transaksi yang lambat sebelum blok disegel, dan transaksi nonce gap yang semula tertahan langsung diproses pada blok yang sama begitu nonce pendahulunya tereksekusi.