# Modul 02: Arsitektur Node, Jaringan Peer-to-Peer, dan Rekayasa Subsistem Mempool

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan memiliki kapabilitas rekayasa tingkat lanjut untuk:

*   **Menganalisis dan Membedah Arsitektur Node Tingkat Lanjut:** Menguraikan dekomposisi modular antara *Consensus Layer* (CL), *Execution Layer* (EL), dan *Engine API* (EIP-3675/EIP-3860), serta mekanisme sinkronisasi *state* (*State Sync*, *Snap Sync*, *Flat State DB*).
*   **Merancang dan Mengimplementasikan Protokol P2P Terdistribusi:** Mengonfigurasi dan mengoptimalkan primitif jaringan *peer-to-peer* berbasis **libp2p** dan **DevP2P**, termasuk struktur routing Kademlia DHT (*Distributed Hash Table*), protokol propagasi Gossipsub v1.1, mitigasi *Sybil/Eclipse attacks*, dan kontrol topologi *overlay network*.
*   **Membangun Engine Mempool Skala Produksi:** Mengembangkan sistem penampungan transaksi (*transaction pool*) konkuren performa tinggi (*thread-safe*) menggunakan bahasa pemrograman sistem (Go/Rust) dengan algoritma pengurutan prioritas gas dinamis, pelacakan *nonce state per-account*, dan evaluasi *eviction policy* serta *Replace-by-Fee* (RBF).
*   **Menerapkan Strategi Mitigasi MEV dan Vektor Serangan DoS:** Menganalisis risiko kebocoran data transaksi (*front-running*, *sandwich attacks*), membedakan jalur transaksi publik vs privat (*Flashbots Protect*, *builder endpoints*), dan menerapkan pembatasan *rate limiting* berbasis komputasi kriptografis (*Proof-of-Work puzzles* atau *stake-weighted gossip*).

---

## 2. Prerequisites & Assumptions

Sebelum mendalami modul ini, arsitek sistem diasumsikan telah menguasai:

*   **Pemrograman Sistem Konkuren:** Pemahaman mendalam tentang *memory model*, *mutex*, *read-write locks*, *channels/actor model*, dan struktur data berbasis *heap/priority queue* pada Go atau Rust.
*   **Jaringan Komputer Lanjutan:** Pemahaman terhadap *TCP/IP stack*, protokol *transport* UDP, multiplexing (QUIC, Yamux), NAT traversal (*STUN, TURN, ICE, UPnP*), dan enkripsi sesi (*Noise Protocol Framework*, RLPx, TLS 1.3).
*   **Kriptografi Dasar Blockchain:** Struktur *hash* (Keccak-256, SHA-256), kurva eliptis (*ECDSA secp256k1*, *BLS12-381*), format serialisasi biner (*RLP, SSZ, Protobuf*), dan struktur data pohon (*Merkle Patricia Trie*, *Verkle Tree*).

---

## 3. Concept & Internal Architecture

Node blockchain bukanlah aplikasi monolitik tunggal, melainkan sistem terdistribusi heterogen yang memadukan penyimpanan persisten performa tinggi, orkestrasi konsensus, mesin virtual deterministik (*EVM/Wasm*), dan lapisan jaringan *gossip* terdesentralisasi.

```
+---------------------------------------------------------------------------------------+
|                                    BLOCKCHAIN NODE                                    |
|                                                                                       |
|  +-----------------------------------+     Engine API (RPC)   +--------------------+  |
|  |     CONSENSUS LAYER (CL)          |<======================>|   EXECUTION LAYER  |  |
|  |  (Beacon Node - PoS, Fork Choice) |     (JWT Auth, IPC)    |   (Geth/Besu/Nether)  |  |
|  +-----------------+-----------------+                        +---------+----------+  |
|                    |                                                    |             |
|          Libp2p / Gossipsub                                       DevP2P / RLPx       |
|                    |                                                    |             |
+--------------------+----------------------------------------------------+-------------+
                     |                                                    |
                     v                                                    v
         [CL Peers: Attestations]                             [EL Peers: Tx Propagation]
                     |                                                    |
                     +------------------+     +---------------------------+
                                        |     |
                                        v     v
                            +--------------------------+
                            |       P2P NETWORK        |
                            | (Kademlia DHT, Discovery)|
                            +--------------------------+
```

### 3.1. Dekomposisi Node: Execution Layer (EL) vs. Consensus Layer (CL)

Pasca-The Merge (Ethereum) dan pada arsitektur modern (misal: Avalanche, Celestia, rollups modular), abstraksi komputasi dipisahkan dari abstraksi konsensus:

1.  **Execution Layer (EL):** Bertanggung jawab atas pemrosesan dan validasi transaksi, manajemen *state transition*, eksekusi kode *smart contract* via EVM, pengelolaan penyimpanan lokal (*State DB, History DB*), dan subsistem **Mempool** (antrean transaksi lokal).
2.  **Consensus Layer (CL):** Mengoperasikan mekanisme penentuan cabang terpanjang (*fork-choice rule*, misal: LMD-GHOST), pengelolaan finalitas (*Casper FFG*), pelacakan validator aktif, dan koordinasi *proposer-builder separation* (PBS).
3.  **Engine API:** Lapisan komunikasi asinkron berbasis JSON-RPC aman (terautentikasi melalui *symmetric secret* JWT-HMAC-SHA256) yang menjembatani EL dan CL. API ini mencakup *endpoint* kritis seperti:
    *   `engine_forkchoiceUpdated`: Menginstruksikan EL untuk memperbarui *head block*, finalitas *block*, dan opsional memulai *block building pipeline*.
    *   `engine_newPayload`: Mengirimkan payload blok baru dari jaringan CL ke EL untuk divalidasi transaksinya dan diverifikasi akar *state*-nya (*state root*).
    *   `engine_getPayload`: Mengambil payload eksekusi yang telah dirangkai oleh EL untuk disebarkan oleh CL *proposer*.

### 3.2. Topologi Jaringan Peer-to-Peer: Kademlia DHT, DevP2P, dan Libp2p

Jaringan *peer-to-peer* blockchain mengandalkan topologi *unstructured* dan *structured overlay*:

#### Kademlia DHT (Discovery Phase)
Protokol pencarian node (*node discovery*, misal: `discv4`, `discv5`) berbasis Kademlia. Setiap node memiliki ID 256-bit atau 512-bit (dari public key). Jarak metrik antar-node dihitung menggunakan operasi bitwise XOR:
$$d(x, y) = x \oplus y$$
Node mengorganisir *peers* ke dalam *k-buckets* berdasarkan rentang jarak $2^i \le d(x, y) < 2^{i+1}$. Mekanisme ini memastikan pencarian node manapun dalam jaringan skala $N$ dapat diselesaikan dalam $O(\log N)$ hop. Pada `discv5`, protokol berjalan di atas UDP dan menyertakan enkripsi berbasis *session keys* dengan pesan `FINDNODE`, `NODES`, `PING`, dan `PONG`.

