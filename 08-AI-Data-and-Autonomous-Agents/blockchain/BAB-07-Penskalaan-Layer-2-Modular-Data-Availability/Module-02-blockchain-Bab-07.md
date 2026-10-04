# BAB 07: Penskalaan Layer-2 & Modular Data Availability
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Merancang, mengonfigurasi, dan mengoperasikan arsitektur *Modular Rollup* end-to-end yang memisahkan layer *Execution*, *Settlement*, *Consensus*, dan *Data Availability* (DA).
- Mengimplementasikan pipeline pengiriman data transaksi L2 (*batch posting*) ke layer Data Availability menggunakan standar **EIP-4844 (Blob Transactions)** dan layer DA alternatif seperti **Celestia** (Namespaced Merkle Trees).
- Menulis dan menguji *Settlement Contract* di L1 (Ethereum) yang memvalidasi komitmen data ketersediaan (DA commitment) via KZG Point Evaluation Precompile (`0x0A`).
- Mengembangkan subsistem *Sequencer Batcher* dan *Rollup Node* berkinerja tinggi menggunakan Go/Rust dengan penanganan konkurensi, reorganisasi rantai (reorg handling), dan optimasi gas.
- Membangun strategi observabilitas, mitigasi risiko *Data Availability Withholding Attack*, dan merancang sistem *fault-tolerance* pada layer desentralisasi Sequencer.

---

### 2. Prerequisite
Untuk mencerna materi ini secara optimal, engineer wajib memiliki pemahaman mendalam tentang:
- **Sistem Terdistribusi**: Mekanisme konsensus BFT, Directed Acyclic Graph (DAG), P2P gossipsub network (libp2p).
- **Kriptografi Lanjut**: Elliptic Curve Cryptography (secp256k1, BLS12-381), Polynomial Commitments (KZG), Reed-Solomon Erasure Coding, Merkle Trees & Sparse Merkle Trees (SMT).
- **Internal Blockchain**: EVM bytecode execution model, format transaksi L1/L2, mempool mechanics, dynamic fee market (EIP-1559 & EIP-4844 blob gas mechanics).
- **Bahasa Pemrograman**:
  - **Go**: Konkurensi tingkat lanjut (`goroutines`, `channels`, `sync.Pool`), manipulasi byte mentah, library `go-ethereum` (`geth`).
  - **Solidity (v0.8.24+)**: Inline assembly (Yul), custom storage layouts, EIP-4844 precompiles integration.

---

### 3. Concept & Internal Architecture

#### 3.1 Dekonstruksi Paradigma Monolitik ke Modular
Dalam blockchain monolitik (misal: Vanilla Ethereum Layer-1 atau Solana), satu set validator bertanggung jawab mengeksekusi transaksi (*Execution*), mencapai konsensus urutan (*Consensus*), memvalidasi status transisi (*Settlement*), dan memastikan data dapat diunduh oleh publik (*Data Availability*).

Arsitektur Modular memecah fungsi-fungsi ini:
1. **Execution**: Node L2 (Sequencer) memproses transaksi di luar rantai (*off-chain*) dengan memori terisolasi berkecepatan tinggi, memutakhirkan *State DB* lokal, dan menghasilkan *State Transition*.
2. **Settlement**: Smart contract di Layer-1 bertindak sebagai pengadilan akhir. Mengunci aset pada jembatan (*canonical bridge*), memverifikasi validitas eksekusi (*Validity Proof / ZK*) atau menangani sengketa (*Fraud Proof*).
3. **Consensus**: Menentukan kanonisitas urutan transaksi (bisa diwarisi dari L1 atau didelegasikan ke *Consensus Layer* khusus).
4. **Data Availability (DA)**: Menjamin bahwa data payload mentah yang merepresentasikan mutasi status tersedia bagi siapa saja untuk mengonstruksi ulang *State* L2 jika Sequencer bertindak curang atau mati.

```
+-------------------------------------------------------------+
|                     MODULAR ROLLUP STACK                    |
+-------------------------------------------------------------+
| [ Execution Layer ]     -> Rollup Execution Engine (EVM/Wasm)|
|                            (e.g., op-geth, Nitro, Reth)     |
+-------------------------------------------------------------+
| [ Settlement Layer ]    -> L1 Rollup Contract (Bridge & Disp)|
|                            (e.g., Ethereum Mainnet)         |
+-------------------------------------------------------------+
| [ Consensus Layer ]     -> Shared/Canonical L1 Consensus     |
|                            (e.g., Ethereum Beacon Chain)    |
+-------------------------------------------------------------+
| [ Data Availability ]   -> EIP-4844 Blobs / Celestia / Avail|
|                            (Erasure Coding, KZG, DAS)       |
+-------------------------------------------------------------+
```

#### 3.2 Anatomi Masalah Ketersediaan Data (Data Availability Problem)
Masalah Data Availability **bukan** tentang penyimpanan arsip historis permanen, melainkan: *Apakah data yang dibutuhkan untuk memverifikasi transisi state saat ini benar-benar dipublikasikan ke jaringan secara tepat waktu sehingga tidak ada pihak yang dapat menyembunyikan transaksi valid atau ilegal?*

Jika Sequencer mengusulkan state root baru ($S_{t+1}$) ke L1 tetapi menolak mempublikasikan transaksi yang menghasilkan $S_{t+1}$ (*Data Withholding Attack*):
- Node verifikator tidak dapat merekonstruksi state L2.
- Pada Optimistic Rollups, penantang tidak dapat membuat *Fraud Proof*.
- Pada ZK-Rollups, prover lain tidak dapat memperbarui state pohon, membekukan dana pengguna.

