# BAB-08: Kriptografi Nol-Pengetahuan (Zero-Knowledge Cryptography)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Mengonstruksi** sistem aritmetisasi sirkuit tingkat lanjut menggunakan *Rank-1 Constraint Systems* (R1CS) dan skema *PlonKish arithmetization*.
- **Mengimplementasikan** pipeline pembuktian kriptografi (*proving pipeline*) ujung-ke-ujung berbasis Groth16 dan PLONK dengan pustaka tingkat produksi (Circom, SnarkJS, dan Gnark).
- **Mendesain dan Menerapkan** kontrak pintar verifikator EVM (*Ethereum Virtual Machine*) yang hemat gas dengan proteksi terhadap serangan *malleability* dan *under-constrained circuits*.
- **Mengevaluasi dan Mengoptimalkan** kinerja komputasi intensif *Multi-Scalar Multiplication* (MSM) dan *Number Theoretic Transform* (NTT) pada node prover skala enterprise.
- **Mengintegrasikan** pembuktian ZK ke dalam arsitektur Agen Otonom (*Autonomous Agents*) untuk inferensi model AI terverifikasi (*Zero-Knowledge Machine Learning* / ZK-ML) dan komputasi *off-chain* berintegritas tinggi.

---

### 2. Prerequisites
Untuk menyerap materi ini secara optimal, Anda wajib menguasai:
- **Aljabar Abstrak Komputasional**: Medan hingga (*finite fields* $\mathbb{F}_p$), kurva eliptik (*elliptic curves* BN254/Alt-bn128, BLS12-381), dan *bilinear pairing* ($e: \mathbb{G}_1 \times \mathbb{G}_2 \to \mathbb{G}_T$).
- **Sistem dan Bahasa Pemrograman**: Rust (tingkat menengah) atau Go (untuk backend prover), Node.js/TypeScript (tooling), dan Solidity (EVM assembly/Yul dasar).
- **Konsep Kriptografi Dasar**: Fungsi hash ramah-ZK (*algebraic hashes* seperti Poseidon dan MiMC), skema komitmen polinomial (*KZG/Kate Commitment* dan *FRI*).
- **Sistem Operasi dan Arsitektur Mesin**: Pemahaman mendalam tentang manajemen memori, *multi-threading*, instruksi vektor SIMD (AVX-512), dan akselerasi GPU (CUDA/OpenCL).

---

### 3. Concept & Internal Architecture

Implementasi sistem *Zero-Knowledge* (ZK) tingkat enterprise membagi komputasi menjadi dua domain: domain eksekusi komputasional (*untrusted prover*) dan domain verifikasi deterministik (*succinct verifier*).

```
+-------------------------------------------------------------------------------+
|                             PROVER ARCHITECTURE                               |
|                                                                               |
|  [High-Level DSL] (Circom / Gnark / Halo2)                                    |
|          |                                                                    |
|          v                                                                    |
|  [Intermediate Representation (IR)]                                           |
|          |                                                                    |
|          +-----------------------------------+                                |
|          |                                   |                                |
|          v                                   v                                |
|  [Constraint System]                [Witness Generator]                       |
|   - R1CS (Groth16)                   - Evaluasi sinyal sirkuit (w)            |
|   - PlonKish Gates (PLONK)           - Private + Public inputs                |
|          |                                   |                                |
|          +-----------------+-----------------+                                |
|                            |                                                  |
|                            v                                                  |
|                 [Prover Core Engine]                                          |
|                  - Polynomial Interpolation (iNTT)                            |
|                  - Multi-Scalar Multiplication (MSM)                          |
|                  - Quotient Polynomial Construction                           |
|                  - Proof Synthesis (pi_A, pi_B, pi_C / Plonk Proof)           |
+----------------------------+--------------------------------------------------+
                             |
                      Proof Payload (bytes) + Public Signals
                             |
                             v
+-------------------------------------------------------------------------------+
|                             VERIFIER ARCHITECTURE                             |
|                                                                               |
|  [On-Chain EVM Contract / Verifier Engine]                                    |
|   1. Input Parsing & Validation: Validasi rentang medan hingga c < r          |
|   2. Linear Combination: IC = IC_0 + \sum(x_i * IC_i)                         |
|   3. Bilinear Pairing Check:                                                  |
|      e(pi_A, pi_B) == e(\alpha, \beta) * e(IC, \gamma) * e(pi_C, \delta)      |
|   4. State Update: Revert jika invalid; ubah state aplikasi jika valid        |
+-------------------------------------------------------------------------------+
```

#### 3.1 Aritmetisasi: Dari Kode Komputasi ke Persamaan Polinomial
Komputasi arbitrer tidak dapat dibuktikan secara langsung. Komputasi harus direduksi menjadi relasi aljabar di atas medan hingga $\mathbb{F}_p$:

1. **R1CS (Rank-1 Constraint System)**:
   Kumpulan tiga vektor $(A, B, C) \in \mathbb{F}_p^m$ sedemikian rupa sehingga untuk vektor *witness* $s \in \mathbb{F}_p^m$ (di mana $s_0 = 1$), persamaan berikut terpenuhi:
   $$(A \cdot s) \circ (B \cdot s) = (C \cdot s)$$
   Operasi $\circ$ melambangkan *Hadamard product* (perkalian elemen-demi-elemen). Sirkuit dengan $n$ batasan (*constraints*) diubah menjadi matriks $A, B, C$ berukuran $n \times m$.

