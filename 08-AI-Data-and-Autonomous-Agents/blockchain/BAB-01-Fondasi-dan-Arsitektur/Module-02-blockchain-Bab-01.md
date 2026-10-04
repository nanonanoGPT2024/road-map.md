# Bab 01: Fondasi dan Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Blockchain Execution Engine & State Machine Replication)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis (Analyze)** arsitektur internal *Deterministic State Machine Replication* (SMR), mempool propagation pipeline, dan struktur data mutakhir (*Sparse Merkle Trees* dan *Merkle Patricia Tries*) dalam node blockchain enterprise.
2. **Merancang (Design)** arsitektur layer komputasi terdesentralisasi untuk ekosistem AI Agent, mencakup pemisahan execution engine, storage engine (LSM-Tree), dan settlement layer.
3. **Mengimplementasikan (Implement)** engine transisi status (*State Transition Engine*) berkemampuan konkurensi aman (*thread-safe*), verifikasi kriptografis (*signature & nonce ordering*), serta komitmen status deterministik (*atomic state commitment*) berbasis Go.
4. **Mengevaluasi & Memecahkan Masalah (Evaluate & Troubleshoot)** kondisi *non-deterministic state fork*, *mempool front-running*, *storage bloat*, dan kegagalan konsensus BFT pada throughput transaksi tinggi.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut:
* **Sistem Terdistribusi**: Pemahaman CAP/PACELC theorem, konsistensi linearizable, model kegagalan *Byzantine Fault Tolerant* (BFT), serta gossip protocol.
* **Kriptografi Terapan**: Hashing (*Keccak-256*, *BLAKE3*), Asymmetric Cryptography (*ECDSA secp256k1*, *Ed25519*), dan verifikasi *Merkle Inclusion Proof*.
* **Bahasa Pemrograman**: Mahir menggunakan bahasa pemrograman bertipe statis (diutamakan Go atau Rust) dengan fokus pada konkurensi (channel, sync primitives), pointer memory layout, dan serialisasi data (*Protobuf*, *RLP*).
* **Storage Engine**: Pemahaman mendasar terkait arsitektur *Log-Structured Merge-tree* (LSM-tree) seperti LevelDB, RocksDB, atau PebbleDB.

---

### 3. Concept & Internal Architecture

Blockchain pada tingkat arsitektur enterprise bukanlah sekadar rantai blok (linked list hash), melainkan sebuah **Deterministic State Machine Replication (SMR)** terdesentralisasi yang berjalan di atas jaringan P2P *untrusted*.

```
+-----------------------------------------------------------------------+
|                           P2P Network Layer                           |
|      (libp2p, GossipSub, Peer Discovery, Encrypted Handshake)         |
+-----------------------------------------------------------------------+
                                   | Tx Gossip
                                   v
+-----------------------------------------------------------------------+
|                             Mempool Layer                             |
|  - Ingestion Validation (Signature, Account Balance, Replay Attack)   |
|  - Prioritization Queue (Fee Density / Tip, Nonce Ordering)           |
+-----------------------------------------------------------------------+
                                   | Proposed Block / Ordered Txs
                                   v
+-----------------------------------------------------------------------+
|                    Consensus Engine (e.g., Tendermint/PBFT)           |
|         Deterministic Proposal -> Pre-vote -> Pre-commit -> Commit    |
+-----------------------------------------------------------------------+
                                   | Finalized Tx Batch
                                   v
+-----------------------------------------------------------------------+
|                    Execution Engine (State Transition)                |
|                    S_{t+1} = APPLY(S_t, Transaction)                  |
|  - Deterministic VM / Native Handlers (AI Agent Action Verification)  |
|  - Gas Metering / Resource Exhaustion Guard                           |
+-----------------------------------------------------------------------+
                                   |
                     +-------------+-------------+
                     v                           v
+-----------------------------------+ +----------------------------------+
|           World State             | |          Commitment Layer        |
| (Key-Value State DB: PebbleDB)    | | (Sparse Merkle Tree / MPT Root)  |
| Key: AccountID -> Value: StatePayload | StateRoot = Hash(Trie_Nodes)     |
+-----------------------------------+ +----------------------------------+
```

#### Deterministic State Transition Model
Secara matematis, evolusi status blockchain didefinisikan sebagai fungsi transisi deterministik:

$$\sigma_{t+1} = \Upsilon(\sigma_t, B_{t})$$

Di mana:
* $\sigma_t$ adalah *World State* pada blok $t$.
* $B_t$ adalah blok terurut yang berisi daftar transaksi $[T_0, T_1, \dots, T_n]$.
* $\Upsilon$ adalah *State Transition Function* formal. Untuk setiap transaksi $T_k$:

$$\sigma' = \text{APPLY}(\sigma, T_k)$$

Kriteria mutlak dari fungsi $\Upsilon$ adalah **Determinisme Total**:
1. Tidak ada dependensi terhadap jam internal sistem host (*system wall-clock*).
2. Tidak ada ketergantungan pada operasi floating-point arsitektural hardware non-standar (IEEE 754 precision drifting).
3. Penanganan eksepsi mutlak konsisten; jika operasi gagal akibat *out-of-gas* atau invariant violation, seluruh mutasi parsial dari $T_k$ harus di-*rollback* secara atomik, namun state tetap mencatat penalti gas/biaya eksekusi.

#### Sparse Merkle Tree (SMT) vs Merkle Patricia Trie (MPT)
Penyimpanan status memerlukan pembuktian kriptografis instan (*cryptographic proofs*) bahwa suatu status ada (*proof of membership*) atau tidak ada (*proof of non-membership*).
* **Merkle Patricia Trie (MPT)**: Digunakan oleh Ethereum. Menggabungkan Radix Tree (Patricia) dengan Merkle Tree. Kompleks, efisien untuk prefix sharing, namun overhead deserialisasi dan kalkulasi *intermediate hash* tinggi.
* **Sparse Merkle Tree (SMT)**: Merupakan Merkle Tree penuh dengan ruang kunci berukuran $2^{256}$. Sebagian besar daun (*leaves*) bernilai nol (*default hash*). SMT memberikan verifikasi *membership* dan *non-membership* dengan efisiensi kalkulasi tinggi, sangat ideal untuk memvalidasi identitas dan *action credit* autonomous AI agent secara off-chain dengan ringkas.