Solusi Industri:
- **EIP-4844 (Proto-Danksharding)**: Memperkenalkan tipe transaksi baru (`BlobTxType = 0x03`). Setiap blob berukuran $128 \text{ KB}$ (4096 field elements masing-masing 32 bytes pada kurva BLS12-381). Blob dipangkas dari konsensus node setelah $\sim 18$ hari.
- **Celestia Data Availability Sampling (DAS)**: Menggunakan 2D Reed-Solomon Erasure Coding dan Namespaced Merkle Trees (NMT). Light client dapat memverifikasi bahwa 100% data tersedia hanya dengan mengunduh sampel kecil data acak ($\sim \text{log}(N)$).

#### 3.3 KZG Commitment Mechanics pada EIP-4844
Dalam EIP-4844, payload tidak dimuat ke dalam `calldata` EVM (yang mahal karena $16 \text{ gas/non-zero byte}$), melainkan dibawa sebagai referensi komitmen kriptografis:
1. Data transaksi diubah menjadi polinomial interpolasi $p(x)$ menggunakan Roots of Unity.
2. Dihitung komitmen KZG: $C = [p(s)]_1$, di mana $s$ adalah secret parameter dari Trusted Setup (Powers of Tau).
3. Hash versi komitmen ($kzg\_to\_versioned\_hash(C)$) dioperasikan di level EVM (dimulai dengan prefix byte `0x01`).
4. Kontrak settlement memverifikasi ketersediaan via precompile point evaluation:
   $$\text{Precompile Address: } 0x000000000000000000000000000000000000000A$$
   Input yang dibutuhkan: $(versioned\_hash, x, y, C, \pi)$ di mana $\pi$ adalah bukti evaluasi $p(x) = y$.

---

### 4. Why & What

| Dimensi | Calldata Tradisional (Monolithic/Legacy Rollup) | EIP-4844 Blobs | Celestia / External DA |
| :--- | :--- | :--- | :--- |
| **Kapasitas Penyimpanan** | Terbatas oleh L1 Block Gas Limit (30M gas $\approx$ 1.8 MB teoritis, 150 KB realistis) | Maksimal 6 blob/blok ($\sim 768 \text{ KB}$), target 3 blob ($\sim 384 \text{ KB}$) | Fleksibel, modul throughput tinggi hingga multi-MB/blok |
| **Pruning Lifecycle** | Permanen dalam L1 State History | Otomatis dipangkas setelah $\approx 18$ hari ($\approx 4096$ epoch) | Tergantung validator consensus pruning (biasanya 30 hari) |
| **Model Biaya Gas** | Bersaing langsung dengan eksekusi DeFi L1 | Memiliki pasar gas independen (Blob Gas EIP-1559 terpisah) | Bayar fee native TIA/Token DA independen |
| **Overhead Komputasi Node** | Sangat tinggi, seluruh node L1 harus menyimpan dan memproses | Rendah, Beacon Node hanya memvalidasi KZG commitments | Rendah untuk rollups; sampling berbasis light-client |
| **Keamanan Ekonomi** | Full Ethereum L1 Consensus Security | Full Ethereum L1 Consensus Security | Bergantung pada Consensus Set & Token Market Cap Layer DA terkait |

---

### 5. How (Workflow Detail)

Alur eksekusi batch L2 dan settlement menuju L1 menggunakan EIP-4844:

```
[ L2 Users ]
     │ (1) Send L2 Tx
     ▼
[ Sequencer Mempool ]
     │
     ▼
[ Rollup Engine (op-geth/Nitro) ] ── (2) Execute & Produce L2 Blocks
     │
     ▼
[ Batch Submitter (Batcher) ]
     │ (3) Read L2 Blocks & Compress (Brotli/zstd)
     │ (4) Slice into 4096-field-element Chunks (Max 128KB/blob)
     │ (5) Compute Polynomial & KZG Commitment + Proof
     ▼
[ L1 Transaction Pool ] ────────── (6) Send Type-3 Tx with Blobs attached
     │
     ├─────────────────────────────────────────┐
     ▼                                         ▼
[ Execution Clients (geth) ]        [ Consensus Clients (Prysm/Lighthouse) ]
 (Only sees Versioned Hash,          (Stores raw Blob Data & KZG commitments
  executes Point Evaluation)          for ~18 days, serves P2P DAS)
     │                                         │
     ▼                                         ▼
[ L1 Rollup Contract ]              [ Verifier / Challenger Nodes ]
 (Updates Rollup State Root)         (Download blob from Consensus Layer,
                                      replay tx, verify state transitions)
```

1. **Agregasi & Kompresi**: Batcher mengekstrak transaksi L2 yang belum final di L1, menyusunnya dalam format RLP, dan mengompresinya menggunakan algoritma kompresi tinggi (misal: Zstandard atau Brotli).
2. **Segmentasi Blob**: Batch data yang terkompresi dibagi ke dalam segmen 131.072 byte ($4096 \times 32$ byte). Field element diwajibkan valid di scalar field BLS12-381 ($r < 0x73eda753...$).
3. **Kalkulasi Kriptografis**: Batcher memanggil library C-KZG / Go-KZG untuk membangkitkan `KZGCommitment` dan `KZGProof` untuk setiap blob.
4. **Diseminasi L1**: Membentuk transaksi `BlobTx` (EIP-2718 Type `0x03`). Transaksi mencakup array blob data di sidecar, hash versi komitmen di L1 body, dan mengeksekusi instruksi settlement root.
5. **Verifikasi Kontrak**: Kontrak di L1 memeriksa apakah hash versi yang dikirimkan cocok dengan commitment yang diverifikasi di blok consensus layer saat itu.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah **Mahkamah Agung (L1 Settlement)** dan **Kantor Cabang Pengiriman Dokumen (L2 Sequencer)**.
- **Calldata Tradisional**: Kantor Cabang mengirim seluruh buku kas transaksi harian secara fisik ke lemari arsip Mahkamah Agung. Mahkamah mengenakan biaya sewa rak arsip yang sangat mahal untuk selamanya.
- **Modular Data Availability (EIP-4844)**: Kantor Cabang menyimpan buku kas di loker penitipan sementara bandara yang memiliki sistem pengurutan barcode anti-pemalsuan (**KZG Commitment**). Kantor Cabang hanya menyerahkan tanda terima barcode tersebut ke Mahkamah. Mahkamah hanya mengecek stempel barcode. Jika ada audit, auditor punya waktu 18 hari untuk menyalin data dari loker sementara tersebut ke cold storage mereka sendiri.

