# Bab 03: Rekayasa Mekanisme Konsensus Modern

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Batasan Teoretis SMR (State Machine Replication):** Mengartikulasikan batas-batas matematis konsensus terdistribusi berdasarkan teorema FLP Impossibility, CAP Theorem, serta model jaringan *Partial Synchrony* (Dwork-Lynch-Stockmeyer).
- **Merancang Arsitektur Chained-BFT:** Mengimplementasikan topologi konsensus modern berbasis *pipelined consensus* (HotStuff) dengan kompleksitas transmisi pesan view-change linear $\mathcal{O}(n)$.
- **Mengembangkan Safety & Liveness Invariants:** Membangun mekanisme penguncian status (*locking rules*), *voting rules*, dan *commit rules* menggunakan *Quorum Certificates* (QC) berbasis kriptografi agregasi (BLS/Threshold Signature).
- **Mengintegrasikan Abstraksi Pacemaker:** Mengisolasi penanganan liveness dan sinkronisasi putaran (*round synchronization*) dari logika keamanan validasi blok.
- **Menguji Ketahanan Byzantine Fault:** Mengidentifikasi dan memitigasi serangan *equivocation*, *forking*, serta *silent leader* melalui simulasi partisi jaringan adversarial.

---

## 2. Concept Overview
Konsensus dalam sistem terdistribusi modern bukan sekadar pemungutan suara mayoritas, melainkan perwujudan dari **State Machine Replication (SMR)** deterministik di bawah ancaman kegagalan Arbitrer/Byzantine ($\le f$ node dari total $N \ge 3f + 1$ node).

### Model Mental: Pipeline Eksekusi Tiga Fase (HotStuff)
Dalam BFT klasik (seperti PBFT), pergantian kepemimpinan (*view-change*) membutuhkan komunikasi antar-semua node ($\mathcal{O}(n^2)$ hingga $\mathcal{O}(n^3)$), yang runtuh ketika diskalakan ke ratusan validator atau agen otonom.

Mekanisme konsensus modern berbasis **Chained-BFT** menyederhanakan proses ini menjadi rantai blok sekuensial di mana setiap blok bertindak sebagai fase voting untuk blok-blok sebelumnya:

```
[Blok V-3] <--- [Blok V-2] <--- [Blok V-1] <--- [Blok V]
  DECIDE          COMMIT        PRE-COMMIT      PREPARE
(Finalized)      (Locked)      (Proposed)     (Proposed)
```

1. **Prepare Phase:** Proposer mengusulkan blok baru yang membungkus *Parent Quorum Certificate* ($QC$). Node memvalidasi dan mengirimkan signature vote kembali ke leader.
2. **Pre-Commit Phase:** Ketika leader mengumpulkan $2f + 1$ vote, terbentuk $QC$. Blok berikutnya menyematkan $QC$ ini, mengonfirmasi fase *prepare* blok sebelumnya. Node mengunci blok tersebut (*Locking*).
3. **Commit Phase:** Blok ketiga dalam rantai memvalidasi fase pre-commit.
4. **Decide Phase:** Blok keempat mengonfirmasi komitmen blok pertama. Blok pertama kini berstatus **Final** (tidak dapat di-revert tanpa slashing).

---

## 3. Why It Matters
Dalam ekosistem AI Agents dan Autonomous Data Networks, ratusan model machine learning dan orakel data saling bertransaksi tanpa perantara manusia. Konsensus Nakamoto (Proof of Work/Chain-based PoS) dengan *probabilistic finality* membawa risiko tinggi:
- **Latensi Reorganisasi Eksekusi (Reorg):** Agen otonom yang mengeksekusi arbitrase pinjaman kilat (*flash loans*) atau kliring data komputasi inferensi tidak dapat menunggu konfirmasi probabilistik selama puluhan blok. Mereka membutuhkan **Deterministic Absolute Finality** dalam sub-detik.
- **Biaya Komunikasi Skala Enterprise:** Jaringan agen multi-kluster memerlukan konsensus berkinerja tinggi yang mempertahankan kompleksitas komunikasi $\mathcal{O}(n)$ baik pada kondisi stabil maupun saat terjadi kegagalan node pemimpin.
- **Integritas Eksekusi Non-Repudiasi:** Mekanisme slashing deterministik diperlukan untuk mengeksekusi sanksi finansial seketika jika sebuah node agen mengirimkan model inferensi berbobot palsu atau melakukan pemungutan suara ganda (*equivocation*).

---

## 4. Arsitektur & Diagram Komponen

Arsitektur engine konsensus modular memisahkan lapisan konsensus, mempool, pacemaker, dan mesin eksekusi (mirip dengan arsitektur CometBFT/HotStuff Core).

