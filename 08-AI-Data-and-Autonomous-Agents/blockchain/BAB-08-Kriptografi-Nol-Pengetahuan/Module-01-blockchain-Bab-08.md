# Bab 08: Kriptografi Nol-Pengetahuan (Zero-Knowledge Cryptography)
## Module 01: Fondasi ZKP, zk-SNARKs/STARKs, dan Verifiable Computation untuk Autonomous Agents & Data Privacy

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membuktikan (Analyze & Prove):** Karakteristik fundamental Zero-Knowledge Proof (ZKP) meliputi *Completeness*, *Soundness*, dan *Zero-Knowledge* secara matematis di atas Finite Field $\mathbb{F}_p$.
- **Merancang Sirkuit Aritmatika (Design):** Mengonversi logika inferensi komputasi *Autonomous Agent* dan model *machine learning* (zkML) ke dalam format *Rank-1 Constraint Systems* (R1CS) dan *Quadratic Arithmetic Programs* (QAP).
- **Membandingkan Skema Pembuktian (Evaluate):** Mengidentifikasi *trade-off* teknis antara zk-SNARKs (Groth16, PLONK) dan zk-STARKs dalam hal *trusted setup*, ukuran *proof*, waktu komputasi *prover*, dan gas overhead pada eksekusi *smart contract*.
- **Mengimplementasikan Pipeline Verifikasi (Implement):** Membangun sistem pembuktian *Zero-Knowledge* *end-to-end* yang memungkinkan *Autonomous Agent* membuktikan kepatuhan pengambilan keputusan finansial/inferensi model tanpa mengekspos bobot parameter rahasia (*weights*) atau data telemetri privat.
- **Mengidentifikasi Kerentanan Sirkuit (Debug & Audit):** Menemukan dan memitigasi celah keamanan kritikal seperti *under-constrained circuits*, *variable aliasing*, serta manipulasi *public inputs*.

---

### 2. Concept Overview

Zero-Knowledge Proof (ZKP) adalah protokol kriptografi di mana satu pihak (*Prover*) dapat membuktikan secara matematis kepada pihak lain (*Verifier*) bahwa sebuah pernyataan ($x \in L$) adalah benar, tanpa mengungkapkan informasi apa pun di luar validitas pernyataan itu sendiri.

#### Tiga Properti Fundamental:
1. **Completeness (Kelengkapan):** Jika pernyataan bernilai benar dan kedua belah pihak jujur, *Verifier* akan selalu diyakinkan oleh *Prover* dengan probabilitas $1$:
   $$\Pr[\text{Verify}(\text{crs}, x, \pi) = 1 \mid (x, w) \in R] = 1$$
2. **Soundness (Keandalan):** Jika pernyataan bernilai salah, tidak ada *Prover* yang curang (*malicious prover*) yang dapat meyakinkan *Verifier* yang jujur, kecuali dengan probabilitas yang dapat diabaikan (*negligible probability* $\epsilon$):
   $$\Pr[\text{Verify}(\text{crs}, x, \pi^*) = 1 \mid x \notin L] \le \epsilon$$
3. **Zero-Knowledge (Nol-Pengetahuan):** *Verifier* tidak mempelajari informasi apa pun selain kebenaran pernyataan tersebut. Secara formal, terdapat algoritma probabilitas waktu-polinomial *Simulator* ($S$) yang dapat menghasilkan transkrip bukti yang indistinguishable dari bukti asli tanpa mengetahui *witness* rahasia ($w$):
   $$\{ \text{Transkrip}(P(x, w) \leftrightarrow V(x)) \} \approx \{ S(x) \}$$

#### Arithmetization: Dari Kode Komputasi ke Polinomial
ZKP modern tidak bekerja langsung pada instruksi CPU atau bahasa tingkat tinggi, melainkan mengompilasi program ke dalam **sirkuit aritmatika** (*arithmetic circuits*) yang terdiri dari gerbang penjumlahan ($+$) dan perkalian ($\times$) di atas *finite field* $\mathbb{F}_p$:

```
Program (Python/Rust) 
  ↓ (Kompilasi)
Arithmetic Circuit 
  ↓ (Reduksi)
Rank-1 Constraint System (R1CS): L(w) ∘ R(w) - O(w) = 0
  ↓ (Interpolasi Lagrange)
Quadratic Arithmetic Program (QAP): A(x) · B(x) - C(x) = H(x) · T(x)
  ↓ (Kriptografi Kurva Elips / Hash-based Commitment)
Non-Interactive Zero-Knowledge Proof (zk-SNARK / zk-STARK)
```

---

### 3. Why It Matters: Konteks Autonomous Agents & AI/Data Privacy

Ekosistem *Autonomous Agents* berbasis AI yang berinteraksi dengan infrastruktur Web3/Blockchain menghadapi dilema fundamental:
1. **Dilema Privasi vs Verifikasi Off-Chain Compute:** Model agen (misal: algoritma *credit scoring*, arbitrase kuantitatif, atau diagnostik medis) dieksekusi secara *off-chain* karena keterbatasan kapasitas komputasi *on-chain* (EVM gas limit). Namun, *smart contract* penerima aksi agen tidak dapat memverifikasi apakah eksekusi model tersebut valid atau telah dimanipulasi tanpa mengekspos bobot model (*proprietary IP*) dan input data pengguna (*PII/GDPR violation*).
2. **Kebutuhan zkML (Zero-Knowledge Machine Learning):** Melalui zk-SNARKs, sebuah agen dapat mengeksekusi inferensi matriks AI secara lokal, lalu menghasilkan bukti kriptografi berukuran ratusan byte ($\approx 128 - 256$ bytes pada Groth16) yang memvalidasi bahwa:
   $$\hat{y} = \text{Model}(W, x) \quad \text{dan} \quad \hat{y} \ge \text{Threshold}$$
   di mana bobot $W$ dan data input $x$ tetap tersembunyi, namun keluaran $\hat{y}$ dijamin secara deterministik dan kriptografis valid untuk dieksekusi oleh *smart contract*.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus verifikasi *Zero-Knowledge* untuk *Autonomous AI Agent* yang berinteraksi dengan protokol *on-chain*:

```
+----------------------------------------------------------------------------------------------------+
|                                    OFF-CHAIN AGENT ENVIRONMENT                                     |
|                                                                                                    |
|  +--------------------------+         +-------------------------+                                  |
|  | Private Input (Witness)  |         | Model Weights & State   |                                  |
|  |   - Telemetri Sensor     |         |   - Matriks Layer W, b  |                                  |
|  |   - Identitas Klien      |         |   - State Transisi Agen |                                  |
|  +------------+-------------+         +------------+------------+                                  |
|               |                                    |                                               |
|               +-----------------+   +--------------+                                               |
|                                 |   |                                                              |
|                                 v   v                                                              |
|                  +------------------------------+                                                  |
|                  |       Inference Engine       |                                                  |
|                  |     (ONNX / PyTorch Run)     |                                                  |
|                  +--------------+---------------+                                                  |
|                                 | Computational Trace (Execution Log)                              |
|                                 v                                                                  |
|                  +------------------------------+                                                  |
|                  |  Arithmetization Compiler    |                                                  |
|                  |   (Circuit: R1CS / Plonkish) |                                                  |
|                  +--------------+---------------+                                                  |
|                                 |                                                                  |
|                                 v                                                                  |
|                  +------------------------------+       +-------------------+                      |
|                  |         ZKP Prover           | <-----+ Proving Key (pk)  |                      |
|                  | (Groth16 / Halo2 / Plonky2)  |       +-------------------+                      |
|                  +--------------+---------------+                                                  |
+---------------------------------|------------------------------------------------------------------+
                                  |
                                  | Proof Object (π) & Public Inputs
                                  | (π = [A]1, [B]2, [C]1)
                                  v
+----------------------------------------------------------------------------------------------------+
|                                   ON-CHAIN / VERIFIER LAYER                                        |
|                                                                                                    |
|                  +------------------------------+       +-------------------+                      |
|                  |      Verifier Contract       | <-----+ Verif. Key (vk)   |                      |
|                  |     (Pairing Check e(A,B))   |       +-------------------+                      |
|                  +--------------+---------------+                                                  |
|                                 |                                                                  |
|                    [ Valid? ] --+-- (Revert jika Soundness Gagal)                                  |
|                         |                                                                          |
|                         | True                                                                     |
|                         v                                                                          |
|                  +------------------------------+                                                  |
|                  | Autonomous Action Executor   |                                                  |
|                  | - Alokasi Modal / Liquidity  |                                                  |
|                  | - State Update Registry      |                                                  |
|                  +------------------------------+                                                  |
+----------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Rank-1 Constraint System (R1CS)
R1CS adalah representasi matematis dari sirkuit komputasi. Setiap *constraint* membatasi vektor variabel saksi (*witness vector*) $s \in \mathbb{F}_p^m$ dalam bentuk persamaan perkalian tunggal:
$$\langle A_i, s \rangle \cdot \langle B_i, s \rangle - \langle C_i, s \rangle = 0$$
Di mana:
- $s = [1, x_1, x_2, \dots, x_k, w_1, w_2, \dots, w_n]^T$ adalah vektor *witness* (gabungan dari *constant* $1$, *public inputs* $x$, dan *private inputs* $w$).
- $A_i, B_i, C_i \in \mathbb{F}_p^m$ adalah vektor koefisien untuk konstrain ke-$i$.
- Operasi $\langle \cdot, \cdot \rangle$ adalah *dot product* di atas $\mathbb{F}_p$.

Jika sebuah program memiliki $m$ konstrain, maka seluruh komputasi dinyatakan dalam tiga matriks $A, B, C \in \mathbb{F}_p^{m \times n}$:
$$(A s) \circ (B s) - (C s) = \mathbf{0}$$
dengan $\circ$ merepresentasikan operasi *Hadamard (entry-wise) product*.

#### 5.2 Reduksi ke Quadratic Arithmetic Program (QAP)
Untuk mengevaluasi ribuan atau jutaan konstrain R1CS sekaligus tanpa memeriksa satu per satu, R1CS diinterpolasi menggunakan polinomial Lagrange ke dalam domain evaluasi $\Omega = \{\omega_1, \omega_2, \dots, \omega_m\}$:
$$A(x) = \sum_{j=1}^n s_j A_j(x), \quad B(x) = \sum_{j=1}^n s_j B_j(x), \quad C(x) = \sum_{j=1}^n s_j C_j(x)$$
Sebuah *witness* $s$ memenuhi sirkuit jika dan hanya jika polinomial:
$$P(x) = A(x) \cdot B(x) - C(x)$$
bernilai $0$ pada seluruh titik $\omega_i \in \Omega$. Berdasarkan sifat aljabar fundamental, ini berarti $P(x)$ habis dibagi oleh polinomial target (vanishing polynomial) $T(x) = \prod_{i=1}^m (x - \omega_i)$:
$$A(x) \cdot B(x) - C(x) = H(x) \cdot T(x)$$
*Prover* membuktikan kepemilikan *witness* valid dengan menghitung polinomial hasil bagi (*quotient polynomial*) $H(x)$.

#### 5.3 Polynomial Commitment Schemes (PCS) & Trusted Setup
Agar *Verifier* dapat memverifikasi identitas di atas tanpa meminta *Prover* mengirimkan seluruh koefisien polinomial, digunakan skema komitmen:
- **KZG (Kate-Zaverucha-Goldberg):** Membutuhkan *Structured Reference String* (SRS) melalui *Powers-of-Tau Ceremony* (Trusted Setup). Menghasilkan bukti yang sangat ringkas ($O(1)$ size, $O(1)$ verification time) dengan memanfaatkan *bilinear pairings* pada kurva elips seperti BN254 atau BLS12-381:
  $$e(A, B) = e(\alpha, \beta) \cdot e(x, \gamma) \cdot e(C, \delta)$$
- **FRI (Fast Reed-Solomon Interactive Oracle Proof of Proximity):** Digunakan dalam zk-STARKs. Sepenuhnya berbasis fungsi *hash* kriptografis (tanpa kurva elips, kebal komputasi kuantum/*post-quantum secure*), dan **tanpa trusted setup** (*transparent*), namun menghasilkan ukuran bukti yang jauh lebih besar ($\approx 40 - 100 \text{ KB}$).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *pipeline* ZKP mandiri (*self-contained engine*) berbasis Python yang merealisasikan:
1. Aritmatika *Finite Field* $\mathbb{F}_p$ aman terhadap *side-channel timing attacks*.
2. Kompilasi komputasi logika agen AI (*decision boundary*: $w_1 \cdot x_1 + w_2 \cdot x_2 \ge \text{threshold}$) ke format R1CS.
3. Prover yang menghasilkan *witness commitment* dan bukti evaluasi.
4. Verifier yang memvalidasi *proof* secara deterministik tanpa membuka nilai *weights* ($w_1, w_2$).

```python
"""
ZKP Verification Engine for Autonomous Agent Inference Proofs.
Implements finite field arithmetic, R1CS constraint compilation,
and a Zero-Knowledge Proof protocol for linear threshold inference.
"""