```
       MONOLITHIC CHAIN                     MODULAR ROLLUP PIPELINE
    +--------------------+             +--------------------------------+
    | Execution          |             | L2 Execution (Private Mempool) |
    |      +             |             +--------------------------------+
    | Consensus          |                           │ (Batched Txs)
    |      +             |                           ▼
    | Settlement         |             +--------------------------------+
    |      +             |             | DA Layer: Blobs / Celestia     |
    | Data Availability  |             | (KZG Commitments / NMT Erasure)|
    |                    |             +--------------------------------+
    | (Semua node harus  |                           │ (Versioned Hashes)
    |  simpan & eksekusi |                           ▼
    |  semuanya)         |             +--------------------------------+
    +--------------------+             | L1 Settlement: Rollup Contract |
                                       | (Point Evaluation & State Root)|
                                       +--------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Point Evaluation Precompile Caller (Solidity)
Kontrak ringkas untuk membuktikan penggunaan precompile `0x0A` dalam memvalidasi keabsahan data blob terhadap komitmennya.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract BlobVerifierSimple {
    // Alamat Precompile EIP-4844 Point Evaluation
    address public constant POINT_EVALUATION_PRECOMPILE = address(0x0A);
    
    // BLS12-381 Scalar Field Modulus (r)
    // 0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001
    uint256 public constant BLS_MODULUS = 52435875175126190479447740508185965837690552500527637822603658699938581184513;

    error PrecompileCallFailed();
    error InvalidEvaluation();

    /**
     * @notice Memvalidasi bahwa evaluasi p(x) = y konsisten dengan KZG commitment.
     * @param versionedHash Bytes32 hash dari komitmen KZG (tipe 0x01 + sha256(commitment)[1:])
     * @param x Titik evaluasi (z)
     * @param y Hasil evaluasi p(z)
     * @param commitment Serialized KZG commitment (48 bytes)
     * @param proof Serialized KZG proof (48 bytes)
     */
    function verifyBlobData(
        bytes32 versionedHash,
        bytes32 x,
        bytes32 y,
        bytes memory commitment,
        bytes memory proof
    ) external view returns (bool) {
        require(commitment.length == 48, "Invalid commitment length");
        require(proof.length == 48, "Invalid proof length");
        require(uint256(x) < BLS_MODULUS, "x not in scalar field");
        require(uint256(y) < BLS_MODULUS, "y not in scalar field");

        // Payload memory input precompile:
        // [0:32]   versionedHash
        // [32:64]  x
        // [64:96]  y
        // [96:144] commitment (48 bytes)
        // [144:192] proof (48 bytes)
        bytes memory input = abi.encodePacked(versionedHash, x, y, commitment, proof);

        // Buffer untuk return value (selalu return dua field BLS: FIELD_ELEMENTS_PER_BLOB dan BLS_MODULUS)
        bytes memory output = new bytes(64);

        assembly {
            let success := staticcall(
                gas(),                          // Forward all gas
                POINT_EVALUATION_PRECOMPILE,    // 0x0A
                add(input, 0x20),               // In pointer
                mload(input),                   // In size (192 bytes)
                add(output, 0x20),              // Out pointer
                0x40                            // Out size (64 bytes)
            )
            if iszero(success) {
                // Revert with PrecompileCallFailed()
                mstore(0x00, 0x1f7b0369)
                revert(0x1c, 0x04)
            }
        }

        return true;
    }
}
```

#### 7.2 Practical Example: Enterprise Sequencer Batch Submitter (Go)
Implementasi service batch submission produksi yang mengubah raw payload menjadi blob, menghitung komitmen KZG via `ckzg`, dan mempublikasikannya ke Layer-1 menggunakan Go-Ethereum.

