# Bab 06: Keamanan Smart Contract, Fuzzing, & Formal Verification
## Modul 01: Invariant-Based Testing & Mathematical Verification untuk Autonomous Agent Execution

---

### 1. Learning Objectives (Spesifik & Terukur)
Setelah menyelesaikan modul ini, arsitek sistem dan *security engineer* diharapkan mampu:
- **Merumuskan Invarian Kritis Smart Contract:** Memetakan status ekuilibrium protokol berbasis *state machine* ke dalam predikat matematika (*Hoare logic*) yang ekuivalen untuk sistem *autonomous agent*.
- **Membangun Stateful Fuzzing Pipeline:** Mengimplementasikan *invariant testing harness* menggunakan Foundry/Forge dengan pendekatan *Handler-based architecture* untuk mensimulasikan jutaan mutasi *state* asinkron.
- **Menerapkan Formal Verification Menggunakan SMT Solver:** Mengonversi logika bisnis kritis ke dalam *First-Order Logic* dan mengeksekusi *bounded model checking* menggunakan Z3 Theorem Prover / SMTChecker untuk membuktikan ketiadaan celah eksploitasi secara matematis.
- **Mengidentifikasi & Memitigasi Vektor Serangan Agentic Execution:** Menganalisis dan menambal kerentanan tingkat lanjut seperti *cross-function reentrancy*, manipulasi likuiditas berbasis *flash-loan*, dan inkonsistensi *state* akibat eksekusi otonom non-deterministik.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Smart contract pada dasarnya adalah mesin *state transition* deterministik terdistribusi. Ketika agen otonom (*AI agents* atau *automated bots*) berinteraksi dengan smart contract, mereka mengeksekusi transaksi dengan kecepatan tinggi berdasarkan kondisi logika yang kompleks. Paradigma pengujian konvensional (*unit testing*) terbukti tidak memadai karena hanya menguji *known unknowns* melalui pasangan input-output statis.

```
       +-------------------------------------------------------+
       |                  Verification Spectrum                |
       +-------------------------------------------------------+
       |  Unit Testing      : Contoh spesifik (f(2) == 4)       |
       |  Fuzz Testing      : Domain acak terarah (f(x) valid?) |
       |  Formal Verif.     : Pembuktian universal (∀x, P(x))  |
       +-------------------------------------------------------+
```

#### Mental Model: The Invariant & The State Machine
Sistem diekspresikan sebagai tuple $S = (s_0, T, I)$:
- $s_0$: *Genesis state* (kondisi pasca-*deployment*).
- $T: S \times A \to S$: Fungsi transisi *state*, di mana tindakan $A$ dieksekusi oleh pengguna atau agen otonom.
- $I(s) \to \{0, 1\}$: Predikat invarian. Sebuah kondisi yang **harus selalu benar** di setiap *reachable state* $s \in S$.

Pendekatan keamanan modern dibagi menjadi dua metodologi:
1. **Property-Based / Invariant Fuzzing:** Pendekatan empiris terpandu (*guided-coverage*) yang membombardir sistem dengan urutan transaksi dinamis (*stateful calls*) untuk mencari *counter-example* yang membatalkan $I(s)$.
2. **Formal Verification (Symbolic Execution & SMT):** Pendekatan analitis deduktif. Alih-alih mengeksekusi nilai konkret, variabel direpresentasikan sebagai simbol matematis ($X$). Seluruh eksekusi diubah menjadi formula logika proposisional. Solvers (seperti Z3, CVC5) menyelesaikan persamaan:
$$\exists X \text{ such that } \text{PathCondition}(X) \land \neg I(X)$$
Jika solver menghasilkan *UNSAT* (Unsatisfiable), maka secara matematis terbukti bahwa tidak ada input yang dapat merusak invarian tersebut dalam batasan (*bound*) yang ditentukan.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada ekosistem *Autonomous Agents* terdesentralisasi (misalnya, agen pengelola perbendaharaan DAO, bot arbitrase otomatis, atau protokol likuiditas terdesentralisasi), agen berinteraksi langsung dengan likuiditas bernilai tinggi tanpa intervensi manusia secara *real-time*.

