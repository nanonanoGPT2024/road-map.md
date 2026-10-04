# BAB 03: Rekayasa Mekanisme Konsensus Modern
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** batas teoretis konsensus terdistribusi (BFT Bounds, FLP Impossibility, CAP/PACELC) di bawah model jaringan *partially synchronous* dan *asynchronous*.
- **Merancang** arsitektur *State Machine Replication* (SMR) deterministik berbasis *Quorum Certificate* (QC) dan *Directed Acyclic Graph* (DAG).
- **Mengimplementasikan** *consensus engine* tingkat produksi dengan proteksi *equivocation* (double-signing detection), *Write-Ahead Logging* (WAL) fail-safe, dan agregasi tanda tangan kriptografi (BLS12-381).
- **Mendiagnosis & Memitigasi** anomali konsensus enterprise: *liveness denial*, *amnesia attacks*, *split-brain under network partition*, dan degradasi latensi agregasi $O(n^2) \to O(n)$.
- **Mengintegrasikan** konsensus deterministik sub-detik untuk validasi pertukaran data agen otonom (*Autonomous AI Agent Settlement Layer*).

---

### 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Distributed Systems**: Jam logis (Lamport/Vector Clocks), Paxos/Raft primitives, model kegagalan (*fail-stop* vs *Byzantine fail-arbitrary*).
- **Applied Cryptography**: Kurva eliptik (Ed25519), BLS (*Boneh-Lynn-Shacham*) Multi-Signatures, *Verifiable Random Functions* (VRF), SHA-256/Keccak-256 Merkle Trees.
- **Sistem & Jaringan**: Bahasa pemrograman Go (versi $\ge$ 1.22) atau Rust, pemrograman konkurensi (channel, mutex, atomic memory primitives), P2P gossip network (libp2p/GossipSub), dan gRPC/Protobuf.

---

### 3. Concept & Internal Architecture

Konsensus modern pada jaringan *blockchain* enterprise berevolusi dari model probabilistik (Nakamoto PoW/PoS) menuju deterministik *Byzantine Fault Tolerant* (BFT) dan *DAG-based consensus* untuk memenuhi *Service Level Agreement* (SLA) latensi rendah dan kepastian finalitas (*instant finality*).

```
                      +---------------------------------------+
                      |          AI Agent / Client            |
                      +---------------------------------------+
                                          |
                               [ Transactions / Proposals ]
                                          v
+---------------------------------------------------------------------------------+
| Node Consensus Layer (Validator)                                                |
|                                                                                 |
|   +--------------------+      +---------------------------------------------+   |
|   |   Mempool Engine   | ---> | Consensus Engine (PBFT / HotStuff / DAG)    |   |
|   |  - Nonce checking  |      |  - Round-Robin / VRF Proposer Selection     |   |
|   |  - Tx Gas Limit    |      |  - 3-Phase / 2-Phase Chained QC Engine      |   |
|   +--------------------+      +---------------------------------------------+   |
|                                     |                         |                 |
|            [ Append Step Event ]    |                         | [ Quorum QC ]   |
|                                     v                         v                 |
|                       +--------------------+     +------------------------+     |
|                       |   WAL Persistence  |     |   App Engine (ABCI)    |     |
|                       |  (Atomic disk fsync|     |  - State Transition    |     |
|                       |   Anti-Equivocation)     |  - Merkle State Root   |     |
|                       +--------------------+     +------------------------+     |
+---------------------------------------------------------------------------------+
```

#### 3.1 Model Matematika Batas Toleransi Byzantine
Sebuah sistem terdistribusi dengan $n$ node validator dapat mentoleransi hingga $f$ validator yang mengalami *arbitrary failure* (berperilaku jahat, offline, atau korup) jika dan hanya jika:

$$n \ge 3f + 1$$

*Bukti Intuitif*: Jika terdapat $f$ node jahat yang mengirimkan informasi bertentangan, dan $f$ node lambat/mati, sistem harus tetap mampu mengambil keputusan dengan $n - f$ respon. Agar $n - f$ respon tersebut didominasi oleh node jujur melampaui node jahat yang berpartisipasi, kuorum validasi minimum ($Q$) harus memenuhi:

$$Q = \left\lfloor \frac{2n}{3} \right\rfloor + 1$$

#### 3.2 Evolusi Mekanisme BFT
1. **Classical PBFT (Castro & Liskov, 1999)**: Membutuhkan 3 fase (`Pre-prepare`, `Prepare`, `Commit`). Kompleksitas komunikasi per ronde adalah $O(n^2)$ pada fase prepare dan commit. Tidak efisien untuk validator set berukuran $> 100$.
2. **Linear BFT / HotStuff (Yin et al., 2019)**: Mentransformasikan komunikasi menjadi *star-topology* melalui *Leader*, memanfaatkan *Threshold Signature* (BLS), mereduksi kompleksitas per ronde menjadi $O(n)$. Mengintegrasikan fase konsensus ke dalam rantai blok (*pipelined/chained consensus*).
3. **Decoupled DAG-Consensus (Narwhal & Bullshark / Sui)**: Memisahkan *data dissemination* (diseminasi mempool berkecepatan tinggi membentuk DAG) dari *consensus ordering* (pemberian urutan blok nol komunikasi jaringan tambahan).