```go
package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"fmt"
	"log"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc/bls12-381/fr"
	ckzg "github.com/ethereum/c-kzg-4844/bindings/go"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
)

const (
	BlobSize            = 131072 // 4096 elements * 32 bytes
	FieldElementsPerBlob = 4096
	BytesPerFieldElement = 32
	BlobTxType           = 0x03
	VersionedHashVersionKZG = 0x01
)

type BatchSubmitter struct {
	client     *ethclient.Client
	privateKey []byte
	l1Address  common.Address
	inboxAddr  common.Address
	chainID    *big.Int
}

func NewBatchSubmitter(rpcURL string, privKeyHex string, inbox common.Address) (*BatchSubmitter, error) {
	client, err := ethclient.Dial(rpcURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to L1 RPC: %w", err)
	}

	key, err := crypto.HexToECDSA(privKeyHex)
	if err != nil {
		return nil, fmt.Errorf("invalid private key: %w", err)
	}

	chainID, err := client.ChainID(context.Background())
	if err != nil {
		return nil, fmt.Errorf("failed to fetch chain ID: %w", err)
	}

	return &BatchSubmitter{
		client:     client,
		privateKey: crypto.FromECDSA(key),
		l1Address:  crypto.PubkeyToAddress(key.PublicKey),
		inboxAddr:  inbox,
		chainID:    chainID,
	}, nil
}

// EncodeBatchToBlob mengubah byte stream menjadi format blob 4096 field element yang valid
func (b *BatchSubmitter) EncodeBatchToBlob(data []byte) (*ckzg.Blob, error) {
	if len(data) > BlobSize {
		return nil, fmt.Errorf("data size exceeds max blob capacity: %d > %d", len(data), BlobSize)
	}

	var blob ckzg.Blob
	copy(blob[:], data)

	// Pastikan setiap field element modulo scalar field r BLS12-381
	for i := 0; i < FieldElementsPerBlob; i++ {
		start := i * BytesPerFieldElement
		end := start + BytesPerFieldElement

		var element fr.Element
		element.SetBytes(blob[start:end])
		// Write back normalized bytes in canonical form
		bBytes := element.Bytes()
		copy(blob[start:end], bBytes[:])
	}

	return &blob, nil
}

// BuildAndBroadcastBlobTx memvalidasi komitmen dan membroadcast transaksi tipe-3 EIP-4844
func (b *BatchSubmitter) BuildAndBroadcastBlobTx(ctx context.Context, blob *ckzg.Blob) (common.Hash, error) {
	// 1. Inisialisasi Trusted Setup (wajib diload di real app via ckzg.LoadTrustedSetup)
	commitment, err := ckzg.BlobToKZGCommitment(*blob)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to compute KZG commitment: %w", err)
	}

	proof, err := ckzg.ComputeBlobKZGProof(*blob, commitment)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to compute KZG proof: %w", err)
	}

	// 2. Hitung Versioned Hash: 0x01 + sha256(commitment)[1:]
	h := sha256.Sum256(commitment[:])
	var versionedHash common.Hash
	versionedHash[0] = VersionedHashVersionKZG
	copy(versionedHash[1:], h[1:])

	// 3. Ambil Nonce dan Gas Market Parameters
	nonce, err := b.client.PendingNonceAt(ctx, b.l1Address)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to fetch nonce: %w", err)
	}

	gasPrice, err := b.client.SuggestGasPrice(ctx)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to suggest gas price: %w", err)
	}

	tipCap, err := b.client.SuggestGasTipCap(ctx)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to suggest tip cap: %w", err)
	}

	// Dynamic calculation of blob fee
	blobBaseFee := big.NewInt(1000000000) // Minimum baseline blob fee

	// 4. Susun Blob Transaction Payload
	sidecar := types.BlobTxSidecar{
		Blobs:       []ckzg.Blob{*blob},
		Commitments: []ckzg.Bytes48{commitment},
		Proofs:      []ckzg.Bytes48{proof},
	}

	txData := &types.BlobTx{
		ChainID:    uint256FromBig(b.chainID),
		Nonce:      nonce,
		GasTipCap:  uint256FromBig(tipCap),
		GasFeeCap:  uint256FromBig(gasPrice.Add(gasPrice, tipCap)),
		Gas:        250000,
		To:         b.inboxAddr,
		Value:      uint256FromBig(big.NewInt(0)),
		Data:       []byte{}, // Kosong jika interaksi via Inbox hanya mencatat DA
		BlobFeeCap: uint256FromBig(blobBaseFee.Mul(blobBaseFee, big.NewInt(2))),
		BlobHashes: []common.Hash{versionedHash},
		Sidecar:    &sidecar,
	}

	tx := types.NewTx(txData)

	key, _ := crypto.ToECDSA(b.privateKey)
	signer := types.NewCancunSigner(b.chainID)
	signedTx, err := types.SignTx(tx, signer, key)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to sign blob transaction: %w", err)
	}

	// 5. Broadcast transaksi ke jaringan
	err = b.client.SendTransaction(ctx, signedTx)
	if err != nil {
		return common.Hash{}, fmt.Errorf("failed to broadcast blob transaction: %w", err)
	}

	log.Printf("Blob Transaction broadcasted! TxHash: %s, VersionedHash: %s", signedTx.Hash().Hex(), versionedHash.Hex())
	return signedTx.Hash(), nil
}

func uint256FromBig(n *big.Int) *big.Int {
	return n
}

func main() {
	// Demonstrasi segmentasi mock
	mockBatch := make([]byte, 100000)
	_, _ = rand.Read(mockBatch)

	fmt.Printf("Batch Size: %d bytes siap diproses menjadi Blob.\n", len(mockBatch))
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Settlement FinTech Rollup (5.000 TPS)
- **Konteks**: Sebuah konsorsium perbankan multinasional membangun roll-up berbasis OP-Stack untuk kliring pembayaran antar-bank dengan beban rata-rata 5.000 TPS dan SLA finalitas kliring $\le 3 \text{ detik}$.
- **Problem**: Penggunaan L1 Calldata pada jam puncak menghasilkan biaya transaksi hingga $\approx \$120.000$ per hari pada volatilitas gas Ethereum $60 \text{ Gwei}$. Ketika lonjakan lalu lintas terjadi, batch submission mengalami *stuck* karena batas Gas Limit blok monolitik L1 terlampaui.
- **Solusi Arsitektur**:
  1. **Dual DA Failover Route**: Sistem utama mengalirkan transaksi ke L1 Blobs (EIP-4844). Jika `blobBaseFee` melompat $> 120 \text{ Gwei}$ akibat perebutan ruang blob secara global, *Dynamic Fallback Engine* secara deterministik mengarahkan kompresi data ke jaringan **Celestia Mainnet** menggunakan Namespaced Merkle Trees dengan membungkus batch ID ke dalam namespace L2 milik konsorsium.
  2. **Streaming Compression Pipeline**: Memanfaatkan kompresor paralel level-memory berbasis `zstd` dictionary-trained dengan corpus data finansial ISO-20022 yang menghasilkan rasio kompresi $4.8:1$.
  3. **High-Availability Sequencer Pool**: Menggunakan arsitektur Sequencer aktif-pasif dengan konsensus Raft internal untuk determinasi sekuens lokal sebelum diekspor ke DA, mencegah desinkronisasi batch.
- **Hasil**:
  - Penurunan *settlement operational cost* sebesar $94.6\%$.
  - Kapasitas L2 meningkat dari toleransi maksimum 350 TPS (saat menggunakan Calldata) menjadi stabil pada 5.200 TPS tanpa membebani L1 Gas Pool.
  - Latensi konfirmasi soft-finality tetap pada $250 \text{ ms}$.

---

### 9. Trade-offs

```
                  SECURITY (Full L1 Economic Guarantee)
                               /\
                              /  \
                             /    \
                            /  A   \
                           /        \
                          /          \
     (EIP-4844 Blobs)    /____________\ (EigenDA - Restaked ETH)
                        / \          / \
                       /   \   C    /   \
                      /  B  \      /  D  \
                     /_______\____/_______\