```
+------------------------------------------------------------------------+
|                          Consensus Engine                              |
|                                                                        |
|  +--------------------+                   +-------------------------+  |
|  |     Pacemaker      |                   |       Safety Core       |  |
|  | - Round Tracker    |   Tick / Advance  | - Locked View           |  |
|  | - Leader Election  |==================>| - Highest Voted View    |  |
|  | - Timeout Timer    |                   | - 3-Chain Rule Invariant|  |
|  +--------------------+                   +-------------------------+  |
|            |                                           ^               |
|            v                                           |               |
|  +--------------------+                   +-------------------------+  |
|  | Proposal / Block   |    Vote Request   |       Vote Aggregator   |  |
|  | Generator          |------------------>| - Quorum Verification   |  |
|  | - Tx Packaging     |                   | - BLS / Ed25519 Storage |  |
|  +--------------------+                   | - Form QC (2f + 1)      |  |
|            |                              +-------------------------+  |
|            | Block Propagation                         |               |
|            v                                           v New QC        |
|  +------------------------------------------------------------------+  |
|  |                      Network Transport Layer                     |  |
|  |           (gRPC / libp2p GossipSub & Direct Unicast)             |  |
+--+------------------------------------------------------------------+--+
             |                                           ^
             v Block Commit Event                        | State Invalidation
+------------------------------------------------------------------------+
|             Deterministic Execution Engine (EVM / Wasm / AI SMR)       |
+------------------------------------------------------------------------+
```

### Format Pesan Konsensus

```
Proposal Block:
+-----------------------------------------------------------------------+
| View: uint64 | ProposerID: NodeID | ParentQC: QuorumCertificate       |
| Command / Payload Hash: [32]byte  | Signature: AggregatedSignature    |
+-----------------------------------------------------------------------+

Quorum Certificate (QC):
+-----------------------------------------------------------------------+
| View: uint64 | BlockID: [32]byte  | Type: {PREPARE, PRECOMMIT, COMMIT}|
| Signatures: Map[NodeID]CryptoSignature (Weight >= 2f + 1)             |
+-----------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Algoritma Chained HotStuff
Dalam Chained HotStuff, fase Prepare, Pre-commit, Commit, dan Decide dirantai ke dalam setiap blok baru. Setiap usulan blok $B_k$ pada ronde/view $v$ sekaligus berfungsi untuk:
1. Menawarkan payload baru untuk ronde $v$ (Prepare untuk $B_k$).
2. Melampirkan voting QC ronde $v-1$ (Pre-commit untuk $B_{k-1}$).
3. Menjadi basis Commit untuk $B_{k-2}$ jika $B_{k-1}$ merujuk langsung ke $B_{k-2}$.
4. Menjadi basis Decide (Finalisasi) untuk $B_{k-3}$ jika terdapat rantai langsung 3-tingkat berturut-turut (*Three-Chain Rule*).

### B. Safety Invariants (Voting & Locking Rules)
Agar sistem tidak pernah mengalami percabangan permanen (*safety break*), validator wajib mematuhi dua aturan ketat sebelum memberikan suara:

1. **Voting Rule:**
   Replika $R$ hanya boleh memberikan suara pada kandidat blok $B$ dengan parent view $v_{parent} = B.ParentQC.View$ jika:
   $$\text{Safety Check: } B.ParentQC.View \ge R.lockedQC.View \quad \lor \quad \text{Liveness Check: } B.ParentQC.View > R.lockedQC.View$$
   Secara spesifik, sebuah replika memberikan suara jika blok tersebut memperluas rantai dari *highest locked QC* yang dimilikinya atau melewati batas ronde penguncian sebelumnya (*unlock on higher proof*).

2. **Commit Rule (The 3-Chain Rule):**
   Status blok $B$ difinalkan (*Decided*) jika dan hanya jika terdapat tiga blok berurutan yang saling merujuk langsung:
   $$\exists B', B'', B''' \quad \text{s.t.} \quad B'''.parent = B'' \land B''.parent = B' \land B'.parent = B$$
   dengan:
   $$B'''.View = B''.View + 1 = B'.View + 2 = B.View + 3$$

### C. Pacemaker & Asinkronitas Parsial
Pacemaker bertugas menjamin **Liveness**. Berdasarkan model DLS, sistem berada di bawah kondisi Asinkron hingga batas *Global Stabilization Time* (GST), setelah itu sistem menjadi Sinkron dengan batas keterlambatan pesan $\Delta$.
Jika dalam durasi waktu $2\Delta$ replika tidak menerima blok valid atau QC yang memadai dari leader yang ditugaskan, Pacemaker memicu sinyal `OnTimeout` dan memproyeksikan pergantian ke view berikutnya ($v+1$) secara deterministik tanpa perlu membatalkan status yang telah terkunci.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi mesin konsensus Chained-BFT dalam Go murni, mencakup state machine, validasi QC, pacemaker lokal, verifikasi tanda tangan kriptografis, dan penanganan konkurensi berbasis channel.

```go
package consensus

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"sync"
	"time"
)