#### Lapisan Transportasi & Framing Data (DevP2P vs Libp2p)
*   **DevP2P (RLPx):** Protokol enkripsi berbasis sesi di atas TCP yang menggunakan *ECIES (Elliptic Curve Integrated Encryption Scheme)* untuk *handshake* awal, kemudian dinegosiasikan ke enkripsi simetris AES-256-GCM atau ChaCha20-Poly1305. RLPx membagi transmisi data ke dalam *frames* berlapis yang memungkinkan multiplexing berbagai protokol sub-spesifik (misal: `eth/66`, `eth/67`, `snap/1`).
*   **Libp2p (Modular Network Stack):** Digunakan secara ekstensif pada Consensus Client dan jaringan terdistribusi modern. Mengandalkan transport fleksibel (TCP, QUIC, WebSocket), modularitas negosiasi keamanan (Noise Protocol, TLS 1.3), stream multiplexing (Yamux, Mplex), dan deteksi *peer routing* modular.

#### Gossipsub v1.1
Mekanisme transmisi data berskala besar (*mesh-based pub-sub*). Alih-alih melakukan *flooding* buta yang menghabiskan *bandwidth* $O(N \cdot M)$ di mana $N$ adalah jumlah node dan $M$ koneksi, Gossipsub membangun topologi *mesh* dinamis berderajat terikat ($D_{low} \le D \le D_{high}$, umumnya $6 \le D \le 12$).
*   **Graft/Prune:** Pesan kontrol untuk menambahkan atau menghapus node dari *mesh* topik tertentu.
*   **IHAVE/IWANT:** Metadata ringkas yang mengiklankan ketersediaan pesan tanpa membebani jaringan dengan *full payload*.
*   **Peer Scoring:** Mekanisme defensif multi-parameter (P1 hingga P7) yang menilai reputasi peer berdasarkan waktu respons, validitas pesan, dan kepatuhan pengiriman. Peer dengan skor negatif diputus (*pruned*), memitigasi serangan DoS dan spam secara otonom.

---

## 4. Why & What: Permasalahan Arsitektur Mempool

Mempool (*Memory Pool*) adalah subsistem memori non-standar non-konsensus yang bertindak sebagai ruang tunggu *staging* bagi transaksi valid sebelum dikemas ke dalam blok oleh *proposer/miner*.

### Masalah yang Dihadapi (Why)
1.  **Memory Exhaustion (DoS Attack):** Penyerang dapat menyemburkan jutaan transaksi dengan *fee* minimal untuk membuat node kehabisan RAM (*OOM Kill*).
2.  **Nonce Dependency Graphs:** Pada sistem berbasis akun (*Ethereum-like*), transaksi dari akun tertentu harus dieksekusi secara berurutan sesuai $Nonce, Nonce+1, Nonce+2$. Munculnya celah (*nonce gap*) menyebabkan transaksi berikutnya terhenti (*stalled*).
3.  **MEV Exploitation (Mempool Transparency):** Pengeksposan transaksi mentah ke publik memungkinkan bot pencari MEV (*Maximal Extractable Value*) melakukan serangan arbitrase manipulatif (*front-running*, *back-running*, *sandwiching*).
4.  **State Desynchronization & Reorgs:** Ketika terjadi reorganisasi rantai (*chain reorg*), transaksi dari blok yang dibatalkan harus dikembalikan ke Mempool secara aman tanpa merusak struktur antrean yang ada.

### Definisi dan Karakteristik Solusi (What)
Arsitektur Mempool tingkat lanjut membagi antrean menjadi dua kompartemen terisolasi:
*   **Pending Pool:** Transaksi yang siap dieksekusi segera (semua nonce pendahulu telah terpenuhi, balance mencukupi, gas limit valid).
*   **Queued (Future) Pool:** Transaksi yang belum bisa dieksekusi karena adanya celah nonce (*nonce gap*) atau balance yang tidak mencukupi untuk gas saat ini.

Mempool harus mengimplementasikan:
1.  **Replace-by-Fee (RBF):** Mekanisme penggantian transaksi macet dengan transaksi baru ber-nonce identik tetapi memiliki gas tip/fee signifikan lebih tinggi ($fee_{new} \ge fee_{old} \times (1 + \Delta_{min})$).
2.  **Eviction Engine Berbasis Bi-directional Heap:** Ketika mempool mencapai ambang batas kapasitas memori maksimum, sistem harus secara otomatis melakukan *eviction* (pendepakan) terhadap transaksi dengan prioritas ekonomi terendah (*lowest gas price / tip*), bukan transaksi tertua.

---

## 5. How: Alur Kerja Siklus Transaksi dan Propagasi Jaringan

Berikut adalah alur hidup end-to-end transaksi dari RPC Ingress hingga masuk ke blok:

```
[Client RPC / Wallet] 
        | (eth_sendRawTransaction)
        v
+-----------------------------------------------------------+
| Execution Client: Ingress Stage                           |
| 1. Deserialisasi RLP/EIP-2718                             |
| 2. Validasi Kriptografis (ECDSA Signature ecrecover)      |
| 3. Validasi Sintaktis (Intrinsic Gas, ChainID)            |
+-----------------------------------------------------------+
        |
        v
+-----------------------------------------------------------+
| Mempool Ingestion & Processing Pipeline                   |
| 1. Cek Balance >= (Value + GasLimit * MaxFee)             |
| 2. Evaluasi Nonce:                                        |
|    - Nonce == Account.StateNonce -> Insert PENDING Heap   |
|    - Nonce >  Account.StateNonce -> Insert QUEUED List    |
|    - Nonce <  Account.StateNonce -> Reject (Nonce too low)|
| 3. Evaluasi RBF (Jika Nonce Identik sudah ada)            |
| 4. Cek Mempool Limits -> Evict lowest fee jika penuh      |
+-----------------------------------------------------------+
        |
        v
+-----------------------------------------------------------+
| Network Propagation Engine                                |
| 1. Tandai Tx Hash di Bloom Filter Peer Lokal              |
| 2. Sebarkan Announce Hash (eth/66 Msg Type: NewPooledTx)  |
| 3. Remote Peer membalas via GetPooledTransactions         |
| 4. Broadcast Full Tx Payload ke sub-set peer (Mesh P2P)   |
+-----------------------------------------------------------+
        |
        v
+-----------------------------------------------------------+
| Block Building / Proposer Phase                           |
| 1. Engine API: engine_getPayload                          |
| 2. Tarik top-K transaksi dari Pending Heap                |
| 3. Eksekusi pada EVM State Transition                     |
| 4. Generate State Root, Receipt Root, Block Header        |
+-----------------------------------------------------------+
```

1.  **Ingress:** RPC endpoint menerima payload heksadesimal mentah. Thread parser mendeserialisasi *byte array* ke struktur data `Transaction`. Public key dipulihkan menggunakan Keccak-256 dan operasi `ecrecover` untuk mendapatkan alamat pengirim (`Sender address`).
2.  **Admission Control:** Node memeriksa *state view* terkini melalui database flat/cache. Transaksi ditolak instan apabila:
    *   Ukuran data payload melebihi ambang batas ukuran data transaksi (misal: 128 KB).
    *   Intrinsic gas komputasi transaksi ($21000 + 4 \times zero\_bytes + 16 \times non\_zero\_bytes + execution\_cost$) melebihi parameter gas limit transaksi.
    *   Pengirim tidak memiliki alokasi native token yang mencukupi.
3.  **Mempool State Mutation:** Lock konkurensi diakuisisi secara eksklusif (atau menggunakan struktur *fine-grained per-account lock*). Transaksi dimasukkan ke antrean terurut.
4.  **Network Gossip:** Transaksi tidak dibroadcast penuh ke ribuan node sekaligus. Node hanya mengumumkan hash transaksi kepada tetangga (*announcement-based gossip*). Tetangga yang belum memiliki transaksi tersebut di mempool lokalnya akan mengirimkan request balik `GetPooledTransactions`. Ini menghemat *uplink bandwidth* hingga 90%.