2. **QAP (Quadratic Arithmetic Program)**:
   R1CS ditransformasikan ke dalam bentuk polinomial menggunakan interpolasi Lagrange. Diberikan akar-akar pembuat nol $r_1, r_2, \dots, r_n \in \mathbb{F}_p$:
   $$A_i(X), B_i(X), C_i(X)$$
   Persamaan batasan menjadi identitas pembagian polinomial:
   $$P(X) = \sum_{i=0}^{m} s_i A_i(X) \cdot \sum_{i=0}^{m} s_i B_i(X) - \sum_{i=0}^{m} s_i C_i(X) = H(X) \cdot Z(X)$$
   di mana $Z(X) = \prod_{j=1}^{n} (X - r_j)$ adalah *vanishing polynomial*. Prover membuktikan bahwa $P(X)$ habis dibagi oleh $Z(X)$ tanpa membuka isi $s$.

3. **PlonKish Arithmetization**:
   Menggunakan matriks gerbang fleksibel (*custom gates*) dan argumen permutasi (*copy constraints* via polinomial permutasi $\sigma$):
   $$q_{L_i} a_i + q_{R_i} b_i + q_{O_i} c_i + q_{M_i} (a_i b_i) + q_{C_i} = 0$$
   Memungkinkan implementasi operasi non-linear (seperti XOR, rotasi bit, dan *S-box* hash) jauh lebih efisien dibandingkan R1CS murni.

#### 3.2 Komputasi Prover: Bottleneck Bottleneck Utama
Operasi pembuktian ZK didominasi oleh dua algoritma komputasi masif:
- **Number Theoretic Transform (NTT / iNTT)**: Transformasi Fourier Diskrit di atas $\mathbb{F}_p$. Digunakan untuk konversi antara representasi koefisien dan evaluasi polinomial dalam kompleksitas waktu $\mathcal{O}(N \log N)$.
- **Multi-Scalar Multiplication (MSM)**: Menghitung $\sum_{i=1}^N k_i P_i$ di mana $k_i \in \mathbb{F}_p$ dan $P_i \in \mathbb{G}_1$ (atau $\mathbb{G}_2$). Ini memakan ~70-80% waktu pembangkitan bukti. Prover produksi menggunakan algoritma Pippenger dengan dekomposisi jendela (*bucket method*).

---

### 4. Why & What

| Dimensi | Pendekatan Sentralistis / Web2 | Komputasi Blockchain Standar | Solusi Zero-Knowledge Skala Enterprise |
| :--- | :--- | :--- | :--- |
| **Model Integritas** | Kepercayaan pada entitas sentral (AWS, Otoritas API) | Re-eksekusi deterministik oleh seluruh node (Sangat lambat, boros) | Eksekusi komputasi *off-chain* sekali; verifikasi matematis ringkas *on-chain* |
| **Kerahasiaan Data** | Enkripsi at-rest/in-transit (terbuka saat runtime) | Publik secara default (Semua data/storage terlihat di mempool/ledger) | *Provable privacy*: Komputasi valid tanpa mengekspos variabel internal |
| **Kompleksitas Verifikasi** | $\mathcal{O}(N)$ (Audit log penuh) | $\mathcal{O}(N)$ (Setiap validator mengeksekusi $N$ langkah instruksi) | $\mathcal{O}(1)$ atau $\mathcal{O}(\log N)$ independen dari kompleksitas sirkuit asli |
| **Integrasi Agen Otonom** | API Key terpusat, eksekusi black-box tak tepercaya | Terbatas oleh *gas limit* block; model inferensi AI mustahil dieksekusi | Agen mempublikasikan bukti inferensi AI; smart contract mengeksekusi aksi finansial |

Mengapa ini penting? Pada sistem agen cerdas dan enterprise finance, verifikasi eksekusi logika tidak boleh bergantung pada asumsi "server terpercaya", dan pada saat yang sama dilarang membocorkan data kepemilikan intelektual atau data transaksi privat ke ruang publik blockchain.

---

### 5. How (Workflow Detail)

Alur kerja operasional sistem produksi terdiri dari fase *Design-time*, *Setup-time*, dan *Runtime*:

```
1. SIKLUS HIDUP DESAIN SIRKUIT & SETUP
   [Circuit Code (.circom)] 
          |
          v (circom compiler)
   [R1CS Representation] + [C++ / Wasm Witness Generator]
          |
          v (snarkjs powers-of-tau / perpetual tau)
   [Universal Setup (Phase 1)] 
          |
          v (circuit-specific contribution)
   [Circuit Proving Key (zkey)] + [Verification Key (vkey / Solidity)]

2. SIKLUS RUNTIME EKSEKUSI & VERIFIKASI
   [Client/Agent Node]
          |-- a. Input Sensitif (Private Witness) + Kondisi Sistem (Public Input)
          |-- b. Eksekusi Witness Generator -> Menghasilkan file .wtns
          |-- c. Prover Core (GPU/CPU) mengeksekusi MSM + NTT menggunakan Proving Key
          v
   [Tersusun Proof (pi_A, pi_B, pi_C) + Public Signals]
          |
          v (Kirim Transaksi EVM: verifier.verifyProof(proof, publicSignals))
   [EVM Smart Contract Engine]
          |-- Validasi format dan titik kurva eliptik
          |-- Eksekusi Precompiled Contract Alt_bn128 Pairing (0x08)
          v
   [State Transisi Berhasil Diotorisasi]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah **Gudang Brankas Otonom**.
- **Pelanggan (Prover)** ingin membuktikan bahwa ia mengetahui kode kombinasi 128-digit yang jika dimasukkan ke sistem brankas akan menghasilkan checksum tertentu, tanpa pernah menyebutkan satupun digit kode tersebut kepada penjaga.
- **Sirkuit (Circuit)** adalah skema mekanis brankas yang diubah menjadi serangkaian roda gigi matematika interlocking.
- **Proving Key** adalah bayangan proyeksi matematis dari semua roda gigi tersebut.
- **Proof** adalah sebuah koin logam cetakan tipis hasil interaksi kode rahasia dengan roda gigi.
- **Penjaga Brankas (Verifier Contract)** hanya memegang sebuah cetakan pembanding (*Verification Key*). Ia cukup memasukkan koin tipis itu ke cetakannya: jika pas secara presisi mikroskopis (*pairing operation* bernilai identitas), pintu terbuka seketika. Penjaga tidak tahu dan tidak perlu tahu bagaimana kombinasi angka awal disusun.

```
       WITNESS GENERATION                  PROVER PIPELINE                     ON-CHAIN VERIFIER
   
   +----------------------+
   | Private: Secret Key  |
   | Public: Merkle Root  |
   +----------+-----------+
              |
              v
     [ Circuit Gates ]
      x * (x + 5) == y 
              |
              v
   +----------------------+           +----------------------+            +-----------------------+
   |  Vector Witness (w)  | --------> |  MSM (Linear G1/G2)  | ---------> | EVM alt_bn128         |
   |  [1, pub, priv...]   |           |  NTT (Polinomial H)  |            | Precompile 0x08 Check |
   +----------------------+           +----------+-----------+            +-----------+-----------+
                                                 |                                    |
                                                 v                                    v
                                       Proof = (A, B, C)                     Valid ? State Execution
                                                                                   : Revert()
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi sistem produksi autentikasi dan transfer saldo privat berbasis hash Poseidon dan pembuktian Groth16.

#### 7.1 Sirkuit Circom: Pembuktian Kepemilikan Saldo Tanpa Membocorkan Identitas (`PrivateBalanceProof.circom`)

```circom
pragma circom 2.1.6;

include "circomlib/circuits/poseidon.circom";
include "circomlib/circuits/comparators.circom";

// Sirkuit untuk membuktikan:
// 1. Prover mengetahui secretKey yang menghasilkan commitHash tertentu.
// 2. Prover memiliki saldo privat >= transferAmount.
// 3. Prover menghitung state commitment baru secara deterministik.
template PrivateBalanceProof() {
    // --- PUBLIC SIGNALS ---
    signal input currentCommitment;
    signal input transferAmount;
    signal input newCommitment;

    // --- PRIVATE SIGNALS ---
    signal input secretKey;
    signal input currentBalance;
    signal input newSecretKey;

    // 1. Validasi kepemilikan commitment lama
    component currentHasher = Poseidon(2);
    currentHasher.inputs[0] <== secretKey;
    currentHasher.inputs[1] <== currentBalance;
    currentHasher.out === currentCommitment;

    // 2. Validasi kelayakan saldo (currentBalance >= transferAmount)
    // Menggunakan pembanding 64-bit untuk menghindari integer overflow
    component comp = GreaterEqThan(64);
    comp.in[0] <== currentBalance;
    comp.in[1] <== transferAmount;
    comp.out === 1;

    // 3. Menghitung saldo baru dan memvalidasi newCommitment
    signal calculatedNewBalance;
    calculatedNewBalance <== currentBalance - transferAmount;

    component newHasher = Poseidon(2);
    newHasher.inputs[0] <== newSecretKey;
    newHasher.inputs[1] <== calculatedNewBalance;
    newHasher.out === newCommitment;
}

component main {public [currentCommitment, transferAmount, newCommitment]} = PrivateBalanceProof();
```

#### 7.2 Implementasi Engine Prover Gnark (Go)
Jika sistem membutuhkan performa throughput tinggi (microservice prover), implementasi langsung pada bahasa sistem seperti Go via Gnark jauh lebih unggul dibanding Javascript.

```go
package main

import (
	"bytes"
	"fmt"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/frontend/cs/r1cs"
)

// Circuit mendefinisikan relasi: Y == X^3 + X + 5
type CubicCircuit struct {
	X frontend.Variable `gnark:",secret"`
	Y frontend.Variable `gnark:",public"`
}

func (circuit *CubicCircuit) Define(api frontend.API) error {
	x3 := api.Mul(circuit.X, circuit.X, circuit.X)
	res := api.Add(x3, circuit.X, 5)
	api.AssertIsEqual(circuit.Y, res)
	return nil
}

func main() {
	var myCircuit CubicCircuit
	r1cs, err := frontend.Compile(ecc.BN254.ScalarField(), r1cs.NewBuilder, &myCircuit)
	if err != nil {
		panic(fmt.Sprintf("Kompilasi R1CS gagal: %v", err))
	}

	pk, vk, err := groth16.Setup(r1cs)
	if err != nil {
		panic(fmt.Sprintf("Setup gagal: %v", err))
	}

	// Witness: X = 3, Y = 3^3 + 3 + 5 = 35
	assignment := CubicCircuit{
		X: 3,
		Y: 35,
	}

	witness, err := frontend.NewWitness(&assignment, ecc.BN254.ScalarField())
	if err != nil {
		panic(err)
	}

	publicWitness, err := witness.Public()
	if err != nil {
		panic(err)
	}

	// Generate Groth16 Proof
	proof, err := groth16.Prove(r1cs, pk, witness)
	if err != nil {
		panic(fmt.Sprintf("Gagal membangkitkan proof: %v", err))
	}

	// Verifikasi Proof
	err = groth16.Verify(proof, vk, publicWitness)
	if err != nil {
		panic("Verifikasi gagal: Proof tidak valid!")
	}

	fmt.Println("Proof berhasil diverifikasi secara kriptografis.")

	// Ekspor Verifier Key ke format Solidity
	var buf bytes.Buffer
	err = vk.ExportSolidity(&buf)
	if err != nil {
		panic("Gagal ekspor smart contract verifier")
	}
	fmt.Printf("Solidity Verifier Contract di-generate (%d bytes)\n", buf.Len())
}
```