---

### 4. Why & What

| Dimensi | Pendekatan Database Terdistribusi Konvensional (Spanner, CockroachDB) | Arsitektur Blockchain SMR Enterprise (Execution Node) |
| :--- | :--- | :--- |
| **Trust Model** | Semi-trusted internal cluster nodes. Autentikasi berbasis mTLS internal infra. | Zero-Trust. Node beroperasi di jaringan adversarial; validasi kriptografis di tiap lapisan. |
| **State Mutation** | ACID transactions via two-phase commit (2PC) / Raft. State dimutasi langsung in-place. | Append-only execution log. Transisi status deterministik diverifikasi melalui cryptographic root hash. |
| **Provenance & Audit** | Database audit logs (CDC) eksternal; dapat dimanipulasi oleh administrator infrastruktur. | Kriptografis dan tak terubahkan (*tamper-evident*). Status divalidasi oleh Merkle Proofs hingga Genesis. |
| **Agent Autonomy** | Agent bergantung pada API keys dan database RBAC tersentralisasi. | Agent beroperasi menggunakan kunci asimetris, menandatangani payload tindakan secara mandiri. |

Mengapa arsitektur ini penting untuk ekosistem **AI Data & Autonomous Agents**?
Ketika autonomous agent mengeksekusi aksi bernilai moneter atau data kritikal (misalnya pembayaran API compute inference, pertukaran dataset berbobot privasi tinggi, atau koordinasi swarm), sistem tidak boleh bergantung pada satu entitas tunggal yang dapat memalsukan log komputasi atau membatalkan transaksi sepihak. Arsitektur eksekusi deterministik memberikan fondasi *provable state transition* yang aman secara kriptografis.

---

### 5. How (Workflow Detail)

Alur komprehensif perjalanan sebuah transaksi dalam node execution engine:

```
[ AI Agent Client ]
        |
        | 1. Signs Payload: Tx = {Nonce, To, Amount, GasLimit, Data, Signature}
        v
[ RPC Ingestion Layer ]
        |
        | 2. Basic Static Validation (Size limit, Correct Encoding)
        v
[ Mempool Admission Controller ]
        |
        | 3. Recover Public Key & Verify Cryptographic Signature
        | 4. Fetch State: Balance >= Amount + GasLimit, CurrentNonce == Tx.Nonce
        | 5. Insert to Priority Heap (GasPrice Order) & Nonce-Map
        v
[ Consensus Block Assembly (Proposer Mode) ]
        |
        | 6. Pack Transactions up to Block Gas/Size Limit
        | 7. Propose Block through BFT Layer (Pre-vote -> Pre-commit)
        v
[ Block Execution Engine ]
        |
        | 8. Initialize Journal / Execution Cache
        |--- Loop: For Each Tx in Block:
        |      |-- A. Deduct Upfront Execution Gas Fee
        |      |-- B. Increment Account Nonce
        |      |-- C. Instantiate Isolated Sub-Context
        |      |-- D. Execute Payload (Update State Cache)
        |      |-- E. If Error -> Revert Sub-Context, retain Gas Fee
        |      `-- F. Append Event Logs & Update Bloom Filter
        | 9. Commit State Cache to Database Staging Batch
        | 10. Compute New Merkle State Root
        v
[ Storage Layer (LSM-Tree) ]
        |
        | 11. Write Atomic Batch: Flat State + State Trie Nodes + Block Header
        | 12. Flush to Disk (WAL + SSTables)
        v
[ Finality & Event Dispatch ]
        | 13. Notify Subscribed AI Agents via WebSocket / RPC
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Mesin Akuntansi Ruang Steril (*Sterile Room Accounting Engine*)
Bayangkan sebuah bank dengan ribuan akuntan yang saling tidak percaya. 
* Nasabah (AI Agent) mengirim instruksi transaksi dalam amplop bersegel lilin berlogo unik (*Cryptographic Signature*).
* Setiap instruksi memiliki nomor urut (*Nonce*). Tidak ada instruksi nomor 5 yang dapat diproses sebelum nomor 4 selesai diverifikasi.
* Di dalam ruang kerja (*Sandbox Execution*), akuntan tidak boleh membawa kalkulator yang memiliki fitur pembulatan otomatis (*No floating-point*), tidak boleh memiliki jam tangan (*No system wall-clock*), dan hanya boleh mencatat mutasi menggunakan pena hitam standar (*State Journal*).
* Setelah seluruh transaksi satu periode selesai, semua akuntan menyusun lembar pembukuan ke dalam struktur pohon kode rahasia (*Sparse Merkle Tree*), dan menghasilkan satu kode segel akhir (*State Root Hash*). Jika satu huruf saja berbeda, seluruh bank serentak menolak buku tersebut (*Consensus Halt/Fork Prevention*).

```
                      SPARSE MERKLE TREE ROOT
                               [R]
                             /     \
                           /         \
                         /             \
                      [H_0]           [H_1]
                     /    \           /    \
                   /        \       /        \
                [H_00]    [H_01] [H_10]    [H_11]
                 /   \     /   \  /   \     /   \
               (A)   (B)  (0) (0)(C)  (0)  (0)  (D)
                ^
                |
          Leaf Node: Keccak256(Account State)
          Path: Bitwise representation of Account Address (e.g., 000...)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Deterministic Account State Invariant Transition (Go)
Contoh dasar validasi transisi status nondeterministik vs deterministik:

```go
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
)

type Account struct {
	Nonce   uint64
	Balance uint64
}

// ApplyTransaction memvalidasi dan memutasi state secara deterministik
func ApplyTransaction(sender, receiver *Account, amount, fee uint64, txNonce uint64) error {
	// Invariant 1: Nonce harus strictly sequential
	if txNonce != sender.Nonce {
		return errors.New("invalid nonce: sequence mismatch")
	}

	// Invariant 2: Balance harus mencukupi biaya total (transfer + fee)
	totalDebit := amount + fee
	if sender.Balance < totalDebit {
		return errors.New("insufficient balance")
	}

	// Eksekusi mutasi state
	sender.Balance -= totalDebit
	sender.Nonce++
	receiver.Balance += amount

	return nil
}