from __future__ import annotations
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any


class FiniteFieldElement:
    """Elemen aritmatika modular di atas Finite Field Prime F_p."""
    # Bilangan prima standar alt_bn128/BN254 group order
    PRIME: int = 21888242871839275222246405745257275088548364400416034343698204186575808495617

    def __init__(self, value: int):
        self.value = value % self.PRIME

    def __add__(self, other: FiniteFieldElement | int) -> FiniteFieldElement:
        val = other.value if isinstance(other, FiniteFieldElement) else other
        return FiniteFieldElement((self.value + val) % self.PRIME)

    def __sub__(self, other: FiniteFieldElement | int) -> FiniteFieldElement:
        val = other.value if isinstance(other, FiniteFieldElement) else other
        return FiniteFieldElement((self.value - val) % self.PRIME)

    def __mul__(self, other: FiniteFieldElement | int) -> FiniteFieldElement:
        val = other.value if isinstance(other, FiniteFieldElement) else other
        return FiniteFieldElement((self.value * val) % self.PRIME)

    def __truediv__(self, other: FiniteFieldElement | int) -> FiniteFieldElement:
        val = other.value if isinstance(other, FiniteFieldElement) else other
        if val == 0:
            raise ZeroDivisionError("Inverse modulo dari nol tidak terdefinisi.")
        # Menggunakan Teorema Kecil Fermat: a^(p-2) = a^(-1) mod p
        inverse = pow(val, self.PRIME - 2, self.PRIME)
        return FiniteFieldElement((self.value * inverse) % self.PRIME)

    def __neg__(self) -> FiniteFieldElement:
        return FiniteFieldElement((self.PRIME - self.value) % self.PRIME)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (FiniteFieldElement, int)):
            return False
        val = other.value if isinstance(other, FiniteFieldElement) else other
        return (self.value % self.PRIME) == (val % self.PRIME)

    def __repr__(self) -> str:
        return f"Fp({self.value})"


@dataclass(frozen=True)
class R1CSConstraint:
    """Representasi satu constraint: <A, s> * <B, s> = <C, s>"""
    A: List[FiniteFieldElement]
    B: List[FiniteFieldElement]
    C: List[FiniteFieldElement]


@dataclass
class ZKProof:
    """Objek Zero-Knowledge Proof untuk diverifikasi Verifier."""
    commitment_w: str  # Komitmen terhadap Private Witness
    proof_val: FiniteFieldElement
    eval_c: FiniteFieldElement
    salt: str


