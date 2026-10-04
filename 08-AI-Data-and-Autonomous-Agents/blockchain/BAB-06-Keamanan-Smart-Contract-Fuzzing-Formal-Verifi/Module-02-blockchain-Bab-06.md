# BAB 06: Keamanan Smart Contract, Fuzzing & Formal Verification
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengidentifikasi** celah keamanan tingkat lanjut pada EVM (*reentrancy variants*, *flash-loan price manipulation*, *rounding/inflation attacks* pada ERC-4626, serta *storage collision* pada upgradeable proxy).
- **Merancang Arsitektur Invariant Testing** berbasis *Handler-based Stateful Fuzzing* menggunakan Foundry dan Echidna untuk sistem terdesentralisasi multi-kontrak.
- **Mengimplementasikan Spesifikasi Formal** (*Formal Specifications*) menggunakan *Symbolic Execution* (Halmos/HEVM) dan *SMT-based Verification* (SMTChecker/Certora CVL) untuk membuktikan kebenaran matematis sistem.
- **Membangun Pipeline CI/CD Otomatis** untuk verifikasi keamanan smart contract skala enterprise dengan gerbang kualitas (*quality gates*) berbasis metrik cakupan invarian (*invariant coverage*).

---

### 2. Prerequisites
Sebelum memulai modul ini, Anda wajib menguasai:
- **EVM Internals**: Layout memori, call stack, storage slot packing, operasi delegatecall, dan gas optimization.
- **Solidity Lanjutan**: Interface, custom errors, inline assembly (Yul), modifier execution order, dan ERC standards (ERC-20, ERC-721, ERC-4626).
- **Foundry Toolchain**: Penggunaan `forge test`, cheatcodes (`vm.prank`, `vm.warp`, `vm.roll`, `vm.assume`), serta penulisan unit test dasar.
- **Logika Predikat & Matematika Diskrit**: Logika proposisi orde pertama ($\forall, \exists$), relasi ekuivalensi, dan state machine transition logic.

---

### 3. Concept & Internal Architecture

Keamanan smart contract modern telah berevolusi dari *manual code review* dan *unit testing* statis menjadi *mathematical proof systems* dan *guided state-space exploration*.

```
   +-----------------------------------------------------------------------+
   |                       Level of Rigor & Assurance                      |
   +-----------------------------------------------------------------------+
   |  [Formal Verification] -> Jaminan Matematis Mutlak (SMT/Symbolic)     |
   |           ^                                                           |
   |  [Stateful Fuzzing]    -> Eksplorasi State-Space Multi-Transaksi      |
   |           ^                                                           |
   |  [Stateless Fuzzing]   -> Input Acak pada Fungsi Tunggal              |
   |           ^                                                           |
   |  [Unit Testing]        -> Titik Evaluasi Deterministik Statis         |
   +-----------------------------------------------------------------------+
```

#### A. Coverage-Guided Stateful Mutational Fuzzing (Foundry / Echidna)
Berbeda dengan *stateless fuzzing* yang hanya menguji fungsi individual $f(x)$ dengan variasi parameter $x$, *stateful fuzzing* memodelkan smart contract sebagai Finite State Machine (FSM):

$$\sigma_0 \xrightarrow{T_1(x_1)} \sigma_1 \xrightarrow{T_2(x_2)} \sigma_2 \dots \xrightarrow{T_n(x_n)} \sigma_n$$

Fuzzer mempertahankan korpus transaksi dan bermutasi berdasarkan metrik *edge coverage* pada bytecode EVM:
1. **Instrumentasi Bytecode**: Melacak transisi PC (*Program Counter*) untuk mendeteksi eksekusi branch baru (`JUMP`, `JUMPI`).
2. **Corpus Generation**: Transaksi yang menghasilkan code coverage baru disimpan ke dalam korpus utama untuk mutasi lebih lanjut.
3. **Handler Architecture**: Handler bertindak sebagai *middleware* yang memfilter domain parameter input acak menjadi rentang valid yang bermakna secara semantik bagi kontrak target, mencegah fuzzer menghabiskan waktu pada *trivial reverts*.

#### B. Symbolic Execution & SMT-based Formal Verification
Formal Verification membuktikan bahwa properti invarian $\Phi$ terpenuhi untuk *semua* kemungkinan state yang dapat dicapai ($\Sigma_{reachable}$):