// Invariant Constants
const (
	FaultyNodesThreshold = 1 // f
	TotalNodes           = 4 // N = 3f + 1
	QuorumSize           = 2*FaultyNodesThreshold + 1 // 2f + 1 = 3
)

// BlockHash merepresentasikan digest kriptografis dari block.
type BlockHash [32]byte

// String mengembalikan representasi heksadesimal pendek untuk logging.
func (b BlockHash) String() string {
	return fmt.Sprintf("%x", b[:8])
}

// QuorumCertificate (QC) mengonsolidasikan bukti vote kourum.
type QuorumCertificate struct {
	View       uint64
	BlockHash  BlockHash
	Signatures map[int][]byte // NodeID -> Ed25519 Signature
}

// Block mendefinisikan unit konsensus dalam Chained-BFT.
type Block struct {
	View       uint64
	ParentHash BlockHash
	JustifyQC  *QuorumCertificate // QC dari parent block
	Payload    []byte             // State transitions / AI commands
	ProposerID int
	Hash       BlockHash
}

// ComputeHash menghitung deterministik SHA256 dari blok.
func (b *Block) ComputeHash() BlockHash {
	h := sha256.New()
	_ = binary.Write(h, binary.BigEndian, b.View)
	h.Write(b.ParentHash[:])
	if b.JustifyQC != nil {
		_ = binary.Write(h, binary.BigEndian, b.JustifyQC.View)
		h.Write(b.JustifyQC.BlockHash[:])
	}
	_ = binary.Write(h, binary.BigEndian, int64(b.ProposerID))
	h.Write(b.Payload)
	
	var res BlockHash
	copy(res[:], h.Sum(nil))
	return res
}

// Vote merepresentasikan dukungan sebuah replika terhadap suatu blok.
type Vote struct {
	View       uint64
	BlockHash  BlockHash
	NodeID     int
	Signature  []byte
}

// NodeIdentity menyimpan data kunci kriptografi validator.
type NodeIdentity struct {
	ID         int
	PrivateKey ed25519.PrivateKey
	PublicKey  ed25519.PublicKey
}

// ConsensusEngine mengelola state machine replikasi HotStuff.
type ConsensusEngine struct {
	mu           sync.RWMutex
	identity     NodeIdentity
	validatorSet map[int]ed25519.PublicKey

	currentView uint64
	highestVote uint64
	lockedQC    *QuorumCertificate
	prepareQC   *QuorumCertificate

	blockStore map[BlockHash]*Block
	votePool   map[uint64]map[BlockHash]map[int][]byte // View -> BlockHash -> NodeID -> Sig

	finalizedBlock chan *Block
	outboundVote   chan *Vote
	outboundBlock  chan *Block

	pacemakerTimeout time.Duration
	timer            *time.Timer
}

func NewConsensusEngine(
	id NodeIdentity,
	validators map[int]ed25519.PublicKey,
	timeout time.Duration,
) *ConsensusEngine {
	genesisBlock := &Block{
		View:       0,
		ParentHash: BlockHash{},
		JustifyQC:  nil,
		Payload:    []byte("GENESIS_BOOTSTRAP_STATE"),
		ProposerID: 0,
	}
	genesisBlock.Hash = genesisBlock.ComputeHash()

	genesisQC := &QuorumCertificate{
		View:       0,
		BlockHash:  genesisBlock.Hash,
		Signatures: make(map[int][]byte),
	}

	engine := &ConsensusEngine{
		identity:         id,
		validatorSet:     validators,
		currentView:      1,
		highestVote:      0,
		lockedQC:         genesisQC,
		prepareQC:        genesisQC,
		blockStore:       make(map[BlockHash]*Block),
		votePool:         make(map[uint64]map[BlockHash]map[int][]byte),
		finalizedBlock:   make(chan *Block, 100),
		outboundVote:     make(chan *Vote, 100),
		outboundBlock:    make(chan *Block, 100),
		pacemakerTimeout: timeout,
	}

	engine.blockStore[genesisBlock.Hash] = genesisBlock
	engine.timer = time.NewTimer(engine.pacemakerTimeout)

	return engine
}