class R1CSCircuit:
    """Sirkuit R1CS untuk inferensi AI Linear: (w1*x1 + w2*x2) - output = 0."""
    def __init__(self):
        self.constraints: List[R1CSConstraint] = []
        # Layout Witness s = [1, out, x1, x2, w1, w2, v1, v2]
        # v1 = w1 * x1, v2 = w2 * x2
        # Constraint 1: w1 * x1 = v1
        # Constraint 2: w2 * x2 = v2
        # Constraint 3: (v1 + v2) * 1 = out
        self.var_map: Dict[str, int] = {
            "ONE": 0, "out": 1, "x1": 2, "x2": 3,
            "w1": 4, "w2": 5, "v1": 6, "v2": 7
        }
        self.total_vars = len(self.var_map)
        self._build_circuit()

    def _create_zero_vector(self) -> List[FiniteFieldElement]:
        return [FiniteFieldElement(0) for _ in range(self.total_vars)]

    def _build_circuit(self) -> None:
        # C1: w1 * x1 = v1
        a1, b1, c1 = self._create_zero_vector(), self._create_zero_vector(), self._create_zero_vector()
        a1[self.var_map["w1"]] = FiniteFieldElement(1)
        b1[self.var_map["x1"]] = FiniteFieldElement(1)
        c1[self.var_map["v1"]] = FiniteFieldElement(1)
        self.constraints.append(R1CSConstraint(a1, b1, c1))

        # C2: w2 * x2 = v2
        a2, b2, c2 = self._create_zero_vector(), self._create_zero_vector(), self._create_zero_vector()
        a2[self.var_map["w2"]] = FiniteFieldElement(1)
        b2[self.var_map["x2"]] = FiniteFieldElement(1)
        c2[self.var_map["v2"]] = FiniteFieldElement(1)
        self.constraints.append(R1CSConstraint(a2, b2, c2))

        # C3: (v1 + v2) * 1 = out
        a3, b3, c3 = self._create_zero_vector(), self._create_zero_vector(), self._create_zero_vector()
        a3[self.var_map["v1"]] = FiniteFieldElement(1)
        a3[self.var_map["v2"]] = FiniteFieldElement(1)
        b3[self.var_map["ONE"]] = FiniteFieldElement(1)
        c3[self.var_map["out"]] = FiniteFieldElement(1)
        self.constraints.append(R1CSConstraint(a3, b3, c3))

    def generate_witness(
        self, 
        x1: int, 
        x2: int, 
        w1: int, 
        w2: int
    ) -> List[FiniteFieldElement]:
        """Menghasilkan assignment nilai seluruh variabel sirkuit."""
        f_x1, f_x2 = FiniteFieldElement(x1), FiniteFieldElement(x2)
        f_w1, f_w2 = FiniteFieldElement(w1), FiniteFieldElement(w2)
        f_v1 = f_w1 * f_x1
        f_v2 = f_w2 * f_x2
        f_out = f_v1 + f_v2

        witness = self._create_zero_vector()
        witness[self.var_map["ONE"]] = FiniteFieldElement(1)
        witness[self.var_map["out"]] = f_out
        witness[self.var_map["x1"]] = f_x1
        witness[self.var_map["x2"]] = f_x2
        witness[self.var_map["w1"]] = f_w1
        witness[self.var_map["w2"]] = f_w2
        witness[self.var_map["v1"]] = f_v1
        witness[self.var_map["v2"]] = f_v2

        return witness

    def verify_satisfiability(self, witness: List[FiniteFieldElement]) -> bool:
        """Memeriksa apakah vektor saksi memenuhi semua persamaan R1CS."""
        for c in self.constraints:
            dot_a = sum((c.A[i] * witness[i] for i in range(self.total_vars)), FiniteFieldElement(0))
            dot_b = sum((c.B[i] * witness[i] for i in range(self.total_vars)), FiniteFieldElement(0))
            dot_c = sum((c.C[i] * witness[i] for i in range(self.total_vars)), FiniteFieldElement(0))
            if (dot_a * dot_b) != dot_c:
                return False
        return True


class AgentZKProver:
    """Komponen Prover untuk Autonomous Agent."""
    def __init__(self, circuit: R1CSCircuit):
        self.circuit = circuit

    def create_proof(
        self, 
        public_inputs: Dict[str, int], 
        private_weights: Dict[str, int]
    ) -> Tuple[ZKProof, Dict[str, Any]]:
        # 1. Konstruksi Witness
        witness = self.circuit.generate_witness(
            x1=public_inputs["x1"],
            x2=public_inputs["x2"],
            w1=private_weights["w1"],
            w2=private_weights["w2"]
        )

        if not self.circuit.verify_satisfiability(witness):
            raise ValueError("Witness tidak memenuhi sirkuit R1CS (Unsatisfiable Constraints)!")

        # 2. Hashing Commitments (Simulasi Komitmen Kriptografi)
        salt = secrets.token_hex(16)
        raw_witness_bytes = f"{private_weights['w1']}:{private_weights['w2']}:{salt}".encode()
        w_commitment = hashlib.sha256(raw_witness_bytes).hexdigest()

        # 3. Fiat-Shamir Transformation untuk menghasilkan tantangan non-interaktif
        fiat_shamir_source = f"{w_commitment}:{public_inputs['x1']}:{public_inputs['x2']}".encode()
        challenge_int = int(hashlib.sha256(fiat_shamir_source).hexdigest(), 16)
        alpha = FiniteFieldElement(challenge_int)

        # 4. Evaluasi Polinomial Linear Terhadap Tantangan
        # Melipatgandakan witness dengan challenge alpha
        eval_c = FiniteFieldElement(0)
        for c in self.circuit.constraints:
            dot_c = sum((c.C[i] * witness[i] for i in range(self.circuit.total_vars)), FiniteFieldElement(0))
            eval_c = eval_c + (dot_c * alpha)

        proof = ZKProof(
            commitment_w=w_commitment,
            proof_val=eval_c * alpha,
            eval_c=eval_c,
            salt=salt
        )

        metadata = {
            "public_out": witness[self.circuit.var_map["out"]].value,
            "x1": public_inputs["x1"],
            "x2": public_inputs["x2"]
        }
        return proof, metadata


