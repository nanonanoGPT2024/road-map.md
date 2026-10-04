# Bab 07: Penskalaan Layer 2 & Modular Data Availability
## Module 01: Arsitektur Modular Execution & Data Availability untuk Autonomous Agent Swarms

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** batasan throughput, state bloat, dan ekonomi gas pada arsitektur monolitik (Layer 1) saat mengeksekusi beban kerja *Autonomous Agent* berfrekuensi tinggi.
- **Merancang** topologi *modular rollup* yang memisahkan *Execution*, *Settlement*, *Consensus*, dan *Data Availability* (DA) secara matematis dan kriptografis.
- **Mengimplementasikan** mekanisme pemrosesan batch transaksi agen (*sequencing*), penghitungan komitmen *Namespaced Merkle Tree* (NMT), dan publikasi *blob* ke modular DA layer.
- **Membangun** pipeline verifikasi off-chain untuk *state root transition* dan pembuktian ketersediaan data menggunakan *KZG Commitments* / *Merkle Inclusion Proofs*.
- **Mengevaluasi & Memitigasi** anomali sistemik seperti *data withholding attacks*, *sequencer liveness failure*, dan *cross-layer state desynchronization*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Mental Model: Dekonstruksi Paradigma Monolitik
Pada arsitektur monolitik tradisional (misalnya Ethereum Layer 1 standar), sebuah *node* tunggal harus melakukan empat tugas sekaligus:
1. **Execution**: Menghitung transisi status (*state transition function* $S' = f(S, T_x)$).
2. **Settlement**: Menyelesaikan sengketa, memvalidasi bukti (*fraud/validity proof*), dan menjembatani likuiditas.
3. **Consensus**: Menyepakati urutan kanonikal transaksi (*transaction ordering*).
4. **Data Availability (DA)**: Menjamin bahwa data transaksi tersedia untuk diunduh dan diverifikasi oleh seluruh validator.

Beban komputasi gabungan ini menghasilkan *trilemma blockchain*. Sistem agen otonom (*Autonomous Agents*) yang memproses ribuan inferensi terdistribusi, negosiasi multi-agen, dan pertukaran sinyal mikropembayaran per detik akan langsung melumpuhkan rantai monolitik akibat biaya gas eksorbitan dan latensi blok.

```
       ARSITEKTUR MONOLITIK                ARSITEKTUR MODULAR
   +--------------------------+       +--------------------------+
   |        Execution         |       | Execution Layer (L2/L3)  | -> Agen Otonom (Off-chain VM)
   +--------------------------+       +--------------------------+
   |        Settlement        |       | Settlement Layer (L1/L2) | -> Bridge & Proof Verification
   +--------------------------+  vs   +--------------------------+
   |        Consensus         |       | Consensus Layer (L1/DA)  | -> Konsensus Urutan
   +--------------------------+       +--------------------------+
   |    Data Availability     |       | Data Availability Layer  | -> Celestia, EigenDA, EIP-4844
   +--------------------------+       +--------------------------+
```

#### Teori Inti: The Data Availability Problem & DAS
*Data Availability Problem* bukan persoalan penyimpanan jangka panjang (*storage archiving*), melainkan jaminan kriptografis pada saat blok diusulkan bahwa seluruh data transaksi benar-benar dipublikasikan ke jaringan sehingga validator mana pun dapat merekonstruksi *state* terbaru.

Untuk mencapai skalabilitas ekstrem tanpa mengorbankan keamanan, arsitektur modular menerapkan:
1. **Erasure Coding (2D Reed-Solomon Code)**: Mengubah data berukuran $M$ potongan menjadi $2M$ potongan. Operator hanya perlu mengumpulkan sebagian kecil pecahan unik untuk merekonstruksi keseluruhan data.
2. **Data Availability Sampling (DAS)**: *Light clients* dapat membuktikan dengan kepastian statistik tinggi ($> 99.99\%$) bahwa data tersedia hanya dengan meminta sampel acak berukuran kecil dari blok data tanpa perlu mengunduh seluruh *payload*.
3. **Namespaced Merkle Trees (NMT)**: Struktur pohon Merkle di mana daun (*leaf*) diurutkan berdasarkan *Namespace ID*. Ini memungkinkan setiap kelompok agen otonom hanya mengunduh data yang relevan dengan domain mereka sendiri (*filtered query*), membuktikan ketiadaan atau keberadaan transaksi dalam namespace secara kriptografis.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada ekosistem *AI Data & Autonomous Agents*, agen beroperasi secara kontinu:
- **Mikrotransaksi Frekuensi Tinggi**: Agen arbitrase atau perute likuiditas lintas rantai melakukan evaluasi status per milidetik.
- **Inference Attestation**: Mengirimkan bukti inferensi model AI (zkML atau optimis) ke buku besar.
- **Multi-Agent Coordination**: Orkestrasi ribuan sub-agen yang membutuhkan sinkronisasi status transparan.

**Dampak Kegagalan Arsitektur Monolitik:**
- **Economic Infeasibility**: Mengirimkan bukti input/output inferensi sebesar 500 KB ke Ethereum L1 memakan biaya calldata ribuan dolar saat gas tinggi. Pada modular DA (misal: Celestia, EigenDA, atau EIP-4844 Blobs), biaya tersebut turun hingga $99\%$.
- **Bandwidth Throttling**: L1 membatasi *block space*. Tanpa modularitas, throughput agen tercekik di kisaran 15–30 TPS, menghentikan automasi berbasis agen skala enterprise.
- **Sovereignty**: Lapisan eksekusi modular memungkinkan agen mendefinisikan *runtime environment* khusus (misal: EVM yang dimodifikasi dengan akselerasi WebAssembly atau precompile tensor algebra) tanpa terikat batasan eksekusi L1 dasar.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah end-to-end arsitektur modular rollup yang dirancang khusus untuk memproses volume transaksi agen otonom secara terpisah:

```
+-----------------------------------------------------------------------------------+
|                           AUTONOMOUS AGENTS ECOSYSTEM                             |
|  [Agent Worker 1]   [Agent Worker 2]   [Agent Worker 3] ... [Inference Verifier]  |
+-----------------------------------------------------------------------------------+
                                         │  Signed Action Payloads (JSON-RPC/gRPC)
                                         ▼
+-----------------------------------------------------------------------------------+
|                        MODULAR EXECUTION LAYER (ROLLUP)                           |
|  +-----------------------------------------------------------------------------+  |
|  | Mempool & Sequencer Pipeline                                                |  |
|  |  1. Ingestion Engine (Deduplication, Nonce Validation, Signature Check)    |  |
|  |  2. Agent State Transition Engine (Deterministic EVM/SVM State Executor)    |  |
|  |  3. State DB (Sparse Merkle Tree / Verkle Tree)                             |  |
|  +-----------------------------------------------------------------------------+  |
|                                        │                                          |
|        Raw Transactions Batch          │ Post-State Root (S') & Commitments       |
+────────────────────────────────────────┼──────────────────────────────────────────+
                         │               │
                         ▼               ▼
+------------------------------------+  +------------------------------------------+
|      DATA AVAILABILITY LAYER       |  |       SETTLEMENT / CONSENSUS LAYER       |
|  (e.g., Celestia / EigenDA / Blob) |  |             (e.g., Ethereum)             |
|                                    |  |                                          |
| +--------------------------------+ |  | +--------------------------------------+ |
| | Namespaced Merkle Tree (NMT)   | |  | | Rollup Bridge & Settlement Contract  | |
| | - Namespace: Agent_Telemetry   | |  | |                                      | |
| | - Namespace: Agent_Settlement  | |  | | - Invariant Check                    | |
| | - 2D Erasure Coding            | |  | | - Updates Canonical State Root       | |
| +--------------------------------+ |  | | - Resolves Fraud/Validity Proofs     | |
|                 │                  |  | +--------------------------------------+ |
|                 ▼                  |                       ▲                     |
|     DAS Sampling / DA Quorum       |                       │                     |
|                 │                  |                       │                     |
|                 └──────── Inclusion Proof / Blob Hash ─────┘                     |
+----------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Step 1: Penyerapan & Pengelompokan Data Agen (Batching)
Agen mengeksekusi aksi lokal dan menandatangani transaksi payload. Sequencer L2 menerima ribuan transaksi ini, memverifikasi tanda tangan kriptografis, dan mengeksekusi transisi status internal:

$$S_{t+1} = \text{STF}(S_t, \text{Tx}_i)$$

Di mana $\text{STF}$ adalah *State Transition Function*. Sequencer menghasilkan `Intermediate State Roots` dan mengelompokkan transaksi ke dalam blok eksekusi terkompresi.

#### Step 2: Fragmentasi Berbasis Namespaced Merkle Tree (NMT)
Sebelum mempublikasikan data ke DA Layer, sequencer memetakan transaksi berdasarkan namespace:
- Namespace `0x00000001`: Pendaftaran identitas & izin Agen (*Registry*).
- Namespace `0x00000002`: Bukti komputasi inferensi (*zkML/Attestation payloads*).
- Namespace `0x00000003`: Mikropembayaran & penyelesaian saldo antar-agen (*Settlement balance*).

Setiap *node* pada NMT memiliki format:

$$\text{Node} = \text{Hash}(\text{min\_ns} \mathbin{\Vert} \text{max\_ns} \mathbin{\Vert} \text{left\_child} \mathbin{\Vert} \text{right\_child})$$

Properti ini menjamin bahwa setiap *node* membawa rentang namespace eksplisit dari anak-anaknya, memungkinkan pembuktian bersyarat (*range proofs*) tanpa kebocoran data lain.

#### Step 3: Publikasi Blob DA & Penyelesaian L1
1. **DA Submission**: Sequencer mengirimkan paket data ke DA layer sebagai *Blob*. DA layer mengkodekan data menggunakan Reed-Solomon 2D, membaginya ke dalam matriks kuadrat, menghitung akar Merkle/KZG, dan memberikan sertifikat DA (*Data Availability Certificate* / DAC) atau tanda terima blok.
2. **Settlement Anchoring**: Sequencer memanggil kontrak cerdas settlement pada L1 dengan argumen:
   - `prev_state_root`
   - `new_state_root`
   - `blob_commitment` (atau pointer DA reference: Block Height, Namespace, Merkle/KZG Root)
3. **Verifikasi L1**: L1 memverifikasi apakah DA inclusion proof valid atau apakah komitmen blob telah terdaftar secara kanonikal sebelum memperbarui *state root*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Modular Rollup Sequencer Engine** berbasis **Go (Golang)** yang siap produksi. Komponen ini menangani konsumsi transaksi agen, pengelompokan ke dalam Namespaced Merkle Data, simulasi transmisi ke DA Layer, dan pengiriman akar transisi status ke lapisan L1 Settlement.

```go
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"sort"
	"sync"
	"time"
)