---

## 6. Analogy & Diagram ASCII: Dynamic Transaction Pipeline

Bayangkan bandara internasional super sibuk dengan protokol keamanan mutlak:

*   **P2P Network = Radar & Jalur Udara ATC:** Mengatur koordinasi antar bandara tanpa otoritas terpusat. Jika jalur padat, pesan status penerbangan dibagikan secara hemat kapasitas melalui sinyal radar ringkas (*Hash announcement*), bukan laporan manifes penuh.
*   **Pending Pool = Landasan Pacu (Active Runway):** Pesawat yang seluruh penumpangnya siap, dokumen lengkap, dan berada pada antrean nomor penerbangan yang tepat (*consecutive nonces*).
*   **Queued Pool = Ruang Tunggu Terminal (Terminal Lounge):** Pesawat yang izin terbangnya tertunda karena nomor penerbangan sebelumnya belum mendarat (*nonce gap*).
*   **Eviction Engine = Biaya Parkir Pesawat:** Jika kapasitas apron parkir penuh, otoritas bandara mendepak pesawat dengan biaya sewa termurah (*lowest gas fee*) untuk memberikan ruang bagi maskapai yang bersedia membayar tarif tinggi (*RBF replacement*).

```
   ====================== MEMPOOL STORAGE BUFFER ======================
   Capacity Limit: N Transactions / M MegaBytes
  
   +------------------------------------------------------------------+
   |                        PENDING POOL                              |
   |              (Ready for Block Proposal Assembly)                 |
   |                                                                  |
   |   Account 0xAAA:  [Nonce 10] -> [Nonce 11] -> [Nonce 12]         |
   |   Account 0xBBB:  [Nonce 01]                                     |
   |   Account 0xCCC:  [Nonce 45] -> [Nonce 46]                       |
   |                                                                  |
   |  Priority Matrix: Max Priority Fee Per Gas (Max-Heap Order)      |
   |  +------------------------------------------------------------+  |
   |  | [0xBBB: Nonce 01] (Fee: 150 Gwei)                          |  |
   |  | [0xAAA: Nonce 10] (Fee: 120 Gwei)                          |  |
   |  | [0xCCC: Nonce 45] (Fee: 80 Gwei)                           |  |
   |  +------------------------------------------------------------+  |
   +------------------------------------------------------------------+
                                   ^
                                   | (Promoted when Nonce 02 arrives)
   +------------------------------------------------------------------+
   |                         QUEUED POOL                              |
   |                 (Stalled by Nonce Gaps)                          |
   |                                                                  |
   |   Account 0xBBB:  [Nonce 03] (Waiting for Nonce 02)              |
   |   Account 0xDDD:  [Nonce 88] (Waiting for Nonce 87)              |
   |                                                                  |
   |   Eviction Policy: Discard lowest tip if Queue Max Limit hit     |
   +------------------------------------------------------------------+
   ====================================================================
```

---

## 7. Simple & Practical Implementation: Enterprise Mempool Core

Berikut adalah implementasi Go skala produksi untuk subsistem **Mempool Core Engine**. Kode ini mencakup struktur data *thread-safe*, *nonce-tracking*, integrasi *Max-Heap* berbasis prioritas biaya (*gas tip*), penggantian *Replace-by-Fee* (RBF), dan *eviction policy*.