$$\forall \sigma \in \Sigma_{reachable}, \quad \sigma \models \Phi$$

1. **Symbolic Execution (e.g., Halmos)**: Mengganti input konkret dengan variabel simbolik $\alpha$. Setiap branch kondisional mengekspansi *execution tree*. Halmos mengevaluasi constraints pada path menggunakan algoritma SAT/SMT (Z3/CVC5).
2. **SMT Encoding**: Smart contract dan properti diverifikasi dengan menerjemahkan EVM opcode dan assertion ke First-Order Logic modulo theories (Bitvectors, Arrays, Uninterpreted Functions).
3. **Soundness vs. Completeness**:
   - *Soundness*: Jika solver menyatakan properti valid, properti tersebut benar-benar valid secara matematis.
   - *Completeness*: Jika properti valid, solver selalu dapat membuktikannya (seringkali terbentur masalah undecidability dan path explosion pada loop unbounded).

---

### 4. Why & What

| Dimensi | Unit Testing Konvensional | Fuzzing (Stateful/Invariant) | Formal Verification (SMT/Symbolic) |
| :--- | :--- | :--- | :--- |
| **Cakupan State** | Titik tunggal diskrit ($10^0 - 10^2$ kombinasi) | Ruang sampel heuristik terarah ($10^5 - 10^7$ kombinasi) | Seluruh ruang input secara absolut ($2^{256}$ kombinasi) |
| **Pendekatan** | Berbasis contoh (*Example-based*) | Berbasis properti stokastik (*Property-based*) | Berbasis pembuktian matematis (*Deductive proof*) |
| **Kekurangan** | *Confirmation bias* pengembang; rentan terhadap *edge cases* tak terduga | Tidak menjamin pembuktian 100%; probabilistik | Terkena masalah *path explosion*; biaya komputasi dan penulisan spesifikasi tinggi |
| **Peran di Produksi** | Verifikasi fungsionalitas dasar dan regresi cepat | Menemukan interaksi state tak terduga (*reentrancy*, *arbitrage*, *drain*) | Mengunci core invariant fundamental (contoh: *solvency*, *authorization*) |

---

### 5. How (Workflow Detail)

Alur kerja audit dan verifikasi continuous integration (CI) kelas enterprise diimplementasikan sebagai pipeline bertingkat:

```
[Solidity Source Code]
          |
          v
+-------------------+
| Static Analysis   | -> Slither, Aderyn (Pemeriksaan pola rentan statis AST)
+-------------------+
          |
          v
+-------------------+
| Unit Tests        | -> Forge standard tests (Cakupan branch dasar)
+-------------------+
          |
          v
+-------------------+
| Stateless Fuzzing | -> Forge testFuzz (Input boundaries: 0, 1, type(uint256).max)
+-------------------+
          |
          v
+-------------------+
| Stateful Fuzzing  | -> Handler-based Invariant Testing (Foundry / Echidna)
| (Multi-Tx Engine) |    Target: Solvency, Token conservation, No-free-mint
+-------------------+
          |
          v
+-------------------+
| Symbolic Exec /   | -> Halmos / Certora Prover
| Formal Verif      |    Membuktikan mathematical invariants tanpa eksekusi konkret
+-------------------+
          |
          +--> [PASS: Deploy to Testnet/Staging]
          +--> [FAIL: Counterexample Found -> Fix -> Re-test]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah brankas bank kelas dunia:
- **Unit Testing**: Memasukkan satu kunci buatan ke lubang kunci dan memeriksa apakah pintu terbuka.
- **Fuzzing**: Menugaskan robot mekanis yang memutar tuas, menekan tombol angka secara acak, dan mengguncang brankas jutaan kali dalam urutan transaksi berbeda untuk melihat apakah pintu terbuka tanpa kunci.
- **Formal Verification**: Mengambil cetak biru mekanik brankas, menerjemahkannya ke dalam persamaan fisika/matematika, dan membuktikan secara analitis bahwa tidak ada torsi atau kombinasi roda gigi mekanis yang dapat menggerakkan gerendel tanpa kunci yang tepat.

```
       EVM Execution Path Exploration:

       [Root State: S0]
          /        \
       Call A()    Call B()
        /    \       /    \
      S1      S2   S3      S4
     /  \    /  \
   S11  S12 S21 S22 ...
    |    |
    v    v
  [Invariant Violations Detected Here via Mutation or Symbolic Solver]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Arithmetic Invariant Violation (Rounding Issue)