#### 3.3 Anatomi State Transition Konsensus Modern
Siklus konsensus berbasis *Round* dan *Step*:
- **NewRound**: Penentuan *Leader* (*Proposer*) menggunakan fungsi deterministik:
  $$\text{Proposer}(h, r) = \text{StakeWeightedSelect}(\text{VRF}(\text{Seed}_{h-1} \parallel r))$$
- **Propose**: Leader menyiarkan blok berisi transaksi beserta *Quorum Certificate* (QC) dari ronde sebelumnya.
- **Prevote / Prepare**: Setiap validator memvalidasi proposal, memverifikasi tidak terjadi pelanggaran *locking rules*, menandatangani payload dengan BLS, dan menyiarkannya.
- **Precommit / Pre-Commit-QC**: Jika terkumpul $\ge 2f + 1$ suara, dibuat *Prepare QC*. Validator masuk ke status *locked* pada blok tersebut.
- **Commit & Execute**: Setelah $\ge 2f + 1$ *Precommit*, blok memperoleh finalitas mutlak (*Absolute Finality*), dimasukkan ke dalam *ledger*, dan dieksekusi pada *State Machine*.

---

### 4. Why & What

| Dimensi | Nakamoto Consensus (PoW/PoS Tradisional) | Modern Enterprise BFT (CometBFT/HotStuff) | DAG-Based Engine (Narwhal/Bullshark) |
| :--- | :--- | :--- | :--- |
| **Finality Type** | Probabilistik (butuh $k$-konfirmasi blok) | Deterministik Sektoral (1-blok finalitas) | Deterministik Causal Order |
| **Latency to Finality** | Menit hingga Jam | 400ms – 1.5 detik | 200ms – 800ms |
| **Throughput (TPS)** | 7 - 100 TPS | 2.000 - 10.000 TPS | 50.000 - 150.000+ TPS |
| **Network Overhead** | $O(n)$ gossip | $O(n)$ chained HotStuff / $O(n^2)$ PBFT | $O(n)$ linear DAG Mempool |
| **Tolerance Model** | $51\%$ Hash / $33\%-51\%$ Stake (Probabilistic) | $33\%$ Byzantine ($3f+1$) | $33\%$ Byzantine ($3f+1$) |
| **Kasus Penggunaan AI** | Tidak Layak (Risiko Reorg) | Data Settlement, Registry Agen, SLA Logs | High-frequency Inter-agent Inference State |

*Mengapa deterministik finalitas mutlak dibutuhkan pada arsitektur AI-Data?*
Agen otonom mengeksekusi transfer modal, alokasi *compute resource*, atau pembaruan bobot model secara desentralisasi. Jika sistem konsensus mengalami *micro-reorganization* (seperti pada model Nakamoto), eksekusi finansial atau *inference pipeline* di dunia nyata menjadi tidak konsisten (*state rollback disaster*).

---

### 5. How: Workflow Detail

Tahapan pertukaran pesan pada Chained HotStuff / Modern BFT Engine:

```
Validator A (Leader)        Validator B                 Validator C                 Validator D
      |                          |                           |                           |
      |--- Propose(H, R, B1) --->|                           |                           |
      |------------------------->|--- Propose(H, R, B1) ---->|                           |
      |----------------------------------------------------->|--- Propose(H, R, B1) ---->|
      |                          |                           |                           |
      |<-- Vote(B1, BLS_sigB) ---|                           |                           |
      |<-------------------------|-- Vote(B1, BLS_sigC) -----|                           |
      |<-----------------------------------------------------|-- Vote(B1, BLS_sigD) -----|
      |                                                                                  |
[Aggregate Signatures] -> Form QC(B1)                                                    |
      |                                                                                  |
      |--- Propose(H, R+1, B2, QC(B1)) ------------------------------------------------->|
      |                          |                           |                           |
      |             [Verify QC(B1) & Lock(B1)]  [Verify QC(B1) & Lock(B1)]  [Verify QC(B1)]
      |<-- Vote(B2, BLS_sigB) ---|                           |                           |
```

1. **Inisialisasi Ronde ($H, R$)**: Mesin konsensus mencatat tinggi blok ($H$) dan ronde aktif ($R$).
2. **Leader Proposal**: Leader mengirimkan kandidat blok yang memuat *parent Hash* dan *Quorum Certificate* (QC) ronde sebelumnya.
3. **Pemeriksaan Liveness & Safety Rule**:
   - *Safety Rule*: Validator hanya boleh mem-vote blok baru jika blok tersebut memperpanjang blok yang telah di-*lock*, atau nilai ronde blok lebih tinggi dari ronde kunci (`lockedRound`).
   - *Anti-Equivocation Rule*: Validator tidak boleh menandatangani 2 proposal berbeda pada tinggi dan ronde yang sama ($H_i, R_j$).