// --- Domain Models ---

type NamespaceID [8]byte

type AgentTransaction struct {
	ID          string      `json:"id"`
	AgentID     string      `json:"agent_id"`
	Namespace   NamespaceID `json:"namespace"`
	Payload     []byte      `json:"payload"`
	Nonce       uint64      `json:"nonce"`
	Signature   []byte      `json:"signature"`
	GasUsed     uint64      `json:"gas_used"`
}

type NMTNode struct {
	MinNS []byte
	MaxNS []byte
	Hash  [32]byte
}

type BlobCommitment struct {
	DAHeight  uint64   `json:"da_height"`
	DataRoot  [32]byte `json:"data_root"`
	Namespace NamespaceID
}

type StateTransitionBatch struct {
	BatchNumber  uint64          `json:"batch_number"`
	PrevState    [32]byte        `json:"prev_state"`
	NewState     [32]byte        `json:"new_state"`
	BlobRef      BlobCommitment  `json:"blob_ref"`
	TxCount      int             `json:"tx_count"`
	Timestamp    int64           `json:"timestamp"`
}

// --- Namespaced Merkle Tree Logic ---

type NamespacedData struct {
	Namespace NamespaceID
	Data      []byte
}

func HashLeaf(ns NamespaceID, data []byte) NMTNode {
	h := sha256.New()
	h.Write(ns[:])
	h.Write(data)
	var digest [32]byte
	copy(digest[:], h.Sum(nil))

	return NMTNode{
		MinNS: ns[:],
		MaxNS: ns[:],
		Hash:  digest,
	}
}