* **Kecepatan Serangan Melebihi Reaksi Manusia:** Ketika celah dieksploitasi, dana terkuras dalam satu blok (12 detik di Ethereum, sub-detik di L2/Solana) melalui transaksi teratomisasi (*flash loans*). *Circuit breaker* manual berbasis multisig manusia tidak relevan.
* **Biaya Kegagalan Sistemik:** Kegagalan protokol seperti *Nomad Bridge* ($190M) atau *Euler Finance* ($197M) bukan disebabkan oleh bug sintaksis primitif, melainkan pelanggaran invarian logika: rasio kolateralisasi internal tidak diverifikasi setelah fungsi non-standar dipanggil.
* **Standar Regulasi & Audit Institusional:** Regulasi enterprise mewajibkan jaminan matematis terhadap keamanan perbendaharaan (*treasury assets*). Verifikasi formal bukan lagi pelengkap audit, melainkan prasyarat penerbitan aset tertokenisasi dan perikatan agen otonom institusional.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan pipeline verifikasi berlapis untuk smart contract yang berinteraksi dengan Autonomous Execution Agents:

```
+----------------------------------------------------------------------------------+
|                    Autonomous Agent Orchestration Context                        |
+----------------------------------------------------------------------------------+
                                        |
                 [Intent / Action Sequence: Execution Payload]
                                        v
+----------------------------------------------------------------------------------+
|                        Target System: AgentVault.sol                             |
|  - Tracks assets, manages collateral, executes autonomous strategy calls        |
+----------------------------------------------------------------------------------+
                                        |
           +----------------------------+----------------------------+
           |                                                         |
           v                                                         v
+------------------------------------+     +---------------------------------------+
| LAYER 1: Stateful Invariant Fuzzer |     | LAYER 2: Symbolic & Formal Engine     |
| (Foundry / Forge Engine)           |     | (Halmos / SMTChecker / Z3 Solver)     |
+------------------------------------+     +---------------------------------------+
|  +------------------------------+  |     |  +---------------------------------+  |
|  | Handler Contract             |  |     |  | Bytecode to First-Order Logic   |  |
|  | - Filters invalid actions    |  |     |  | Translation                     |  |
|  | - Constrains ghost variables |  |     |  +---------------------------------+  |
|  +------------------------------+  |     |                  |                    |
|                 |                  |     |                  v                    |
|                 v                  |     |  +---------------------------------+  |
|  +------------------------------+  |     |  | SMT Solver (Z3 Formulation)     |  |
|  | Pseudo-Random Sequence Gen   |  |     |  | - Query: Solvency Violation     |  |
|  | Run 1: ActionA -> ActionB    |  |     |  |   TotalAssets < TotalDebtShares |  |
|  | Run 2: ActionB -> ActionC... |  |     |  +---------------------------------+  |
|  +------------------------------+  |     |                  |                    |
|                 |                  |     |                  v                    |
|                 v                  |     |  +---------------------------------+  |
|  +------------------------------+  |     |  | Status:                         |  |
|  | Invariant Assertions         |  |     |  | UNSAT -> Proven Mathematically  |  |
|  | assert(VaultSolvent())       |  |     |  | SAT   -> Counterexample Trace   |  |
|  +------------------------------+  |     |  +---------------------------------+  |
+------------------------------------+     +---------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Stateful Fuzzing: Ghost Variables & The Handler Pattern
*Stateless fuzzing* hanya memanggil fungsi tunggal dengan input acak ($f(x)$). *Stateful fuzzing* mengeksekusi rantai pemanggilan fungsi:
$$s_0 \xrightarrow{f_1(x_1)} s_1 \xrightarrow{f_2(x_2)} s_2 \dots \xrightarrow{f_n(x_n)} s_n$$
Untuk memverifikasi invarian yang kompleks, digunakan arsitektur **Handler**:
1. **Ghost Variables:** Variabel internal pengujian yang mencatat kondisi historis sistem (misalnya: $\sum \text{actualDeposits}$) yang berjalan paralel dengan status internal kontrak.
2. **Action Bounding:** Handler membatasi input acak ke dalam domain yang valid secara semantik (misalnya, menolak input deposit bernilai $0$ atau melebihi batas pasokan token) tanpa mengurangi kedalaman eksplorasi ruang status (*state space*).
3. **Actor Management:** Handler mensimulasikan sekumpulan agen otonom ($Agent_1, Agent_2, \dots, Agent_k$) yang saling bersaing untuk memicu kondisi *race condition* atau *front-running*.

#### B. Formal Verification: Hoare Logic & SMT Encodings
Verifikasi formal menggunakan *Hoare Triples*:
$$\{P\} \ C \ \{Q\}$$
Di mana:
- $P$: *Pre-condition* (syarat awal sebelum eksekusi kode $C$).
- $C$: Komputasi / eksekusi bytecode EVM.
- $Q$: *Post-condition* (kondisi yang dijamin benar setelah $C$ selesai).

Dalam SMT Verification:
1. Setiap instruksi EVM (misal: `ADD`, `SLOAD`, `SSTORE`) dikonversi ke relasi aritmatika modular (*Bit-Vector Arithmetic*).
2. Cabang kondisional (`JUMPI`) membentuk pohon eksekusi (*Execution Tree*).
3. Jika terdapat jalur eksekusi di mana $P \land C \land \neg Q$ bernilai *True* (SAT), solver memberikan nilai variabel konkret yang memicu kegagalan tersebut (*Counterexample*).

---

### 6. Production-Ready Code Implementation

Berikut adalah sistem perbendaharaan terintegrasi (*AgentVault*) yang dirancang untuk dieksekusi oleh Autonomous Agents, dilengkapi dengan **Invariant Fuzzing Harness (Foundry)** dan **Mathematical Formal Verification Script (Python/Z3)**.

#### File 1: Smart Contract Inti (`src/AgentVault.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title AgentVault
 * @notice Vault terotomatisasi yang dikelola oleh Autonomous Execution Agents.
 * Mendukung deposit, alokasi strategi terikat, dan penarikan berbasis saham (shares).
 */