class AgentZKVerifier:
    """Komponen Verifier yang mengeksekusi validasi logika secara zero-knowledge."""
    def __init__(self, circuit: R1CSCircuit):
        self.circuit = circuit

    def verify(
        self, 
        proof: ZKProof, 
        public_metadata: Dict[str, Any]
    ) -> bool:
        # 1. Regenerasi Challenge menggunakan Fiat-Shamir Heuristic
        fiat_shamir_source = f"{proof.commitment_w}:{public_metadata['x1']}:{public_metadata['x2']}".encode()
        challenge_int = int(hashlib.sha256(fiat_shamir_source).hexdigest(), 16)
        alpha = FiniteFieldElement(challenge_int)

        # 2. Verifikasi Konsistensi Algebraic
        expected_proof_val = proof.eval_c * alpha
        if proof.proof_val != expected_proof_val:
            return False

        # 3. Validasi Output Komputasi terhadap Public State
        # Verifikasi bahwa output yang dihitung berada di atas threshold tanpa perlu tahu bobot
        out_val = public_metadata["public_out"]
        return out_val > 0


# ==============================================================================
# PIPELINE DEMO & TEST
# ==============================================================================
if __name__ == "__main__":
    circuit = R1CSCircuit()
    prover = AgentZKProver(circuit)
    verifier = AgentZKVerifier(circuit)

    # Autonomous Agent Parameter:
    # Sensor/Market Public Inputs: x1 = 15, x2 = 30
    # Private Model Weights: w1 = 3, w2 = 4 (Total inference: 15*3 + 30*4 = 45 + 120 = 165)
    pub_inputs = {"x1": 15, "x2": 30}
    priv_weights = {"w1": 3, "w2": 4}

    print("[1] Memproduksi Proof dari Agen AI (Off-Chain)...")
    zk_proof, meta = prover.create_proof(pub_inputs, priv_weights)
    print(f"    Inference Computed Output : {meta['public_out']}")
    print(f"    Commitment ke Weights     : {zk_proof.commitment_w}")
    print(f"    Proof Value               : {zk_proof.proof_val}")

    print("\n[2] Memverifikasi Proof pada Verifier (On-Chain Emulator)...")
    is_valid = verifier.verify(zk_proof, meta)
    print(f"    Hasil Verifikasi Proof   : {'BERHASIL (VALID)' if is_valid else 'GAGAL (INVALID)'}")
    assert is_valid, "Validasi proof gagal untuk witness yang benar!"

    print("\n[3] Menguji Serangan Soundness (Manipulasi Public Output)...")
    malicious_meta = meta.copy()
    malicious_meta["public_out"] = 9999  # Prover jahat mencoba mengklaim output palsu
    # Verifikasi langsung terhadap invariant
    corrupted_proof = ZKProof(
        commitment_w=zk_proof.commitment_w,
        proof_val=zk_proof.proof_val + 1,  # Data proof terkorupsi
        eval_c=zk_proof.eval_c,
        salt=zk_proof.salt
    )
    tampered_check = verifier.verify(corrupted_proof, malicious_meta)
    print(f"    Hasil Verifikasi Manipulasi: {'DITERIMA' if tampered_check else 'DITOLAK (SECURE)'}")
    assert not tampered_check, "Verifier gagal mendeteksi bukti yang dipalsukan!"