Contoh berikut menunjukkan kerentanan pembagian integer yang dapat dieksploitasi jika invariant rasio tidak diuji:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract VulnerableRewardPool {
    uint256 public totalStake;
    uint256 public rewardPool;
    mapping(address => uint256) public stakes;

    function deposit(uint256 amount) external {
        require(amount > 0, "Zero amount");
        stakes[msg.sender] += amount;
        totalStake += amount;
    }

    function addRewards(uint256 amount) external {
        rewardPool += amount;
    }

    // VULNERABLE: Rounding down to 0 allows draining or front-running exploits
    function calculateReward(address user) public view returns (uint256) {
        if (totalStake == 0) return 0;
        return (stakes[user] * rewardPool) / totalStake;
    }
}
```

#### B. Practical Enterprise Example: Yield Vault Menggunakan Invariant Testing & Halmos

Di bawah ini adalah implementasi Vault berbasis standar ERC-4626 yang diperkuat terhadap *donation attacks*, dilengkapi dengan arsitektur invariant handler Foundry dan Halmos symbolic test.

##### 1. Core Contract: `SecuredYieldVault.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract SecuredYieldVault is ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public immutable asset;
    uint256 public totalShares;
    
    // Virtual shares and assets offset to prevent inflation/donation attacks
    uint256 internal constant VIRTUAL_OFFSET = 1e3;
    
    mapping(address => uint256) public balanceOf;

    error ZeroDeposit();
    error ZeroSharesMinted();
    error InsufficientBalance();

    constructor(IERC20 _asset) {
        asset = _asset;
    }

    function totalAssets() public view returns (uint256) {
        return asset.balanceOf(address(this));
    }

    function convertToShares(uint256 assets) public view returns (uint256) {
        return (assets * (totalShares + VIRTUAL_OFFSET)) / (totalAssets() + VIRTUAL_OFFSET);
    }

    function convertToAssets(uint256 shares) public view returns (uint256) {
        return (shares * (totalAssets() + VIRTUAL_OFFSET)) / (totalShares + VIRTUAL_OFFSET);
    }

    function deposit(uint256 assets, address receiver) external nonReentrant returns (uint256 shares) {
        if (assets == 0) revert ZeroDeposit();
        
        shares = convertToShares(assets);
        if (shares == 0) revert ZeroSharesMinted();

        balanceOf[receiver] += shares;
        totalShares += shares;

        asset.safeTransferFrom(msg.sender, address(this), assets);
    }

    function withdraw(uint256 shares, address receiver) external nonReentrant returns (uint256 assets) {
        if (shares == 0) revert ZeroDeposit();
        if (balanceOf[msg.sender] < shares) revert InsufficientBalance();

        assets = convertToAssets(shares);

        balanceOf[msg.sender] -= shares;
        totalShares -= shares;

        asset.safeTransfer(receiver, assets);
    }
}
```

##### 2. Fuzz Handler: `VaultHandler.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {SecuredYieldVault} from "./SecuredYieldVault.sol";
import {ERC20Mock} from "@openzeppelin/contracts/mocks/token/ERC20Mock.sol";