COST-EFFICIENCY                            THROUGHPUT CAPACITY
(Celestia / DAC)                           (Off-Chain Data Shards)
```

- **A (EIP-4844 Blobs)**: Keamanan L1 murni. Trade-off: Ukuran blob terbatas (maksimal 6 per block saat ini) dan retensi hanya $\approx 18$ hari.
- **B (External DA - Celestia/Avail)**: Biaya terendah dan kapasitas sangat besar. Trade-off: Menambahkan asumsi kepercayaan (*trust assumption*) baru di luar Layer-1 (Validator Set DA eksternal harus jujur $\ge 2/3$ atau $\ge 1/6$ tergantung skema sampling).
- **C (Restaked DA - EigenDA)**: Mewarisi sebagian keamanan modal kripto L1 via restaking tanpa batasan blockspace EVM. Trade-off: Slashing conditions yang rumit, dual-quorum penalty latency.
- **D (Data Availability Committees - DAC / Validium)**: Throughput jutaan TPS, biaya mendekati nol. Trade-off: Kripto-ekonomi lemah; kolusi 5 dari 7 anggota DAC dapat membekukan rantai (*Data Withholding* total).

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Blob Scalar Field Overflow
- **Penyebab**: Data mentah diinjeksi ke dalam field element 32-byte tanpa validasi scalar BLS12-381 ($r = 0x73eda753...$). Jika nilai byte element $\ge r$, komputasi KZG proof lokal atau point evaluation di kontrak L1 akan gagal dengan error revert generik tanpa pesan yang jelas.
- **Solusi**: Masking byte tertinggi (set 2 bit paling signifikan pada byte indeks 0 menjadi nol) atau gunakan encoding konversi representasi field elements kanonikal sebelum evaluasi komitmen.

#### 10.2 Asumsi Persistensi Permanen Blob
- **Penyebab**: Pengembang mendesain kontrak indexer atau audit log internal dengan asumsi bahwa RPC layer consensus (`eth/v1/beacon/blob_sidecars`) akan menyimpan blob selamanya.
- **Dampak**: Node baru yang melakukan sinkronisasi *from scratch* setelah 30 hari gagal memvalidasi rantai karena blob telah dipangkas oleh node konsensus.
- **Solusi**: Bangun subsistem *Archival Bridge* independen yang menyalin blob dari consensus client ke sistem penyimpanan persisten desentralisasi (Filecoin/Arweave) atau S3-compatible cold vault tepat sebelum jendela pruning tercapai.

#### 10.3 Nonce & Reorg Desynchronization pada Batcher
- **Gejala**: Batcher terhenti (*stuck*) dengan error `replacement transaction underpriced` atau `nonce too low` saat frekuensi blob submission tinggi.
- **Troubleshooting Steps**:
  1. Deteksi apakah terjadi L1 micro-reorg (1-2 block deep).
  2. Implementasikan *Transaction Tracking Buffer* lokal yang memetakan UUID Batch L2 ke hash transaksi L1.
  3. Gunakan teknik *Blob Gas Dynamic Bumping*: naikkan `BlobFeeCap` minimal $12\%$ dan `GasFeeCap` minimal $10\%$ secara bersamaan untuk melakukan `tx replacement` legal sesuai aturan Geth mempool.

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Encoding Sanitization**: Pastikan seluruh chunk 32-byte blob berada di bawah modulus kurva $r$ sebelum diteruskan ke fungsi binding C-KZG.
- [ ] **Dual-Prover / Multi-DA Fallback**: Siapkan mekanisme sirkuit pemutus (*circuit breaker*) di Settlement Contract yang memungkinkan alur batch diarahkan sementara ke L1 Calldata konvensional jika pasar blob mengalami kemacetan parah atau DoS.
- [ ] **Blob Base Fee Tracking**: Gunakan EIP-1559 style controller untuk memproyeksikan lonjakan `blobBaseFee` dan tahan (*buffer*) submission di mempool internal L2 jika fee melonjak di luar target batas profitabilitas sequencer.
- [ ] **Precompile Input Formatting**: Saat memanggil contract precompile `0x0A`, susun layout byte memory secara ketat: 192 bytes payload rata kiri tanpa trailing garbage padding.
- [ ] **Observabilitas Metrik**:
  - `rollup_batcher_submission_latency_seconds`: Waktu dari L2 block creation hingga L1 inclusion confirmation.
  - `rollup_batcher_blob_gas_cost_wei`: Realized gas burn per blob.
  - `rollup_da_verification_failures_total`: Total revert pada precompile verifier.
- [ ] **Independent Pruning Resilience**: Jangan pernah bergantung pada node eksternal untuk menyimpan data historis blob; jalankan minimal 2 instance *Historical Blob Archiver* mandiri di region fisik terpisah.

---

### 12. Hands-on Practice

Buat repositori mini praktikum untuk memvalidasi integrasi Blob Verification pada direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── contracts/
│   └── ProductionRollupInbox.sol
├── scripts/
│   └── submit_blob.go
├── test/
│   └── BlobVerification.t.sol
├── go.mod
└── foundry.toml
```