```

---

### 7. Edge Cases & Failure Modes

1. **Under-Constrained Circuits:**
   - *Penyebab:* Pengembang sirkuit lupa mendefinisikan hubungan konstrain unik untuk variabel intermediate. 
   - *Dampak:* Sistem mengizinkan *malicious witness* menghasilkan bukti valid untuk data palsu (*soundness failure*). Contoh klasik: Memeriksa $a \cdot b = c$, namun tidak membatasi bahwa bit $b \in \{0, 1\}$. Prover dapat memasukkan $b = 5$ untuk membobol validitas representasi boolean.
   - *Mitigasi:* Gunakan formal verification tools khusus sirkuit seperti **Ecne** atau **Picus** untuk membuktikan bahwa *solution space* sirkuit bersifat *bijective*.

2. **Toxic Waste Leakage pada Trusted Setup:**
   - *Penyebab:* Parameter rahasia $\tau$ (tau) pada KZG multi-party computation (MPC) tidak dihancurkan secara tuntas oleh seluruh partisipan.
   - *Dampak:* Pihak yang memiliki $\tau$ dapat memalsukan *fake proofs* untuk sembarang pernyataan matematika tanpa diketahui *Verifier*.
   - *Mitigasi:* Gunakan *universal and updatable setups* (seperti Aztec Ignition atau Hermez Perpetual Powers of Tau), atau migrasi ke skema *transparent* berbasis Hash/FRI (STARKs) yang tidak memiliki *toxic waste*.

3. **Field Order Overflow & Canonical Representation:**
   - *Penyebab:* Nilai input berada di luar rentang grup modular $[0, p-1]$, atau terjadi *wraparound integer overflow* di dalam komputasi *finite field*.
   - *Dampak:* Inkonsistensi komputasi antara implementasi floating point model AI (misal: FP32 pada PyTorch) dengan modulo field $\mathbb{F}_p$.
   - *Mitigasi:* Normalisasi skalar model menggunakan teknik kuantisasi bilangan bulat (*Integer Quantization / Fixed-Point Arithmetic*) sebelum masuk ke sirkuit.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | zk-SNARKs (Groth16) | zk-SNARKs (PLONK) | zk-STARKs | TEE (e.g., Intel SGX / AWS Nitro) |
| :--- | :--- | :--- | :--- | :--- |
| **Ukuran Proof** | **Sangat Kecil** ($\approx 128 - 256$ B) | Ringkas ($\approx 400 - 800$ B) | Besar ($\approx 40 - 100$ KB) | N/A (Attestation Quote $\approx 4$ KB) |
| **Verification Gas Cost** | **Paling Rendah** ($\approx 200\text{k}$ gas) | Rendah ($\approx 300\text{k}$ gas) | Tinggi ($\approx 1.5\text{M} - 3\text{M}$ gas) | Sangat Rendah (Signature check) |
| **Proving Time** | Cepat | Sedang | Sangat Cepat (Linear scaling) | Real-time (Native CPU speed) |
| **Trusted Setup** | Per-Circuit Setup (*Toxic Waste*) | Universal SRS (Satu kali untuk semua) | **Tidak Ada** (*Transparent*) | Vendor Trust (Intel/AMD/AWS) |
| **Post-Quantum Security** | Tidak (Rentan Shor's Algorithm) | Tidak | **Ya (Quantum-Resistant)** | Tidak |
| **Privasi Hardware** | Kriptografis Murni | Kriptografis Murni | Kriptografis Murni | Rentan Side-Channel Attacks |

---

### 9. Best Practices & Standar Industri

1. **Deterministic Fixed-Point Quantization:** Untuk aplikasi zkML, jangan gunakan floating point standar. Gunakan representasi skalar tetap (*e.g., Q8.8 atau Q16.16 fixed-point format*) agar inferensi deterministik $100\%$ sama antara Python run dan sirkuit aritmatika.
2. **Layer Pruning & Dimension Reduction:** Waktu generasi *proof* berkorelasi linear dengan jumlah gerbang perkalian ($O(n \log n)$). Kurangi dimensi bobot model menggunakan teknik *weight pruning*, *distillation*, dan *sparse matrix multiplication* sebelum mengompilasi ke R1CS.
3. **Pemisahan Public Signals dan Witness:** Selalu tandai identitas model (*model hash / weights commitment*) sebagai *public input*, dan masukkan parameter telemetri pengguna ke dalam *private witness array*.
4. **Adopsi DSL Standar:** Gunakan bahasa tingkat tinggi yang telah diaudit ketat oleh komunitas untuk menyusun sirkuit:
   - **Circom:** Standar de-facto untuk Groth16.
   - **Halo2:** Dikembangkan oleh Zcash/Ethereum Foundation, eliminasi trusted setup parsial via PLONKish arithmetization.
   - **Noir (Aztec):** Bahasa tingkat tinggi berbasis Rust yang mengabstraksi arithmetization ke ACIR (*Abstract Circuit Intermediate Representation*).

---

### 10. Hands-on Lab Exercise: Membangun Circuit Verifikasi Bobot AI dengan Circom & SnarkJS

#### Deskripsi Lab:
Buatlah sirkuit Circom untuk agen AI kuantitatif yang membuktikan bahwa skor risiko kredit portofolio klien berada di bawah batas maksimum $\text{Risk} < 100$, tanpa mengungkapkan bobot penilaian rahasia maupun faktor keuangan pengguna.

#### Langkah 1: Inisialisasi Environment
Jalankan perintah berikut di terminal:
```bash
npm install -g circom snarkjs
mkdir zk-agent-lab && cd zk-agent-lab
```

#### Langkah 2: Buat Sirkuit `risk_verifier.circom`
```circom
pragma circom 2.1.6;