```go
package main

import (
	"container/heap"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"math/big"
	"sync"
	"time"
)

// Definisi Error Domain Mempool
var (
	ErrNonceTooLow          = errors.New("mempool: transaction nonce lower than account state nonce")
	ErrInsufficientBalance  = errors.New("mempool: account balance insufficient to cover max cost")
	ErrReplacementUnderpriced = errors.New("mempool: replacement transaction underpriced (RBF threshold not met)")
	ErrMempoolFull          = errors.New("mempool: transaction pool is at hard capacity")
)

// Transaction mewakili representasi EIP-1559 transaction pada internal mempool
type Transaction struct {
	Hash        [32]byte
	From        string
	To          string
	Nonce       uint64
	Value       *big.Int
	GasLimit    uint64
	GasTipCap   *big.Int // Max Priority Fee per Gas
	GasFeeCap   *big.Int // Max Total Fee per Gas
	Payload     []byte
	ReceivedAt  time.Time
	HeapIndex   int // Diperlukan untuk modul Heap container
}

// AccountState simulasi abstraksi snapshot state dari Execution Database
type AccountState struct {
	Nonce   uint64
	Balance *big.Int
}

// TxPriorityQueue mengimplementasikan heap.Interface untuk pengurutan prioritas tip tertinggi
type TxPriorityQueue []*Transaction

func (pq TxPriorityQueue) Len() int           { return len(pq) }
func (pq TxPriorityQueue) Less(i, j int) bool {
	// Urutkan descending: Transaksi dengan GasTipCap lebih besar diletakkan di indeks 0
	return pq[i].GasTipCap.Cmp(pq[j].GasTipCap) > 0
}
func (pq TxPriorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].HeapIndex = i
	pq[j].HeapIndex = j
}
func (pq *TxPriorityQueue) Push(x interface{}) {
	n := len(*pq)
	item := x.(*Transaction)
	item.HeapIndex = n
	*pq = append(*pq, item)
}
func (pq *TxPriorityQueue) Pop() interface{} {
	old := *pq
	n := len(old)
	item := old[n-1]
	old[n-1] = nil // Avoid memory leak
	item.HeapIndex = -1
	*pq = old[0 : n-1]
	return item
}

// EnterpriseMempool mengelola antrean transaksi concurrent secara granular
type EnterpriseMempool struct {
	mu           sync.RWMutex
	capacity     int
	rbfBumpRatio int64 // Ambang batas minimum kenaikan gas fee untuk RBF (dalam persen, misal: 10%)
	
	// Lookup indeks
	allTxs       map[[32]byte]*Transaction
	pendingTxs   map[string]map[uint64]*Transaction // From Address -> Nonce -> Tx
	queueTxs     map[string]map[uint64]*Transaction // From Address -> Nonce -> Tx
	priorityHeap TxPriorityQueue

	// State Provider mock (di produksi dihubungkan ke FlatKV / Trie State)
	stateDB map[string]*AccountState
}

// NewEnterpriseMempool menginisialisasi instansiasi pool baru
func NewEnterpriseMempool(capacity int, rbfBumpRatio int64) *EnterpriseMempool {
	pq := make(TxPriorityQueue, 0)
	heap.Init(&pq)
	return &EnterpriseMempool{
		capacity:     capacity,
		rbfBumpRatio: rbfBumpRatio,
		allTxs:       make(map[[32]byte]*Transaction),
		pendingTxs:   make(map[string]map[uint64]*Transaction),
		queueTxs:     make(map[string]map[uint64]*Transaction),
		priorityHeap: pq,
		stateDB:      make(map[string]*AccountState),
	}
}

// SetMockAccountState menyuntikkan data dummy untuk pengujian unit deterministik
func (mp *EnterpriseMempool) SetMockAccountState(addr string, nonce uint64, balance *big.Int) {
	mp.mu.Lock()
	defer mp.mu.Unlock()
	mp.stateDB[addr] = &AccountState{Nonce: nonce, Balance: balance}
}

// AddRemoteTransaction melakukan pipeline validasi ketat dan memasukkan tx ke pool
func (mp *EnterpriseMempool) AddRemoteTransaction(tx *Transaction) error {
	mp.mu.Lock()
	defer mp.mu.Unlock()

	// 1. Cek duplikasi identik
	if _, exists := mp.allTxs[tx.Hash]; exists {
		return nil // Abaikan secara idempoten jika transaksi sudah terdaftar
	}

	// 2. Verifikasi terhadap State Database terkini
	state, exists := mp.stateDB[tx.From]
	if !exists {
		// Asumsi state baru jika belum ada record
		state = &AccountState{Nonce: 0, Balance: big.NewInt(0)}
		mp.stateDB[tx.From] = state
	}

	if tx.Nonce < state.Nonce {
		return ErrNonceTooLow
	}

	// Hitung kalkulasi pembebanan saldo maksimum (Cost = Value + GasLimit * GasFeeCap)
	maxCost := new(big.Int).Mul(tx.GasFeeCap, new(big.Int).SetUint64(tx.GasLimit))
	maxCost.Add(maxCost, tx.Value)
	if state.Balance.Cmp(maxCost) < 0 {
		return ErrInsufficientBalance
	}

	// 3. Evaluasi Replace-By-Fee (RBF)
	if existingTx, exists := mp.findTxBySenderNonce(tx.From, tx.Nonce); exists {
		// Hitung persentase batas ambang kenaikan fee: NewTip >= OldTip * (100 + Bump) / 100
		threshold := new(big.Int).Mul(existingTx.GasTipCap, big.NewInt(100+mp.rbfBumpRatio))
		threshold.Div(threshold, big.NewInt(100))

		if tx.GasTipCap.Cmp(threshold) < 0 {
			return ErrReplacementUnderpriced
		}

		// Valid RBF: Singkirkan transaksi lama dari antrean
		mp.removeTxInternal(existingTx)
	}

	// 4. Evaluasi Batas Kapasitas Mempool & Eksekusi Eviction
	if len(mp.allTxs) >= mp.capacity {
		if !mp.evictLowestTipTx(tx.GasTipCap) {
			return ErrMempoolFull
		}
	}

	// 5. Ingestion ke Jalur Pending vs Queued
	currentExpectedNonce := state.Nonce
	if pendingMap, ok := mp.pendingTxs[tx.From]; ok && len(pendingMap) > 0 {
		// Cari nonce maksimum di antrean pending
		for n := range pendingMap {
			if n >= currentExpectedNonce {
				currentExpectedNonce = n + 1
			}
		}
	}

	if tx.Nonce == currentExpectedNonce {
		// Transaksi memenuhi sekuensial nonce: Masuk ke Pending Pool
		if _, ok := mp.pendingTxs[tx.From]; !ok {
			mp.pendingTxs[tx.From] = make(map[uint64]*Transaction)
		}
		mp.pendingTxs[tx.From][tx.Nonce] = tx
		heap.Push(&mp.priorityHeap, tx)

		// Evaluasi apakah transaksi di queued pool sekarang dapat dipromosikan ke pending
		mp.promoteQueuedTransactions(tx.From, tx.Nonce+1)
	} else {
		// Ada celah nonce: Simpan sementara di Queued Pool
		if _, ok := mp.queueTxs[tx.From]; !ok {
			mp.queueTxs[tx.From] = make(map[uint64]*Transaction)
		}
		mp.queueTxs[tx.From][tx.Nonce] = tx
	}

	mp.allTxs[tx.Hash] = tx
	return nil
}

// promoteQueuedTransactions memindahkan transaksi yang gap-nya telah terisi ke pending pool
func (mp *EnterpriseMempool) promoteQueuedTransactions(sender string, nextExpectedNonce uint64) {
	queuedMap, exists := mp.queueTxs[sender]
	if !exists {
		return
	}

	curr := nextExpectedNonce
	for {
		tx, found := queuedMap[curr]
		if !found {
			break
		}

		// Pindahkan dari Queued ke Pending
		delete(queuedMap, curr)
		if mp.pendingTxs[sender] == nil {
			mp.pendingTxs[sender] = make(map[uint64]*Transaction)
		}
		mp.pendingTxs[sender][curr] = tx
		heap.Push(&mp.priorityHeap, tx)
		curr++
	}

	if len(queuedMap) == 0 {
		delete(mp.queueTxs, sender)
	}
}

// evictLowestTipTx mendepak transaksi dengan GasTip terendah jika tip transaksi baru lebih tinggi
func (mp *EnterpriseMempool) evictLowestTipTx(newTxTip *big.Int) bool {
	if mp.priorityHeap.Len() == 0 {
		return false
	}

	// Indeks paling belakang dari array heap memiliki prioritas relatif lebih rendah
	// Catatan: Pada binary heap, elemen terendah ada di antara daun (leaf nodes).
	// Untuk implementasi skala enterprise optimal, dual-index heap (Min-Max) direkomendasikan.
	// Di sini kita ambil elemen terakhir antrean sebagai heuristik pembersihan.
	lowestTx := mp.priorityHeap[mp.priorityHeap.Len()-1]

	if newTxTip.Cmp(lowestTx.GasTipCap) <= 0 {
		return false // Transaksi baru memiliki insentif lebih rendah daripada yang paling murah saat ini
	}

	// Depak elemen terendah
	heap.Remove(&mp.priorityHeap, lowestTx.HeapIndex)
	mp.removeTxInternal(lowestTx)
	return true
}

// findTxBySenderNonce mencari transaksi dengan pengirim dan nonce yang ditentukan
func (mp *EnterpriseMempool) findTxBySenderNonce(sender string, nonce uint64) (*Transaction, bool) {
	if pMap, ok := mp.pendingTxs[sender]; ok {
		if tx, exists := pMap[nonce]; exists {
			return tx, true
		}
	}
	if qMap, ok := mp.queueTxs[sender]; ok {
		if tx, exists := qMap[nonce]; exists {
			return tx, true
		}
	}
	return nil, false
}

// removeTxInternal membersihkan referensi transaksi dari internal state
func (mp *EnterpriseMempool) removeTxInternal(tx *Transaction) {
	delete(mp.allTxs, tx.Hash)
	if pMap, ok := mp.pendingTxs[tx.From]; ok {
		delete(pMap, tx.Nonce)
		if len(pMap) == 0 {
			delete(mp.pendingTxs, tx.From)
		}
	}
	if qMap, ok := mp.queueTxs[tx.From]; ok {
		delete(qMap, tx.Nonce)
		if len(qMap) == 0 {
			delete(mp.queueTxs, tx.From)
		}
	}
}

// ExtractBestPendingTransactions mengekstraksi transaksi siap bungkus untuk perakitan blok
func (mp *EnterpriseMempool) ExtractBestPendingTransactions(limit int) []*Transaction {
	mp.mu.Lock()
	defer mp.mu.Unlock()

	var selected []*Transaction
	count := 0

	for mp.priorityHeap.Len() > 0 && count < limit {
		item := heap.Pop(&mp.priorityHeap).(*Transaction)
		selected = append(selected, item)
		mp.removeTxInternal(item)
		count++
	}

	return selected
}

func main() {
	mempool := NewEnterpriseMempool(100, 10) // Kapasitas 100 tx, 10% RBF minimum bump

	senderAddr := "0x71C95911E9a5D330f4D621450a2404F7Ce40f3Ca"
	mempool.SetMockAccountState(senderAddr, 0, big.NewInt(1000000000000000000)) // 1 ETH

	// 1. Injeksi Transaksi Nonce 0 (Prioritas Normal)
	tx1 := &Transaction{
		Hash:       sha256.Sum256([]byte("tx1")),
		From:       senderAddr,
		Nonce:      0,
		Value:      big.NewInt(10000),
		GasLimit:   21000,
		GasTipCap:  big.NewInt(2000000000),  // 2 Gwei
		GasFeeCap:  big.NewInt(30000000000), // 30 Gwei
		ReceivedAt: time.Now(),
	}
	if err := mempool.AddRemoteTransaction(tx1); err != nil {
		fmt.Printf("Tx1 Error: %v\n", err)
	} else {
		fmt.Println("Tx1 (Nonce 0) sukses terdaftar di Pending Pool.")
	}

	// 2. Injeksi Transaksi Nonce 2 (Celah Nonce: Nonce 1 hilang)
	tx3 := &Transaction{
		Hash:       sha256.Sum256([]byte("tx3")),
		From:       senderAddr,
		Nonce:      2,
		Value:      big.NewInt(10000),
		GasLimit:   21000,
		GasTipCap:  big.NewInt(5000000000),  // 5 Gwei
		GasFeeCap:  big.NewInt(30000000000), // 30 Gwei
		ReceivedAt: time.Now(),
	}
	if err := mempool.AddRemoteTransaction(tx3); err != nil {
		fmt.Printf("Tx3 Error: %v\n", err)
	} else {
		fmt.Println("Tx3 (Nonce 2) masuk ke Queued Pool akibat Nonce Gap.")
	}

	// 3. Uji Replace-By-Fee (RBF) pada Nonce 0
	// Mencoba mengganti dengan kenaikan tip hanya 5% (di bawah batas 10%)
	tx1Underpriced := &Transaction{
		Hash:       sha256.Sum256([]byte("tx1_cheap_replacement")),
		From:       senderAddr,
		Nonce:      0,
		Value:      big.NewInt(10000),
		GasLimit:   21000,
		GasTipCap:  big.NewInt(2100000000), // Kenaikan cuma 5%
		GasFeeCap:  big.NewInt(30000000000),
		ReceivedAt: time.Now(),
	}
	err := mempool.AddRemoteTransaction(tx1Underpriced)
	fmt.Printf("Tx1 RBF Underpriced Hasil: %v\n", err) // Mengembalikan ErrReplacementUnderpriced

	// Mencoba mengganti dengan kenaikan tip 25% (Valid RBF)
	tx1ValidRBF := &Transaction{
		Hash:       sha256.Sum256([]byte("tx1_valid_replacement")),
		From:       senderAddr,
		Nonce:      0,
		Value:      big.NewInt(10000),
		GasLimit:   21000,
		GasTipCap:  big.NewInt(2500000000), // Naik 25%
		GasFeeCap:  big.NewInt(30000000000),
		ReceivedAt: time.Now(),
	}
	err = mempool.AddRemoteTransaction(tx1ValidRBF)
	fmt.Printf("Tx1 Valid RBF Hasil: %v (Sukses diganti)\n", err)

	// 4. Injeksi Transaksi Nonce 1 yang Menutup Celah (Promosi Otomatis Nonce 2)
	tx2 := &Transaction{
		Hash:       sha256.Sum256([]byte("tx2")),
		From:       senderAddr,
		Nonce:      1,
		Value:      big.NewInt(10000),
		GasLimit:   21000,
		GasTipCap:  big.NewInt(3000000000), // 3 Gwei
		GasFeeCap:  big.NewInt(30000000000),
		ReceivedAt: time.Now(),
	}
	mempool.AddRemoteTransaction(tx2)
	fmt.Println("Tx2 (Nonce 1) disuntikkan. Membuka blokir Queued Pool.")

	// 5. Ekstraksi Transaksi Terbaik untuk Perakitan Blok Baru
	blockPayload := mempool.ExtractBestPendingTransactions(10)
	fmt.Printf("\nPerakitan Blok: Berhasil mengekstrak %d transaksi berurutan sesuai prioritas:\n", len(blockPayload))
	for i, tx := range blockPayload {
		fmt.Printf("  [%d] Nonce: %d | Tip: %s Wei | Hash: %s\n",
			i, tx.Nonce, tx.GasTipCap.String(), hex.EncodeToString(tx.Hash[:8]))
	}
}
```