func main() {
	alice := &Account{Nonce: 0, Balance: 1000}
	bob := &Account{Nonce: 0, Balance: 200}

	err := ApplyTransaction(alice, bob, 300, 10, 0)
	if err != nil {
		panic(err)
	}

	fmt.Printf("Alice Balance: %d, Bob Balance: %d, Alice Nonce: %d\n", alice.Balance, bob.Balance, alice.Nonce)
}
```

#### B. Practical Example: Enterprise Multi-Agent State Execution Engine

Implementasi engine eksekusi produksi yang menangani:
1. Verifikasi ECDSA Secp256k1 & Nonce sequence.
2. Isolated State Journaling (Atomic Rollback).
3. Sparse-style Merkle Root State Computation.

Simpan file berikut sebagai komponen inti arsitektur execution node:

```go
package main

import (
	"bytes"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"math/big"
	"sort"
	"sync"
)

// --- Domain Models ---

type Address [20]byte

func (a Address) String() string {
	return hex.EncodeToString(a[:])
}

type AccountState struct {
	Nonce   uint64
	Balance uint64
}

func (as AccountState) Hash() [32]byte {
	buf := make([]byte, 16)
	binary.BigEndian.PutUint64(buf[0:8], as.Nonce)
	binary.BigEndian.PutUint64(buf[8:16], as.Balance)
	return sha256.Sum256(buf)
}

type Transaction struct {
	Sender    Address
	Recipient Address
	Amount    uint64
	Fee       uint64
	Nonce     uint64
	Signature []byte // 64 bytes (R || S)
}

func (tx *Transaction) SigningHash() [32]byte {
	buf := make([]byte, 20+20+8+8+8)
	copy(buf[0:20], tx.Sender[:])
	copy(buf[20:40], tx.Recipient[:])
	binary.BigEndian.PutUint64(buf[40:48], tx.Amount)
	binary.BigEndian.PutUint64(buf[48:56], tx.Fee)
	binary.BigEndian.PutUint64(buf[56:64], tx.Nonce)
	return sha256.Sum256(buf)
}

// --- State Database with Journaling ---

type StateDB struct {
	mu       sync.RWMutex
	accounts map[Address]AccountState
	journal  map[Address]AccountState // Snapshot for atomic rollback
}

func NewStateDB() *StateDB {
	return &StateDB{
		accounts: make(map[Address]AccountState),
		journal:  make(map[Address]AccountState),
	}
}

func (s *StateDB) GetAccount(addr Address) AccountState {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.accounts[addr]
}

func (s *StateDB) BeginTx() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.journal = make(map[Address]AccountState)
}

func (s *StateDB) ModifyAccount(addr Address, state AccountState) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.journal[addr]; !exists {
		s.journal[addr] = s.accounts[addr] // Simpan status awal sebelum perubahan
	}
	s.accounts[addr] = state
}

func (s *StateDB) Rollback() {
	s.mu.Lock()
	defer s.mu.Unlock()
	for addr, originalState := range s.journal {
		s.accounts[addr] = originalState
	}
	s.journal = make(map[Address]AccountState)
}

func (s *StateDB) Commit() [32]byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.journal = make(map[Address]AccountState) // Bersihkan journal

	// Kalkulasi deterministik Merkle State Root dari state yang ada
	var addresses []string
	for addr := range s.accounts {
		addresses = append(addresses, addr.String())
	}
	sort.Strings(addresses) // Menjamin urutan leksikografis deterministik

	var leaves [][]byte
	for _, addrStr := range addresses {
		addrBytes, _ := hex.DecodeString(addrStr)
		var addr Address
		copy(addr[:], addrBytes)
		acc := s.accounts[addr]
		accHash := acc.Hash()

		leafData := append(addr[:], accHash[:]...)
		leafHash := sha256.Sum256(leafData)
		leaves = append(leaves, leafHash[:])
	}

	return computeMerkleRoot(leaves)
}

func computeMerkleRoot(leaves [][]byte) [32]byte {
	if len(leaves) == 0 {
		return sha256.Sum256([]byte("empty_state"))
	}
	if len(leaves) == 1 {
		var root [32]byte
		copy(root[:], leaves[0])
		return root
	}

	var nextLevel [][]byte
	for i := 0; i < len(leaves); i += 2 {
		if i+1 < len(leaves) {
			h := sha256.Sum256(append(leaves[i], leaves[i+1]...))
			nextLevel = append(nextLevel, h[:])
		} else {
			// Jika ganjil, duplikasi leaf terakhir sesuai standar RFC 6962
			h := sha256.Sum256(append(leaves[i], leaves[i]...))
			nextLevel = append(nextLevel, h[:])
		}
	}
	return computeMerkleRoot(nextLevel)
}

// --- Execution Engine ---

type ExecutionEngine struct {
	stateDB *StateDB
}

func NewExecutionEngine(db *StateDB) *ExecutionEngine {
	return &ExecutionEngine{stateDB: db}
}

func (ee *ExecutionEngine) VerifySignature(pubKey *ecdsa.PublicKey, tx *Transaction) bool {
	if len(tx.Signature) != 64 {
		return false
	}
	r := new(big.Int).SetBytes(tx.Signature[:32])
	s := new(big.Int).SetBytes(tx.Signature[32:])
	h := tx.SigningHash()

	return ecdsa.Verify(pubKey, h[:], r, s)
}