contract VaultHandler is Test {
    SecuredYieldVault public immutable vault;
    ERC20Mock public immutable asset;

    address[] public actors;
    address internal currentActor;

    uint256 public ghost_depositSum;
    uint256 public ghost_withdrawSum;

    constructor(SecuredYieldVault _vault, ERC20Mock _asset) {
        vault = _vault;
        asset = _asset;
        
        for (uint256 i = 1; i <= 4; i++) {
            address actor = address(uint160(0x1000 + i));
            actors.push(actor);
            asset.mint(actor, 1_000_000 ether);
            vm.prank(actor);
            asset.approve(address(vault), type(uint256).max);
        }
    }

    modifier useActor(uint256 actorIndexSeed) {
        currentActor = actors[actorIndexSeed % actors.length];
        _;
    }

    function deposit(uint256 amount, uint256 actorSeed) external useActor(actorSeed) {
        amount = bound(amount, 1, 100_000 ether);
        
        vm.prank(currentActor);
        try vault.deposit(amount, currentActor) returns (uint256 shares) {
            ghost_depositSum += amount;
        } catch {}
    }

    function withdraw(uint256 shares, uint256 actorSeed) external useActor(actorSeed) {
        uint256 userShares = vault.balanceOf(currentActor);
        if (userShares == 0) return;

        shares = bound(shares, 1, userShares);

        vm.prank(currentActor);
        try vault.withdraw(shares, currentActor) returns (uint256 assets) {
            ghost_withdrawSum += assets;
        } catch {}
    }

    function donate(uint256 amount) external {
        amount = bound(amount, 1, 10_000 ether);
        address donor = actors[0];
        vm.prank(donor);
        asset.transfer(address(vault), amount);
    }
}
```

##### 3. Stateful Invariant Test: `VaultInvariant.t.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {SecuredYieldVault} from "./SecuredYieldVault.sol";
import {VaultHandler} from "./VaultHandler.sol";
import {ERC20Mock} from "@openzeppelin/contracts/mocks/token/ERC20Mock.sol";

contract VaultInvariantTest is Test {
    SecuredYieldVault internal vault;
    ERC20Mock internal asset;
    VaultHandler internal handler;

    function setUp() public {
        asset = new ERC20Mock();
        vault = new SecuredYieldVault(asset);
        handler = new VaultHandler(vault, asset);

        targetContract(address(handler));
    }

    /// @notice Invariant: Solvabilitas Vault mutlak tidak boleh dilanggar
    /// Total balance asset internal di Vault harus selalu >= asset yang dikonversi dari total shares
    function invariant_solvencyCheck() public view {
        uint256 vaultAssetBalance = vault.totalAssets();
        uint256 claimableAssets = vault.convertToAssets(vault.totalShares());
        
        assertGe(
            vaultAssetBalance, 
            claimableAssets, 
            "Solvency invariant violated: Vault is insolvent"
        );
    }

    /// @notice Invariant: Akuntansi Share Konsisten
    /// Jumlah saldo share seluruh aktor harus selalu sama dengan totalShares
    function invariant_shareConservation() public view {
        uint256 aggregateActorShares = 0;
        for (uint256 i = 0; i < 4; i++) {
            address actor = address(uint160(0x1000 + i + 1));
            aggregateActorShares += vault.balanceOf(actor);
        }
        assertEq(
            aggregateActorShares, 
            vault.totalShares(), 
            "Conservation invariant violated: Total shares mismatch"
        );
    }
}
```

##### 4. Formal Verification Harness (Halmos): `VaultSymbolic.t.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {SecuredYieldVault} from "./SecuredYieldVault.sol";
import {ERC20Mock} from "@openzeppelin/contracts/mocks/token/ERC20Mock.sol";

contract VaultSymbolicTest is Test {
    SecuredYieldVault internal vault;
    ERC20Mock internal asset;

    function setUp() public {
        asset = new ERC20Mock();
        vault = new SecuredYieldVault(asset);
    }

    /// @dev Symbolic proof: Buktikan bahwa share conversion monotonik
    /// assets_1 <= assets_2 ==> shares_1 <= shares_2 untuk state arbitrary
    function check_monotonicityOfShares(uint256 a1, uint256 a2) public view {
        vm.assume(a1 <= a2);
        
        uint256 shares1 = vault.convertToShares(a1);
        uint256 shares2 = vault.convertToShares(a2);

        assert(shares1 <= shares2);
    }
}
```

---

### 8. Real World Case Study: Euler Finance Exploit Analysis ($197M Hack)

#### A. Akar Masalah Teknis
Pada Maret 2023, Euler Finance dieksploitasi akibat interaksi antara fungsi `donateToReserves` dan logika `checkLiquidity`.
- Protokol mengizinkan pengguna mendonasikan token agunan (*collateral*) ke cadangan tanpa memeriksa apakah pendonor berada dalam kondisi *undercollateralized* pasca donasi.
- **Invariant yang Dilanggar**: 
  $$\forall \text{account}, \quad \text{HealthFactor}(\text{account}) \ge 1.0 \quad \lor \quad \text{InLiquidation}(\text{account})$$

```
[Attacker] 
   |-- 1. Deposit 20M DAI (Mint eDAI)
   |-- 2. Mint 10x leveraged position via dDAI (Borrow 190M DAI)
   |-- 3. Call donateToReserves(100M eDAI)
          \--> Invariant Failure: Health Factor drop drastic, but no revert!
   |-- 4. Protocol triggers liquidation with massive bad debt discounts
   \--> Exploit Result: Drained $197M across multiple lending pools