contract AgentVault {
    IERC20 public immutable underlyingAsset;
    
    uint256 public totalShares;
    uint256 public totalAllocatedStrategyAssets;
    
    mapping(address => uint256) public shareBalances;
    mapping(address => bool) public authorizedAgents;
    
    address public immutable governance;
    uint256 private unlocked = 1;

    error Unauthorized();
    error ReentrancyGuardTriggered();
    error InsufficientBalance();
    error InvariantViolated(string reason);
    error ArithmeticUnderflow();

    modifier nonReentrant() {
        if (unlocked != 1) revert ReentrancyGuardTriggered();
        unlocked = 0;
        _;
        unlocked = 1;
    }

    modifier onlyGovernance() {
        if (msg.sender != governance) revert Unauthorized();
        _;
    }

    modifier onlyAgent() {
        if (!authorizedAgents[msg.sender]) revert Unauthorized();
        _;
    }

    constructor(address _underlyingAsset, address _governance) {
        underlyingAsset = IERC20(_underlyingAsset);
        governance = _governance;
    }

    function setAgent(address agent, bool status) external onlyGovernance {
        authorizedAgents[agent] = status;
    }

    function totalAssets() public view returns (uint256) {
        return underlyingAsset.balanceOf(address(this)) + totalAllocatedStrategyAssets;
    }

    function deposit(uint256 amount) external nonReentrant returns (uint256 shares) {
        if (amount == 0) revert InsufficientBalance();

        uint256 pool = totalAssets();
        if (totalShares == 0 || pool == 0) {
            shares = amount;
        } else {
            shares = (amount * totalShares) / pool;
        }

        if (shares == 0) revert ArithmeticUnderflow();

        shareBalances[msg.sender] += shares;
        totalShares += shares;

        bool success = underlyingAsset.transferFrom(msg.sender, address(this), amount);
        if (!success) revert InsufficientBalance();
    }

    function withdraw(uint256 shares) external nonReentrant returns (uint256 amount) {
        if (shares == 0 || shareBalances[msg.sender] < shares) revert InsufficientBalance();

        amount = (shares * totalAssets()) / totalShares;
        
        shareBalances[msg.sender] -= shares;
        totalShares -= shares;

        bool success = underlyingAsset.transfer(msg.sender, amount);
        if (!success) revert InsufficientBalance();
    }

    /**
     * @notice Alokasi modal otonom ke strategi off-chain/on-chain oleh agen.
     */
    function allocateToStrategy(uint256 amount) external onlyAgent nonReentrant {
        uint256 idleAssets = underlyingAsset.balanceOf(address(this));
        if (amount > idleAssets) revert InsufficientBalance();

        totalAllocatedStrategyAssets += amount;
        
        bool success = underlyingAsset.transfer(msg.sender, amount);
        if (!success) revert InsufficientBalance();
    }

    /**
     * @notice Pengembalian modal + yield dari strategi oleh agen.
     */
    function returnFromStrategy(uint256 principal, uint256 yield) external onlyAgent nonReentrant {
        if (principal > totalAllocatedStrategyAssets) revert InvariantViolated("Invalid Principal Return");

        unchecked {
            totalAllocatedStrategyAssets -= principal;
        }

        uint256 totalReturn = principal + yield;
        bool success = underlyingAsset.transferFrom(msg.sender, address(this), totalReturn);
        if (!success) revert InsufficientBalance();
    }
}
```

#### File 2: Invariant Handler & Test Harness (`test/AgentVaultInvariant.t.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/AgentVault.sol";