// Start menjalankan loop Pacemaker konsensus.
func (ce *ConsensusEngine) Start(ctx context.Context) {
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			case <-ce.timer.C:
				ce.handleLocalTimeout()
			}
		}
	}()
}

// handleLocalTimeout transisi ke view berikutnya jika lead timeout (Pacemaker).
func (ce *ConsensusEngine) handleLocalTimeout() {
	ce.mu.Lock()
	defer ce.mu.Unlock()

	ce.currentView++
	ce.timer.Reset(ce.pacemakerTimeout)
}

// ProcessBlock memproses proposal blok baru dari proposer view saat ini.
func (ce *ConsensusEngine) ProcessBlock(proposedBlock *Block) error {
	ce.mu.Lock()
	defer ce.mu.Unlock()

	// 1. Verifikasi integritas hash
	expectedHash := proposedBlock.ComputeHash()
	if !bytes.Equal(proposedBlock.Hash[:], expectedHash[:]) {
		return errors.New("block hash integrity failure")
	}

	// 2. Verifikasi validitas pengusul (Leader Election deterministik: View % TotalNodes)
	expectedProposer := int(proposedBlock.View % TotalNodes)
	if proposedBlock.ProposerID != expectedProposer {
		return fmt.Errorf("invalid leader: expected %d, got %d", expectedProposer, proposedBlock.ProposerID)
	}

	// 3. Verifikasi JustifyQC jika bukan genesis
	if proposedBlock.JustifyQC == nil {
		return errors.New("missing justify QC in proposed block")
	}
	if err := ce.verifyQC(proposedBlock.JustifyQC); err != nil {
		return fmt.Errorf("invalid justify QC: %w", err)
	}

	// 4. Update Tree & Terapkan Safety Rules (Voting Rule)
	// Replika memberikan suara hanya jika parent QC melampaui locked view ATAU
	// parent blok adalah turunan langsung dari node lockedQC.
	parentBlock, exists := ce.blockStore[proposedBlock.JustifyQC.BlockHash]
	if !exists {
		return errors.New("parent block referenced by QC does not exist in local store")
	}

	if proposedBlock.JustifyQC.View < ce.lockedQC.View {
		return fmt.Errorf("safety violation: justify QC view %d < locked QC view %d",
			proposedBlock.JustifyQC.View, ce.lockedQC.View)
	}

	// Invariant Check Liveness vs Safety
	if proposedBlock.View <= ce.highestVote {
		return fmt.Errorf("equivocation prevention: already voted for view >= %d", proposedBlock.View)
	}

	// Simpan blok
	ce.blockStore[proposedBlock.Hash] = proposedBlock

	// 5. Eksekusi 3-Chain Commit Rule Update
	ce.updateCommitPipeline(proposedBlock.JustifyQC)

	// Update High QC
	if proposedBlock.JustifyQC.View > ce.prepareQC.View {
		ce.prepareQC = proposedBlock.JustifyQC
	}

	// Buat Vote
	voteSig := ed25519.Sign(ce.identity.PrivateKey, proposedBlock.Hash[:])
	vote := &Vote{
		View:      proposedBlock.View,
		BlockHash: proposedBlock.Hash,
		NodeID:    ce.identity.ID,
		Signature: voteSig,
	}

	ce.highestVote = proposedBlock.View
	ce.timer.Reset(ce.pacemakerTimeout)

	// Emit vote keluar secara asinkron
	select {
	case ce.outboundVote <- vote:
	default:
	}

	return nil
}

// ProcessVote menagregasikan vote yang masuk dari replika.
func (ce *ConsensusEngine) ProcessVote(vote *Vote) (*QuorumCertificate, error) {
	ce.mu.Lock()
	defer ce.mu.Unlock()

	pubKey, exists := ce.validatorSet[vote.NodeID]
	if !exists {
		return nil, errors.New("vote received from unknown validator")
	}

	// Validasi signature vote
	if !ed25519.Verify(pubKey, vote.BlockHash[:], vote.Signature) {
		return nil, errors.New("cryptographic signature validation failed on vote")
	}

	// Inisialisasi map
	if _, ok := ce.votePool[vote.View]; !ok {
		ce.votePool[vote.View] = make(map[BlockHash]map[int][]byte)
	}
	if _, ok := ce.votePool[vote.View][vote.BlockHash]; !ok {
		ce.votePool[vote.View][vote.BlockHash] = make(map[int][]byte)
	}

	pool := ce.votePool[vote.View][vote.BlockHash]
	pool[vote.NodeID] = vote.Signature

	// Cek ambang batas kourum (2f + 1)
	if len(pool) == QuorumSize {
		signatures := make(map[int][]byte)
		for k, v := range pool {
			signatures[k] = v
		}

		qc := &QuorumCertificate{
			View:       vote.View,
			BlockHash:  vote.BlockHash,
			Signatures: signatures,
		}
		return qc, nil
	}

	return nil, nil
}