#### Langkah 1: Inisialisasi Dependensi Go
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
go mod init enterprise-da-lab
go get github.com/ethereum/go-ethereum@v1.13.14
go get github.com/ethereum/c-kzg-4844/bindings/go@v0.1.0
go get github.com/consensys/gnark-crypto@v0.12.1
```

#### Langkah 2: Buat Settlement Inbox Contract
Tulis file `contracts/ProductionRollupInbox.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract ProductionRollupInbox {
    address public constant POINT_EVALUATION = address(0x0A);
    address public immutable sequencer;
    bytes32 public currentL2StateRoot;

    event BlockBatched(bytes32 indexed versionedHash, bytes32 newStateRoot);

    modifier onlySequencer() {
        require(msg.sender == sequencer, "Unauthorized: Not Sequencer");
        _;
    }

    constructor(bytes32 initialRoot) {
        sequencer = msg.sender;
        currentL2StateRoot = initialRoot;
    }

    function commitBatch(
        bytes32 newStateRoot,
        bytes32 versionedHash,
        bytes32 x,
        bytes32 y,
        bytes calldata commitment,
        bytes calldata proof
    ) external onlySequencer {
        // Validasi ketersediaan data via point evaluation
        bytes memory args = abi.encodePacked(versionedHash, x, y, commitment, proof);
        
        (bool success, ) = POINT_EVALUATION.staticcall(args);
        require(success, "KZG verification failed: DA invalid");

        // Perbarui Root Status L2
        currentL2StateRoot = newStateRoot;

        emit BlockBatched(versionedHash, newStateRoot);
    }
}
```

#### Langkah 3: Eksekusi Test Suite Menggunakan Foundry
Jalankan fork test lokal yang mensimulasikan hardfork Cancun:

```bash
forge init --force
forge test --evm-version cancun -vvv
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi utilitas Go: `func ValidateFieldElement(element []byte) bool` yang menerima slice 32-byte dan memvalidasi apakah byte array tersebut merepresentasikan nilai integer yang valid dan berada dalam rentang scalar field modulus BLS12-381 secara matematis.

#### Level: Medium
Tulis smart contract Solidity yang memproses *Multi-Blob Submission*. Kontrak harus mampu menerima hingga 6 `versionedHash` dalam satu pemanggilan metode L1, memvalidasi verifikasi point evaluation untuk seluruh komitmen yang masuk, dan membatalkan status jika salah satu evaluasi blob gagal (revert atomic).

#### Level: Hard
Rancang dan implementasikan service *Batch Pipeline* paralel dalam Go yang mengonsumsi channel transaksi L2 yang masuk secara kontinu.
Spesifikasi:
1. Membaca hingga $50.000$ transaksi dummy L2.
2. Membagi payload secara otomatis menjadi $N$ blob (masing-masing maksimal $128 \text{ KB}$).
3. Menjalankan komputasi komitmen KZG dan proof secara paralel menggunakan goroutine pool.
4. Menghasilkan struktur `BlobTxSidecar` yang siap ditandatangani.

---

### 14. Challenge: Split-Brain Sequencer & Dynamic DA Failover System

#### Skenario Kasus Kompleks
Anda adalah Principal Architect sebuah Rollup L2 institusional. Jaringan Anda mengalami split-brain pada layer DA primer (Celestia) akibat partisi jaringan lintas benua, sementara pada saat yang sama, pasar blob L1 Ethereum mengalami kemacetan ekstrem di mana `blobBaseFee` melonjak $10.000\%$ dalam rentang 15 blok akibat aktivitas inscription minting.

#### Kebutuhan Arsitektural:
1. **Rancang Fallback Controller Algoritma**: Rancang mekanisme deterministik pada L2 client yang mampu mendeteksi ketiadaan konfirmasi finalitas dari layer DA primer dalam batas ambang $T_{timeout} = 60 \text{ detik}$.
2. **Dynamic Compression Escalation**: Jika data dialihkan secara darurat ke Calldata L1 (jalur alternatif darurat), pipeline batcher harus beralih dari algoritma kompresi kecepatan tinggi standar ke kompresor kamus kustom multi-pass untuk meminimalkan byte size, terlepas dari konsumsi resource CPU.
3. **Pencegahan Equivocation**: Rancang spesifikasi settlement contract L1 yang mencegah sequencer jahat mempublikasikan batch state yang sama ke dua DA layer secara paralel untuk menduplikasi penarikan dana (*double-spending canonical state bridge*).
4. **Deliverable**: Susun dokumen arsitektur teknis lengkap yang mencakup diagram state machine sequencer, layout data payload fallback, dan proteksi inline assembly pada settlement contract untuk mengunci ID provider DA kanonikal.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Berapa ukuran byte maksimal dari sebuah blob data individual pada EIP-4844?**
   - A. 64 KB
   - B. 128 KB
   - C. 256 KB
   - D. 1 MB
   *Jawaban*: B. Tepatnya 131.072 bytes, terdiri dari 4096 field element berukuran masing-masing 32 bytes.