func (ee *ExecutionEngine) ExecuteBlock(txs []*Transaction, pubKeys map[Address]*ecdsa.PublicKey) ([32]byte, error) {
	for idx, tx := range txs {
		ee.stateDB.BeginTx() // Buat checkpoint sebelum mengeksekusi satu transaksi

		pubKey, exists := pubKeys[tx.Sender]
		if !exists {
			ee.stateDB.Rollback()
			return [32]byte{}, fmt.Errorf("tx %d failed: public key not registered for sender", idx)
		}

		// 1. Verifikasi Signature Kriptografis
		if !ee.VerifySignature(pubKey, tx) {
			ee.stateDB.Rollback()
			return [32]byte{}, fmt.Errorf("tx %d failed: invalid cryptographic signature", idx)
		}

		// 2. Fetch State
		senderState := ee.stateDB.GetAccount(tx.Sender)
		recipientState := ee.stateDB.GetAccount(tx.Recipient)

		// 3. Validasi Nonce
		if tx.Nonce != senderState.Nonce {
			ee.stateDB.Rollback()
			return [32]byte{}, fmt.Errorf("tx %d failed: nonce mismatch (expected %d, got %d)", idx, senderState.Nonce, tx.Nonce)
		}

		// 4. Validasi Balance
		totalDebit := tx.Amount + tx.Fee
		if senderState.Balance < totalDebit {
			ee.stateDB.Rollback()
			return [32]byte{}, fmt.Errorf("tx %d failed: insufficient funds", idx)
		}

		// 5. State Transition Execution
		senderState.Balance -= totalDebit
		senderState.Nonce++
		recipientState.Balance += tx.Amount

		// 6. Write back to State DB
		ee.stateDB.ModifyAccount(tx.Sender, senderState)
		ee.stateDB.ModifyAccount(tx.Recipient, recipientState)
	}

	// Commit batch transisi dan peroleh State Root baru
	newRoot := ee.stateDB.Commit()
	return newRoot, nil
}

// --- Main Verification Flow ---