4. **Agregasi Tanda Tangan**: Leader mengumpulkan tanda tangan parsial, menggabungkannya via *BLS Signature Aggregation* menjadi satu tanda tangan tunggal berukuran konstan (48 byte untuk BLS12-381 G1).
5. **Penerbitan QC**: QC valid dibroadcast bersama proposal ronde berikutnya. Setelah 2 hingga 3 rantai QC berturut-turut terbentuk, status blok dinyatakan *Finalized* dan committed ke database status.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan sebuah **Dewan Direksi Multi-Regional** yang terdiri dari 4 direktur independen (A, B, C, D) yang berkomunikasi via kurir pos yang sering terlambat, dan salah satu direktur (D) diketahui korup dan berusaha menandatangani dua kontrak yang saling bertentangan secara diam-diam.
- **Leader Proposal**: Direktur A merancang surat keputusan (SK) dan mengirimkannya ke B, C, dan D.
- **Prevote (Veto check)**: Direktur B membaca draft. Jika draft tidak melanggar anggaran dasar dan belum pernah menandatangani draft lain di hari yang sama, B membubuhkan paraf segel lilin unik dan mengirim balik ke A.
- **QC Creation**: Ketika Direktur A memegang 3 paraf (A, B, C yang mana $\ge 3(1)+1 - 1 = 3$), segel gabungan disahkan.
- **Commitment**: Tidak ada satupun keputusan lain yang bisa disahkan tanpa 3 paraf tersebut. Bahkan jika D berbohong, ia tidak akan pernah bisa membentuk kuorum 3 tanda tangan independen secara sah.

#### Diagram Arsitektur Internal Engine
```
+---------------------------------------------------------------------------------------+
|                              CONSENSUS PROTOCOL ENGINE                                |
+---------------------------------------------------------------------------------------+
|  [ P2P Transport Layer: libp2p GossipSub / Dedicated Direct Stream ]                   |
+---------------------------------------------------------------------------------------+
         |                                                       ^
  Inbound Network Msgs                                    Outbound Broadcast
         v                                                       |
+------------------------------------+          +--------------------------------------+
|       Consensus Dispatcher         |          |       Broadcast & Aggregator         |
| - Filter Malformed Msgs            |          | - BLS Aggregation Worker             |
| - Rate Limiting & Peer Scoring     |          | - Batch Network Sender               |
+------------------------------------+          +--------------------------------------+
         |                                                       ^
         v                                                       |
+--------------------------------------------------------------------------------------+
|                               State Machine Controller                               |
|                                                                                      |
|  +--------------------+    Round Step Tick     +----------------------------------+  |
|  |   Round Timeout    | ---------------------> |        Engine State Core         |  |
|  |     Scheduler      |                        |  - Current: (Height: H, Round: R)|  |
|  +--------------------+                        |  - LockedBlock: Hash, QC         |  |
|                                                |  - ValidBlock: Hash, QC          |  |
|                                                +----------------------------------+  |
+--------------------------------------------------------------------------------------+
         |                                                                |
         | Commit Proof Validated                                         | Check & Append
         v                                                                v
+------------------------------------+                 +-------------------------------+
|     Execution Manager (ABCI)       |                 |       Write-Ahead Log (WAL)   |
| - Execute Transactions             |                 | - Atomic Record Writes        |
| - Calculate AppHash / State Root   |                 | - fsync strictly enforced     |
| - Persist Committed State to Disk  |                 | - Double-Sign Prevention DB   |
+------------------------------------+                 +-------------------------------+
```

---

### 7. Implementasi Teknis

Berikut adalah implementasi *Consensus Core Engine* menggunakan bahasa Go dengan arsitektur produksi, mencakup proteksi *Anti-Equivocation*, verifikasi BLS, serta logging kejadian ke WAL (*Write-Ahead Log*).