```

#### B. Bagaimana Invariant Fuzzing & Formal Verification Mencegahnya
Jika Euler mengimplementasikan *Handler-based Invariant Testing* dengan invarian:
```solidity
function invariant_protocolCollateralization() public view {
    for (uint256 i = 0; i < accounts.length; i++) {
        address acc = accounts[i];
        if (euler.debtOf(acc) > 0) {
            assertTrue(euler.getHealthFactor(acc) >= 1e18 || euler.isLiquidatable(acc));
        }
    }
}
```
Fuzzer Foundry/Echidna akan mengeksekusi path: `deposit() -> borrow() -> donateToReserves()` dan secara otomatis mendeteksi kegagalan invariant dalam <10.000 iterasi.

---

### 9. Trade-offs Architecture Matrix

| Strategi | Kecepatan Eksekusi CI | Kompleksitas Setup | False Positive / Negative Rate | Skalabilitas Pipeline | Biaya Komputasi |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stateless Fuzzing** | Tinggi (~10-30 detik) | Rendah (mirip unit test) | FN: Tinggi (melewatkan bug multi-tx), FP: Sangat Rendah | Linear terhadap jumlah fungsi | Rendah (CPU single-core) |
| **Stateful Handler Fuzzing**| Sedang (~5-15 menit) | Tinggi (memerlukan ghost variable & bounded handler) | FN: Sedang, FP: Rendah | Memerlukan tuning kedalaman mutasi (*runs* & *depth*) | Sedang-Tinggi (Multi-core fuzz worker) |
| **Symbolic Execution (Halmos)**| Cepat-Sedang (1-5 menit) | Sedang (memerlukan asumsi/constraints yang presisi) | FN: Nol (untuk bounded depth), FP: Sedang (unconstrained state) | Eksponensial terhadap kedalaman percabangan (*branches*) | Tinggi (SMT solver memory & CPU) |
| **Certora Formal Verification**| Lambat (15-60 menit) | Sangat Tinggi (bahasa formal CVL tersendiri) | FN: Nol secara matematis, FP: Rendah jika spec akurat | Terbatas pada modul-modul kritis core ledger | Sangat Tinggi (Dedicated Prover Cloud Server) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Ineffective Fuzzing Through Over-Constraining (`vm.assume`)
```solidity
// SALAH: Mengabaikan 99.9% ruang input acak, menyebabkan "fuzz test discarded inputs"
function testFuzz_withdraw(uint256 amount) public {
    vm.assume(amount > 100 && amount < 105); // Bad practice
    vault.withdraw(amount);
}