---

## 8. Real-World Case Study: Flashbots MEV-Boost & The Private Mempool Revolution

### Latar Belakang Masalah
Pada siklus pasar 2020–2021 di Ethereum Mainnet, mempool publik terbuka (*Public Mempool*) memicu fenomena destruktif: **Priority Gas Auctions (PGA)**. 

Ketika peluang arbitrase likuidasi atau DEX bernilai tinggi muncul, puluhan bot arbitrase MEV membanjiri jaringan p2p dengan transaksi yang mematok gas price ribuan Gwei. Dampaknya:
1.  **Kemacetan Masif Jaringan (Chain Congestion):** Blok dipenuhi transaksi arbitrase yang 95%-nya gagal dieksekusi (*reverted transactions*), menghabiskan kapasitas ruang blok dan menaikkan biaya gas untuk pengguna ritel.
2.  **Mempool Sniping & Vektor Front-Running:** Operator node yang tidak bermoral atau pencari MEV melakukan manipulasi urutan (*sandwich attack*) terhadap transaksi pertukaran token milik pengguna umum.
3.  **Instabilitas Konsensus (Time-Bandit Attacks):** Miner diinsentifkan untuk melakukan reorganisasi (*reorg*) blok historis yang baru ditambang demi merebut nilai MEV yang tertinggal.

### Solusi Arsitektural: MEV-Boost & Private Order Flow
Ekosistem Ethereum merekayasa ulang alur transaksi melalui **Proposer-Builder Separation (PBS)** di luar protokol (*out-of-protocol*) via `MEV-Boost`:

```
[Private Client/Wallet] 
        | (Private JSON-RPC)
        v
[MEV Searcher / User] 
        | (Signed Private Bundles)
        v
+-----------------------------------------------------------+
| MEV Relay / Block Builder (Off-Chain Private Mempool)     |
| 1. Memvalidasi transaksi secara private tanpa p2p gossip |
| 2. Menjalankan simulasi EVM paralel deterministik        |
| 3. Menyusun Full Block paling optimal secara profit      |
| 4. Membuka lelang ke Block Proposer via Engine API       |
+-----------------------------------------------------------+
        |
        v (Merkle Root + Execution Header)
[Consensus Proposer (Validator)] === (Sign Header) ===> [Deliver Payload to Chain]
```

### Hasil Rekayasa dan Metrik Produksi
*   **Zero P2P Leakage:** Transaksi yang dikirim via jalur *Flashbots Protect* atau *Private RPC* tidak pernah disebarkan (*gossiped*) melalui protokol DevP2P/Gossipsub. Transaksi langsung masuk ke mempool milik *Builder*.
*   **Pencegahan Revert On-Chain:** Builder hanya memasukkan bundel transaksi yang dijamin sukses melalui simulasi komputasi mendalam sebelum penyusunan blok.
*   **Pengurangan Beban Mempool:** Node publik menghemat kapasitas I/O disk dan RAM secara signifikan karena terhindar dari pemrosesan ratusan ribu transaksi *spam PGA*.

---

## 9. Trade-offs & Deep Engineering Analysis