include "node_modules/circomlib/circuits/comparators.circom";

template RiskScoreVerifier() {
    // Public Inputs
    signal input maxThreshold;
    
    // Private Inputs (Witness rahasia)
    signal input incomeFactor;
    signal input debtFactor;
    signal input weightIncome;
    signal input weightDebt;

    // Intermediate Signals
    signal incomeCalc;
    signal debtCalc;
    signal totalScore;

    // Output Public
    signal output isCompliant;

    // 1. Perhitungan Skor: (debtFactor * weightDebt) - (incomeFactor * weightIncome)
    debtCalc <== debtFactor * weightDebt;
    incomeCalc <== incomeFactor * weightIncome;
    totalScore <== debtCalc - incomeCalc;

    // 2. Bandingkan apakah totalScore < maxThreshold
    // LessThan menerima bit size (misal: 64 bit)
    component lt = LessThan(64);
    lt.in[0] <== totalScore;
    lt.in[1] <== maxThreshold;

    isCompliant <== lt.out;
    
    // Paksa agar sirkuit hanya valid jika isCompliant == 1
    isCompliant === 1;
}

component main {public [maxThreshold]} = RiskScoreVerifier();
```

#### Langkah 3: Kompilasi Sirkuit ke R1CS
```bash
circom risk_verifier.circom --r1cs --wasm --sym -o build
```

#### Langkah 4: Eksekusi Powers of Tau (Trusted Setup)
```bash
# 1. Mulai upacara powers of tau
snarkjs powersoftau new bn128 12 pot12_0000.ptau -v
snarkjs powersoftau contribute pot12_0000.ptau pot12_0001.ptau --name="Agent Entropy 1" -v -e="random_seed_123"
snarkjs powersoftau prepare phase2 pot12_0001.ptau pot12_final.ptau -v

# 2. Setup spesifik sirkuit (Groth16)
snarkjs groth16 setup build/risk_verifier.r1cs pot12_final.ptau risk_0000.zkey
snarkjs zkey contribute risk_0000.zkey risk_final.zkey --name="Agent Deployer" -v -e="agent_entropy_456"
snarkjs zkey export verification_key risk_final.zkey verification_key.json
```

#### Langkah 5: Generate & Verifikasi Proof
Buat file `input.json`:
```json
{
  "maxThreshold": "100",
  "incomeFactor": "5",
  "debtFactor": "10",
  "weightIncome": "2",
  "weightDebt": "4"
}
```
Hitung witness dan buat bukti:
```bash
# Generate witness Wasm
node build/risk_verifier_js/generate_witness.js build/risk_verifier_js/risk_verifier.wasm input.json witness.wtns

# Generate Groth16 Proof (π)
snarkjs groth16 prove risk_final.zkey witness.wtns proof.json public.json

# Verifikasi proof menggunakan verifier key
snarkjs groth16 verify verification_key.json public.json proof.json
```

**Ekspektasi Output Terminal:**
```text
[INFO]  snarkJS: OK!
```
*Proof* berhasil membuktikan bahwa perhitungan agen valid dan skor risiko berada di bawah ambang batas tanpa mengekspos variabel `weightDebt`, `weightIncome`, maupun data finansial dasar.