func main() {
	// Setup Database & Execution Engine
	db := NewStateDB()
	engine := NewExecutionEngine(db)

	// Buat cryptographic keypair untuk dua Autonomous Agent
	agentA_Key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	agentB_Key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)

	var addrA, addrB Address
	// Generasi Address dari Public Key Hash (20 bytes)
	pubABytes := elliptic.Marshal(elliptic.P256(), agentA_Key.PublicKey.X, agentA_Key.PublicKey.Y)
	pubBBytes := elliptic.Marshal(elliptic.P256(), agentB_Key.PublicKey.X, agentB_Key.PublicKey.Y)
	hashA := sha256.Sum256(pubABytes)
	hashB := sha256.Sum256(pubBBytes)
	copy(addrA[:], hashA[0:20])
	copy(addrB[:], hashB[0:20])

	keyRegistry := map[Address]*ecdsa.PublicKey{
		addrA: &agentA_Key.PublicKey,
		addrB: &agentB_Key.PublicKey,
	}

	// Inisialisasi saldo Genesis
	db.ModifyAccount(addrA, AccountState{Nonce: 0, Balance: 10_000})
	db.ModifyAccount(addrB, AccountState{Nonce: 0, Balance: 1_000})
	initialRoot := db.Commit()
	fmt.Printf("[Genesis] Initial State Root: %s\n", hex.EncodeToString(initialRoot[:]))

	// Agent A membuat transaksi transfer 2,500 token ke Agent B (Fee: 50)
	tx1 := &Transaction{
		Sender:    addrA,
		Recipient: addrB,
		Amount:    2500,
		Fee:       50,
		Nonce:     0,
	}

	// Signing Tx1 menggunakan Private Key Agent A
	txHash := tx1.SigningHash()
	r, s, err := ecdsa.Sign(rand.Reader, agentA_Key, txHash[:])
	if err != nil {
		panic(err)
	}

	var sig [64]byte
	rBytes := r.Bytes()
	sBytes := s.Bytes()
	copy(sig[32-len(rBytes):32], rBytes)
	copy(sig[64-len(sBytes):64], sBytes)
	tx1.Signature = sig[:]

	// Eksekusi Block yang berisi Tx1
	txBatch := []*Transaction{tx1}
	newRoot, err := engine.ExecuteBlock(txBatch, keyRegistry)
	if err != nil {
		fmt.Printf("Execution Error: %v\n", err)
		return
	}

	fmt.Printf("[Block #1] Execution Success!\n")
	fmt.Printf("           Updated State Root : %s\n", hex.EncodeToString(newRoot[:]))
	fmt.Printf("           Agent A Balance    : %d (Nonce: %d)\n", db.GetAccount(addrA).Balance, db.GetAccount(addrA).Nonce)
	fmt.Printf("           Agent B Balance    : %d (Nonce: %d)\n", db.GetAccount(addrB).Balance, db.GetAccount(addrB).Nonce)

	// Pengujian Rollback: Simulasi Replay Attack (Mengirim nonce yang sama)
	fmt.Println("\n[Test] Menjalankan Transaksi Ilegal (Replay Nonce 0)...")
	txInvalid := &Transaction{
		Sender:    addrA,
		Recipient: addrB,
		Amount:    100,
		Fee:       10,
		Nonce:     0, // Seharusnya Nonce 1
		Signature: tx1.Signature,
	}

	_, errInvalid := engine.ExecuteBlock([]*Transaction{txInvalid}, keyRegistry)
	if errInvalid != nil {
		fmt.Printf("[Defense Validated] Replay berhasil digagalkan: %v\n", errInvalid)
	}
}
```

---

### 8. Real World Case Study: Decentralized Autonomous AI Market Settlement Engine

#### Konteks Masalah
Sebuah platform koordinasi AI skala global (*Decentralized Compute Marketplace*) mengoperasikan 50.000 agen otonom yang melakukan *inference auction* setiap detik. Agen model (misalnya LLaMA-3 node) menjual throughput komputasi kepada agen agregator.

#### Tantangan Produksi
1. **State Contention**: Ribuan agen memperbarui *escrow balance* mereka secara bersamaan, menyebabkan *lock contention* tinggi pada database PostgreSQL utama.
2. **Double Spending Compute**: Agen dapat membatalkan saldo off-chain sebelum bukti inferensi (*Proof of Compute*) selesai divalidasi on-chain.
3. **Storage Explosion**: Mencatat setiap inferensi mikro secara on-chain mengakibatkan pembengkakan ukuran state ledger hingga 12 TB per kuartal.

#### Solusi Arsitektural Enterprise
Membangun *Dedicated Sovereign Execution Layer* (AppChain/Subnet) dengan spesifikasi:
1. **State Isolation**: Menerapkan state slot berbasis *Deterministic Account Trees*. Transaksi compute settlement menggunakan skema *Unidirectional Payment Channels* yang di-commit dalam batch periodik ke *World State*.
2. **Off-chain Compute Anchor**: Agen pembeli mengunci dana di contract smart escrow. Agen pekerja menyertakan hash dari bobot *inference trace* di payload transaksi, bukan seluruh raw data model.
3. **Pruned State Commitment**: State root dihitung menggunakan *Sparse Merkle Tree* flat storage dengan *State Pruning Pipeline* yang mengarsipkan status historis di storage terdesentralisasi (Arweave/Filecoin) dan hanya mempertahankan 256 blok status aktif di LSM-Tree lokal (PebbleDB).

#### Hasil Implementasi
* Throughput meningkat dari 42 TPS (pada public L1) menjadi 3.200 TPS pada settlement layer khusus.
* P99 State Transition latency berkurang dari 12 detik menjadi 410 milidetik.
* Jejak penyimpanan (*storage footprint*) terpangkas hingga 91% menggunakan agresif state trie pruning.

---

### 9. Trade-offs

| Aspek | State Model: Merkle Patricia Trie (MPT) | State Model: Sparse Merkle Tree (SMT) | State Model: Flat KV (e.g., Solana Account Model) |
| :--- | :--- | :--- | :--- |
| **Proof Size** | Pendek untuk key yang bertetangga (prefix shared). | Berukuran tetap (log2(N) hash path, misal: 256 * 32 bytes). | Tidak menyediakan cryptographic inclusion proof secara instan. |
| **Write Amplification** | Sangat Tinggi. Modifikasi 1 key memicu serialisasi ulang node leaf, extension, dan branch. | Sedang. Operasi write hanya memutasi jalur vertikal log2(N). | Sangat Rendah. Langsung memutasi key pada storage engine LSM-Tree. |
| **Proof of Non-Existence** | Kompleks; memerlukan traversal proof hingga branch kosong. | Alami dan instan; membuktikan leaf mengarah ke default `0x00...00`. | Tidak memungkinkan tanpa audit log eksternal. |
| **Cocok untuk** | General-purpose smart contract (Ethereum kompatibel). | Identity registry, Verifiable AI Agent Credentials, Whitelist/Blacklist. | Ultra-high throughput transaction pipelines tanpa dependensi root proof per block. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Non-Deterministic State Forking (Kesalahan Fatal)
* **Gejala**: Sebagian node validator menolak sebuah blok yang valid menurut node lain (*Consensus Split / Network Halt*).
* **Akar Masalah**: Penggunaan implementasi iterasi `map` di Go secara langsung saat menghitung state hash. Urutan iterasi map Go diacak secara sengaja oleh runtime:
  ```go
  // BUG: Iterasi map tidak deterministik di Go!
  for addr, state := range stateDB.accounts {
      hasher.Write(addr[:])
      hasher.Write(state.Bytes())
  }
  ```
* **Solusi**: Lakukan sorting deterministik terhadap keys (misal leksikografis menggunakan `sort.Strings` atau `bytes.Compare`) sebelum menghitung state hash atau root tree:
  ```go
  keys := make([]string, 0, len(stateDB.accounts))
  for k := range stateDB.accounts {
      keys = append(keys, string(k[:]))
  }
  sort.Strings(keys)
  for _, k := range keys {
      hasher.Write([]byte(k))
      // ...
  }
  ```

#### 2. Nonce Gap Stalling pada Mempool
* **Gejala**: Transaksi transaksi dari agent tertentu dengan nonce tinggi tertahan (*stuck*) berjam-jam di mempool dan tidak pernah masuk ke dalam blok.
* **Akar Masalah**: Ada satu transaksi dengan nonce perantara (misal Nonce #4) yang gagal digossipkan atau memiliki fee terlalu rendah, sehingga memblokir transaksi Nonce #5, #6, dst.
* **Solusi**: Implementasikan *Replace-by-Fee (RBF)* logic di mana transaksi baru dengan nonce yang sama tetapi gas price minimal 10-15% lebih tinggi dapat menimpa transaksi yang macet.

#### 3. State Trie DB Write Amplification & IOPS Exhaustion
* **Gejala**: Latensi penyelesaian blok melonjak drastis seiring bertambahnya ukuran disk node. Disk IOPS mencapai 100% capacity.
* **Akar Masalah**: Menyimpan setiap intermediate trie node langsung ke disk pada setiap blok.
* **Solusi**: Gunakan arsitektur *Ephemere Trie Cache*. Akumulasi perubahan trie dalam memori selama $N$ blok (misal 128 blok), dan hanya commit flat state dan trie dirty nodes secara periodik menggunakan background thread.

---

### 11. Best Practices (Production Checklist)

- [ ] **Engine Isolation**: Pastikan runtime eksekusi bebas dari syscall non-deterministik: matikan akses ke `time.Now()`, `rand.Read()`, pembacaan env host, dan floating-point precision yang tidak seragam.
- [ ] **Safe Math Operations**: Gunakan operasi integer dengan pengecekan overflow eksplisit (misal: deteksi underflow saat pengurangan saldo akun atau gunakan `math/big`).
- [ ] **Cryptographic Isolation**: Lakukan verifikasi signature *sebelum* transaksi masuk ke queue mempool utama. Gunakan worker pool multi-core untuk menjalankan `ecdsa.Verify` atau `ed25519.Verify` secara paralel.
- [ ] **State Rollback Granularity**: Terapkan pola *Journaling/Snapshotting*. Jangan pernah memutasi storage disk sebelum seluruh batch transaksi dalam sebuah blok selesai dieksekusi tanpa error invariant.
- [ ] **Storage Tuning**: Konfigurasikan LSM-Tree storage engine:
  - Gunakan block cache yang memadai (minimal 30% dari total RAM yang dialokasikan).
  - Terapkan *Bloom Filters* pada SSTables untuk meminimalkan random disk read saat validasi keberadaan akun.
- [ ] **Graceful Node Shutdown**: Pastikan proses shutdown menangkap sinyal `SIGINT`/`SIGTERM` dan menyelesaikan proses flush Write-Ahead Log (WAL) ke disk untuk mencegah korupsi state root.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun modul penanganan mempool deterministik dengan prioritas fee dan ordering nonce yang aman dari *out-of-order delivery*.

#### Struktur Direktori
```
hands-on/m02/
├── go.mod
├── mempool.go
└── mempool_test.go
```

#### Langkah 1: Inisialisasi Modul
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-mempool
```