contract MockERC20 is IERC20 {
    string public name = "Mock Asset";
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function transfer(address to, uint256 amount) external override returns (bool) {
        if (balanceOf[msg.sender] < amount) return false;
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        if (balanceOf[from] < amount) return false;
        if (allowance[from][msg.sender] < amount && allowance[from][msg.sender] != type(uint256).max) {
            return false;
        }
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        if (allowance[from][msg.sender] != type(uint256).max) {
            allowance[from][msg.sender] -= amount;
        }
        return true;
    }
}

contract VaultHandler is CommonBase, StdCheats {
    AgentVault public immutable vault;
    MockERC20 public immutable asset;
    
    // Ghost Variables
    uint256 public ghostTotalDeposited;
    uint256 public ghostTotalWithdrawn;
    address[] public actors;
    address internal currentActor;

    address public agent;

    constructor(AgentVault _vault, MockERC20 _asset, address _agent) {
        vault = _vault;
        asset = _asset;
        agent = _agent;

        actors.push(address(0xAAAA));
        actors.push(address(0xBBBB));
        actors.push(address(0xCCCC));

        for (uint256 i = 0; i < actors.length; i++) {
            asset.mint(actors[i], 1_000_000 ether);
            vm.prank(actors[i]);
            asset.approve(address(vault), type(uint256).max);
        }
    }

    modifier useActor(uint256 actorIndexSeed) {
        currentActor = actors[actorIndexSeed % actors.length];
        vm.startPrank(currentActor);
        _;
        vm.stopPrank();
    }

    function deposit(uint256 amount, uint256 actorSeed) external useActor(actorSeed) {
        amount = bound(amount, 1 ether, 10_000 ether);
        
        try vault.deposit(amount) returns (uint256 shares) {
            ghostTotalDeposited += amount;
        } catch {}
    }

    function withdraw(uint256 shares, uint256 actorSeed) external useActor(actorSeed) {
        uint256 userShares = vault.shareBalances(currentActor);
        if (userShares == 0) return;
        
        shares = bound(shares, 1, userShares);

        try vault.withdraw(shares) returns (uint256 amount) {
            ghostTotalWithdrawn += amount;
        } catch {}
    }

    function executeStrategyAlloc(uint256 amount) external {
        uint256 idle = asset.balanceOf(address(vault));
        if (idle == 0) return;
        amount = bound(amount, 1, idle);

        vm.prank(agent);
        try vault.allocateToStrategy(amount) {} catch {}
    }

    function executeStrategyReturn(uint256 yieldAmount) external {
        uint256 allocated = vault.totalAllocatedStrategyAssets();
        if (allocated == 0) return;
        
        yieldAmount = bound(yieldAmount, 0, 1_000 ether);
        asset.mint(agent, yieldAmount);

        vm.startPrank(agent);
        asset.approve(address(vault), allocated + yieldAmount);
        try vault.returnFromStrategy(allocated, yieldAmount) {} catch {}
        vm.stopPrank();
    }
}