// BENAR: Gunakan bound() untuk memetakan distribusi merata
function testFuzz_withdraw_fixed(uint256 amount) public {
    amount = bound(amount, 100, 105);
    vault.withdraw(amount);
}
```

#### 2. Revert Invariant Masking
- **Masalah**: Handler selalu revert karena pra-kondisi yang terlalu ketat, menyebabkan invariant test selalu `PASS` secara semu tanpa pernah mengeksekusi logika internal.
- **Troubleshooting**: Tambahkan variabel pelacak eksekusi (*call counters*). Di akhir invariant test run, assert bahwa fungsi handler benar-benar sukses terpanggil:
  ```solidity
  assertGt(handler.ghost_successfulCalls(), 1000, "Fuzzer did not execute valid transitions");
  ```

#### 3. Path Explosion pada Symbolic Testing
- **Masalah**: Halmos kehabisan memori atau time-out pada loop tidak terbatas.
- **Troubleshooting**: Lakukan loop unrolling terikat atau batasi array length pada symbolic testing harness menggunakan `vm.assume(symbolicArray.length <= 3)`.

---

### 11. Best Practices & Production Checklist

- [ ] **State Machine Modeling**: Petakan seluruh transisi state sistem ke dalam diagram status sebelum menulis handler.
- [ ] **Ghost Variables**: Gunakan ghost variable untuk mencatat riwayat transfer token global secara independen dari storage kontrak target.
- [ ] **Invariant Classification**:
  - [ ] *State invariants*: Selalu benar setiap saat (contoh: `totalAssets() >= totalShares()`).
  - [ ] *Transition invariants*: Perubahan state $\Delta$ harus sesuai aturan (contoh: penarikan $x$ share mengurangi balance tepat $x$).
- [ ] **Dual Fuzzer Architecture**: Integrasikan Foundry untuk invariant CI lokal cepat, dan jalankan Echidna selama 24 jam sebelum peluncuran produksi (*deep fuzzing*).
- [ ] **Fail-Safe Constraints**: Pastikan assertion formal mencakup properti solvency, authorization limit, dan reentrancy absence.

---

### 12. Hands-on Practice

Buat dan simpan konfigurasi dan file implementasi berikut di direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek Foundry
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
forge init --no-commit
forge install OpenZeppelin/openzeppelin-contracts --no-commit
```

#### Langkah 2: Konfigurasi `foundry.toml`
Pastikan pengaturan invariant testing dioptimalkan untuk eksplorasi state yang mendalam:

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]

[fuzz]
runs = 10000
max_test_rejects = 65536