#### Langkah 2: Buat File `hands-on/m02/mempool.go`

```go
package main

import (
	"container/heap"
	"errors"
	"sync"
)

type Tx struct {
	Hash     [32]byte
	Sender   string
	Nonce    uint64
	FeePrice uint64
	Payload  []byte
}

// TxPriorityQueue mengimplementasikan heap.Interface berbasis FeePrice terbesar
type TxPriorityQueue []*Tx

func (pq TxPriorityQueue) Len() int           { return len(pq) }
func (pq TxPriorityQueue) Less(i, j int) bool { return pq[i].FeePrice > pq[j].FeePrice }
func (pq TxPriorityQueue) Swap(i, j int)      { pq[i], pq[j] = pq[j], pq[i] }
func (pq *TxPriorityQueue) Push(x any)        { *pq = append(*pq, x.(*Tx)) }
func (pq *TxPriorityQueue) Pop() any {
	old := *pq
	n := len(old)
	item := old[n-1]
	*pq = old[0 : n-1]
	return item
}

type AgentMempool struct {
	mu          sync.RWMutex
	txByHash    map[[32]byte]*Tx
	txsBySender map[string]map[uint64]*Tx // Sender -> (Nonce -> Tx)
	priority    TxPriorityQueue
}

func NewAgentMempool() *AgentMempool {
	pq := make(TxPriorityQueue, 0)
	heap.Init(&pq)
	return &AgentMempool{
		txByHash:    make(map[[32]byte]*Tx),
		txsBySender: make(map[string]map[uint64]*Tx),
		priority:    pq,
	}
}

func (mp *AgentMempool) Add(tx *Tx) error {
	mp.mu.Lock()
	defer mp.mu.Unlock()

	if _, exists := mp.txByHash[tx.Hash]; exists {
		return errors.New("duplicate transaction")
	}

	if _, exists := mp.txsBySender[tx.Sender]; !exists {
		mp.txsBySender[tx.Sender] = make(map[uint64]*Tx)
	}

	// Validasi pencegahan penimpaan transaksi kecuali ada implementasi RBF
	if _, exists := mp.txsBySender[tx.Sender][tx.Nonce]; exists {
		return errors.New("nonce already exists in mempool")
	}

	mp.txByHash[tx.Hash] = tx
	mp.txsBySender[tx.Sender][tx.Nonce] = tx
	heap.Push(&mp.priority, tx)

	return nil
}

// ReapBatch mengambil hingga maxTx transaksi dengan prioritas fee tertinggi,
// dengan syarat transaksi harus valid secara sekuensial dari currentAccountNonce.
func (mp *AgentMempool) ReapBatch(accountNonces map[string]uint64, maxTx int) []*Tx {
	mp.mu.Lock()
	defer mp.mu.Unlock()

	var batch []*Tx
	var deferredTx []*Tx

	for mp.priority.Len() > 0 && len(batch) < maxTx {
		candidate := heap.Pop(&mp.priority).(*Tx)

		expectedNonce := accountNonces[candidate.Sender]
		if candidate.Nonce == expectedNonce {
			batch = append(batch, candidate)
			accountNonces[candidate.Sender]++ // Mutasi virtual nonce untuk batch ini
			delete(mp.txByHash, candidate.Hash)
			delete(mp.txsBySender[candidate.Sender], candidate.Nonce)
		} else if candidate.Nonce > expectedNonce {
			// Nonce ada di masa depan (out of order), simpan kembali ke antrean
			deferredTx = append(deferredTx, candidate)
		} else {
			// Nonce sudah usang (stale), hapus dari tracking
			delete(mp.txByHash, candidate.Hash)
			delete(mp.txsBySender[candidate.Sender], candidate.Nonce)
		}
	}

	// Kembalikan transaksi yang ditangguhkan ke antrean priority
	for _, tx := range deferredTx {
		heap.Push(&mp.priority, tx)
	}

	return batch
}
```

#### Langkah 3: Buat Unit Test `hands-on/m02/mempool_test.go`

```go
package main

import (
	"crypto/sha256"
	"testing"
)

func mockHash(id byte) [32]byte {
	var h [32]byte
	h[0] = id
	return h
}

func TestMempoolOrderingAndReap(t *testing.T) {
	mp := NewAgentMempool()

	agent1 := "agent_alpha"
	agent2 := "agent_beta"

	// Insert transaksi dengan fee dan nonce acak
	// Agent 1 mengirim nonce 1 duluan sebelum nonce 0
	mp.Add(&Tx{Hash: mockHash(1), Sender: agent1, Nonce: 1, FeePrice: 100})
	mp.Add(&Tx{Hash: mockHash(2), Sender: agent1, Nonce: 0, FeePrice: 50})
	// Agent 2 mengirim nonce 0 dengan fee kecil
	mp.Add(&Tx{Hash: mockHash(3), Sender: agent2, Nonce: 0, FeePrice: 10})

	// Current committed nonces di blockchain:
	currentNonces := map[string]uint64{
		agent1: 0,
		agent2: 0,
	}

	// Ambil batch maksimal 2 transaksi
	batch := mp.ReapBatch(currentNonces, 2)

	if len(batch) != 2 {
		t.Fatalf("Expected 2 txs, got %d", len(batch))
	}

	// Transaksi pertama yang diambil harus Agent 1 Nonce 0 (karena Nonce 1 tertahan dependensi)
	// atau dievaluasi berdasarkan kelayakan eksekusi sekuensial
	if batch[0].Sender != agent1 || batch[0].Nonce != 0 {
		t.Errorf("First tx should be agent1 nonce 0, got %s nonce %d", batch[0].Sender, batch[0].Nonce)
	}

	// Transaksi kedua: sekarang Agent 1 Nonce 1 menjadi eligible dan fee-nya (100) > Agent 2 (10)
	if batch[1].Sender != agent1 || batch[1].Nonce != 1 {
		t.Errorf("Second tx should be agent1 nonce 1, got %s nonce %d", batch[1].Sender, batch[1].Nonce)
	}
}
```