func HashNode(left, right NMTNode) NMTNode {
	h := sha256.New()
	
	// Min namespace adalah batas bawah dari anak kiri
	minNS := left.MinNS
	// Max namespace adalah batas atas dari anak kanan (jika daun terurut)
	maxNS := right.MaxNS
	if bytes.Compare(left.MaxNS, right.MaxNS) > 0 {
		maxNS = left.MaxNS
	}

	h.Write(left.MinNS)
	h.Write(left.MaxNS)
	h.Write(left.Hash[:])
	h.Write(right.MinNS)
	h.Write(right.MaxNS)
	h.Write(right.Hash[:])

	var digest [32]byte
	copy(digest[:], h.Sum(nil))

	return NMTNode{
		MinNS: minNS,
		MaxNS: maxNS,
		Hash:  digest,
	}
}

func BuildNMT(items []NamespacedData) ([32]byte, error) {
	if len(items) == 0 {
		return [32]byte{}, errors.New("cannot build NMT with zero items")
	}

	// Sortir berdasarkan Namespace ID secara ketat
	sort.Slice(items, func(i, j int) bool {
		return bytes.Compare(items[i].Namespace[:], items[j].Namespace[:]) < 0
	})

	var currentLevel []NMTNode
	for _, item := range items {
		currentLevel = append(currentLevel, HashLeaf(item.Namespace, item.Data))
	}

	for len(currentLevel) > 1 {
		if len(currentLevel)%2 != 0 {
			// Duplicate leaf ganjil
			currentLevel = append(currentLevel, currentLevel[len(currentLevel)-1])
		}

		var nextLevel []NMTNode
		for i := 0; i < len(currentLevel); i += 2 {
			nextLevel = append(nextLevel, HashNode(currentLevel[i], currentLevel[i+1]))
		}
		currentLevel = nextLevel
	}

	return currentLevel[0].Hash, nil
}

// --- Interfaces for Modular Components ---