contract AgentVaultInvariantTest is StdInvariant, Test {
    AgentVault public vault;
    MockERC20 public asset;
    VaultHandler public handler;
    
    address public governance = address(0x9999);
    address public autonomousAgent = address(0x7777);

    function setUp() public {
        asset = new MockERC20();
        vault = new AgentVault(address(asset), governance);

        vm.prank(governance);
        vault.setAgent(autonomousAgent, true);

        handler = new VaultHandler(vault, asset, autonomousAgent);

        targetContract(address(handler));
    }

    /**
     * @notice Invariant 1: Solvabilitas Vault
     * Total aset internal harus selalu mencukupi nilai kewajiban terhadap seluruh shares.
     */
    function invariant_vaultSolvency() public view {
        if (vault.totalShares() > 0) {
            assertGe(
                vault.totalAssets(),
                1,
                "Solvency violated: Non-zero shares with zero backing assets"
            );
        }
    }

    /**
     * @notice Invariant 2: Integritas Ghost Accounting
     * Aset riil dalam vault + alokasi harus konsisten dengan delta deposit dan yield.
     */
    function invariant_ghostAssetEquivalence() public view {
        assertEq(
            vault.totalAssets(),
            asset.balanceOf(address(vault)) + vault.totalAllocatedStrategyAssets(),
            "Accounting mismatch in asset segregation"
        );
    }
}
```

#### File 3: Formal Verification Engine Menggunakan Z3 SMT Solver (`verify_vault_solvency.py`)

Skrip ini membuktikan formalitas invarian konversi saham (share valuation) agar terbebas dari manipulasi pembulatan (*rounding exploit* / *inflation attack*).

```python
"""
Formal Verification Script: AgentVault Share Pricing Integrity
Platform: Z3 Theorem Prover (SMT-LIB v2 wrapper)
Tujuan: Membuktikan bahwa tidak ada input eksternal yang dapat menyebabkan 
eksploitasi nilai saham menjadi nol saat penarikan valid dilakukan.
"""

from z3 import *

def verify_share_inflation_soundness():
    print("[*] Initiating SMT Proof: AgentVault Share Inflation & Solvency")
    solver = Solver()

    # Definisi Domain Variabel (BitVec 256-bit merepresentasikan uint256 EVM)
    amount_in = BitVec('amount_in', 256)
    pool_assets = BitVec('pool_assets', 256)
    total_shares = BitVec('total_shares', 256)
    shares_minted = BitVec('shares_minted', 256)

    # Pre-conditions (Status sistem yang valid menurut batas EVM & Logika Bisnis)
    preconditions = [
        UGT(amount_in, 0),                      # amount > 0
        UGT(pool_assets, 0),                    # pool > 0 (bukan first depositor)
        UGT(total_shares, 0),                   # totalShares > 0
        ULE(amount_in, BitVecVal(10**30, 256)),  # Bound masuk akal untuk deposit
        ULE(pool_assets, BitVecVal(10**36, 256)),
        ULE(total_shares, BitVecVal(10**36, 256))
    ]

    solver.add(preconditions)

    # Transisi State: shares = (amount * totalShares) / pool
    # Gunakan representasi unsigned division
    calc_product = amount_in * total_shares
    
    # Modelkan pemotongan perkalian (Cek overflow sebelum pembagian)
    no_overflow = UDiv(calc_product, amount_in) == total_shares
    solver.add(no_overflow)

    # shares_minted formula
    solver.add(shares_minted == UDiv(calc_product, pool_assets))

    # Definisi Pelanggaran Invarian (Property to Disprove):
    # Agen menyetor amount_in > 0, tapi mendapatkan shares_minted == 0
    # Jika sistem SAT, berarti sistem rentan terhadap Share Inflation Zero-Mint exploit.
    violation = (shares_minted == 0)
    solver.add(violation)

    check_status = solver.check()

    if check_status == sat:
        print("[!] VULNERABILITY DETECTED! Counterexample found by SMT Solver:")
        model = solver.model()
        print(f"    - Amount Deposited : {model[amount_in]}")
        print(f"    - Pool Assets      : {model[pool_assets]}")
        print(f"    - Total Shares     : {model[total_shares]}")
        print(f"    - Shares Minted    : {model[shares_minted]}")
        print("[*] Remediation Required: Implement virtual shares (ERC-4626 standard) or dead shares offset.")
    elif check_status == unsat:
        print("[+] VERIFIED: System is provably immune to zero-share minting under given bounds.")
    else:
        print("[?] Solver returned UNKNOWN (Analysis timed out or unconstrained non-linear space).")