```go
package consensus

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"os"
	"sync"
)

var (
	ErrEquivocationDetected = errors.New("security alert: Byzantine equivocation detected")
	ErrInvalidQuorumSize    = errors.New("signature count does not satisfy BFT quorum")
	ErrBlockLocked          = errors.New("proposal conflicts with locked block")
	ErrStaleRound           = errors.New("round is stale")
)

type Step int8

const (
	StepNewRound Step = iota + 1
	StepPropose
	StepPrevote
	StepPrecommit
	StepCommit
)

func (s Step) String() string {
	switch s {
	case StepNewRound:
		return "NewRound"
	case StepPropose:
		return "Propose"
	case StepPrevote:
		return "Prevote"
	case StepPrecommit:
		return "Precommit"
	case StepCommit:
		return "Commit"
	default:
		return "Unknown"
	}
}

// Vote merepresentasikan payload suara dari validator pada ronde tertentu.
type Vote struct {
	ValidatorID string
	Height      uint64
	Round       uint32
	Step        Step
	BlockHash   [32]byte
	Signature   []byte // Mocking 48-byte BLS partial signature
}

// SignHash menghitung representasi byte deterministik untuk penandatanganan.
func (v *Vote) SignHash() [32]byte {
	buf := new(bytes.Buffer)
	_ = binary.Write(buf, binary.BigEndian, v.Height)
	_ = binary.Write(buf, binary.BigEndian, v.Round)
	_ = binary.Write(buf, binary.BigEndian, int8(v.Step))
	buf.Write(v.BlockHash[:])
	return sha256.Sum256(buf.Bytes())
}

// QuorumCertificate (QC) membuktikan konsensus telah tercapai pada fase tertentu.
type QuorumCertificate struct {
	Height             uint64
	Round              uint32
	Step               Step
	BlockHash          [32]byte
	AggregateSignature []byte
	SignersBitMap      uint64 // Bitmask representasi node penandatangan
}

// ProposalBlock merepresentasikan payload data terstruktur dari Proposer.
type ProposalBlock struct {
	Height    uint64
	Round     uint32
	ParentQC  QuorumCertificate
	Payload   [][]byte
	BlockHash [32]byte
}

func NewProposal(height uint64, round uint32, parentQC QuorumCertificate, payload [][]byte) *ProposalBlock {
	h := sha256.New()
	_ = binary.Write(h, binary.BigEndian, height)
	_ = binary.Write(h, binary.BigEndian, round)
	h.Write(parentQC.BlockHash[:])
	for _, tx := range payload {
		h.Write(tx)
	}
	var hash [32]byte
	copy(hash[:], h.Sum(nil))

	return &ProposalBlock{
		Height:    height,
		Round:     round,
		ParentQC:  parentQC,
		Payload:   payload,
		BlockHash: hash,
	}
}

// WriteAheadLog bertugas mengunci keputusan sebelum mempublikasikannya ke jaringan.
type WriteAheadLog struct {
	mu   sync.Mutex
	file *os.File
}

func OpenWAL(path string) (*WriteAheadLog, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR|os.O_APPEND, 0600)
	if err != nil {
		return nil, err
	}
	return &WriteAheadLog{file: f}, nil
}

func (w *WriteAheadLog) RecordVote(v *Vote) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	buf := new(bytes.Buffer)
	_ = binary.Write(buf, binary.BigEndian, v.Height)
	_ = binary.Write(buf, binary.BigEndian, v.Round)
	_ = binary.Write(buf, binary.BigEndian, int8(v.Step))
	buf.Write(v.BlockHash[:])
	_ = binary.Write(buf, binary.BigEndian, uint32(len(v.Signature)))
	buf.Write(v.Signature)

	if _, err := w.file.Write(buf.Bytes()); err != nil {
		return err
	}
	return w.file.Sync() // Memaksa hardware storage melakukan commit segera (flush cache)
}

func (w *WriteAheadLog) Close() error {
	return w.file.Close()
}

// ConsensusEngine mengelola state machine replikasi konsensus BFT.
type ConsensusEngine struct {
	mu           sync.RWMutex
	nodeID       string
	height       uint64
	round        uint32
	step         Step
	totalNodes   int
	quorumSize   int
	lockedBlock  *[32]byte
	lockedRound  uint32
	wal          *WriteAheadLog
	voteRegistry map[string][32]byte // Key: "Height:Round:Step", Value: BlockHash (Anti-Equivocation)
}

func NewConsensusEngine(nodeID string, totalNodes int, walPath string) (*ConsensusEngine, error) {
	wal, err := OpenWAL(walPath)
	if err != nil {
		return nil, fmt.Errorf("gagal menginisialisasi WAL: %w", err)
	}

	// Persamaan BFT: kuorum minimum = 2f + 1, dengan f = (totalNodes - 1)/3
	f := (totalNodes - 1) / 3
	qSize := 2*f + 1

	return &ConsensusEngine{
		nodeID:       nodeID,
		height:       1,
		round:        0,
		step:         StepNewRound,
		totalNodes:   totalNodes,
		quorumSize:   qSize,
		wal:          wal,
		voteRegistry: make(map[string][32]byte),
	}, nil
}

// ProcessProposal mengevaluasi proposal blok dan menghasilkan Prevote jika lolos safety rules.
func (e *ConsensusEngine) ProcessProposal(p *ProposalBlock) (*Vote, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	if p.Height != e.height || p.Round < e.round {
		return nil, ErrStaleRound
	}

	// Safety Rule: Proposal harus sejalan dengan locked block kecuali rondenya lebih tinggi dari lockedRound
	if e.lockedBlock != nil {
		if p.BlockHash != *e.lockedBlock && p.Round <= e.lockedRound {
			return nil, ErrBlockLocked
		}
	}

	// Buat Vote Prevote
	vote := &Vote{
		ValidatorID: e.nodeID,
		Height:      p.Height,
		Round:       p.Round,
		Step:        StepPrevote,
		BlockHash:   p.BlockHash,
		Signature:   []byte(fmt.Sprintf("sig-%s-%x", e.nodeID, p.BlockHash[:4])), // Simulasi tanda tangan
	}

	if err := e.guardedSignAndRecord(vote); err != nil {
		return nil, err
	}

	e.round = p.Round
	e.step = StepPrevote
	return vote, nil
}

// guardedSignAndRecord memverifikasi kepatuhan anti-equivocation dan menuliskan ke WAL secara atomik.
func (e *ConsensusEngine) guardedSignAndRecord(v *Vote) error {
	registryKey := fmt.Sprintf("%d:%d:%d", v.Height, v.Round, v.Step)
	recordedHash, exists := e.voteRegistry[registryKey]

	if exists {
		if recordedHash != v.BlockHash {
			// CRITICAL: Node terdeteksi diminta menandatangani dua blok berbeda pada step yang sama!
			return fmt.Errorf("%w: terdaftar %x, ditolak %x", ErrEquivocationDetected, recordedHash, v.BlockHash)
		}
		// Idempotent: Blok sama sudah pernah di-vote, tidak perlu re-record
		return nil
	}

	// Tulis secara sinkron ke WAL sebelum broadcast
	if err := e.wal.RecordVote(v); err != nil {
		return fmt.Errorf("kegagalan fatal WAL persistence: %w", err)
	}

	e.voteRegistry[registryKey] = v.BlockHash
	return nil
}

// ProcessQuorum memproses QC yang terkumpul dan menaikkan state (Commit / Lock).
func (e *ConsensusEngine) ProcessQuorum(qc *QuorumCertificate) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	if qc.Height != e.height {
		return errors.New("QC height tidak cocok")
	}

	switch qc.Step {
	case StepPrevote:
		// Mengunci proposal blok setelah 2f+1 Prevote tercapai
		e.lockedBlock = &qc.BlockHash
		e.lockedRound = qc.Round
		e.step = StepPrecommit
	case StepPrecommit:
		// Blok berstatus finalize, siap dieksekusi oleh State Machine
		e.step = StepCommit
		e.height++
		e.round = 0
		e.lockedBlock = nil
		e.lockedRound = 0
	}

	return nil
}

func (e *ConsensusEngine) Close() error {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.wal.Close()
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Autonomous Cross-Enterprise AI Agent Billing & Settlement Network
- **Skala Produksi**: Konsorsium industri logistik global (60 node validator dioperasikan di AWS, Azure, dan GCP oleh entitas independen).
- **Kebutuhan**: Validasi konsensus untuk transaksi mikro agen AI (rute armada, pembayaran tokenisasi gas, validasi hash komputasi inferensi). Target throughput: $7.500\text{ TPS}$ dengan *finality latency* $\le 1.000\text{ ms}$.
- **Insiden Lapangan (The Equivocation Cascade)**:
  - Pada Q2 2024, satu penyedia cloud mengalami *network flap* yang menyebabkan validator Leader dianggap *offline* oleh sekelompok node, namun tetap terhubung ke node lain.
  - Implementasi *failover* pod otomatis (Kubernetes StatefulSet dengan `ReadWriteMany` PVC) me-reboot validator di region berbeda tanpa melepaskan lock WAL lama.
  - Dua instance validator aktif bersamaan dengan *private key* yang sama. Instans A menandatangani Proposal Blok $K_1$, sementara Instans B menandatangani Blok $K_2$ pada Height 4.102.394 Round 1.
- **Dampak**: 
  - Jaringan mengeksekusi *Automated Slashing Protocol*. Kunci validator disuspensi permanen, dan deposit konsorsium senilai \$250.000 ter-slash secara deterministik akibat bukti *Equivocation Evidence* yang diajukan oleh validator kompetitor.
- **Solusi Arsitektur**:
  1. Penggunaan **External Key-Management HSM (YubiHSM / AWS CloudHSM)** yang mengimplementasikan *High-Watermark Tracking* di level chip hardware. HSM menolak secara fisik menandatangani muatan apapun jika `(Height, Round, Step) <= PreviousHighWatermark`.
  2. Implementasi **Consensus Sentry Architecture** untuk melindungi validator nodes dari *direct DDoS*, serta memecah komunikasi P2P gossip menggunakan sub-channel independen.

---

### 9. Trade-Off Analysis

```
                              [ Decentralization (Nodes: >1000) ]
                                            /   \
                                           /     \
                                          /       \
                        Nakamoto (PoW/PoS)         HotStuff + BLS
                                        /           \
                                       /             \