type DataAvailabilityClient interface {
	SubmitBlob(ctx context.Context, ns NamespaceID, data []byte) (BlobCommitment, error)
	VerifyBlobInclusion(ctx context.Context, commit BlobCommitment) (bool, error)
}

type SettlementContract interface {
	PostStateUpdate(ctx context.Context, batch StateTransitionBatch) error
	GetLatestStateRoot(ctx context.Context) ([32]byte, error)
}

// --- Mock Implementations (Enterprise Testing) ---

type MockCelestiaDAClient struct {
	mu           sync.Mutex
	currentHeight uint64
}

func NewMockCelestiaDAClient() *MockCelestiaDAClient {
	return &MockCelestiaDAClient{currentHeight: 1000}
}

func (m *MockCelestiaDAClient) SubmitBlob(ctx context.Context, ns NamespaceID, data []byte) (BlobCommitment, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	select {
	case <-ctx.Done():
		return BlobCommitment{}, ctx.Err()
	default:
	}

	m.currentHeight++
	h := sha256.Sum256(data)

	return BlobCommitment{
		DAHeight:  m.currentHeight,
		DataRoot:  h,
		Namespace: ns,
	}, nil
}

func (m *MockCelestiaDAClient) VerifyBlobInclusion(ctx context.Context, commit BlobCommitment) (bool, error) {
	return commit.DAHeight > 0 && commit.DataRoot != [32]byte{}, nil
}

type MockL1Settlement struct {
	mu        sync.RWMutex
	stateRoot [32]byte
	history   []StateTransitionBatch
}

func NewMockL1Settlement(initialState [32]byte) *MockL1Settlement {
	return &MockL1Settlement{stateRoot: initialState}
}

func (s *MockL1Settlement) PostStateUpdate(ctx context.Context, batch StateTransitionBatch) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if batch.PrevState != s.stateRoot {
		return fmt.Errorf("invalid state transition: expected %x, got %x", s.stateRoot, batch.PrevState)
	}

	s.stateRoot = batch.NewState
	s.history = append(s.history, batch)
	return nil
}

func (s *MockL1Settlement) GetLatestStateRoot(ctx context.Context) ([32]byte, error) {
	s.mu.RUnlock()
	defer s.mu.RUnlock()
	return s.stateRoot, nil
}

// --- Production Rollup Sequencer Engine ---

type SequencerConfig struct {
	BatchSizeLimit int
	FlushInterval  time.Duration
	MaxRetries     int
}

type AgentRollupSequencer struct {
	cfg        SequencerConfig
	daClient   DataAvailabilityClient
	settlement SettlementContract
	txMempool  chan AgentTransaction
	stateRoot  [32]byte
	batchSeq   uint64

	mu         sync.Mutex
	ctx        context.Context
	cancel     context.CancelFunc
	wg         sync.WaitGroup
}

func NewAgentRollupSequencer(
	cfg SequencerConfig,
	daClient DataAvailabilityClient,
	settlement SettlementContract,
	genesisState [32]byte,
) *AgentRollupSequencer {
	ctx, cancel := context.WithCancel(context.Background())
	return &AgentRollupSequencer{
		cfg:        cfg,
		daClient:   daClient,
		settlement: settlement,
		txMempool:  make(chan AgentTransaction, 5000),
		stateRoot:  genesisState,
		batchSeq:   0,
		ctx:        ctx,
		cancel:     cancel,
	}
}

func (seq *AgentRollupSequencer) Start() {
	seq.wg.Add(1)
	go seq.batchingLoop()
}

func (seq *AgentRollupSequencer) Stop() {
	seq.cancel()
	seq.wg.Wait()
	close(seq.txMempool)
}

func (seq *AgentRollupSequencer) EnqueueTransaction(tx AgentTransaction) error {
	select {
	case <-seq.ctx.Done():
		return errors.New("sequencer stopped")
	case seq.txMempool <- tx:
		return nil
	default:
		return errors.New("mempool buffer saturated; backpressure activated")
	}
}

func (seq *AgentRollupSequencer) batchingLoop() {
	defer seq.wg.Done()
	ticker := time.NewTicker(seq.cfg.FlushInterval)
	defer ticker.Stop()

	var pendingBatch []AgentTransaction

	for {
		select {
		case <-seq.ctx.Done():
			if len(pendingBatch) > 0 {
				_ = seq.processBatch(pendingBatch)
			}
			return

		case tx := <-seq.txMempool:
			pendingBatch = append(pendingBatch, tx)
			if len(pendingBatch) >= seq.cfg.BatchSizeLimit {
				if err := seq.processBatch(pendingBatch); err != nil {
					fmt.Printf("[CRITICAL ERROR] Failed to process batch: %v\n", err)
				}
				pendingBatch = nil
			}

		case <-ticker.C:
			if len(pendingBatch) > 0 {
				if err := seq.processBatch(pendingBatch); err != nil {
					fmt.Printf("[CRITICAL ERROR] Failed to flush batch: %v\n", err)
				}
				pendingBatch = nil
			}
		}
	}
}