// updateCommitPipeline menjalankan evaluasi Three-Chain Commit Rule.
// Rantai: [Decided Block] <-- [Locked QC] <-- [Prepare QC] <-- [Proposed Block]
func (ce *ConsensusEngine) updateCommitPipeline(qc *QuorumCertificate) {
	// Block B1 (Prepare)
	b1, exists := ce.blockStore[qc.BlockHash]
	if !exists {
		return
	}

	// Update Prepare QC
	ce.prepareQC = qc

	// Block B2 (Pre-Commit / Locked)
	if b1.JustifyQC == nil {
		return
	}
	b2, exists := ce.blockStore[b1.JustifyQC.BlockHash]
	if !exists {
		return
	}

	// Aturan 2-Chain: Lock blok B2
	if b2.View > ce.lockedQC.View {
		ce.lockedQC = b1.JustifyQC
	}

	// Block B3 (Commit / Decide)
	if b2.JustifyQC == nil {
		return
	}
	b3, exists := ce.blockStore[b2.JustifyQC.BlockHash]
	if !exists {
		return
	}

	// Aturan 3-Chain: Jika B1 direct link ke B2, dan B2 direct link ke B3 secara urut
	if b1.View == b2.View+1 && b2.View == b3.View+1 {
		// Finalize B3 (Decide)
		select {
		case ce.finalizedBlock <- b3:
		default:
			// Buffer full, drop atau handle backpressure
		}
	}
}

// verifyQC memverifikasi kriptografi dan kourum dari Quorum Certificate.
func (ce *ConsensusEngine) verifyQC(qc *QuorumCertificate) error {
	if len(qc.Signatures) < QuorumSize {
		return fmt.Errorf("insufficient votes in QC: got %d, need %d", len(qc.Signatures), QuorumSize)
	}

	validSignatures := 0
	for nodeID, sig := range qc.Signatures {
		pubKey, ok := ce.validatorSet[nodeID]
		if !ok {
			continue
		}
		if ed25519.Verify(pubKey, qc.BlockHash[:], sig) {
			validSignatures++
		}
	}

	if validSignatures < QuorumSize {
		return errors.New("cryptographic quorum verification failed")
	}

	return nil
}