#### 7.3 Smart Contract Verifikator EVM Teroptimasi (`ZKBalanceVerifier.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface ICircomVerifier {
    function verifyProof(
        uint[2] calldata a,
        uint[2][2] calldata b,
        uint[2] calldata c,
        uint[3] calldata input
    ) external view returns (bool r);
}

contract ZKBalanceManager {
    ICircomVerifier public immutable verifier;
    bytes32 public currentRootCommitment;

    // Mencegah replay attack dengan proof nullifier
    mapping(bytes32 => bool) public nullifiedCommitments;

    event BalanceTransferred(bytes32 indexed oldCommitment, bytes32 indexed newCommitment, uint256 amount);

    error InvalidProof();
    error CommitmentAlreadySpent();

    constructor(address _verifierAddress, bytes32 _initialCommitment) {
        verifier = ICircomVerifier(_verifierAddress);
        currentRootCommitment = _initialCommitment;
    }

    function transferPrivate(
        uint[2] calldata a,
        uint[2][2] calldata b,
        uint[2] calldata c,
        bytes32 oldCommitment,
        uint256 transferAmount,
        bytes32 newCommitment
    ) external {
        if (nullifiedCommitments[oldCommitment]) {
            revert CommitmentAlreadySpent();
        }

        // Susun public signals sesuai urutan deklarasi di sirkuit Circom:
        // [currentCommitment, transferAmount, newCommitment]
        uint[3] memory publicSignals = [
            uint256(oldCommitment),
            transferAmount,
            uint256(newCommitment)
        ];

        // Eksekusi verifikasi via alt_bn128 pairing precompile
        bool isValid = verifier.verifyProof(a, b, c, publicSignals);
        if (!isValid) {
            revert InvalidProof();
        }

        // Tandai komitmen lama telah digunakan
        nullifiedCommitments[oldCommitment] = true;
        currentRootCommitment = newCommitment;

        emit BalanceTransferred(oldCommitment, newCommitment, transferAmount);
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Eksekusi Agen AI Finansial Terdesentralisasi (ZK-Credit Layer)
- **Konteks**: Konsorsium perbankan multinasional mengizinkan agen AI otonom melakukan pemeringkatan kredit UKM dan eksekusi pencairan pinjaman langsung di atas *private EVM rollup*, tanpa pernah membuka data neraca internal UKM kepada publik validator.
- **Beban Kerja**: 100.000 evaluasi kredit per hari, throughput puncak 80 evaluasi/detik.
- **Arsitektur Produksi**:

```
+-------------------------------------------------------------------------------+
| UKM Local Enclave / Secure Runner                                             |
|  1. Eksekusi Model XGBoost (Model Parameters dipublikasikan via KZG commit)   |
|  2. Generate Saksi: Data Neraca Keuangan (Private) -> Score (Private)         |
|  3. Sirkuit: Inferensi Matriks + Validasi Ambang Batas Skor Kredit            |
+------------------------------------+------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------------+
| Distributed Prover Farm (Kubernetes + NVIDIA A100 Tensor Core GPUs)           |
|  - Ingestion via gRPC stream                                                  |
|  - Engine: C++ accelerated Lock-free MSM & NTT (cuZK / ICICLE)                |
|  - Latensi Proof Generation: 1.8 detik per transaksi                          |
|  - Recursive Folding: 64 proof individual dibundel menjadi 1 STARK/Groth16    |
|    Proof menggunakan skema Halo2/Nova aggregation                             |
+------------------------------------+------------------------------------------+
                                     | Single Aggregated Proof (1.2 KB)
                                     v
+-------------------------------------------------------------------------------+
| On-Chain Settlement (L2 EVM Engine)                                           |
|  - 1 Transaksi Verifikasi Kontrak pintar per batch (320,000 gas flat)         |
|  - Gas Cost per UKM: 320,000 / 64 = 5,000 gas (Super ekonomis)                |
|  - Smart contract langsung mencairkan stablecoin pool jika proof verified      |
+-------------------------------------------------------------------------------+
```

---

### 9. Trade-offs

| Parameter | Groth16 | PLONK (KZG) | STARK (FRI) |
| :--- | :--- | :--- | :--- |
| **Ukuran Bukti (Proof Size)** | **~130-200 bytes** (Terkecil, konstan $\mathcal{O}(1)$) | ~400-800 bytes (Sangat ringkas) | ~40-100 KB (Besar, mahal untuk calldata L1 EVM) |
| **Biaya Verifikasi On-Chain** | **Sangat Murah** (~200k gas, 3-4 bilinear pairings) | Murah (~300k gas) | Sangat Mahal jika native (~1-2M gas untuk verifikasi Merkle/FRI) |
| **Kecepatan Prover** | Cepat (Hanya butuh komputasi $\mathbb{G}_1$ dan $\mathbb{G}_2$) | Menengah (Banyak komputasi quotient polynomial) | **Paling Cepat** (Tanpa kurva eliptik, hanya NTT & Hash) |
| **Trusted Setup Requirement** | **Toxic Waste Spesifik Sirkuit**: Harus run setup ceremony untuk SETIAP perubahan sirkuit | **Universal & Updatable**: Setup sekali untuk semua sirkuit hingga bound tertentu | **Transparent**: Tidak butuh Trusted Setup sama sekali |
| **Ketahanan Pasca-Kuantum** | Rentan (Didasarkan pada Discrete Logarithm problem) | Rentan (Didasarkan pada DLP) | **Tahan Pasca-Kuantum** (Hanya berbasis fungsi hash resistan-kolisi) |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Under-constrained Circuit (Bug Terbesar dalam ZK)
- **Kesalahan Fatal**: Menggunakan operator assignment biasa `<--` alih-alih constraint equality `<==` atau `===` di Circom.
  ```circom
  // CACAT FATAL: Hanya menghitung witness, TIDAK MEMBATASI sirkuit!
  // Prover jahat dapat memalsukan sinyal 'out' dengan nilai apapun!
  out <-- in[0] * in[1];
  ```
- **Solusi**: Selalu tegakkan constraint eksplisit.
  ```circom
  out <-- in[0] * in[1];
  out === in[0] * in[1]; // Batasan R1CS dipaksa
  // Atau lebih baik langsung:
  out <== in[0] * in[1];
  ```

#### 10.2 Field Wraparound / Arithmetic Overflow
- **Kesalahan**: Asumsi bahwa pengurangan integer `a - b` akan otomatis negatif jika `b > a`.
- **Gejala Masalah**: Di $\mathbb{F}_p$, jika $a=3$ dan $b=5$, maka $3 - 5 \equiv p - 2 \pmod p$. Hasilnya adalah angka yang luar biasa besar mendekati nilai skalar kurva (misal: $\approx 2.18 \times 10^{77}$ pada BN254). Jika nilai ini dimasukkan ke gerbang pembanding tanpa pengecekan bit-width (misal `Num2Bits(64)`), sirkuit akan menganggap nilai tersebut valid sebagai angka positif raksasa.
- **Solusi**: Selalu paksa *range checking* ketat pada setiap operasi aritmetika bertanda atau pengurangan dengan komponen `CompConstant` atau `Num2Bits`.

#### 10.3 Proof Malleability pada Verifier On-Chain
- **Kesalahan**: Membiarkan input publik atau elemen kurva eliptik dimodifikasi tanpa pembatalan proof. Kurva BN254 memiliki sifat simetri di mana $(x, y)$ dan $(x, -y)$ valid secara projective coordinates jika verifier tidak mengecek apakah koordinat titik berada tepat di subgrup $\mathbb{G}_1$ dan di dalam rentang modulo $p$.
- **Solusi**: Pastikan verifikasi EVM menerapkan pemeriksaan rentang tegas:
  ```solidity
  uint256 constant FIELD_ORDER = 21888242871839275222246405745257275088548364400416034343698204186575808495617;
  require(publicSignals[i] < FIELD_ORDER, "Public signal out of field bounds");
  ```

---

### 11. Best Practices (Production Checklist)

1. **Formal Circuit Auditing**:
   - Jalankan penganalisis statis seperti `Circomspect` atau `Ecne` untuk mendeteksi *unconstrained signals*.
   - Verifikasi manual: Pastikan jumlah sinyal independen sama dengan jumlah batasan derajat 1 R1CS non-trivial.
2. **Proving Infrastructure Ops**:
   - Gunakan memori server bertipe *high-memory allocation* (minimal 64 GB RAM untuk sirkuit dengan $>2^{20}$ gerbang).
   - Simpan file `.zkey` di memori terpetakan (*mmap*) NVMe ultra-cepat untuk mengurangi *I/O serialization bottlenecks*.
3. **Smart Contract Hardening**:
   - Terapkan mekanisme *Nullifier Tree* untuk mencegah eksekusi ganda (*double-spend*) dari bukti ZK yang sama.
   - Jangan pernah menyematkan *Verification Key* di storage yang dapat diubah tanpa mekanisme *timelock governance* yang ketat.
4. **Hardware Acceleration**:
   - Kompilasi modul witness ke C++ asli (`circom --c`) daripada WebAssembly untuk beban komputasi server backend.
   - Manfaatkan instruksi multithreading OpenMP saat melakukan interpolasi polinomial skala besar.

---

### 12. Hands-on Practice

Siapkan struktur direktori:
```bash
mkdir -p hands-on/m02/circuits hands-on/m02/contracts hands-on/m02/scripts
cd hands-on/m02
npm init -y
npm install --save-dev snarkjs@latest circomlib@latest hardhat ethers
```

#### Langkah 1: Tulis Sirkuit Pembuktian Hash Pre-Image (`circuits/PreimageVerifier.circom`)
```circom
pragma circom 2.1.6;

include "../node_modules/circomlib/circuits/poseidon.circom";

template PreimageVerifier() {
    signal input preimage;
    signal input hash;

    component hasher = Poseidon(1);
    hasher.inputs[0] <== preimage;
    
    // Constraint: hash yang diinput publik HARUS sama persis dengan Poseidon(preimage)
    hasher.out === hash;
}

component main {public [hash]} = PreimageVerifier();
```

#### Langkah 2: Kompilasi dan Jalankan Trusted Setup Lokal
```bash
# 1. Kompilasi Sirkuit ke format R1CS & Wasm
circom circuits/PreimageVerifier.circom --r1cs --wasm --sym -o circuits/

# 2. Inisialisasi Ceremony Powers of Tau (Hermez multi-party ceremony simulasi lokal)
snarkjs powersoftau new bn128 12 circuits/pot12_0000.ptau -v
snarkjs powersoftau contribute circuits/pot12_0000.ptau circuits/pot12_0001.ptau --name="First Contribution" -v -e="some random text"
snarkjs powersoftau prepare phase2 circuits/pot12_0001.ptau circuits/pot12_final.ptau -v

# 3. Setup Groth16 spesifik untuk sirkuit
snarkjs groth16 setup circuits/PreimageVerifier.r1cs circuits/pot12_final.ptau circuits/circuit_0000.zkey
snarkjs zkey contribute circuits/circuit_0000.zkey circuits/circuit_final.zkey --name="Second Contributor" -v -e="entropy seed"
snarkjs zkey export verification_key circuits/circuit_final.zkey circuits/verification_key.json

# 4. Generate Solidity Verifier Contract
snarkjs zkey export solidityverifier circuits/circuit_final.zkey contracts/Verifier.sol
```

#### Langkah 3: Eksekusi Prover Ujung-ke-Ujung (`scripts/executeProof.js`)
```javascript
const fs = require("fs");
const snarkjs = require("snarkjs");
const { buildPoseidon } = require("circomlibjs");

async function run() {
    const poseidon = await buildPoseidon();
    
    // Tentukan nilai rahasia (preimage)
    const secretPreimage = 1337n;
    // Hitung hash Poseidon (Representasi skalar kurva eliptik)
    const hash = poseidon([secretPreimage]);
    const hashStr = poseidon.F.toString(hash);

    console.log("Secret Preimage:", secretPreimage.toString());
    console.log("Calculated Poseidon Hash (Public):", hashStr);

    const inputData = {
        preimage: secretPreimage.toString(),
        hash: hashStr
    };

    // Panggil SnarkJS untuk generate proof dan menghitung witness secara serentak
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(
        inputData,
        "circuits/PreimageVerifier_js/PreimageVerifier.wasm",
        "circuits/circuit_final.zkey"
    );

    console.log("Proof successfully generated!");
    console.log("Public Signal Output:", publicSignals);

    // Verifikasi bukti di sisi off-chain sebelum dipancarkan ke on-chain
    const vKey = JSON.parse(fs.readFileSync("circuits/verification_key.json"));
    const isValid = await snarkjs.groth16.verify(vKey, publicSignals, proof);
    console.log("Off-chain Verification Result:", isValid);

    // Format calldata untuk eksekusi kontrak pintar Solidity
    const calldata = await snarkjs.groth16.exportSolidityCallData(proof, publicSignals);
    console.log("\nCopy-Paste Calldata berikut ke fungsi verifyProof() di Verifier.sol:");
    console.log(calldata);
}

run().then(() => process.exit(0)).catch(console.error);
```

Jalankan script:
```bash
node scripts/executeProof.js
```

---

### 13. Exercises

#### Level Easy
Kompilasi sebuah sirkuit yang membuktikan bahwa Anda mengetahui dua bilangan skalar $A$ dan $B$ sedemikian rupa sehingga $A + B = 100$ tanpa membocorkan nilai $A$ dan $B$.
- **Kriteria Keberhasilan**: Sirkuit Circom meng-output public signal konstan `100`, dan menghasilkan proof yang dapat diverifikasi oleh snarkjs.

#### Level Medium
Buat sirkuit verifikasi *Merkle Tree Inclusion Proof* untuk kedalaman pohon (*depth*) = 4 menggunakan fungsi hash `Poseidon(2)`.
- Input privat: `leaf`, `pathElements[4]`, `pathIndices[4]`.
- Input publik: `expectedMerkleRoot`.
- **Kriteria Keberhasilan**: Sirkuit berhasil merekonstruksi root dari bawah ke atas dan memvalidasi kecocokan dengan `expectedMerkleRoot`. Jika index salah, pembuktian gagal (*constraint failed*).

#### Level Hard
Rancang sirkuit otentikasi signature EdDSA di atas kurva BabyJubjub menggunakan Circom (`circomlib/circuits/eddsaposeidon.circom`).
- Buat microservice menggunakan Node.js/Go yang menandatangani instruksi transaksi Agen AI, kemudian Agen membuktikan on-chain bahwa instruksi tersebut ditandatangani oleh Master Public Key tanpa membocorkan Public Key itu sendiri (hanya membuktikan Public Key tersebut terdaftar di dalam Merkle Set of Authorized Agents).
- **Kriteria Keberhasilan**: Gas penggunaan pada verifikasi on-chain tidak melebihi 280.000 gas.

---

### 14. Challenge

**Tantangan Sistem Terdistribusi: Fault-Tolerant Decentralized Prover Pool**

Rancang dan bangun arsitektur *Decentralized Prover Network* berskala produksi untuk memproses antrean transaksi ZK-Rollup berlatensi rendah:
1. **Spesifikasi Masalah**: Klien mengirimkan *witness assignments* ke sistem antrean terdistribusi (misal: Apache Kafka / RabbitMQ). Beban kerja harus didistribusikan ke minimal 3 *worker node* prover yang memiliki akselerasi perangkat keras independen.
2. **Kebutuhan Teknis**:
   - Jika satu node prover mengalami *Out of Memory* (OOM) atau crash saat menghitung MSM/NTT, antrean harus otomatis dialihkan ke node lain (*automatic failover*) tanpa menimbulkan *duplicate proof delivery*.
   - Node Prover wajib membungkus bukti ke format serialisasi biner terkompresi yang siap dikonsumsi transaksi EVM.
   - Terapkan mekanisme komitmen kriptografis *Proof-of-Authority Prover* agar validator smart contract dapat memverifikasi bahwa bukti действительно dikerjakan oleh node yang memiliki lisensi perangkat keras terdaftar.
3. **Deliverables Arsitektur**:
   - Diagram arsitektur subsistem worker.
   - Skrip orkestrator pipeline pemrosesan paralel bukti.
   - Desain penanganan *state race condition* ketika beberapa transaksi saling bergantung (*dependent state updates*).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa peran *vanishing polynomial* $Z(X)$ dalam aritmetisasi Quadratic Arithmetic Program (QAP)?
   - *Jawaban*: $Z(X)$ adalah polinomial pembagi yang memiliki akar pada setiap titik evaluasi gerbang batasan. Polinomial target $P(X)$ harus habis dibagi oleh $Z(X)$ jika dan hanya jika seluruh batasan R1CS sirkuit terpenuhi secara valid oleh witness.
2. Mengapa fungsi hash konvensional seperti SHA-256 atau Keccak-256 sangat tidak efisien jika diimplementasikan di dalam sirkuit ZK?
   - *Jawaban*: Karena SHA-256 dan Keccak-256 dirancang untuk komputasi perangkat keras berbasis bitwise operations (AND, XOR, bit rotations). Operasi non-linear bitwise ini membutuhkan ribuan batasan R1CS per putaran (round), sedangkan hash ramah-ZK (seperti Poseidon) beroperasi langsung pada aritmetika medan hingga ($\mathbb{F}_p$) yang hanya membutuhkan puluhan batasan per permutasi.
3. Apa perbedaan fundamental antara fasa Setup *Powers-of-Tau* (Phase 1) dan *Circuit-Specific Setup* (Phase 2) pada protokol Groth16?
   - *Jawaban*: Phase 1 bersifat universal dan dapat digunakan kembali oleh sirkuit apapun hingga kapasitas batasan tertentu. Phase 2 bersifat terikat ketat (*circuit-specific*) pada struktur matriks R1CS sirkuit yang bersangkutan; jika kode sirkuit berubah sedikit saja, Phase 2 harus dijalankan ulang.
4. Apa yang dimaksud dengan operasi *Multi-Scalar Multiplication* (MSM)?
   - *Jawaban*: MSM adalah komputasi perkalian titik kurva eliptik skalar besar dengan bentuk $\sum_{i=1}^n s_i P_i$, di mana $s_i$ adalah elemen skalar medan dan $P_i$ adalah titik-titik pada kurva eliptik generator grup.
5. Apa konsekuensi keamanan jika parameter acak rahasia (*toxic waste* $\tau, \alpha, \beta, \gamma, \delta$) dalam trusted setup Groth16 bocor ke publik?
   - *Jawaban*: Pihak yang memegang rahasia tersebut dapat memalsukan bukti ZK palsu (*fake proofs*) untuk pernyataan yang salah secara matematis tanpa terdeteksi oleh verifier, yang berakibat fatal pada keamanan dana/status sistem.

#### Intermediate (5 Pertanyaan)
6. Mengapa sirkuit dengan baris kode `signal x; x <-- a * b;` tanpa constraint kesetaraan berbahaya bagi integritas smart contract?
   - *Jawaban*: Operator `<--` hanya menghitung nilai untuk dimasukkan ke dalam witness runtime lokal (komputasi witness), namun tidak mendaftarkan batasan apapun ke sistem matriks R1CS. Akibatnya, prover jahat dapat mengisi nilai $x$ dengan angka acak tanpa membatalkan keabsahan bukti secara matematis (*under-constrained system*).
7. Bagaimana skema polynomial commitment KZG memungkinkan verifikasi instan $\mathcal{O}(1)$ independen dari derajat polinomial?
   - *Jawaban*: Melalui sifat homomorfik evaluasi kurva eliptik terpasang (*bilinear pairing*). Verifier cukup memeriksa satu pembuktian evaluasi pada titik evaluasi acak rahasia $r$ menggunakan satu operasi *bilinear pairing check* $e(C - [v]_1, [1]_2) == e([\pi]_1, [x - r]_2)$.
8. Apa kelemahan utama skema STARK jika dibandingkan dengan Groth16 dalam implementasi L1 Ethereum rollups?
   - *Jawaban*: Ukuran bukti (proof size) STARK berkisar puluhan hingga ratusan kilobyte (berbasis FRI/Merkle path), yang menghasilkan biaya gas sangat mahal saat dipublikasikan sebagai `calldata` ke L1 Ethereum, dibandingkan bukti Groth16 yang hanya berukuran ratusan byte.
9. Apa fungsi *Nullifier* dalam arsitektur privasi transaksi keuangan seperti Tornado Cash atau Zcash?
   - *Jawaban*: Nullifier bertindak sebagai penanda deterministik unik satu arah yang diturunkan dari secret note. Nullifier dipublikasikan saat pembelanjaan untuk mencegah pembelanjaan ganda (*double-spending*) tanpa mengungkap kaitan langsung ke komitmen (*commitment*) saldo awal.
10. Bagaimana teknik *Recursive Proofs* (misal: Nova, Halo2) mengatasi limitasi kapasitas memori hardware prover?
    - *Jawaban*: Dengan membuktikan validitas dari satu atau lebih bukti ZK sebelumnya di dalam sebuah sirkuit pembuktian baru. Ini memadatkan rangkaian rantai komputasi panjang menjadi satu bukti ringkas akhir (*folding schemes*), menghilangkan kebutuhan memuat seluruh riwayat komputasi ke dalam RAM sekaligus.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: Tim Anda merilis sirkuit identitas anonim. Di testnet lokal verifikasi smart contract selalu sukses, namun saat di-deploy ke Sepolia testnet, transaksi verifikasi selalu *revert* dengan pesan `execution reverted` pada instruksi precompile `0x08`. Analisis apa akar masalahnya dan langkah perbaikannya!
    - *Solusi Root Cause*: Parameter koordinat eliptik pada proof (`pi_A`, `pi_B`, `pi_C`) atau sinyal input publik tidak dikonversi ke format modulo skalar yang sesuai dengan kurva Alt-bn128 EVM ($p = 21888242871839275222246405745257275088548364400416034343698204186575808495617$). Nilai input calldata melebihi modulo medan ($x \ge p$), sehingga *precompiled contract alt_bn128 pairing check* menganggap koordinat bukan elemen subgrup yang sah dan secara otomatis mengembalikan status *invalid* atau *OOG/revert*. Lakukan sanitasi data pada script frontend/backend dengan `BigInt(x) % FIELD_MODULUS`.

12. **Skenario 2**: Sebuah Agen AI menghasilkan bukti ZK untuk transaksi arbitrase DeFi. Namun, setiap kali transaksi di-broadcast ke public mempool Ethereum, transaksi tersebut gagal karena terdeteksi *front-run* oleh bot MEV yang mengirim ulang argumen proof yang sama persis namun mengubah alamat penerima dana keuntungan arbitrase. Bagaimana cara merestrukturisasi sirkuit untuk memitigasi serangan ini secara mutlak?
    - *Solusi Root Cause*: Proof mengalami celah *malleability context*. Alamat penerima keuntungan (*recipient address*) berada di luar jangkauan validasi sirkuit ZK. 
    - *Perbaikan*: Masukkan variabel `recipientAddress` (misal address ethereum `msg.sender`) ke dalam sinyal sirkuit sebagai **Public Input**. Di dalam sirkuit, buat batasan *dummy constraint* (misal: `signal input recipient; signal dummy; dummy <== recipient * recipient;`). Dengan cara ini, jika penyerang bot MEV mencoba mengganti parameter alamat penerima pada transaksi, verifikasi *bilinear pairing* smart contract akan otomatis gagal total karena public input yang terikat pada proof tidak lagi cocok.

13. **Skenario 3**: Node Prover server enterprise Anda sering mengalami lonjakan alokasi memori (*OOM Crash*) ketika sirkuit memiliki lebih dari $2^{22}$ batasan constraints, terutama pada fasa perhitungan polinomial quotient. Strategi optimasi infrastruktur dan algoritma apa yang harus diterapkan?
    - *Solusi Root Cause*: Operasi Inverse NTT (iNTT) dan perkalian polinomial pada $2^{22}$ batasan membutuhkan alokasi memori berkesinambungan yang sangat besar jika seluruh koefisien ditampung secara in-memory.
    - *Perbaikan*: 
      1. Terapkan implementasi *Out-of-Core NTT* di mana polinomial dipecah menjadi sub-blok dan dialirkan (*streamed*) ke/dari NVMe SSD menggunakan memory mapping (`mmap`).
      2. Migrasi komputasi MSM ke pustaka akselerasi GPU (seperti *cuZK* atau *ICICLE*) yang memanfaatkan memori VRAM GPU berkecepatan tinggi dengan pipeline *pipelined chunk execution*.
      3. Ubah arsitektur sirkuit tunggal monolitik menjadi arsitektur modular terfragmentasi menggunakan skema agregasi bukti *Halo2/Plonky2* atau *Nova IVC (Incrementally Verifiable Computation)*.

---

### 16. Summary

Modul ini telah membedah anatomi sistem *Zero-Knowledge* tingkat produksi dari lapisan matematis paling dasar hingga eksekusi on-chain:
- **Aritmetisasi**: Komputasi diubah menjadi batasan aljabar menggunakan format R1CS atau PlonKish gates, yang kemudian diinterpolasi menjadi persamaan polinomial derajat tinggi (QAP).
- **Komputasi Berat Prover**: Fase pembuktian didominasi oleh operasi Number Theoretic Transform (NTT) untuk manipulasi polinomial dan Multi-Scalar Multiplication (MSM) pada kurva eliptik.
- **Verifikasi Ringkas (Succinct)**: Groth16 dan PLONK mereduksi verifikasi komputasi masif menjadi sekadar evaluasi operasi *bilinear pairing* $\mathcal{O}(1)$ yang sangat hemat gas di dalam mesin virtual EVM.
- **Keamanan Sistem ZK**: Bahaya paling kritis pada implementasi ZK bukan terletak pada algoritma kurva eliptiknya, melainkan pada kode logika sirkuit yang kurang batasan (*under-constrained*) serta kegagalan mengikat konteks transaksi (*public signals binding*) pada smart contract verifier. Implementasi enterprise menuntut *formal verification*, akselerasi perangkat keras terdistribusi, dan desain sirkuit yang modular.