func (seq *AgentRollupSequencer) processBatch(txs []AgentTransaction) error {
	seq.mu.Lock()
	defer seq.mu.Unlock()

	var nmtItems []NamespacedData
	marshaledTxs, err := json.Marshal(txs)
	if err != nil {
		return fmt.Errorf("failed to serialize batch: %w", err)
	}

	for _, tx := range txs {
		txRaw, _ := json.Marshal(tx)
		nmtItems = append(nmtItems, NamespacedData{
			Namespace: tx.Namespace,
			Data:      txRaw,
		})
	}

	// 1. Hitung Root NMT
	nmtRoot, err := BuildNMT(nmtItems)
	if err != nil {
		return fmt.Errorf("failed to build NMT: %w", err)
	}

	// 2. Dispatch payload ke DA Layer
	var defaultNamespace NamespaceID
	copy(defaultNamespace[:], []byte("AGENT_TX"))
	
	blobCommitment, err := seq.dispatchWithRetry(func() (BlobCommitment, error) {
		return seq.daClient.SubmitBlob(seq.ctx, defaultNamespace, marshaledTxs)
	})
	if err != nil {
		return fmt.Errorf("da publication aborted: %w", err)
	}

	// 3. Simulasi Transisi State Off-Chain (State Transition Function)
	newStateRoot := seq.computeNewState(seq.stateRoot, nmtRoot, txs)

	// 4. Update ke Settlement Layer (L1)
	seq.batchSeq++
	batchEnvelope := StateTransitionBatch{
		BatchNumber: seq.batchSeq,
		PrevState:   seq.stateRoot,
		NewState:    newStateRoot,
		BlobRef:     blobCommitment,
		TxCount:     len(txs),
		Timestamp:   time.Now().Unix(),
	}

	err = seq.settlement.PostStateUpdate(seq.ctx, batchEnvelope)
	if err != nil {
		return fmt.Errorf("l1 settlement failed: %w", err)
	}

	// Mutasi status lokal sequencer setelah L1 berhasil di-update
	seq.stateRoot = newStateRoot
	fmt.Printf("[BATCH COMMITTED] Seq: %d | Txs: %d | DA Block: %d | New State: %x\n",
		batchEnvelope.BatchNumber, batchEnvelope.TxCount, blobCommitment.DAHeight, newStateRoot[:8])

	return nil
}

func (seq *AgentRollupSequencer) computeNewState(currentState [32]byte, nmtRoot [32]byte, txs []AgentTransaction) [32]byte {
	h := sha256.New()
	h.Write(currentState[:])
	h.Write(nmtRoot[:])
	
	// Deterministic execution accumulator (dummy state update untuk demo engine)
	nonceAcc := make([]byte, 8)
	binary.BigEndian.PutUint64(nonceAcc, uint64(len(txs)))
	h.Write(nonceAcc)

	var res [32]byte
	copy(res[:], h.Sum(nil))
	return res
}

func (seq *AgentRollupSequencer) dispatchWithRetry(fn func() (BlobCommitment, error)) (BlobCommitment, error) {
	var lastErr error
	backoff := 50 * time.Millisecond

	for i := 0; i < seq.cfg.MaxRetries; i++ {
		commit, err := fn()
		if err == nil {
			return commit, nil
		}
		lastErr = err
		select {
		case <-seq.ctx.Done():
			return BlobCommitment{}, seq.ctx.Err()
		case <-time.After(backoff):
			backoff *= 2
		}
	}
	return BlobCommitment{}, fmt.Errorf("exhausted retries: %w", lastErr)
}

// --- Main Verification Flow ---