#### Langkah 4: Jalankan Pengujian
```bash
go test -v ./...
```
Output yang diharapkan:
```text
=== RUN   TestMempoolOrderingAndReap
--- PASS: TestMempoolOrderingAndReap (0.00s)
PASS
ok      m02-mempool     0.003s
```

---

### 13. Exercise

#### Level Easy
Modifikasi implementasi `AccountState` pada Practical Example agar mendukung field `Data []byte` (menyimpan hash state model inferensi agent). Pastikan kalkulasi `AccountState.Hash()` menyertakan serialisasi `Data` tersebut secara deterministik.

#### Level Medium
Tambahkan mekanisme **Gas Metering System** pada `ExecutionEngine`. Setiap transaksi harus menyertakan `GasLimit` dan `GasPrice`. Hitung konsumsi gas dengan ketentuan:
* Base cost: 21,000 gas.
* Payload byte cost: 16 gas per non-zero byte, 4 gas per zero byte.
Jika konsumsi gas melebihi `GasLimit`, gagalkan eksekusi, kembalikan state mutasi, namun potong saldo pengirim sebesar `GasLimit * GasPrice`.

#### Level Hard
Rancang dan implementasikan struktur **Sparse Merkle Tree (SMT)** 256-bit sederhana secara native di Go. SMT harus mendukung fungsi:
1. `Update(key [32]byte, valueHash [32]byte) error`
2. `GetProof(key [32]byte) (AuditPath [][32]byte, error)`
3. `VerifyProof(root [32]byte, key [32]byte, valueHash [32]byte, proof [][32]byte) bool`
Pastikan simpul-simpul kosong (*zero nodes*) di-cache secara statis di memori untuk mencegah overhead alokasi memori berlebih.

---

### 14. Challenge

**Studi Kasus Penyelamatan Produksi**:
Sebuah cluster node execution engine AI Agent Anda mengalami insiden **State Divergence Crisis**:
- Pada Blok `#1,249,000`, 60% validator menghasilkan `StateRoot = 0xAA4F...`, sedangkan 40% validator (termasuk node archive korporat Anda) menghasilkan `StateRoot = 0x7E1B...`.
- Jaringan terancam terbelah (*chain split*).
- Investigasi awal menunjukkan bahwa pada blok tersebut terdapat transaksi dari Autonomous Agent yang mengeksekusi operasi floating point division untuk membagi reward pool sebesar 10,000 unit ke 3 worker agent: `10000 / 3 = 3333.3333...`.
- Arsitektur node yang berbeda (ARM64 AWS Graviton vs x86_64 Intel Xeon) menghasilkan pembulatan presisi desimal internal yang berbeda sebelum dikonversi kembali ke integer saldo.

**Tugas Anda**:
1. Buat *Post-Mortem & Architecture Remediation Strategy* tertulis.
2. Tulis sebuah program simulator fork detector (Go) yang membuktikan bagaimana floating-point menghasilkan State Root berbeda pada dua node berbeda.
3. Rancang mekanisme *Deterministic Fixed-Point Math Engine* (misalnya menggunakan basis $10^{18}$ atau integer fraction pairs) yang menjamin seluruh node menghasilkan state identik di platform arsitektur CPU mana pun.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. Mengapa urutan iterasi `map` di bahasa Go tidak boleh digunakan secara langsung dalam penyusunan data hash state blockchain?
   - *Jawaban*: Runtime Go sengaja mengacak urutan iterasi map (*random seed initialization*) pada setiap runtime run untuk mencegah eksploitasi Algorithmic Complexity Attacks. Jika digunakan langsung, setiap node akan membaca urutan key yang berbeda, menghasilkan hash state root yang berbeda, dan memicu *state divergence fork*.
2. Apa fungsi utama *Nonce* dalam transaksi akun pada blockchain?
   - *Jawaban*: Nonce berfungsi sebagai pelindung dari *Replay Attack* dan menjamin urutan eksekusi transaksi yang deterministik dan strictly sequential dari setiap akun.
3. Apa perbedaan fundamental antara Proof of Membership dan Proof of Non-Membership pada Merkle Tree?
   - *Jawaban*: Proof of Membership membuktikan bahwa suatu key-value ada di dalam tree dan terikat ke root hash tertentu. Proof of Non-Membership membuktikan bahwa suatu key tertentu *sama sekali tidak ada* di dalam state tanpa harus membeberkan seluruh isi database.
4. Apa yang dimaksud dengan Write-Ahead Log (WAL) pada storage engine node blockchain?
   - *Jawaban*: WAL adalah log append-only di mana setiap mutasi status dicatat ke disk sebelum diaplikasikan ke struktur memori (MemTable) atau file tabel status (SSTables), menjamin durabilitas data jika terjadi *power loss* atau crash mendadak.
5. Mengapa pembagian angka desimal (*floating point*) dilarang keras dalam smart contract atau native blockchain execution logic?
   - *Jawaban*: Standar floating point (IEEE 754) dapat menghasilkan perbedaan bit terkecil tergantung pada arsitektur hardware, compiler flags, dan microcode CPU, yang menyebabkan hilangnya konsistensi determinisme state transition antar node.

#### Intermediate Questions
6. Mengapa Sparse Merkle Tree (SMT) lebih disukai dibandingkan Merkle Patricia Trie (MPT) untuk registry kredensial identitas AI Agent?
   - *Jawaban*: SMT memiliki kedalaman tetap (misal 256-bit) yang memetakan key langsung ke posisi bit tree, membuat pembuktian *proof of non-existence* menjadi sangat murah dan deterministik (cukup membuktikan jalurnya mengarah ke default null-hash), serta memudahkan integrasi dengan Zero-Knowledge Circuit (seperti zk-SNARKs).
7. Bagaimana pola *Journaling* mencegah korupsi state database jika transaksi ke-4 dari 5 transaksi dalam sebuah blok gagal akibat *out-of-gas*?
   - *Jawaban*: Journaling mencatat state awal (sebelum perubahan) dari setiap akun yang disentuh oleh transaksi ke-4. Saat transaksi ke-4 gagal, engine melakukan rollback parsial terhadap mutasi yang dilakukan oleh transaksi tersebut menggunakan catatan journal, mengembalikan state akun ke status sebelum transaksi ke-4 dieksekusi (kecuali pemotongan gas fee transaksi).