| Dimensi Arsitektural | Desain P2P Murni (Pure Gossip Flooding) | Desain Relay Terisolasi (Private Relays/PBS) | Trade-Off & Analisis Konsekuensi |
| :--- | :--- | :--- | :--- |
| **Latensi Propagasi** | **Tinggi (~200ms - 1.5s)**: Terikat oleh latensi multi-hop gossip mesh dan verifikasi di setiap persinggahan peer. | **Sangat Rendah (<50ms)**: Menggunakan koneksi langsung via jalur pipa TCP/gRPC multiplexed teroptimasi. | Mengorbankan desentralisasi topologi demi kecepatan deterministik (kritis untuk HFT dan MEV). |
| **Resistensi Sensor** | **Maksimum**: Hampir mustahil memblokir transaksi secara global tanpa menundukkan 51% kekuatan jaringan. | **Rentan**: Entitas relay dan builder swasta rentan terhadap tekanan regulasi (misal: penyaringan OFAC). | Mempertahankan sifat tanpa sensor (*censorship-resistance*) membutuhkan jalur fallback wajib ke public mempool. |
| **Konsumsi Bandwidth & I/O** | **Tinggi ($O(N \cdot D)$)**: Node menerima pengumuman hash transaksi yang redundan dari beberapa peer yang terhubung. | **Minimal**: Hanya satu blok pra-rakit tunggal yang diunduh langsung saat menerima payload. | Beban konsumsi bandwidth node validator rumahan (*home staker*) meningkat tajam pada model gossip murni. |
| **Kebutuhan Memori (RAM)** | **Tinggi (Dynamic Heap Pools)**: Membutuhkan ratusan megabyte alokasi RAM konstan untuk mengelola queued & pending pools. | **Sangat Rendah**: Node eksekusi hanya menahan transaksi lokalnya sendiri tanpa memelihara transaksi global. | Risiko kebocoran memori (*OOM Crash*) tinggi saat lonjakan transaksi abnormal jika alokasi pool limit tidak dipatok kaku. |

---

## 10. Common Mistakes & Production Troubleshooting

### Kesalahan Desain Umum
1.  **Unbounded Mempool Memory Allocations:** Menggunakan map tanpa kapasitas hard-limit pada struktur memori dinamis. Ketika terjadi serangan *spam burst*, garbage collection Go/Rust akan tersendat, memicu *latency spike* pada eksekusi konsensus dan berujung pada *eviction* paksa dari sistem operasi (*OOM Killer*).
2.  **Deadlock pada Akses Concurrent State vs Mempool:** Mengunci `Mempool.Lock()` kemudian memanggil fungsi eksternal yang mencoba mengambil `StateDB.RLock()`, sementara di thread sinkronisasi blok terjadi kebalikannya: `StateDB.Lock()` mencoba mengakses `Mempool.RLock()`.
3.  **Tidak Memeriksa EIP-1559 Base Fee Dynamic Scaling:** Mengabaikan perhitungan `BaseFee` yang dapat melonjak 12.5% per blok secara eksponensial. Transaksi yang valid saat dimasukkan ke mempool dapat menjadi *stalled* secara permanen jika `GasFeeCap < BaseFee`.

### Troubleshooting Matrix Operasional

| Gejala Masalah (Issue) | Akar Masalah (Root Cause) | Prosedur Diagnostik & Solusi Remediasi |
| :--- | :--- | :--- |
| Node kehilangan *Peer Connection* secara drastis (Peer Count -> 0). | NAT Table terdistorsi, atau terkena *ban* reputasi akibat penalti **Gossipsub Peer Scoring**. | 1. Periksa metrik log: `peer_score_fuzz`.<br>2. Verifikasi port forwarding UDP (Discovery) dan TCP (RLPx/Libp2p).<br>3. Pastikan jam internal mesin tersinkronisasi via NTP (drift waktu > 500ms memicu auto-disconnect consensus peer). |
| Transaksi klien tersangkut status *Queued* berminggu-minggu. | Terjadi **Nonce Gap**; sebuah transaksi terdahulu gagal dipropagasi atau memiliki gas price di bawah batas eviksi. | 1. Jalankan kueri RPC `txpool_inspect` atau `parity_allTransactions`.<br>2. Identifikasi nonce terendah yang hilang.<br>3. Kirimkan transaksi baru bernilai 0 ETH dengan nonce identik yang hilang tersebut dan pasang nilai gas tip agresif. |
| Penggunaan memori RAM node melonjak linier hingga Crash. | Kebocoran memori pada *LRU Cache* transaksi atau pembersihan hash historis yang tidak lengkap pasca-reorg. | 1. Ambil pprof heap dump: `go tool pprof http://localhost:6060/debug/pprof/heap`.<br>2. Analisis alokasi pointer pada `allTxs` map.<br>3. Terapkan konfigurasi batas tegas: `--txpool.globalslots=5120 --txpool.globalqueue=1024`. |

---

## 11. Best Practices & Production Checklist

### Production Hardening Checklist
*   [ ] **Konfigurasi Batas Transaksi:** Tetapkan limit slot transaksi secara eksplisit (`--txpool.accountslots=16`, `--txpool.globalslots=4096`).
*   [ ] **Isolasi RPC Ingress:** Jangan pernah membuka RPC endpoint yang mengarah langsung ke node validator aktif. Pasang node *RPC Proxy Layer* (misal: HAProxy/Nginx + Envoy) dengan *rate-limiting* ketat di depan Execution Layer.
*   [ ] **Pengamanan Engine API:** Terapkan file secret JWT acak berkekuatan 256-bit dengan izin akses berkas terbatas (`chmod 600 jwt.hex`).
*   [ ] **Monitoring Gossipsub Scoring:** Ekspor metrik performa peer P2P ke Prometheus dashboard (Metrik: `libp2p_pubsub_peers`, `libp2p_pubsub_topics`, `p2p_peer_score`).
*   [ ] **Kebijakan Penggantian Fee (RBF Policy):** Terapkan ambang batas penggantian harga transaksi minimal $\ge 10\%$ untuk mencegah serangan DoS berbasis spam kalkulasi ulang mempool.

---

## 12. Hands-on Practice: Membangun Mock P2P Network & Mempool Inspection

### Direktori Kerja: `hands-on/m02/`

```bash
# Struktur Hands-on
hands-on/m02/
├── Makefile
├── docker-compose.yml
├── prometheus.yml
└── test-client/
    └── stress_test.go
```

### Langkah 1: Siapkan Konfigurasi Orkestrasi Jaringan Lokal

Simpan berkas berikut sebagai `docker-compose.yml`:

```yaml
version: '3.8'

services:
  execution-node-1:
    image: ethereum/client-go:v1.13.5
    container_name: execution-node-1
    command:
      - --dev
      - --http
      - --http.addr=0.0.0.0
      - --http.api=eth,net,web3,txpool,debug
      - --http.corsdomain=*
      - --txpool.globalslots=100
      - --txpool.pricelimit=1000000000
    ports:
      - "8545:8545"

  prometheus:
    image: prom/prometheus:v2.47.0
    container_name: mempool-monitor
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

### Langkah 2: Konfigurasi Monitoring Metrics

Simpan sebagai `prometheus.yml`:

```yaml
global:
  scrape_interval: 2s

scrape_configs:
  - job_name: 'geth-node'
    metrics_path: '/debug/metrics/prometheus'
    static_configs:
      - targets: ['execution-node-1:8545']