2. **Berapa alamat precompile kontrak pada Layer-1 Ethereum yang didedikasikan untuk KZG Point Evaluation?**
   - A. `0x0000000000000000000000000000000000000001`
   - B. `0x0000000000000000000000000000000000000008`
   - C. `0x000000000000000000000000000000000000000A`
   - D. `0x0000000000000000000000000000000000000010`
   *Jawaban*: C. Alamat `0x0A` (desimal 10) adalah precompile point evaluation yang diperkenalkan pada EIP-4844.

3. **Berapa lama rata-rata blob EIP-4844 disimpan oleh consensus client node sebelum otomatis dipangkas (pruned)?**
   - A. 24 jam
   - B. $\approx 18$ hari (4096 epoch)
   - C. 1 tahun
   - D. Permanen selamanya
   *Jawaban*: B. Blob dirancang sebagai ketersediaan data transien berdurasi sekitar 18 hari untuk memberikan jendela waktu yang cukup bagi prover dan challenger untuk mengunduh data.

4. **Karakter byte pertama (prefix) yang digunakan untuk mengidentifikasi Versioned Hash komitmen KZG tipe 1 adalah:**
   - A. `0x00`
   - B. `0x01`
   - C. `0x03`
   - D. `0xFF`
   *Jawaban*: B. Prefix `0x01` menandakan representasi KZG versioned hash standar saat ini.

5. **Apa fungsi utama dari Reed-Solomon Erasure Coding dalam arsitektur Data Availability modular seperti Celestia?**
   - A. Mengenkripsi isi transaksi agar tidak terbaca validator
   - B. Mengompresi ukuran data agar 10 kali lebih kecil
   - C. Memungkinkan rekonstruksi data utuh meskipun sebagian data hilang atau disembunyikan
   - D. Menghasilkan proof nol-pengetahuan (Zero-Knowledge)
   *Jawaban*: C. Erasure coding memungkinkan node merekonstruksi 100% data hanya dengan menerima proporsi tertentu (misal: 50% pada 1D atau 25% pada 2D sampling).

---

#### Intermediate (5 Pertanyaan)
6. **Mengapa transaksi Blob (Tipe-3) memisahkan Blob Data ke dalam struktur *sidecar* di level Consensus Client dan tidak menyertakannya langsung di Execution Client payload?**
   - A. Agar Execution Client tidak terbebani pemrosesan I/O bandwidth dan alokasi memori yang masif saat mengeksekusi blok L1.
   - B. Karena EVM tidak mampu membaca data hexadecimal.
   - C. Untuk menghindari enkripsi SSL saat transmisi jaringan P2P.
   - D. Karena layer settlement tidak memerlukan hash verifikasi.
   *Jawaban*: A. Pemisahan ini menjaga execution client tetap ringan; EVM hanya perlu memvalidasi komitmen hash pendek, sementara beban propagasi blob ditangani layer konsensus.

7. **Apa yang terjadi jika Sequencer mengevaluasi nilai field element bernilai integer $V$ di mana $V \ge r$ (BLS12-381 scalar modulus)?**
   - A. Nilai otomatis di-wrap via operasi modulo secara implisit oleh EVM.
   - B. Point Evaluation precompile akan langsung me-revert eksekusi transaksi.
   - C. Biaya gas transaksi blob akan didiskon.
   - D. Transaksi berhasil tetapi komitmen blob menjadi nol.
   *Jawaban*: B. Modulus scalar adalah batas strict matematika. Setiap input ke precompile yang berada di luar jangkauan validitas kurva akan membuat precompile gagal (revert).

8. **Manakah dari skenario berikut yang merepresentasikan serangan *Data Availability Withholding Attack*?**
   - A. Hacker mencuri private key sequencer dan mengirimkan transaksi palsu.
   - B. Sequencer memublikasikan State Root baru ke L1 Inbox tetapi sengaja tidak mengunggah data transaksi padanannya ke layer DA.
   - C. Node verifikator menolak menjalankan transaksi yang valid.
   - D. Miner membatalkan transaksi di mempool publik.
   *Jawaban*: B. Dengan menyembunyikan data transaksi, verifikator tidak dapat membuktikan apakah transisi status tersebut valid atau curang.

9. **Mekanisme apa yang mengatur penentuan harga dasar pada pemakaian blob di EIP-4844?**
   - A. Mengikuti secara linier biaya `baseFee` gas reguler Ethereum.
   - B. Ditentukan secara statis melalui voting hardfork tahunan.
   - C. Mekanisme mandiri mirip EIP-1559 yang menaikkan biaya jika utilisasi blob per blok melampaui target (3 blob) dan menurunkannya jika di bawah target.
   - D. Tidak dikenakan biaya (gratis sepenuhnya).
   *Jawaban*: C. EIP-4844 memiliki pasar gas independen (`blobBaseFee`) yang bergerak secara dinamis sesuai utilitas terhadap target blob capacity.