[ Latency: High (>10s) ]-------------+---------------+------------- [ Latency: Sub-second ]
[ Throughput: Low (<50 TPS) ]        \               /             [ Throughput: High (>5k TPS) ]
                                      \             /
                                       \           /
                                  Classic PBFT / Raft
                                            \   /
                                 [ Permissioned / Small Set ]
                                 [ Nodes: 4 - 30 ]
```

| Parameter Arsitektural | 3-Phase PBFT | 2-Chain HotStuff | DAG-Consensus (Narwhal) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Komunikasi Normal** | $O(n^2)$ | $O(n)$ via Master Node | $O(n)$ streaming broadcast |
| **Kompleksitas View-Change (Fault)** | $O(n^3)$ | $O(n)$ | $O(1)$ (Inherent implicit view change) |
| **Beban Validasi Kriptografi** | Rendah (hanya ECDSA/Ed25519) | Tinggi (BLS Threshold Aggregation) | Sedang (Batch ECDSA/Ed25519) |
| **Toleransi Partisi Jaringan** | Hentikan liveness (Safety utuh) | Hentikan liveness (Safety utuh) | Hentikan ordering, Mempool tetap jalan |
| **Overhead Penyimpanan (Disk)** | Rendah (State Machine logis) | Sedang (Commit Chain) | Sangat Tinggi (Full Causal History DAG) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Non-Deterministic Execution dalam SMR
- **Gejala**: Validator set terpecah (*Consensus Fork/Halt*) pada fase `Commit`. Sebagian validator menghasilkan `AppHash` $0xABC...$ dan yang lain $0xDEF...$.
- **Penyebab**: Kode *State Transition Logic* (ABCI) menggunakan elemen nondeterministik: iterasi Golang `map` tanpa sorting, pembacaan `time.Now()`, atau dependensi network call eksternal.
- **Solusi**: Pastikan seluruh eksekusi bersifat *pure state-machine*:
  $$S_{t+1} = f(S_t, \text{Block}_t)$$
  Gunakan index deterministik dan struktur data sorted slice untuk komputasi state hash.

#### 2. False Equivocation Slashing akibat Failover Balapan
- **Gejala**: Node validator Anda sah, namun dislash dan dikeluarkan dari active set karena dianggap memproduksi *double signing*.
- **Penyebab**: Mekanisme auto-healing Kubernetes menjalankan instans cadangan saat instans primer mengalami *unresponsive network* sesaat. Keduanya menandatangani blok di tinggi yang sama.
- **Solusi**: Jangan pernah mengandalkan Kubernetes ReplicaSet untuk validator node! Gunakan model *Active-Passive* yang diproteksi *Hardware Distributed Lock Manager* (seperti Consul/etcd dengan session lease) atau HSM yang memblokir penandatanganan mundur.

#### 3. Memory Exhaustion via Mempool Flooding (Sybil DoS)
- **Gejala**: RAM mesin konsensus melonjak tajam (*OOM Kill*), komunikasi P2P gossip melambat drastis.
- **Penyebab**: *Mempool* tidak menerapkan batas kuota per-rekanan dan tidak memvalidasi amortisasi *Gas / Execution Cost* sebelum memasukkan transaksi ke antrean konsensus.
- **Troubleshooting Runbook**:
  1. Aktifkan *Mempool Admission Control*: Buang transaksi jika antrean melebihi $50.000$ item.
  2. Implementasikan *Prioritized Eviction*: Transaksi dengan fee per byte terendah langsung didepak saat kapasitas memori mencapai 80%.

---

### 11. Best Practices & Production Checklist

#### Production Architecture Topology
```
           +---------------------------------------------+
           |                Internet                     |
           +---------------------------------------------+
                                  |
                   +--------------+--------------+
                   |                             |
                   v                             v
        +--------------------+         +--------------------+
        |  Sentry Node 01    |         |  Sentry Node 02    |
        |  (Public Facing)   |         |  (Public Facing)   |
        +--------------------+         +--------------------+
                   |                             |
                   +--------------+--------------+
                                  | (Private Isolasi VLAN)
                                  v
                       +--------------------+
                       |   Validator Node   |
                       | (Strict Firewall)  |
                       +--------------------+
                                  |
                                  | (Dedicated Serial/mTLS)
                                  v
                       +--------------------+
                       |  Hardware Signer   |
                       |    (HSM / Enclave) |
                       +--------------------+