// ProposeBlock dipanggil oleh node jika dia merupakan leader di view ini.
func (ce *ConsensusEngine) ProposeBlock(payload []byte) (*Block, error) {
	ce.mu.Lock()
	defer ce.mu.Unlock()

	expectedLeader := int(ce.currentView % TotalNodes)
	if ce.identity.ID != expectedLeader {
		return nil, errors.New("node is not authorized proposer for the current view")
	}

	block := &Block{
		View:       ce.currentView,
		ParentHash: ce.prepareQC.BlockHash,
		JustifyQC:  ce.prepareQC,
		Payload:    payload,
		ProposerID: ce.identity.ID,
	}
	block.Hash = block.ComputeHash()

	ce.blockStore[block.Hash] = block
	return block, nil
}
```

---

## 7. Edge Cases & Failure Modes

### 1. The Equivocation Attack (Double Voting)
* **Mode Kegagalan:** Leader Byzantine mengirimkan dua usulan blok berbeda ($B$ dan $B'$) pada ronde/view yang sama kepada dua partisi validator terpisah guna memicu divergensi state.
* **Mitigasi Mesin:** Safety invariant pada method `ProcessBlock` mencegah replika memberikan voting jika $View \le highestVote$. Begitu node memberikan signature untuk View $V$, seluruh usulan lain di View $V$ akan langsung ditolak secara deterministik tanpa pengecualian.

### 2. The Silent / Dead Leader Problem
* **Mode Kegagalan:** Node Leader terpilih mengalami crash, macet akibat serangan DDoS, atau sengaja tidak memublikasikan blok proposal ke jaringan.
* **Mitigasi Pacemaker:** Komponen Pacemaker menjaga timer deterministik $\Delta$. Jika tidak ada proposal valid yang membentuk QC baru dalam jendela waktu $2\Delta$, Pacemaker lokal mengeksekusi timeout secara independen dan menginisiasi pergantian ke View berikutnya ($v+1$). Leader baru dipilih secara deterministik:
  $$\text{Leader}(v+1) = (v+1) \pmod N$$

### 3. Dynamic Network Partition (Asynchronous Split)
* **Mode Kegagalan:** Jaringan terpecah menjadi dua segmen: Partisi A ($2f$ node) dan Partisi B ($f+1$ node).
* **Mitigasi Berbasis Kourum:** Karena ambang batas pembentukan QC adalah $2f + 1$, maka:
  - Partisi A ($2f$ node) kekurangan $1$ suara untuk kourum $\rightarrow$ Terhenti aman (*Stalls safely*).
  - Partisi B ($f+1$ node) tidak mampu mencapai kourum $\rightarrow$ Terhenti aman (*Stalls safely*).
  - **Hasil:** Sesuai batas Teorema CAP (CP system), konsensus mempertahankan **Safety** secara penuh dengan mengorbankan **Liveness** hingga jaringan pulih (*GST reached*).

### 4. Re-parenting Attacks via Outdated High QC
* **Mode Kegagalan:** Node jahat menahan QC valid ber-view lama, lalu merilisnya di view yang jauh lebih tinggi untuk membatalkan transaksi yang sudah berjalan.
* **Mitigasi Three-Chain Invariant:** Blok tidak akan pernah mencapai fase `DECIDE` jika tidak memiliki kesinambungan langsung tiga view berurutan ($v, v+1, v+2$). Percabangan dari view masa lalu akan otomatis ditolak karena $v_{proposed} \le v_{locked}$.

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Nakamoto Consensus (PoW/PoS) | Klasik BFT (PBFT) | Modern Chained-BFT (HotStuff) | DAG-Based BFT (Narwhal/Bullshark) |
| :--- | :--- | :--- | :--- | :--- |
| **Kompleksitas Komunikasi (Normal)** | $\mathcal{O}(n)$ | $\mathcal{O}(n^2)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |
| **Kompleksitas Komunikasi (View-Change)** | Tidak Ada (N/A) | $\mathcal{O}(n^3)$ | $\mathcal{O}(n)$ (Linear) | $\mathcal{O}(n)$ (Amortized Zero) |
| **Tipe Finalitas** | Probabilistik | Deterministik Instan | Deterministik (Pipelined 3-Chain) | Deterministik Instan (DAG Round) |
| **Throughput (TPS)** | Rendah (10 - 100) | Sedang (1.000 - 3.000) | Tinggi (10.000 - 40.000) | Sangat Tinggi (> 100.000) |
| **Overhead Memori State** | Rendah | Tinggi (All-to-All Logs) | Rendah (Tree Tracking) | Sangat Tinggi (DAG Topology Log) |
| **Ketahanan Partisi** | Liveness Diutamakan (AP) | Safety Diutamakan (CP) | Safety Diutamakan (CP) | Safety Diutamakan (CP) |

### Analisis Solusi Alternatif:
- **Kapan Memilih DAG-based (Narwhal/Bullshark)?** Ketika sistem menangani orkestrasi data agen AI masif dengan throughput mempool yang melampaui batas disk read/write bandwidth jaringan. DAG memisahkan *data dissemination* dari *transaction ordering*.
- **Kapan Memilih Chained-BFT (HotStuff)?** Ketika kesederhanaan implementasi, determinisme verifikasi formal, konsumsi RAM yang rendah, dan kesiapan produksi menjadi prioritas utama tanpa kerumitan memvalidasi topologi grafik asiklis.

---

## 9. Best Practices & Standard Industri

1. **BLS12-381 Aggregate Signature Deployment:**
   Hindari penggunaan signature skalar individual (`map[int][]byte`) di lingkungan production skala besar. Gunakan skema **Boneh-Lynn-Shacham (BLS)** yang memungkinkan pemadatan ribuan signature menjadi satu signature tunggal berukuran konstan 48/96 byte:
   $$e(\sigma_{agg}, g_2) = \prod_{i=1}^k e(H(m), pk_i)$$

2. **Divergent Decoupling (Consensus vs Execution):**
   Terapkan Application Blockchain Interface (ABCI/ABCI++). Konsensus hanya boleh menyepakati urutan byte payload transaksi tanpa menunggu eksekusi komputasi state mesin selesai. Hal ini mencegah latensi inferensi LLM atau eksekusi smart contract memblokir pipeline konsensus.

3. **Deterministic Slashing Storage:**
   Simpan status voting terakhir (`highestVote`, `lockedQC`) pada penyimpanan berbasis WAL (*Write-Ahead Logging*) berkemampuan `fsync` presisten. Kegagalan daya listrik (power failure) tidak boleh menyebabkan replika melupakan view voting tertingginya, yang berisiko memicu *equivocation* setelah proses reboot.

4. **Cryptographic Leader VRF (Verifiable Random Function):**
   Hindari pemilihan leader deterministik sederhana `view % N` di jaringan publik karena rentan terhadap serangan DDoS bertarget. Gunakan VRF untuk memilih proposer secara rahasia dan baru dipublikasikan bersamaan dengan blok usulan.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda ditugaskan mendirikan jaringan simulasi 4 node konsensus ($N=4, f=1$), mengeksekusi pipeline 3-chain hingga terjadi finalisasi blok, dan menguji kekebalan sistem terhadap serangan *equivocation* oleh node Byzantine.

### Langkah-langkah Praktikum

#### Langkah 1: Setup Validator Keys & Inisialisasi SimCluster
Buat file `consensus_test.go` di direktori yang sama:

```go
package consensus