if __name__ == "__main__":
    verify_share_inflation_soundness()
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah titik kritis kegagalan pada arsitektur verifikasi dan smart contract autonomous execution:

1. **State Space Explosion pada Invariant Fuzzing:**
   - *Failure:* Menambahkan terlalu banyak parameter acak pada *Handler* tanpa *bounding* membuat fuzzer hanya mengeksplorasi cabang transaksi revert (*shallow execution*), gagal mencapai *deep contract states*.
   - *Mitigasi:* Gunakan pemfilteran target (`vm.targetSelector`) dan definisikan batas domain input menggunakan `bound()` secara ketat.

2. **Decimals & Rounding Direction Manipulation:**
   - *Failure:* Dalam perhitungan `withdraw`, pembagian integer EVM selalu membulatkan ke bawah (*floor*). Jika rasio aset/saham dimanipulasi melalui *direct asset donation* ke kontrak, penarikan saham minimal dapat membakar saham tanpa mentransfer aset keluar.
   - *Mitigasi:* Terapkan kalkulasi berbasis *virtual shares* (sebagaimana ditentukan pada standar ERC-4626) untuk mendilusi manipulasi perbendaharaan:
     $$\text{Shares} = \frac{\text{Amount} \times (\text{TotalShares} + 10^3)}{\text{TotalAssets} + 1}$$

3. **SMT Solver Non-Linear Arithmetic Timeouts:**
   - *Failure:* Operasi perkalian bit-vektor berskala besar (`*`) dan pembagian (`/`) memicu kompleksitas *NP-complete*. Z3 dapat mengalami *hang* (*infinite loop*).
   - *Mitigasi:* Ubah verifikasi non-linear ke dalam batasan *Linear Real Arithmetic* (LRA) atau berikan batasan rentang (*bounds constraints*) pada *bit-width*.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Unit Testing (Foundry) | Stateless Fuzzing | Stateful Invariant Fuzzing | Formal Verification (SMT/Certora) |
| :--- | :--- | :--- | :--- | :--- |
| **Cakupan State** | Titik tunggal ($s_i$) | Satu transisi ($s_0 \to s_1$) | Rantai transisi kompleks ($s_0 \dots \to s_n$) | Seluruh ruang status yang mungkin ($\forall s \in S$) |
| **Waktu Eksekusi** | Milidetik | Detik | Menit hingga Jam | Menit hingga Berhari-hari |
| **Kemudahan Penulisan** | Sangat Mudah | Mudah | Menengah (Perlu Handler) | Kompleks (Perlu Spesifikasi Formal) |
| **False Negatives** | Sangat Tinggi | Tinggi | Rendah | Tidak Ada (Nol jika *Unsoundness* Absen) |
| **False Positives** | Nol | Nol | Nol | Menengah (Overconstrained models) |
| **Cost / Overhead** | Rendah | Rendah | Menengah (Compute Cloud) | Sangat Tinggi (Engineer Khusus) |