```

### Langkah 3: Eksekusi dan Verifikasi Status Mempool

Jalankan container menggunakan command berikut:
```bash
docker-compose up -d
```

Kirimkan kueri inspeksi mempool secara berkala menggunakan `curl`:
```bash
curl -X POST --data '{"jsonrpc":"2.0","method":"txpool_status","params":[],"id":1}' \
  -H "Content-Type: application/json" http://localhost:8545
```
Respon JSON akan memvalidasi volume transaksi yang tersaring di subsistem antrean:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "pending": "0x0",
    "queued": "0x0"
  }
}
```

---

## 13. Exercises

### Level Easy
1. Modifikasi kode implementasi Go pada Seksi 7 agar mencatat timestamp saat transaksi masuk, lalu tambahkan fungsi pembersihan yang otomatis menghapus transaksi berstatus *queued* yang umurnya telah melebihi batas waktu 3 jam (*TTL expiration*).
2. Tulis skrip bash berbasis `curl` untuk mengambil data `txpool_content` dari node lokal dan menampilkan seluruh daftar alamat pengirim (*sender addresses*) yang memiliki lebih dari dua transaksi berstatus pending.

### Level Medium
1. Kembangkan algoritma *Min-Max Heap* atau *Dual Index Priority Queue* pada modul Mempool Go di Seksi 7 untuk menggantikan proses pencarian linear saat melakukan *eviction*, sehingga pencarian transaksi dengan gas tip terendah memiliki performa deterministik $O(1)$ dan eksekusi penghapusan berkinerja $O(\log N)$.
2. Buat simulasi sederhana mekanisme propagasi pesan menggunakan konsep Gossipsub v1.1 di mana node akan memberikan penalti (*peer score downgrade*) kepada node tetangga yang mengirimkan transaksi berulang yang sebelumnya sudah ditandai invalid oleh filter lokal.

### Level Hard
1. Implementasikan modul filter berbasis **Counting Bloom Filter** konkuren untuk memvalidasi keberadaan hash transaksi pada lapisan P2P gossip. Pastikan modul ini mendukung operasi penambahan hash, pengecekan keanggotaan hash, serta pengurangan/penghapusan elemen saat blok baru terfinalisasi, dengan probabilitas *false positive* yang dibatasi secara ketat $\le 0.01\%$.

---

## 14. Real-World Architectural Challenge

### Konteks Skenario
Sebuah konsorsium bursa finansial enterprise sedang meluncurkan jaringan Layer-2 kompatibel EVM berbasis *Rollup* performa tinggi yang ditargetkan mampu memproses **20.000 transaksi per detik (TPS)** dengan latensi konfirmasi sub-detik (<250ms). 

### Kondisi Sistem Saat Uji Beban Berlangsung
*   Node Sequencer menerima semburan transaksi sebesar **85.000 request/detik** yang dikirimkan oleh ratusan bot likuidasi dan market maker frekuensi tinggi (HFT).
*   Arsitektur node Sequencer saat ini mulai mengalami kelumpuhan: Latensi garbage collection Go melompat dari 2ms ke 450ms, antrean RPC buffer meluap (*HTTP 429 Too Many Requests*), dan transaksi milik pengguna ritel ber-nonce valid tertahan di Queued Pool selama lebih dari 4 blok karena Sequencer kehabisan siklus CPU untuk memvalidasi urutan nonce.
*   Muncul indikasi eksploitasi di mana kelompok pencari MEV tertentu sengaja membombardir *unconfirmed transactions* dengan nonce yang melompati ribuan interval ($Nonce + 5000$) untuk memanipulasi alokasi memori Sequencer.

### Sasaran Tantangan
Rancang dokumen arsitektur dan spesifikasi teknis untuk merevisi subsistem **Transaction Ingestion Pipeline, P2P Ingress, dan Mempool Engine** Sequencer tersebut. Solusi Anda harus memuat:

1.  **Dekomposisi Struktur Data:** Desain arsitektur penyimpanan mempool in-memory yang mampu memproses operasi baca/tulis secara konkuren tanpa terkena *stop-the-world locks* saat throughput mencapai level puncak.
2.  **Mekanisme Nonce Pre-Allocation & Throttling:** Algoritma admission control untuk membatasi atau menolak seketika akun-akun yang menyemburkan transaksi *nonce-gap* dalam jumlah tidak wajar tanpa merusak performa throughput akun normal.
3.  **Topologi Jaringan Privat:** Rancang pemisahan gerbang transmisi data (*Data Ingress Topology*) antara transaksi HFT bervolume tinggi, transaksi pengguna reguler, dan sinkronisasi replikasi antar-Sequencer.
4.  **Kriteria Kegagalan (Failure Handling):** Rencana mitigasi deterministik jika Sequencer utama tiba-tiba mati (*crash-fault*) saat puluhan ribu transaksi masih berada di RAM mempool lokal tanpa sempat dituliskan ke state database persisten.

---

## 15. Evaluasi Pemahaman

### 15.1. Pertanyaan Konseptual Dasar (5 Soal)
1.  **Apakah Mempool merupakan bagian dari konsensus blockchain yang bersifat terikat secara deterministik antar seluruh node?**
    *   *Jawaban:* Tidak. Mempool adalah subsistem penyimpanan lokal non-konsensus. Tiap node memiliki konfigurasi batas ukuran, aturan toleransi gas minimum, dan daftar transaksi yang berbeda-beda tergantung topologi jaringan serta waktu penerimaan transaksi.
2.  **Apa perbedaan mendasar antara DevP2P RLPx dan libp2p dalam arsitektur node Ethereum modern?**
    *   *Jawaban:* DevP2P RLPx adalah protokol komunikasi transport/enkripsi warisan yang fokus digunakan pada *Execution Layer*, sedangkan libp2p adalah modular network stack modern yang digunakan pada *Consensus Layer* untuk mendukung Kademlia DHT yang lebih fleksibel dan Gossipsub v1.1.
3.  **Mengapa transaksi dengan nonce yang melompat (misal: nonce saat ini 5, namun yang dikirim nonce 7) dimasukkan ke Queued Pool dan bukan ke Pending Pool?**
    *   *Jawaban:* Karena eksekusi EVM bersifat stateful dan deterministik sequential. Transaksi dengan nonce 7 tidak dapat dieksekusi secara valid sebelum transaksi dengan nonce 6 dimasukkan ke dalam state tree.
4.  **Apa fungsi dari operasi bitwise XOR pada algoritma pencarian Kademlia DHT?**
    *   *Jawaban:* XOR digunakan sebagai metrik jarak matematis searah (*unidirectional distance metric*) abstrak antar-ID node. Sifat simetrisnya ($d(x,y) = d(y,x)$) memastikan konsistensi dalam penentuan kedekatan rute pencarian tanpa terpengaruh oleh topologi fisik jaringan.
5.  **Berapa persentase minimum kenaikan biaya tip gas standar pada mekanisme Replace-by-Fee (RBF) dan apa tujuan diterapkannya batas tersebut?**
    *   *Jawaban:* Umumnya minimal 10%. Batas ini diwajibkan untuk mencegah serangan komputasi DoS di mana penyerang berulang kali mengganti transaksi yang sama dengan selisih tip fraksional kecil hanya untuk membebani siklus CPU validator.