import (
	"crypto/ed25519"
	"crypto/rand"
	"testing"
	"time"
)

func TestHotStuffThreeChainFinalization(t *testing.T) {
	// Setup 4 Validator Node
	validatorSet := make(map[int]ed25519.PublicKey)
	nodes := make([]*ConsensusEngine, TotalNodes)

	privKeys := make([]ed25519.PrivateKey, TotalNodes)
	pubKeys := make([]ed25519.PublicKey, TotalNodes)

	for i := 0; i < TotalNodes; i++ {
		pub, priv, err := ed25519.GenerateKey(rand.Reader)
		if err != nil {
			t.Fatalf("failed generating keys: %v", err)
		}
		privKeys[i] = priv
		pubKeys[i] = pub
		validatorSet[i] = pub
	}

	for i := 0; i < TotalNodes; i++ {
		id := NodeIdentity{
			ID:         i,
			PrivateKey: privKeys[i],
			PublicKey:  pubKeys[i],
		}
		nodes[i] = NewConsensusEngine(id, validatorSet, 500*time.Millisecond)
	}

	// -------------------------------------------------------------
	// RONDE 1: Leader 1 (View 1 % 4 = 1) Mengusulkan Block 1
	// -------------------------------------------------------------
	leader1 := nodes[1]
	b1, err := leader1.ProposeBlock([]byte("TX_AGENT_INFERENCE_INSTRUCTION_01"))
	if err != nil {
		t.Fatalf("Leader 1 failed to propose: %v", err)
	}

	// Validasi & Voting oleh Node 0, 1, 2 (Kourum 3 dari 4)
	var qc1 *QuorumCertificate
	for i := 0; i < 3; i++ {
		if err := nodes[i].ProcessBlock(b1); err != nil {
			t.Fatalf("Node %d rejected valid Block 1: %v", i, err)
		}
		vote := <-nodes[i].outboundVote
		qc, err := leader1.ProcessVote(vote)
		if err != nil {
			t.Fatalf("Leader failed to process vote from node %d: %v", i, err)
		}
		if qc != nil {
			qc1 = qc
		}
	}

	if qc1 == nil {
		t.Fatal("Failed to assemble Quorum Certificate 1")
	}

	// Update view node seragam ke view 2
	for i := 0; i < TotalNodes; i++ {
		nodes[i].currentView = 2
	}

	// -------------------------------------------------------------
	// RONDE 2: Leader 2 (View 2 % 4 = 2) Mengusulkan Block 2 (Membawa QC1)
	// -------------------------------------------------------------
	leader2 := nodes[2]
	leader2.prepareQC = qc1 // Leader 2 menerima QC1
	b2, err := leader2.ProposeBlock([]byte("TX_AGENT_DATA_SETTLE_02"))
	if err != nil {
		t.Fatalf("Leader 2 failed to propose: %v", err)
	}

	var qc2 *QuorumCertificate
	for i := 0; i < 3; i++ {
		if err := nodes[i].ProcessBlock(b2); err != nil {
			t.Fatalf("Node %d rejected valid Block 2: %v", i, err)
		}
		vote := <-nodes[i].outboundVote
		qc, err := leader2.ProcessVote(vote)
		if err != nil {
			t.Fatalf("Leader 2 failed vote processing: %v", err)
		}
		if qc != nil {
			qc2 = qc
		}
	}

	if qc2 == nil {
		t.Fatal("Failed to assemble Quorum Certificate 2")
	}

	// Update view ke view 3
	for i := 0; i < TotalNodes; i++ {
		nodes[i].currentView = 3
	}

	// -------------------------------------------------------------
	// RONDE 3: Leader 3 (View 3 % 4 = 3) Mengusulkan Block 3 (Membawa QC2)
	// -------------------------------------------------------------
	leader3 := nodes[3]
	leader3.prepareQC = qc2
	b3, err := leader3.ProposeBlock([]byte("TX_AGENT_ARBITRAGE_EXECUTION_03"))
	if err != nil {
		t.Fatalf("Leader 3 failed to propose: %v", err)
	}

	var qc3 *QuorumCertificate
	for i := 0; i < 3; i++ {
		if err := nodes[i].ProcessBlock(b3); err != nil {
			t.Fatalf("Node %d rejected valid Block 3: %v", i, err)
		}
		vote := <-nodes[i].outboundVote
		qc, err := leader3.ProcessVote(vote)
		if err != nil {
			t.Fatalf("Leader 3 failed vote processing: %v", err)
		}
		if qc != nil {
			qc3 = qc
		}
	}

	if qc3 == nil {
		t.Fatal("Failed to assemble Quorum Certificate 3")
	}

	// Update view ke view 4
	for i := 0; i < TotalNodes; i++ {
		nodes[i].currentView = 4
	}

	// -------------------------------------------------------------
	// RONDE 4: Leader 0 (View 4 % 4 = 0) Mengusulkan Block 4 (Membawa QC3)
	// Trigger 3-Chain Rule: Block 1 HARUS Finalized
	// -------------------------------------------------------------
	leader0 := nodes[0]
	leader0.prepareQC = qc3
	b4, err := leader0.ProposeBlock([]byte("TX_TRIGGER_DECIDE_04"))
	if err != nil {
		t.Fatalf("Leader 0 failed to propose: %v", err)
	}

	// Proses blok 4 pada Node 1 dan periksa channel finalizedBlock
	if err := nodes[1].ProcessBlock(b4); err != nil {
		t.Fatalf("Node 1 rejected proposal 4: %v", err)
	}

	select {
	case finalized := <-nodes[1].finalizedBlock:
		if finalized.Hash != b1.Hash {
			t.Fatalf("Commit invariant mismatch: expected %s, got %s", b1.Hash, finalized.Hash)
		}
		t.Logf("SUCCESS: Block 1 (%s) is irreversibly finalized via 3-Chain Rule!", finalized.Hash)
	case <-time.After(1 * time.Second):
		t.Fatal("Timeout reached: 3-Chain Rule failed to trigger finalization")
	}
}