```

#### Production Checklist
- [ ] **Jaringan Terisolasi**: Port P2P konsensus validator hanya boleh diakses oleh *Sentry Nodes* resmi via VPC Peering/VLAN privat.
- [ ] **I/O Storage Performance**: Disk direktori WAL harus berada di dedicated NVMe SSD dengan *Write Latency* $< 1\text{ ms}$ dan parameter `fsync` yang tidak pernah di-*bypass* di level kernel (`noasync`).
- [ ] **Penyimpanan Kunci Privat**: Gunakan remote signer terpisah (misal: Tendermint KMS atau Horcrux) dengan skema multi-party computation (MPC) atau HSM fisik.
- [ ] **Monitoring Metrik Kritis**:
  - `consensus_height`: Ketinggian blok saat ini (harus bergerak linear).
  - `consensus_round`: Ronde aktif (jika melonjak $> 5$, sistem berpotensi mengalami fragmentasi leader/proposal drop).
  - `consensus_validators_power`: Komposisi voting power aktif (waspadai jika validator set yang aktif mendekati batas kritis $2f+1$).
  - `wal_fsync_duration_seconds`: Waktu tunggu I/O disk logging.

---

### 12. Hands-on Practice

Buat dan uji coba prototipe mesin konsensus BFT mini yang mampu mendeteksi serangan *Equivocation* dan menangani *Quorum Calculation*.

#### Langkah 1: Struktur Direktori
Buat repositori lokal untuk latihan ini:
```bash
mkdir -p hands-on/m02/consensus
cd hands-on/m02/consensus
go mod init enterprise-consensus
```

#### Langkah 2: Buat Berkas `engine.go`
Salin kode implementasi dari **Seksi 7** ke dalam berkas `hands-on/m02/consensus/engine.go`.

#### Langkah 3: Buat Berkas Pengujian `engine_test.go`
Implementasikan unit test komprehensif untuk menguji skenario deterministik, keberhasilan pencapaian kuorum, dan pencegahan *Equivocation*:

```go
package consensus