### 15.2. Pertanyaan Analisis Menengah (5 Soal)
6.  **Bagaimana mekanisme validasi peer scoring Gossipsub v1.1 mendeteksi dan mengisolasi node penyerang yang melakukan spamming payload transaksi invalid?**
    *   *Jawaban:* Gossipsub melacak metrik skor peer secara berkelanjutan berdasarkan parameter seperti pengiriman pesan valid pertama kali (P1), pengiriman pesan yang konsisten (P2), dan pengiriman pesan invalid (P4). Jika node mengirim payload yang gagal didekode atau invalid menurut EVM, bobot penalti negatif drastis diberikan pada P4, menjatuhkan skor peer di bawah ambang *graylist threshold*, sehingga pesan dari node tersebut akan diabaikan seketika.
7.  **Jelaskan skenario bagaimana sebuah reorganisasi rantai konsensus (chain reorganization) sepanjang 2 blok dapat mempengaruhi internal state dari Mempool!**
    *   *Jawaban:* Transaksi yang berada pada 2 blok yang dibatalkan harus dikembalikan ke Mempool agar tidak hilang. Nonce akun pengirim harus dihitung ulang mundur sesuai state blok kanonikal yang baru. Transaksi yang sebelumnya pending mungkin harus dipindahkan kembali ke queued jika ada transaksi pemicu yang ternyata tidak valid di cabang rantai baru.
8.  **Mengapa penyebaran transaksi di jaringan P2P menggunakan pengumuman hash terlebih dahulu (NewPooledTransactionHashes) alih-alih langsung memancarkan seluruh data transaksi utuh?**
    *   *Jawaban:* Untuk menghemat konsumsi bandwidth jaringan secara masif. Setiap node terhubung ke puluhan peer. Memancarkan payload penuh ke semua koneksi akan menyebabkan duplikasi data berukuran megabyte yang sama berulang-ulang, sementara pengumuman hash hanya berukuran 32-byte per transaksi.
9.  **Apa perbedaan mendasar antara serangan Sybil Attack dan Eclipse Attack pada lapisan jaringan P2P blockchain?**
    *   *Jawaban:* Sybil attack bertujuan menguasai jaringan secara umum dengan membuat jutaan identitas virtual palsu, sedangkan Eclipse attack mengisolasi satu target node spesifik secara tertarget dengan cara membanjiri seluruh kuota koneksi peer target menggunakan node milik penyerang, sehingga target menerima data rantai yang terdistorsi.
10. **Bagaimana penerapan EIP-1559 memengaruhi proses penyusunan transaksi berprioritas tertinggi pada Max-Heap Mempool jika dibandingkan dengan model transaksi legasi (Legacy Transactions)?**
    *   *Jawaban:* Pada transaksi legasi, pengurutan heap murni didasarkan pada `GasPrice`. Pada EIP-1559, pengurutan didasarkan pada `EffectivePriorityFee` (Gas Tip) yang merupakan nilai dinamis: $\min(\text{GasTipCap}, \text{GasFeeCap} - \text{BaseFee})$. Transaksi dengan GasTipCap tinggi tetap bisa kehilangan prioritas jika selisihnya dengan BaseFee menipis.

### 15.3. Skenario Kasus Produksi Terapan (3 Soal)

#### Skenario 1: Ledakan Latensi Mempool Saat Peluncuran Airdrop Masif
*Kasus:* Sebuah protokol GameFi meluncurkan airdrop token. Dalam 60 detik, node publik Anda menerima 100.000 transaksi/menit. Tingkat penggunaan memori melonjak hingga 92% dan latency JSON-RPC melompat dari 15ms menjadi 1800ms. Node mulai menolak transaksi pengguna valid secara acak.
*   **Tindakan Diagnostik:** Periksa distribusi transaksi di mempool menggunakan `txpool_status`. Jika nilai `queued` jauh melampaui `pending`, sistem sedang terhambat oleh *nonce gaps* atau transaksi dari ratusan wallet baru tanpa balance native token yang mencukupi untuk gas.
*   **Solusi:** Naikkan batas nilai `--txpool.pricelimit` secara dinamis untuk menyaring transaksi *low-fee*, perkecil batas alokasi antrean per-akun (`--txpool.accountqueue`), dan pasang *reverse-proxy caching* di depan RPC layer untuk membatasi frekuensi request dari alamat IP penyerang.

#### Skenario 2: Terjadinya Partisi Jaringan P2P Pasca Upgrade Node
*Kasus:* Pasca melakukan upgrade versi node, separuh validator di cluster Anda berhenti memproduksi blok dan log mencatat: `libp2p_pubsub: rejected message due to signature verification failure`.
*   **Tindakan Diagnostik:** Periksa kompatibilitas format serialisasi pesan dan skema enkripsi antar versi. Validasi *Fork Digest* atau *Topic ID* yang digunakan pada libp2p Gossipsub.
*   **Solusi:** Masalah ini biasanya diakibatkan oleh perbedaan *Topic Subscription ID* atau kegagalan parsing SSZ/Protobuf pasca hard-fork. Seluruh node dalam klaster harus disinkronisasikan ke versi *Consensus Specifications* identik dan flag konfigurasi `--network-id` atau `--genesis-validators-root` dipastikan seragam.

#### Skenario 3: Transaksi Penjualan NFT Terkena Front-Running Berulang Kali
*Kasus:* Pengguna VIP enterprise mengeluh bahwa transaksi order settlement bernilai besar selalu disalip oleh bot MEV pihak ketiga sehingga transaksinya gagal (*slippage error*). Padahal transaksi dikirimkan dengan gas fee yang sangat tinggi.
*   **Tindakan Diagnostik:** Telusuri rute transaksi. Jika transaksi dikirimkan melalui node yang mengekspos transaksi ke *Public Mempool*, bot MEV mendeteksi payload transaksi via *Gossip stream* dan otomatis menyusun transaksi pengganti dengan gas tip lebih tinggi untuk mengekstrak profit arbitrase.
*   **Solusi:** Alihkan rute transmisi transaksi klien VIP dari public mempool ke jaringan *Private Order Flow* (seperti Flashbots Protect, Eden Network, atau endpoint RPC internal validator builder) menggunakan payload bertipe *private bundle* yang tidak pernah disiarkan ke publik sebelum dimasukkan ke dalam blok.

---

## 16. Summary

*   **Dua Pilar Komputasi Node:** Arsitektur node blockchain terbagi antara **Execution Layer (EL)** yang mengelola kalkulasi state, eksekusi EVM, dan mempool, serta **Consensus Layer (CL)** yang memimpin finalitas konsensus dan propagasi blok, dihubungkan secara steril melalui antarmuka **Engine API**.
*   **P2P Underlay & Overlay:** Distribusi informasi global bergantung pada penemuan node berbasis jarak XOR via **Kademlia DHT**, dilanjutkan dengan negosiasi sesi aman menggunakan enkripsi Noise/RLPx, serta pemancaran data bertingkat (*mesh gossip*) berbasis **Gossipsub v1.1** yang dilengkapi mitigasi peer scoring otonom.
*   **Dinamika Ekosistem Mempool:** Mempool bukanlah penampung pasif sekuensial, melainkan subsistem real-time berbasis *heap-order priority* yang mengorganisir transaksi ke dalam status *Pending* (siap eksekusi) dan *Queued* (tertahan dependensi nonce).
*   **Proteksi Skala Enterprise:** Menjaga keandalan mempool dari serangan DoS dan kebocoran MEV menuntut pembatasan memori yang ketat (*hard limit slots*), penegakan algoritma *Replace-by-Fee* (RBF) yang deterministik, serta pemisahan tegas antara jalur transaksi publik dengan pipa *Private Order Flow*.