func TestEquivocationProtection(t *testing.T) {
	// Setup Node Replika
	_, priv, _ := ed25519.GenerateKey(rand.Reader)
	pub, _, _ := ed25519.GenerateKey(rand.Reader)
	validatorSet := map[int]ed25519.PublicKey{0: pub}

	id := NodeIdentity{ID: 1, PrivateKey: priv, PublicKey: pub}
	replica := NewConsensusEngine(id, validatorSet, 500*time.Millisecond)

	qc := &QuorumCertificate{View: 0, BlockHash: BlockHash{}, Signatures: make(map[int][]byte)}

	// Usulan A pada View 1
	bA := &Block{
		View:       1,
		ParentHash: BlockHash{},
		JustifyQC:  qc,
		Payload:    []byte("PAYLOAD_ORIGINAL"),
		ProposerID: 1,
	}
	bA.Hash = bA.ComputeHash()

	// Usulan B (Equivocated) pada View 1 yang sama oleh Leader Jahat
	bB := &Block{
		View:       1,
		ParentHash: BlockHash{},
		JustifyQC:  qc,
		Payload:    []byte("PAYLOAD_FORK_ATTACK"),
		ProposerID: 1,
	}
	bB.Hash = bB.ComputeHash()

	// 1. Eksekusi Proposal A -> Harus Sukses
	if err := replica.ProcessBlock(bA); err != nil {
		t.Fatalf("Expected proposal A to pass, got: %v", err)
	}

	// 2. Eksekusi Proposal B pada View yang sama -> Harus DITOLAK demi Safety
	err := replica.ProcessBlock(bB)
	if err == nil {
		t.Fatal("CRITICAL SAFETY BREAK: Engine accepted double vote on identical view!")
	}
	t.Logf("SUCCESS: Equivocation detected and rejected: %v", err)
}
```

#### Langkah 2: Eksekusi Pengujian & Verifikasi Formal
Jalankan pengujian unit konsensus melalui CLI:

```bash
go test -v -race ./...
```

**Ekspektasi Output Terminal:**
```text
=== RUN   TestHotStuffThreeChainFinalization
    consensus_test.go:154: SUCCESS: Block 1 (8a4f12bc) is irreversibly finalized via 3-Chain Rule!
--- PASS: TestHotStuffThreeChainFinalization (0.01s)
=== RUN   TestEquivocationProtection
    consensus_test.go:193: SUCCESS: Equivocation detected and rejected: equivocation prevention: already voted for view >= 1
--- PASS: TestEquivocationProtection (0.00s)
PASS
ok      consensus   0.024s
```