import (
	"bytes"
	"os"
	"testing"
)

func TestConsensusEngine_Lifecycle(t *testing.T) {
	walPath := "./test_consensus.wal"
	defer os.Remove(walPath)

	// Inisialisasi engine dengan 4 node validator (f = 1, Quorum = 3)
	engine, err := NewConsensusEngine("validator-node-01", 4, walPath)
	if err != nil {
		t.Fatalf("Gagal inisialisasi engine: %v", err)
	}
	defer engine.Close()

	// 1. Simulasikan penerimaan proposal yang sah
	parentQC := QuorumCertificate{Height: 0, Round: 0, Step: StepCommit}
	payload := [][]byte{[]byte("tx_ai_inference_settle_001"), []byte("tx_ai_inference_settle_002")}
	proposal := NewProposal(1, 0, parentQC, payload)

	vote, err := engine.ProcessProposal(proposal)
	if err != nil {
		t.Fatalf("Proposal valid gagal diproses: %v", err)
	}

	if vote.Step != StepPrevote {
		t.Errorf("Ekspektasi step Prevote, didapat %s", vote.Step)
	}

	// 2. Simulasikan upaya Byzantine: Proposal berbeda pada tinggi dan ronde yang sama (Equivocation)
	maliciousPayload := [][]byte{[]byte("tx_byzantine_fork")}
	maliciousProposal := NewProposal(1, 0, parentQC, maliciousPayload)

	_, err = engine.ProcessProposal(maliciousProposal)
	if err == nil {
		t.Fatalf("Ekspektasi error equivocation, namun engine menerima proposal ganda!")
	}

	if !errors.Is(err, ErrEquivocationDetected) {
		t.Errorf("Ekspektasi ErrEquivocationDetected, didapat: %v", err)
	}

	// 3. Verifikasi Quorum Processing
	qcPrevote := &QuorumCertificate{
		Height:    1,
		Round:     0,
		Step:      StepPrevote,
		BlockHash: proposal.BlockHash,
	}

	if err := engine.ProcessQuorum(qcPrevote); err != nil {
		t.Fatalf("Gagal memproses Quorum Prevote: %v", err)
	}

	if engine.step != StepPrecommit {
		t.Errorf("Ekspektasi transisi state ke Precommit, didapat %s", engine.step)
	}
}
```

#### Langkah 4: Eksekusi Test
```bash
go test -v -race ./...
```

---

### 13. Exercises

#### Level Easy
Ubah method `NewProposal` agar menghitung Merkle Root Tree dari transaksi dalam array `Payload` alih-alih melakukan *simple flat hashing*, kemudian verifikasi integritas root hash tersebut pada saat `ProcessProposal` dieksekusi.

#### Level Medium
Tambahkan *Round Timeout Mechanism* ke dalam `ConsensusEngine`. Jika proposal tidak diterima dalam interval $\Delta = 2000\text{ ms}$, mesin harus menaikkan status internal dari Ronde $R$ ke $R+1$, memilih proposer baru via round-robin, dan memancarkan suara `TimeoutVote` yang valid.

#### Level Hard
Rancang dan implementasikan layer kompresi tanda tangan BLS agregat. Gantikan implementasi mock signature dengan library kurva eliptik riil (misalnya `github.com/consensys/gnark-crypto/ecc/bls12-381`). Implementasikan verifikasi $2f+1$ tanda tangan hanya dengan satu operasi *Pairing Check*:
$$e(\sum \sigma_i, g_2) = \prod e(H(m), \text{pk}_i)$$

---

### 14. Challenge

**Skenario**: Anda memimpin tim infrastruktur konsensus untuk platform multi-agen AI. Terjadi kondisi *Asynchronous Black Swan Event*: Jaringan P2P terisolasi menjadi 3 partisi secara global:
- Partisi $\alpha$: $40\%$ Voting Power
- Partisi $\beta$: $35\%$ Voting Power
- Partisi $\gamma$: $25\%$ Voting Power

**Tugas Rekayasa Arsitektur**:
1. Buat spesifikasi protokol teknis (*formal safety specification*) yang membuktikan secara matematis bahwa tidak ada satupun partisi yang dapat melakukan komit pada *state* blok baru selama partisi terjadi (*Zero Reorg & Zero State Split*).
2. Rancang algoritma *Self-Healing & Catch-Up Protocol* ketika ketiga partisi kembali terhubung. Rincikan struktur data sinkronisasi delta state (tanpa mendownload ulang database penuh) yang meminimalisir transmisi data berulang dan menjamin verifikasi deterministik dari state root yang hilang.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. Dalam sistem BFT klasik dengan total 10 validator, berapakah jumlah node Byzantine maksimal ($f$) yang dapat ditoleransi sistem tanpa kehilangan safety dan liveness?
2. Apa tujuan utama dari pencatatan kejadian ke *Write-Ahead Log* (WAL) dengan konfigurasi `fsync` sebelum menyiarkan vote ke jaringan P2P?
3. Mengapa algoritma konsensus deterministik modern (seperti PBFT/HotStuff) tidak memiliki risiko *blockchain reorganization* (reorg) seperti pada konsensus Nakamoto?
4. Apa yang dimaksud dengan *Equivocation* dalam terminologi sistem konsensus terdistribusi?
5. Apa peran dari *Quorum Certificate* (QC) dalam protokol konsensus chained HotStuff?

#### Intermediate Questions
6. Mengapa konsensus BFT murni tidak dapat menjamin *Liveness* secara bersamaan dengan *Safety* pada kondisi jaringan yang sepenuhnya *Asynchronous* (analisis berdasarkan FLP Impossibility Theorem)?
7. Bagaimana skema agregasi tanda tangan BLS12-381 mereduksi kompleksitas verifikasi kuorum dari $O(n^2)$ menjadi $O(n)$ atau $O(1)$ verification overhead?
8. Apa perbedaan fundamental antara *Safety Rule* dan *Liveness Rule* pada protokol konsensus replikasi state machine?
9. Jelaskan bagaimana serangan *Amnesia Attack* dapat terjadi pada validator yang me-reboot nodenya tanpa persistensi WAL yang benar!
10. Pada arsitektur DAG-based consensus (seperti Narwhal/Bullshark), mengapa pemisahan diseminasi data mempool dari konsensus ordering dapat meningkatkan throughput secara dramatis?

#### Production Case Scenarios
11. **Skenario 1**: Metrik monitoring cluster konsensus Anda menunjukkan tinggi blok stagnan (*block production halted*), namun utilisasi CPU pada seluruh validator adalah $0\%$. Nilai ronde pada log sistem terus bertambah setiap 3 detik ($R=1, 2, 3, \dots, 50$). Analisis apa yang paling mungkin terjadi pada jaringan Anda dan apa langkah mitigasi darurat pertama yang harus diambil?
12. **Skenario 2**: Node validator Anda berjalan di platform cloud dengan load balancer memetakan request traffic dari sentry node. Tiba-tiba validator Anda ter-slash karena tuduhan *double-signing*, padahal Anda tidak pernah menjalankan instans cadangan. Dari perspektif arsitektur kernel dan storage, apa potensi celah yang menyebabkan kunci Anda menandatangani vote ganda?
13. **Skenario 3**: Sebuah cluster AI settlement network memiliki $3f+1$ node. Satu validator jahat berkolusi dengan $f-1$ validator lain untuk secara sengaja menahan proposal blok mereka setiap kali terpilih sebagai leader (*selective silence*). Bagaimana Anda mendesain mekanisme *dynamic validator reputation score* untuk mendegradasi pengaruh node tersebut tanpa melanggar batasan toleransi BFT?

---

### 16. Summary

- **Fondasi Konsensus Modern**: Replikasi State Machine (SMR) enterprise mensyaratkan finalitas deterministik mutlak yang dijamin oleh batas matematis $n \ge 3f + 1$.
- **Keunggulan BFT Modern**: Protokol mutakhir mentransformasikan kompleksitas klasik $O(n^2)$ menjadi linier $O(n)$ menggunakan agregasi kriptografis (BLS) dan struktur Chained QC atau DAG Mempool berkecepatan tinggi.
- **Integritas Produksi**: Sistem kelas enterprise wajib menerapkan persistensi tingkat rendah yang ketat (WAL fsync), isolasi Sentry Node, dan perlindungan hardware anti-equivocation (HSM) guna mencegah anomali konsensus serta penalti slashing finansial.
- **Kesesuaian AI Ecosystem**: Transaksi dan data state pada ekosistem agen otonom memerlukan kepastian sub-detik yang kebal terhadap reorg, menjadikan mekanisme modern BFT dan DAG sebagai fondasi krusial pada tumpukan teknologi desentralisasi generasi berikutnya.