func main() {
	var genesis [32]byte
	copy(genesis[:], []byte("GENESIS_AGENT_STATE_ROOT_0000000"))

	daClient := NewMockCelestiaDAClient()
	settlement := NewMockL1Settlement(genesis)

	config := SequencerConfig{
		BatchSizeLimit: 3,
		FlushInterval:  200 * time.Millisecond,
		MaxRetries:     3,
	}

	sequencer := NewAgentRollupSequencer(config, daClient, settlement, genesis)
	sequencer.Start()
	defer sequencer.Stop()

	// Simulasi transaksi agen yang masuk
	var nsInference NamespaceID
	copy(nsInference[:], []byte("INFERENC"))

	var nsPayment NamespaceID
	copy(nsPayment[:], []byte("PAYMENT0"))

	txPool := []AgentTransaction{
		{
			ID:        "tx-001",
			AgentID:   "agent-alpha",
			Namespace: nsInference,
			Payload:   []byte("inference_proof_model_v4_result_hash_abc"),
			Nonce:     1,
		},
		{
			ID:        "tx-002",
			AgentID:   "agent-beta",
			Namespace: nsPayment,
			Payload:   []byte("transfer_micro_dai_to_gamma"),
			Nonce:     1,
		},
		{
			ID:        "tx-003",
			AgentID:   "agent-gamma",
			Namespace: nsInference,
			Payload:   []byte("inference_proof_model_v4_result_hash_def"),
			Nonce:     2,
		},
	}

	for _, tx := range txPool {
		if err := sequencer.EnqueueTransaction(tx); err != nil {
			fmt.Printf("Tx Dropped: %v\n", err)
		}
	}

	// Berikan waktu proses batching dan flushing
	time.Sleep(500 * time.Millisecond)

	finalRoot, _ := settlement.GetLatestStateRoot(context.Background())
	fmt.Printf("[FINAL L1 SETTLED STATE] Root: %x\n", finalRoot)
}
```

---

### 7. Edge Cases & Failure Modes (Error Recovery, Validasi, Fallback)

| Kategori Skenario | Mekanisme Kegagalan | Dampak | Penanganan & Pola Pemulihan (*Mitigation*) |
| :--- | :--- | :--- | :--- |
| **Data Withholding Attack** | Sequencer mempublikasikan `New State Root` ke L1, tetapi menolak mempublikasikan data transaksi ke DA layer. | Node lain tidak dapat merekonstruksi *state* untuk mendeteksi penipuan (*fraud*). | L1 settlement contract menerapkan validasi **Blob Inclusion Proof**: L1 menolak pembaruan status kecuali ada bukti DA (*DA attestation certificate* dari quorum atau via EIP-4844 *point evaluation precompile*). |
| **DA Layer Congestion** | Antrean blob pada DA layer memicu lonjakan biaya atau penundaan inklusi (*timeout*). | Penurunan *throughput* agen; antrean mempool sequencer penuh. | **Dynamic Fallback Escalation**: Jika konfirmasi DA melebihi batas $N$ detik, sequencer beralih otomatis ke *fallback* (misalnya dari Celestia ke EigenDA, atau menulis calldata terkompresi langsung ke L1 dengan memotong margin transaksi). |
| **L1 Chain Reorganization** | L1 mengalami reorg setinggi $k$ blok setelah sequencer melakukan settlement. | *State root* pada L1 kembali ke kondisi masa lalu, menyebabkan desinkronisasi sequencer. | Sequencer memelihara *checkpoint DAG*. Penyelesaian final baru diakui jika blok L1 mencapai kedalaman finalitas kanonikal (*finalized block tag*). Mekanisme *unwind* dan *replay* membatalkan status transisi lokal secara deterministik. |
| **Sequencer Byzantine/Censorship** | Sequencer menyensor agen tertentu secara sengaja atau mengalami downtime total. | Agen tidak dapat memvalidasi inferensi atau mencairkan saldo. | **Forced Inclusion Mechanism (Escape Hatch)**: Agen mengirimkan payload langsung ke kontrak L1 inbox (`enqueueTransaction`). Sequencer diwajibkan memproses transaksi L1 dalam $W$ blok, atau kehilangan hak sequencing (*slashing*). |
| **Namespace Boundary Collision** | Agen menyuntikkan Namespace ID yang sengaja dibuat bertabrakan (*spoofing* range minimum/maksimum). | Gangguan pada verifikasi filter NMT downstream. | Validasi ketat pada parsing serialization daun NMT. Enforce deterministik panjang byte namespace (8 bytes fix) dan penolakan *reserved system namespaces*. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur modular melibatkan kompromi fundamental antara latensi, biaya, dan dependensi kriptografis.

```
                              ANALISIS KOMPROMI ARSITEKTUR
   Tinggi ^
          │                                         [Rollup + EIP-4844]
          │                                           (Ethereum Native Security)
  KEAMANAN│
          │                   [Rollup + Celestia/EigenDA]
          │                     (High Throughput, Low Cost)
          │
          │   [Validium / DAC]
          │     (Lowest Cost, Centralized Quorum)
   Rendah └─────────────────────────────────────────────────────────────>
          Rendah                    BIAYA OPERASIONAL                  Tinggi