10. **Apa keunggulan arsitektural utama *Namespaced Merkle Trees* (NMT) pada layer DA Celestia untuk sebuah Rollup?**
    - A. Memungkinkan Rollup node hanya mengunduh data yang relevan dengan ID (namespace) rantai mereka sendiri tanpa mengunduh data rollup lain.
    - B. Menjamin transaksi diproses dalam urutan alfabetis.
    - C. Meniadakan perlunya block header pada rollup.
    - D. Menjamin perlindungan privasi absolut dari pengawasan regulator.
    *Jawaban*: A. NMT memungkinkan pemisahan namespace per aplikasi/rollup, sehingga verifikator cukup memverifikasi inclusion proof untuk namespace mereka sendiri.

---

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Produksi 1**: Tim SRE Anda melaporkan bahwa service *Batch Submitter* rollup mengalami serangkaian transaksi *revert* beruntun di L1. Metrik logging menunjukkan precompile `0x0A` mengembalikan status *FAIL*. Pemeriksaan awal menunjukkan bahwa komputasi KZG Commitment lokal valid dan payload data utuh. Manakah dari penyebab berikut yang paling mungkin terjadi?
    - A. Node Consensus lokal kehabisan kuota RAM.
    - B. Batch Submitter menghitung `versionedHash` menggunakan hashing `keccak256` dan bukan `sha256(commitment)`.
    - C. Sequencer memproses transaksi melebihi batas 5.000 TPS.
    - D. Parameter chain ID transaksi L2 disetel secara asinkron.
    *Solusi & Analisis*: **B**. Spesifikasi resmi EIP-4844 mewajibkan pembuatan versioned hash menggunakan algoritma SHA-256 (`0x01` disambung dengan 31 byte terakhir dari `sha256(commitment)`). Penggunaan `keccak256` (yang standar di Ethereum) akan menghasilkan hash yang tidak cocok dengan komitmen yang dipetakan oleh Beacon Chain, menyebabkan precompile gagal memverifikasi kesetaraan komitmen.

12. **Skenario Produksi 2**: Selama periode volatilitas pasar yang masif, Sequencer batcher node Anda gagal membroadcast transaksi tipe-3 ke L1 mempool selama lebih dari 45 menit karena parameter gas fee statis yang tertinggal dari lonjakan pasar. Transaksi L2 pengguna mulai menumpuk di mempool Sequencer dan terancam membengkak melewati memory footprint maksimum node. Langkah perbaikan darurat apa yang paling aman dan tepat?
    - A. Restart instance Sequencer untuk menghapus mempool.
    - B. Turunkan ukuran batch L2 menjadi 1 transaksi per blob.
    - C. Jalankan *Fee Replacement Script*: broadcast transaksi tipe-3 baru yang membawa batch tertunda dengan `nonce` yang sama persis, namun naikkan `GasFeeCap` dan `BlobFeeCap` minimal $15\%$ di atas harga pasar saat itu.
    - D. Alihkan sequencer ke jaringan testnet sementara.
    - *Solusi & Analisis*: **C**. Melakukan *speed-up* / replacement transaksi di EVM mempool memerlukan penyetelan ulang nonce yang sama dengan bumping fee minimal sesuai aturan node (biasanya $10\% - 12\%$). Ini membersihkan antrian batch yang tersumbat tanpa menghilangkan data transaksi pengguna di mempool.

13. **Skenario Kasus 3**: Audit keamanan pada custom canonical bridge menemukan celah potensial: Verifier kontrak settlement L1 menerima pembaruan state L2 baru hanya dengan memeriksa apakah array `BlobHashes` tidak kosong, tanpa memverifikasi data ketersediaan menggunakan *Point Evaluation Precompile*. Risiko kritis apa yang secara langsung mengancam sistem tersebut?
    - A. Transaksi L1 pengguna akan kehilangan gas tanpa batas.
    - B. Sequencer jahat dapat menyisipkan `versionedHash` dari blob milik aplikasi/rollup lain yang sama sekali tidak berisi transaksi rollup ini, tetapi kontrak L1 tetap mengeksekusi transisi status yang tidak valid tersebut.
    - C. Beacon chain L1 akan terhenti seketika.
    - D. Waktu finalitas blob akan dipercepat menjadi 1 detik.
    - *Solusi & Analisis*: **B**. `BlobHashes` yang tersedia via opcode `BLOBHASH` hanya membuktikan bahwa sebuah blob telah dimasukkan dalam blok L1 saat ini, tetapi tidak membuktikan bahwa isi blob tersebut cocok dengan formula transisi status L2 tertentu tanpa evaluasi titik interpolasi kriptografis ($p(z) = y$) melalui precompile `0x0A`.

---

### 16. Summary
Modularitas Layer-2 membebaskan arsitektur blockchain dari kemacetan monolitik dengan memecah eksekusi dari konsensus dan ketersediaan data. Penskalaan modern enterprise menuntut pemisahan beban: transaksi dieksekusi secara instan pada lingkungan komputasi L2 performa tinggi, sementara integritas historis dijamin melalui komitmen matematika ringkas ke Layer Data Availability. 

Implementasi standar **EIP-4844** merevolusi efisiensi biaya settlement melalui penciptaan ruang data sementara (Blobs) yang beroperasi di bawah rezim pasar gas mandiri dan diverifikasi secara on-chain menggunakan **KZG Polynomial Commitments** via precompile `0x0A`. Untuk membangun sistem kelas produksi yang tangguh, rekayasawan perangkat lunak sistem terdistribusi tidak hanya harus menguasai logika smart contract settlement, namun wajib menguasai sanitasi byte pada scalar field kriptografi kurva eliptik, orkestrasi pipeline blob batching berkonkurensi tinggi di level backend, dan merancang mitigasi failover berlapis saat menghadapi fragmentasi DA atau reorganisasi jaringan.