8. Apa risiko jika sebuah node validator mengabaikan pengecekan signature di mempool dan menunda validasi signature hingga fase eksekusi blok?
   - *Jawaban*: Node rentan terhadap *DoS/Spam Attack*. Penyerang dapat membanjiri jaringan dan mempool dengan transaksi bersignature palsu, membebani kapasitas memori node dan memboroskan sumber daya komputasi saat pembentukan blok.
9. Jelaskan bagaimana Replace-By-Fee (RBF) menyelesaikan masalah *stuck transaction* di mempool!
   - *Jawaban*: RBF memungkinkan pengirim mengirim ulang transaksi baru dengan nonce yang sama persis seperti transaksi yang tersangkut, tetapi menawarkan gas price/fee yang secara signifikan lebih tinggi. Mempool akan mengganti transaksi lama dengan yang baru dalam antrean prioritas.
10. Pada arsitektur LSM-tree, mengapa keberadaan *Bloom Filter* krusial untuk performa verifikasi saldo akun di mempool?
    - *Jawaban*: Mempool sering memeriksa apakah sebuah akun pengirim memiliki balance/state di disk. Bloom filter memungkinkan node mengecek apakah suatu key akun *pasti tidak ada* di SSTable tertentu tanpa perlu melakukan disk I/O, secara drastis mengurangi latensi random disk read.

#### Skenario Kasus Produksi
11. **Skenario Kasus 1**: Pada jaringan settlement AI agent produksi dengan traffic 2,000 TPS, latensi p99 pemrosesan blok tiba-tiba melonjak dari 500ms menjadi 14 detik. Analisis metrik menunjukkan CPU usage rendah (25%), namun `iowait` melonjak hingga 85%. Apa penyebab arsitektural yang paling mungkin dan bagaimana mitigasinya?
    - *Solusi & Analisis*: 
      - **Penyebab**: Terjadi *Write Amplification* dan *Disk Thrashing* akibat penulisan langsung node-node intermediate Merkle Trie ke storage disk pada setiap blok. Setiap mutasi akun memperbarui puluhan parent hash nodes di LSM-tree.
      - **Mitigasi**: Terapkan *In-Memory Trie Layer with Dirty Node Flushing*. Simpan struktur trie hanya di memori dan gunakan Flat Key-Value DB untuk eksekusi reguler. Tulis snapshot state trie ke disk secara asynchronous setiap $K$ blok (checkpointing), serta pisahkan disk fisik untuk Write-Ahead Log (NVMe dengan write latency rendah) dan State Storage SSTables.
12. **Skenario Kasus 2**: Agen AI Anda mengeksekusi arbitrage transaksi mikro. Kadang kala, transaksi agen tersebut disalip oleh agen lain yang membayar fee sedikit lebih tinggi, namun menggunakan parameter transaksi yang diduplikasi dari transaksi agen Anda (*Front-Running / MEV*). Bagaimana merancang arsitektur transaksi yang kebal terhadap eksploitasi ini?
    - *Solusi & Analisis*:
      - Menerapkan skema **Commit-Reveal Scheme** atau **Encrypted Mempool (Threshold Decryption)**.
      - Pada tahap pertama (*Commit*), agen hanya mengirim hash komitmen dari payload aksi: $H = \text{Hash}(\text{ActionData} \parallel \text{SecretSalt})$. Validator memasukkan hash ini ke dalam blok tanpa mengetahui isinya.
      - Setelah blok tersebut final, agen mengirimkan *Reveal* ($ActionData$ dan $SecretSalt$). Node memvalidasi keabsahan hash dan mengeksekusinya. Agen pesaing tidak dapat mengintip dan menyalin payload di mempool publik.
13. **Skenario Kasus 3**: Dua validator independen melaporkan bahwa pada blok `#500`, data account state identik, namun `StateRoot` yang dihasilkan berbeda tipis di 2 byte terakhir. Setelah diisolasi, transaksi melibatkan pembaruan string metadata identitas agent yang menggunakan karakter Unicode. Jelaskan akar masalahnya!
    - *Solusi & Analisis*:
      - **Akar Masalah**: Ketidaksamaan normalisasi Unicode (*Unicode Normalization Form*). Satu sistem menggunakan normalisasi **NFC** (Canonical Decomposition, followed by Canonical Composition) sementara sistem lain menggunakan **NFD** (Canonical Decomposition) atau raw string encoding dari library JSON parser yang berbeda. Walaupun teks terbaca sama di layar, representasi byte utf-8 keduanya berbeda, menghasilkan hash daun (*leaf hash*) yang berbeda.
      - **Solusi**: Wajibkan standardisasi decoding biner ketat di layer serialisasi (misalnya Protobuf atau strict RLP) dan berlakukan normalisasi string eksplisit (misal: Unicode NFC via `golang.org/x/text/unicode/norm`) sebelum hash dihitung di seluruh node.

---

### 16. Summary

1. **Inti Blockchain**: Blockchain pada level sistem enterprise adalah *Deterministic State Machine Replication (SMR)* terdistribusi; tujuan utamanya adalah mengeksekusi batch transaksi yang terurut dan mempertahankan state yang identik di seluruh node tanpa mempercayai satu pihak pun.
2. **Determinisme Mutlak**: Seluruh operasi di dalam execution engine harus terbebas dari non-determinisme host (randomness, time dependency, pointer memory ordering, unpinned floating-point calculations, un-ordered map traversals).
3. **Pemisahan Concerns Arsitektur**: Arsitektur node modern memisahkan P2P Networking, Mempool Validation, Consensus (ordering), Execution (state transition), dan Commitment/Storage (SMT/MPT & LSM-Tree).
4. **Verifikasi Kriptografis Mandiri**: Penggunaan struktur data *Sparse Merkle Tree* memungkinkan verifikasi integritas status akun dan data AI Agent secara ringan, modular, dan dapat dibuktikan via cryptographic inclusion proofs ke sistem off-chain.