```

#### Matriks Perbandingan Komparatif

| Solusi / Pendekatan | Biaya DA (per MB) | Waktu Finalitas | Asumsi Keamanan | Beban Operasional |
| :--- | :--- | :--- | :--- | :--- |
| **L1 Calldata Tradisional** | Sangat Tinggi (~$50 - $300 tergantung gas) | ~12 Detik (Ethereum Slot) | Konsensus L1 penuh (Ethereum PoS Validator Set) | Minimal (Semua di L1, tanpa dependensi eksternal) |
| **EIP-4844 Blobs (Proto-Danksharding)** | Menengah ($0.50 - $5.00) | ~12 Menit (Epoch Finality) | Keamanan L1 asli via KZG Polynomial Commitments | Menengah (Manajemen siklus hidup *pruning blob* 18 hari) |
| **Modular DA (Celestia)** | Sangat Rendah (< $0.05) | ~12 - 15 Detik (Tendermint BFT) | 2/3 Byzantine Stake Celestia Validator Set + DAS | Menengah-Tinggi (Perlu integrasi Light Node & Bridge) |
| **Restaked DA (EigenDA)** | Sangat Rendah (< $0.02) | ~1 - 5 Detik | Operator Ethereum Restaking (EigenLayer Slashable Stake) | Kompleks (Infrastruktur disperser, sertifikat KZG) |
| **Data Availability Committees (DAC / Validium)** | Hampir Nol (< $0.001) | Sub-detik | Asumsi kejujuran komite $M$-of-$N$ (Off-chain federation) | Rendah (Kerapuhan keamanan jika anggota komite berkolusi) |

---

### 9. Best Practices & Standard Industri

1. **Strukturasi Namespace Hierarkis untuk Agen Otonom**:
   Bagi *Namespace ID* ke dalam hierarki modular untuk mencegah pemindaian data yang tidak efisien:
   ```
   [0x00]: Protocol Reserved
   [0x01]: Agent Registry & Staking
   [0x02]: Inference Attestations (zkML/Optimistic Output)
   [0x03]: Inter-Agent Dialogue & Coordination Logs
   [0x04]: Settlement / Balance Delta
   ```
2. **Commitment vs Payload Separation**:
   Jangan pernah menyertakan model weights AI atau tensor data mentah ke dalam payload transaksi rollup. Selalu kirimkan *Pedersen Hash* atau *Keccak-256 Commitments* dari data tensor ke DA layer, dengan data tensor tersimpan di jaringan terdesentralisasi terpisah (IPFS/Arweave).
3. **Blob Retention & Archival Strategy**:
   Data pada DA layer (seperti EIP-4844 atau Celestia) dirancang untuk dipangkas (*pruning*) setelah durasi tertentu (18–30 hari). Tim pengembang wajib menerapkan node pengarsip khusus (*Agent Archival Nodes*) untuk mengekstraksi data sebelum masa retensi habis jika riwayat diperlukan untuk audit regulasi model AI.
4. **Idempotency & Nonce Management pada Autonomous Execution**:
   Agen yang berjalan secara multithreaded dapat mengalami kekacauan urutan eksekusi (*race condition*). Gunakan *Deterministic Salt Nonces* berformat:
   $$\text{Nonce} = \text{AgentID} \mathbin{\Vert} \text{EpochID} \mathbin{\Vert} \text{Counter}$$
5. **Decoupled Verification Pipelines**:
   Pisahkan *Sequencer Node* (fokus pada *throughput* dan *low-latency packing*) dari *Prover Node* (fokus pada pembuatan bukti matematis ZK atau pemantauan fraud). Beban kalkulasi prover tidak boleh mengganggu responsivitas sequencer.

---

### 10. Hands-on Lab Exercise: Membangun Pipeline Rollup Batcher dengan Namespaced Data Verification

#### Sasaran Lab
Membangun skrip verifikasi off-chain yang menerima batch transaksi agen, memvalidasi bukti keanggotaan NMT, dan membuktikan apakah suatu transaksi spesifik dari Agen $A$ termuat di dalam DA root tanpa harus membaca seluruh isi blok transaksi.

#### Prerequisites
- Go Runtime 1.21+ terinstal
- Editor kode (VS Code / GoLand)

#### Langkah 1: Siapkan Direktori & Inisialisasi
```bash
mkdir -p agent-modular-da && cd agent-modular-da
go mod init agent-modular-da
```

#### Langkah 2: Buat Modul Verifikasi Keanggotaan NMT
Buat berkas `nmt_verifier.go`:

```go
package main

import (
	"bytes"
	"crypto/sha256"
	"errors"
	"fmt"
)

type InclusionProofNode struct {
	IsRight bool
	MinNS   []byte
	MaxNS   []byte
	Hash    [32]byte
}