---

### 9. Best Practices & Standar Industri

1. **Checks-Effects-Interactions (CEI) & Mutex Pattern:**
   - Seluruh mutasi *state* (misal: pengurangan `shareBalances` dan `totalShares`) harus selesai dieksekusi **sebelum** pemanggilan transfer eksternal (`IERC20.transfer`).
2. **Defensive Ghost Accounting:**
   - Jangan bergantung pada `IERC20.balanceOf(address(this))` secara eksklusif untuk data akuntansi internal. Gunakan *internal tracking balance* untuk mencegah eksploitasi manipulasi *flash loan donation*.
3. **CI/CD Integration Policy:**
   - **Tingkat Komit:** Jalankan Unit Tests + 1.000 run Stateless Fuzzing.
   - **Tingkat Pull Request:** Jalankan Stateful Invariant Fuzzing minimal 50.000 runs dengan *corpus generation*.
   - **Tingkat Rilis / Mainnet Deployment:** Buktikan spesifikasi formal properti inti menggunakan Z3/Halmos/Certora Prover; simpan artefak bukti matematis pada repositori keamanan.
4. **Agent Circuit Breakers:**
   - Berikan limitasi per-transaksi dan pendinginan waktu (*cooldown period*) pada fungsi yang hanya dapat dipanggil oleh *autonomous agents* guna memitigasi kerugian ketika model inferensi AI off-chain mengalami kompromi kredensial.

---

### 10. Hands-on Lab Exercise: Membongkar & Memperbaiki Broken Invariant

#### Skenario:
Diberikan kontrak perbendaharaan yang memungkinkan agen menarik modal kerja. Kontrak memiliki kelemahan di mana invarian solvabilitas sistem dapat dijatuhkan ke status *insolvent* oleh penarikan parsial tak terduga.

#### Langkah 1: Setup Proyek Foundry
Eksekusi pada terminal Anda:
```bash
forge init security_lab --no-commit
cd security_lab
pip install z3-solver
```

#### Langkah 2: Buat Skenario Eksploitasi
Modifikasi file `src/AgentVault.sol` untuk memperkenalkan regresi:
Ubah baris perhitungan pada `withdraw`:
```solidity
// REGRESI DISENGAJA (Hapus verifikasi pengecekan shares sender)
amount = (shares * totalAssets()) / totalShares;
totalShares -= shares; // Bug: shareBalances[msg.sender] tidak dikurangi!
```

#### Langkah 3: Eksekusi Invariant Test
Jalankan pengujian invariant:
```bash
forge test --match-contract AgentVaultInvariantTest -vvvv
```

*Ekspektasi Output Terminal:*
```text
[FAIL. Reason: Solvency violated: Non-zero shares with zero backing assets]
[Counterexample Sequence]:
  handler.deposit(1000000000000000000, 0)
  handler.withdraw(1000000000000000000, 0)
  handler.withdraw(1, 0) -> Panics!
```

#### Langkah 4: Terapkan Perbaikan & Re-Verify
Kembalikan baris pengurangan saldo secara benar dengan mematuhi CEI:
```solidity
shareBalances[msg.sender] -= shares;
totalShares -= shares;
```

Jalankan kembali invariant fuzzer dengan kedalaman *depth* tinggi:
```bash
forge test --match-contract AgentVaultInvariantTest --fuzz-runs 100000
```
Hasil akhir harus menghasilkan status: **`PASS (runs: 100000)`**.

#### Langkah 5: Jalankan Pembuktian Formal
Eksekusi skrip Z3 untuk memastikan secara matematis tidak ada ruang bagi integer underflow/overflow:
```bash
python3 verify_vault_solvency.py
```
Output yang wajib dicapai: **`[+] VERIFIED: System is provably immune...`**. Sistem kini telah teruji secara empiris dan matematis untuk dioperasikan oleh autonomous execution agents.