[invariant]
runs = 500
depth = 128
fail_on_revert = false
call_override = false
```

#### Langkah 3: Eksekusi Invariant Tests
Salin kode `SecuredYieldVault.sol`, `VaultHandler.sol`, dan `VaultInvariant.t.sol` ke direktori proyek (`src/` dan `test/`).

Jalankan perintah pengujian:
```bash
forge test --match-contract VaultInvariantTest -vvvv
```

Analisis log eksekusi dan perhatikan mutasi sequence yang digenerate oleh Foundry engine.

---

### 13. Exercises

#### Level Easy
Tuliskan test stateless fuzzing pada fungsi transfer ERC-20 yang menguji bahwa transfer dari Akun A ke Akun B tidak pernah mengubah total supply token:
$$\text{totalSupply}_{t0} \equiv \text{totalSupply}_{t1}$$
- **Kriteria Penerimaan**: Menggunakan `bound()`, menguji batas input ekstrem ($0$ dan `balanceOf`), dijalankan minimal 5.000 runs.

#### Level Medium
Tambahkan mekanisme flash loan sederhana pada `SecuredYieldVault.sol`. Kembangkan Handler baru pada `VaultHandler.sol` yang menyimulasikan aktor mengambil flash loan dan memanipulasi balance token underlying pada blok yang sama.
- **Kriteria Penerimaan**: Invariant `invariant_solvencyCheck` harus tetap bertahan meskipun terjadi transfer underlying besar-besaran di tengah transaksi.

#### Level Hard
Buat invariant test harness untuk sistem Staking Multi-Token dengan mekanisme reward terakselerasi waktu (*time-decay reward*). Simulasikan pergerakan waktu (`vm.warp`) secara dinamis di dalam Handler tanpa menyebabkan arithmetic overflow.
- **Kriteria Penerimaan**: Buktikan bahwa reward yang diclaim oleh seluruh staker tidak pernah melebihi total deposit reward yang disediakan admin, apapun skenario warp waktu yang dieksekusi.

---

### 14. Real-World Challenge

**Arsitektur Cross-Chain Yield Bridge Invariant**:
Sebuah protokol mengunci aset di Ethereum dan menerbitkan token representasi (*wrapped*) di Arbitrum via cross-chain messaging bridge.
Tugas Anda:
1. Rancang arsitektur invariant test multi-kontrak yang memodelkan latensi relay pesan cross-chain dan kemungkinan pesan out-of-order.
2. Definisikan sekurang-kurangnya 3 Invariant Global Sistem yang menjamin bahwa invariant solvabilitas cross-chain tidak dapat ditembus oleh serangan reorganisasi blok (*reorg*) atau *message replay*.
3. Susun Handler yang mengeksekusi *state transitions* yang menyimulasikan kegagalan jaringan cross-chain, dan tunjukkan bagaimana sistem menangani status pending settlement secara aman.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Konseptual & Dasar (5 Soal)
1. Apa perbedaan arsitektural utama antara *Stateless Fuzzing* dan *Stateful Fuzzing* pada EVM?
2. Mengapa penggunaan `vm.assume()` secara berlebihan dapat menyebabkan pengujian fuzzing Foundry gagal (*discard limit reached*)?
3. Sebutkan kelemahan fundamental dari metrik 100% *Line Coverage* dalam konteks keamanan smart contract.
4. Apa yang dimaksud dengan *Ghost Variable* dalam pengujian invarian, dan mengapa variabel ini diletakkan di handler bukan di kontrak produksi?
5. Dalam formal verification, apa arti matematis dari properti yang bersifat *Sound*?

#### B. Pertanyaan Lanjutan & Analisis (5 Soal)
6. Bagaimana teknik penambahan virtual shares dan virtual assets (offset) pada ERC-4626 secara matematis mencegah *first-depositor inflation attack*?
7. Jelaskan fenomena *Path Explosion* pada *Symbolic Execution* dan bagaimana solver SMT membatasi kompleksitas ini saat menghadapi array dinamis.
8. Jika sebuah invariant test lolos dengan 0 kegagalan pada 10.000 iterasi, apakah ini menjamin smart contract 100% bebas bug? Jelaskan rasionalisasinya.
9. Mengapa *revert* pada handler terkadang harus diabaikan (`try-catch` wrapper) dalam stateful fuzz testing? Kapan revert justru menandakan bug?
10. Bagaimana representasi memori EVM storage disimulasikan oleh symbolic engine seperti Halmos tanpa melakukan kompilasi penuh ke arsitektur CPU host?

#### C. Skenario Kasus Produksi (3 Soal)
11. **Kasus 1**: Protokol pinjaman (Lending Protocol) mengalami insiden di mana total agunan di pool bernilai $10M, namun pinjaman yang beredar mencapai $12M tanpa memicu likuidasi. Invariant apa yang absen dari pipeline pengujian sebelum deploy?
12. **Kasus 2**: Handler fuzzing Anda melaporkan bahwa eksekusi fungsi `rebalance()` selalu gagal dengan pesan *Arithmetic Underflow*. Saat dianalisis, invariant engine menghasilkan urutan transaksi yang mustahil terjadi karena memanggil fungsi yang dibatasi `onlyOwner` melalui alamat acak. Kesalahan apa yang terjadi pada arsitektur Handler Anda?
13. **Kasus 3**: Tim audit formal menemukan counterexample pada Halmos di mana user dapat mencetak 1 wei share tanpa mentransfer token apapun saat pool kosong. Bagaimana perbaikan spesifikasi matematis pada fungsi `convertToShares` untuk mengeliminasi boundary bug ini?

---

### Rationale & Kunci Jawaban Quiz

<details>
<summary>Klik untuk melihat Kunci Jawaban & Evaluasi</summary>

#### Jawaban Bagian A
1. **Stateless Fuzzing** menguji satu fungsi target secara terisolasi dengan state awal yang selalu di-reset pada setiap run, sedangkan **Stateful Fuzzing** menjalankan urutan (*sequence*) transaksi berantai di mana output state dari transaksi $n$ menjadi input state bagi transaksi $n+1$, memodelkan akumulasi state EVM.
2. `vm.assume()` menolak input yang tidak memenuhi syarat secara total. Jika fuzzer menghasilkan banyak input acak di luar range yang diasumsikan, rejection counter melampaui batas default (`max_test_rejects`), menyebabkan fuzzer berhenti tanpa menyelesaikan evaluasi.
3. *Line coverage* hanya mengukur eksekusi baris instruksi, bukan *state-space coverage*. Jalur eksekusi baris yang sama dapat menghasilkan invariant violation fatal jika dipanggil dalam konfigurasi global state yang berbeda (misalnya variabel global bernilai nol atau manipuated exchange rate).
4. *Ghost Variable* adalah variabel state pelacak tambahan yang disimpan di harness/handler pengujian untuk mencatat akuntansi paralel independen (ground truth). Variabel ini tidak boleh ada di kontrak produksi demi menghemat gas dan menjaga kebersihan codebase implementasi.
5. *Soundness* berarti sistem verifikasi tidak akan pernah menyatakan sebuah program salah sebagai "benar" (tidak ada *false negatives* dalam validitas invarian). Jika sistem membuktikan invarian valid, secara matematis invarian tersebut terbukti benar.

#### Jawaban Bagian B
6. Virtual offset memodulasi rasio dengan menambahkan basis artifisial:
   $$\frac{\text{shares}}{\text{assets}} = \frac{A \cdot (S + 10^3)}{B + 10^3}$$
   Manipulasi rasio dengan donasi langsung tidak dapat mendilusi share hingga bernilai 0 per 1 wei underlying asset karena adanya penyebut dasar virtual.
7. *Path explosion* terjadi ketika setiap branch (`if-else`, loop) menggandakan jumlah cabang jalur simbolik ($2^n$). Solver membatasi kompleksitas ini dengan *bounded loop unrolling*, membatasi kedalaman eksekusi, serta memanfaatkan abstraksi memori *uninterpreted functions*.
8. Tidak. Stateful fuzzing bersifat probabilistik heuristik. Fuzzer dapat melewatkan *edge case* sangat spesifik yang membutuhkan konfigurasi parameter multi-transaksi eksotik yang belum tersampel dalam korpus acak tersebut.
9. Revert diabaikan jika aksi mewakili input pengguna yang tidak valid secara wajar (misal: user mencoba withdraw melebihi saldo). Namun, revert menandakan bug jika aksi merupakan transisi sistem yang valid menurut spesifikasi arsitektur tetapi revert karena *unexpected internal failure* (misalnya arithmetic error tak terduga).
10. Engine simbolik memetakan EVM storage sebagai *symbolic array of words* ($\text{Array}\langle\text{BitVec}_{256}, \text{BitVec}_{256}\rangle$). Operasi `SLOAD` dan `SSTORE` diterjemahkan langsung menjadi aksi `select` dan `store` pada teori array SMT tanpa menyentuh disk fisik.

#### Jawaban Bagian C
11. Absennya Invariant Global Solvabilitas Protokol:
    $$\sum \text{CollateralValue}_{\text{all users}} \ge \sum \text{DebtValue}_{\text{all users}}$$
    yang wajib dievaluasi pada level agregat sistem di setiap akhir transaksi mutasi state.
12. Handler tidak membatasi domain aktor (*caller bounds*). Handler harus mengisolasi peran (*roles segregation*) menggunakan array aktor yang telah diotorisasi dan menerapkan `vm.prank(owner)` secara eksplisit untuk fungsi administrasi, agar fuzzer tidak membuang komputasi pada revert izin akses (*access control*).
13. Perbaiki konversi share dengan menambahkan validasi eksplisit bahwa return shares harus $> 0$, atau enforce *minimum deposit requirement*:
    ```solidity
    if (shares == 0) revert ZeroSharesMinted();
    ```
    Serta gunakan pembulatan ke bawah (*round down*) untuk minting share dan pembulatan ke atas (*round up*) untuk aset penarikan sesuai spesifikasi baku ERC-4626.
</details>

---

### 16. Summary
- Keamanan smart contract kelas enterprise membutuhkan pergeseran paradigma dari pengujian reaktif menuju verifikasi proaktif berbasis **Stateful Invariant Testing** dan **Mathematical Formal Verification**.
- **Foundry Invariant Testing** dengan arsitektur **Handler** memungkinkan simulasi jutaan skenario interaksi pengguna multi-transaksi kompleks, membongkar kerentanan laten seperti *economic rounding exploits* dan *donation attacks*.
- **Symbolic Verification** (Halmos/Certora) melengkapi fuzzing dengan memverifikasi secara deduktif bahwa invariansi inti protokol mematuhi spesifikasi matematis di bawah seluruh domain input EVM $2^{256}$.
- Memadukan static analysis, stateful fuzzing berkedalaman tinggi, dan symbolic execution dalam pipeline CI/CD adalah standar pertahanan terbaik dalam arsitektur Web3 enterprise modern sebelum mengunci kontrak pada mainnet yang tidak dapat diubah (*immutable*).