func VerifyNMTMembership(
	root [32]byte,
	targetNS []byte,
	leafData []byte,
	proof []InclusionProofNode,
) (bool, error) {
	// 1. Rekonstruksi hash daun dasar
	h := sha256.New()
	h.Write(targetNS)
	h.Write(leafData)
	var currentDigest [32]byte
	copy(currentDigest[:], h.Sum(nil))

	currentMinNS := targetNS
	currentMaxNS := targetNS

	// 2. Traversal ke atas pohon menggunakan sibling proof
	for _, sibling := range proof {
		hasher := sha256.New()

		if sibling.IsRight {
			// Sibling ada di sebelah kanan
			hasher.Write(currentMinNS)
			hasher.Write(currentMaxNS)
			hasher.Write(currentDigest[:])
			hasher.Write(sibling.MinNS)
			hasher.Write(sibling.MaxNS)
			hasher.Write(sibling.Hash[:])

			// Update max namespace jika saudara lebih besar
			if bytes.Compare(sibling.MaxNS, currentMaxNS) > 0 {
				currentMaxNS = sibling.MaxNS
			}
		} else {
			// Sibling ada di sebelah kiri
			hasher.Write(sibling.MinNS)
			hasher.Write(sibling.MaxNS)
			hasher.Write(sibling.Hash[:])
			hasher.Write(currentMinNS)
			hasher.Write(currentMaxNS)
			hasher.Write(currentDigest[:])

			// Update min namespace ke saudara kiri
			currentMinNS = sibling.MinNS
		}

		copy(currentDigest[:], hasher.Sum(nil))
	}

	// 3. Periksa apakah akar hasil perhitungan identik dengan root yang dikomit
	if currentDigest != root {
		return false, fmt.Errorf("root mismatch: calculated %x != expected %x", currentDigest, root)
	}

	return true, nil
}
```

#### Langkah 3: Eksekusi Skenario Pengujian Verifikasi Bukti
Tambahkan implementasi runner pada `main.go`:

```go
package main

import (
	"crypto/sha256"
	"fmt"
)

func main() {
	fmt.Println("=== Hands-on Lab: Modular NMT Verification Pipeline ===")

	nsAgent := []byte("AGENT_01")
	txPayload := []byte("ACTION: TRANSFER_100_CREDITS_TO_AGENT_02")

	// Bentuk simulasi Leaf Left (Target Kita)
	hTarget := sha256.New()
	hTarget.Write(nsAgent)
	hTarget.Write(txPayload)
	var targetDigest [32]byte
	copy(targetDigest[:], hTarget.Sum(nil))

	// Bentuk simulasi Leaf Right (Sibling)
	nsSibling := []byte("AGENT_02")
	siblingData := []byte("ACTION: CONFIRM_TASK_COMPLETION")
	hSib := sha256.New()
	hSib.Write(nsSibling)
	hSib.Write(siblingData)
	var sibDigest [32]byte
	copy(sibDigest[:], hSib.Sum(nil))

	// Hitung expected root secara manual
	hRoot := sha256.New()
	hRoot.Write(nsAgent)   // Left min
	hRoot.Write(nsAgent)   // Left max
	hRoot.Write(targetDigest[:])
	hRoot.Write(nsSibling) // Right min
	hRoot.Write(nsSibling) // Right max
	hRoot.Write(sibDigest[:])
	var expectedRoot [32]byte
	copy(expectedRoot[:], hRoot.Sum(nil))

	// Buat struktur proof untuk leaf target
	proof := []InclusionProofNode{
		{
			IsRight: true,
			MinNS:   nsSibling,
			MaxNS:   nsSibling,
			Hash:    sibDigest,
		},
	}

	// Uji 1: Verifikasi Valid
	valid, err := VerifyNMTMembership(expectedRoot, nsAgent, txPayload, proof)
	if err != nil || !valid {
		fmt.Printf("[GAGAL] Pengujian 1 Gagal: %v\n", err)
	} else {
		fmt.Println("[BERHASIL] Pengujian 1: Inklusi transaksi Agen 01 terverifikasi secara valid pada root!")
	}

	// Uji 2: Deteksi Tampering Payload
	tamperedPayload := []byte("ACTION: TRANSFER_999999_CREDITS_TO_ATTACKER")
	_, errTampered := VerifyNMTMembership(expectedRoot, nsAgent, tamperedPayload, proof)
	if errTampered != nil {
		fmt.Println("[BERHASIL] Pengujian 2: Manipulasi transaksi berhasil dideteksi dan ditolak!")
	} else {
		fmt.Println("[GAGAL] Pengujian 2: Sistem gagal mendeteksi modifikasi data ilegal!")
	}
}
```

#### Langkah 4: Uji Coba Implementasi
Jalankan perintah berikut:
```bash
go run main.go nmt_verifier.go
```

**Ekspektasi Output:**
```text
=== Hands-on Lab: Modular NMT Verification Pipeline ===
[BERHASIL] Pengujian 1: Inklusi transaksi Agen 01 terverifikasi secara valid pada root!
[BERHASIL] Pengujian 2: Manipulasi transaksi berhasil dideteksi dan ditolak!
```

---

### Verifikasi Mandiri & Tugas Lanjutan
1. Modifikasi fungsi pohon NMT agar mampu menangani pohon dengan kedalaman $\ge 3$ tingkat (misalnya memproses 8 transaksi dengan 4 namespace berbeda).
2. Tulis tes benchmarking (`go test -bench=.`) untuk mengukur throughput verifikasi inklusi per detik pada 10.000 transaksi agen serentak.
3. Rancang mekanisme *circuit breaker* pada Sequencer: jika koneksi DA Layer terputus selama 3 siklus flush, tahan eksekusi transaksi agen baru (*fail-closed*) dan amankan log buffer ke disk berformat WAL (*Write-Ahead Logging*).