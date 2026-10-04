# BAB 09: Desain Protokol DeFi & Interoperabilitas Cross-Chain
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Protokol DeFi Enterprise-Grade**: Mengembangkan arsitektur *liquidity pool* dan *lending market* yang tahan eksploitasi manipulasi oracle, reentrancy lintas fungsi, dan *economic drain attacks*.
- **Menguasai Protokol Komunikasi Cross-Chain (Arbitrary Messaging Bridges)**: Mengimplementasikan sistem pengiriman pesan lintas-rantai berbasis *generalized messaging* (seperti Chainlink CCIP dan LayerZero V2) dengan verifikasi kriptografis terdesentralisasi.
- **Mengintegrasikan Pola Transient Storage (EIP-1153)**: Menerapkan instruksi EVM Cancun (`TSTORE` dan `TLOAD`) untuk mengoptimalkan efisiensi gas pada mekanisme *flash loan* dan perlindungan reentrancy sementara.
- **Membangun Interaksi Agen Otonom (Autonomous Execution Layer)**: Merancang integrasi kontrak pintar dengan agen otonom (AI/bot eksekutor) berbasis Account Abstraction (ERC-4337) untuk arbitrase terotomatisasi dan likuidasi lintas-rantai berlatensi rendah.
- **Menganalisis Trade-Off Keamanan vs. Latensi Cross-Chain**: Menilai risiko arsitektur jembatan (*optimistic*, *light-client*, dan *multi-entity attestation*) terhadap kebutuhan likuiditas protokol.

---

### 2. Prerequisites

Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis pada:
- **Solidity Lanjutan**: Minimal v0.8.20+ (pemahaman *custom errors*, `immutable`, `assembly/Yul`, memory vs calldata vs storage management).
- **EVM Internals**: Mekanisme gas, slot penyimpanan (*storage packing*), eksekusi *call/delegatecall/staticcall*, dan siklus hidup transaksi.
- **DeFi Primitives**: Mekanika AMM (Constant Product, Concentrated Liquidity), Liquidity Pool, Flash Loans, Compound/Aave interest rate models.
- **Kriptografi Dasar Blockchain**: Merkle Trees, ECDSA signature verification, EIP-712 typed data hashing.
- **Tooling**: Foundry Framework (`forge`, `cast`, `anvil`) terpasang di mesin lokal.

---

### 3. Concept & Internal Architecture

Ekosistem DeFi multi-rantai modern beralih dari model *isolated liquidity* (likuiditas terfragmentasi di masing-masing layer) menuju *shared liquidity* dan *composable cross-chain execution*.

```
+-----------------------------------------------------------------------------------+
|                           DeFi Interoperability Stack                             |
+-----------------------------------------------------------------------------------+
| Layer 4: Application Layer     | Cross-Chain DEX, Omnichain Lending, Yield Routing |
| Layer 3: Agentic/MEV Layer     | Autonomous Arbitrage/Liquidation Bots (ERC-4337)  |
| Layer 2: Interoperability Bus  | Chainlink CCIP / LayerZero V2 / IBC               |
| Layer 1: Settlement & Storage  | Ethereum, Arbitrum, Optimism, Base (EVM Cancun)   |
+-----------------------------------------------------------------------------------+
```

#### A. Verifikasi Komunikasi Cross-Chain
Secara fundamental, protokol *messaging* lintas-rantai bekerja dengan membaca *state* dari Rantai Asal (Source Chain) dan merekonstruksi validitas eksekusinya di Rantai Tujuan (Destination Chain). Terdapat tiga paradigma verifikasi:

1. **Light-Client Verification (State Proofs)**: Rantai tujuan menjalankan modul *light client* dari rantai asal untuk memverifikasi Merkle-Patricia Proof atau ZK-Proof secara deterministik.
   - *Kelebihan*: *Trust-minimized* (tanpa ketergantungan pihak ketiga).
   - *Kelemahan*: Biaya komputasi on-chain sangat mahal, latensi tinggi.
2. **Optimistic Verification**: Transaksi cross-chain dianggap valid secara default kecuali ada agen pengawas (*watcher/challenger*) yang mengajukan *fraud proof* selama jendela waktu sanggahan (*challenge window*).
   - *Kelebihan*: Murah dari sisi komputasi harian.
   - *Kelemahan*: Finalitas likuiditas tertunda (contoh: 30 menit hingga 7 hari).
3. **Multi-Entity Attestation / Decentralized Oracle Networks (DON)**: Verifikasi dilakukan melalui komite validator off-chain atau jaringan oracle independen (seperti Chainlink Risk Management Network + CCIP) yang menandatangani pesan secara kuorum (*threshold signature*).
   - *Kelebihan*: Latensi rendah, biaya efisien, fleksibel untuk integrasi multi-chain instan.
   - *Kelemahan*: Membutuhkan asumsi kepercayaan kriptoekonomi terhadap kelompok validator.

#### B. Mekanisme Transient Storage (EIP-1153)
Pada protokol AMM dan Flash Loan mutakhir (misal: Uniswap v4), perubahan *state* selama transaksi atomik yang tidak perlu disimpan permanen dialihkan ke *transient storage* melalui opcode `TSTORE` (0x5c) dan `TLOAD` (0x5d). Data ini terhapus secara otomatis di akhir transaksi, memangkas biaya gas dari 20.000 gas (SSTORE slot kosong) menjadi hanya 100 gas per interaksi, sekaligus mengeliminasi celah *cross-function reentrancy* secara lebih murah dibanding modifikasi *state variable* penyimpanan permanen.

---

### 4. Why & What

- **Mengapa cross-chain DeFi rentan terhadap peretasan multi-juta dolar?**
  Peretasan jembatan historis (Nomad: $190M, Ronin: $624M, Wormhole: $326M) membuktikan bahwa celah keamanan jarang berada pada algoritma kriptografi murni, melainkan pada:
  - Validasi pesan kosong (*zero-hash initialization*).
  - Sentralisasi kunci relayer (*single point of failure*).
  - Ketidaksinkronan asumsi finalitas (*reorg* pada rantai asal sementara dana telah dicairkan pada rantai tujuan).
- **Apa solusi arsitektur tingkat produksi?**
  - Penerapan sistem verifikasi berlapis (*dual-validation layer*): Jaringan pengirim pesan independen dipadukan dengan jaringan manajemen risiko independen yang berwenang menahan (*pause*) eksekusi pesan anomali secara otomatis.
  - Implementasi desain *pull-based* atau *rate-limited bridging* yang membatasi nilai total transfer per interval waktu (circuit breaker).

---

### 5. How: Workflow Detail

Alur transaksi swap lintas-rantai (Omnichain AMM) menggunakan arsitektur verifikasi terdistribusi:

```
[User/Agent]
    │  1. Inisiasi swapAndBridge()
    ▼
[Source Router Contract] 
    │  2. Kunci/Burn Token lokal & Lock Transient Lock
    │  3. Encode payload instruksi eksekusi di rantai tujuan
    ▼
[Messaging On-Ramp (CCIP/LZero)]
    │  4. Emit event 'MessageSent' dengan Merkle Leaf Hash
    ▼
┌──────────────────────────────────────────────────────────┐
│ OFF-CHAIN LAYER                                          │
│   ├── Oracle/Relayer Network: Baca event, tunggu N konfirmasi
│   └── Risk/Watcher Engine: Analisis anomali volume & gas │
│   └── Sign State Update / Construct Merkle Proof         │
└──────────────────────────────────────────────────────────┘
    │  5. Submit commit & report proofs
    ▼
[Destination Messaging Off-Ramp]
    │  6. Verifikasi kuorum tanda tangan & integritas root
    ▼
[Destination Receiver Contract]
    │  7. Validasi format pesan & whitelist sender
    │  8. Mint/Unlock token sintetis atau swap via DEX lokal
    │  9. Transfer token akhir ke alamat penerima
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan Anda ingin mentransfer uang dari Bank Alpha di Negara X ke Bank Beta di Negara Y tanpa adanya korespondensi bank tunggal. Anda menyerahkan uang fisik ke Brankas Safe Deposit di Alpha (Burn/Lock), kasir Alpha mengeluarkan surat berharga bersegel hologram. Dua kurir independen dari perusahaan keamanan berbeda (Relayer & Independent Risk Oracle) harus memverifikasi nomor seri segel tersebut di kantor perbatasan. Jika kedua tanda tangan kurir cocok dan lolos verifikasi pabean (Circuit Breaker), brankas cabang di Negara Y mencairkan dana lokal yang setara ke rekening Anda.

#### Diagram Arsitektur State Execution

```
+--------------------------------------------------------------------+
|                         SOURCE CHAIN (EVM)                         |
|  +------------------+      +------------------+                    |
|  |   Caller/Agent   | ---> |  OmnichainVault  | (Locks Underlying) |
|  +------------------+      +------------------+                    |
|                                     │                              |
|                                     ▼                              |
|                            +------------------+                    |
|                            |   Router OnRamp  | (Packs Payload)    |
|                            +------------------+                    |
+--------------------------------------------------------------------+
                                      │
                         [Generalized Bridge Bus]
                   (Encrypted Attestation & Relaying)
                                      │
+--------------------------------------------------------------------+
|                       DESTINATION CHAIN (EVM)                      |
|                            +------------------+                    |
|                            |  Router OffRamp  | (Verifies Signatures)|
|                            +------------------+                    |
|                                     │                              |
|                                     ▼                              |
|  +------------------+      +------------------+                    |
|  |   Beneficiary    | <--- | ReceiverConsumer | (Executes Swap/    |
|  +------------------+      +------------------+  Rebalances Pool)  |
+--------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Implementasi Lanjutan: Cross-Chain Token & Instruction Receiver dengan Perlindungan Transient Reentrancy

Berikut adalah implementasi smart contract production-grade berbasis Solidity 0.8.24 yang memanfaatkan `EIP-1153` untuk efisiensi proteksi reentrancy dan mengonsumsi pesan cross-chain secara aman.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {ReentrancyGuardTransient} from "./ReentrancyGuardTransient.sol";

interface ICrossChainRouter {
    function getSourceChainConfig(uint64 chainSelector) external view returns (bool isAllowed, address authorizedSender);
}

/// @title OmnichainLiquidityReceiver
/// @notice Menangani payload likuiditas cross-chain dengan perlindungan transient storage & circuit breaker
contract OmnichainLiquidityReceiver is Ownable2Step, ReentrancyGuardTransient {
    using SafeERC20 for IERC20;

    // Error Definitions (Gas Optimization)
    error UnauthorizedRouter(address caller);
    error UnauthorizedSourceChain(uint64 chainSelector);
    error UnauthorizedSourceSender(address sender);
    error ExceedsCircuitBreaker(uint256 requested, uint256 limit);
    error ExecutionFailed();

    // Structs
    struct MessagePayload {
        address recipient;
        address token;
        uint256 amount;
        bytes actionData;
    }

    // State Variables
    address public immutable i_bridgeRouter;
    uint256 public volumeHourlyLimit;
    uint256 public currentHourlyVolume;
    uint256 public lastHourlyReset;

    mapping(uint64 => bool) public allowedChains;
    mapping(uint64 => address) public trustedRemotes;

    event MessageExecuted(bytes32 indexed messageId, address indexed recipient, uint256 amount);
    event CircuitBreakerTripped(uint256 requested, uint256 available);

    modifier onlyRouter() {
        if (msg.sender != i_bridgeRouter) revert UnauthorizedRouter(msg.sender);
        _;
    }

    constructor(address bridgeRouter, uint256 initialHourlyLimit) Ownable2Step() {
        require(bridgeRouter != address(0), "Zero router address");
        i_bridgeRouter = bridgeRouter;
        volumeHourlyLimit = initialHourlyLimit;
        lastHourlyReset = block.timestamp;
    }

    function setTrustedRemote(uint64 chainSelector, address remoteSender, bool allowed) external onlyOwner {
        allowedChains[chainSelector] = allowed;
        trustedRemotes[chainSelector] = remoteSender;
    }

    function setHourlyLimit(uint256 newLimit) external onlyOwner {
        volumeHourlyLimit = newLimit;
    }

    /// @notice Menerima dan mengeksekusi pesan masuk dari bridge
    /// @dev Menggunakan transient reentrancy guard untuk menekan biaya eksekusi
    function receiveCrossChainExecution(
        bytes32 messageId,
        uint64 sourceChainSelector,
        address sourceSender,
        bytes calldata payload
    ) external onlyRouter nonReentrantTransient {
        // 1. Validasi Autentikasi Pengirim Lintas Rantai
        if (!allowedChains[sourceChainSelector]) revert UnauthorizedSourceChain(sourceChainSelector);
        if (trustedRemotes[sourceChainSelector] != sourceSender) revert UnauthorizedSourceSender(sourceSender);

        // 2. Decode Payload
        MessagePayload memory data = abi.decode(payload, (MessagePayload));

        // 3. Circuit Breaker Mechanism (Rate Limiting)
        _verifyAndUpdateRateLimit(data.amount);

        // 4. State Execution (Release asset/Lakukan Swap)
        IERC20(data.token).safeTransfer(data.recipient, data.amount);

        // 5. Eksekusi instruksi arbitrer secara terproteksi jika tersedia
        if (data.actionData.length > 0) {
            (bool success, ) = data.recipient.call(data.actionData);
            if (!success) revert ExecutionFailed();
        }

        emit MessageExecuted(messageId, data.recipient, data.amount);
    }

    function _verifyAndUpdateRateLimit(uint256 amount) internal {
        if (block.timestamp >= lastHourlyReset + 1 hours) {
            currentHourlyVolume = amount;
            lastHourlyReset = block.timestamp;
        } else {
            if (currentHourlyVolume + amount > volumeHourlyLimit) {
                revert ExceedsCircuitBreaker(amount, volumeHourlyLimit - currentHourlyVolume);
            }
            currentHourlyVolume += amount;
        }
    }
}
```

#### Transient Storage Reentrancy Guard (EIP-1153)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title ReentrancyGuardTransient
/// @notice Proteksi Reentrancy modern memanfaatkan Opcode TSTORE dan TLOAD (EIP-1153)
abstract contract ReentrancyGuardTransient {
    // Slot transient sembarang yang unik untuk guard
    bytes32 private constant REENTRANCY_SLOT = keccak256("guard.transient.reentrancy");

    error ReentrantCallDetected();

    modifier nonReentrantTransient() {
        assembly {
            // Cek apakah slot bernilai 1 (terkunci)
            if tload(REENTRANCY_SLOT) {
                // Revert jika terjadi reentrancy
                mstore(0x00, 0x371303c0) // signature selector ReentrantCallDetected()
                revert(0x1c, 0x04)
            }
            // Kunci: simpan nilai 1 di transient storage
            tstore(REENTRANCY_SLOT, 1)
        }
        _;
        assembly {
            // Buka kunci kembali: simpan 0
            tstore(REENTRANCY_SLOT, 0)
        }
    }
}
```

---

### 8. Real World Case Study: Multi-Chain Liquidity Drainage (Nomad Bridge Exploit Analysis)

#### Post-Mortem Kasus Nomad Bridge (Agustus 2022 - Kerugian ~$190 Juta)
- **Akar Masalah**: Selama pembaruan kontrak pintar (*upgrade* implementation via proxy), tim Nomad menginisialisasi parameter *trusted root* default sebagai `0x00`.
- **Eksploitasi**: Komponen `Replica.sol` Nomad memvalidasi bukti (*proof*) transaksi dengan membandingkan pesan dengan variabel root. Di dalam kodenya:
  ```solidity
  // Buggy Logic:
  function acceptableRoot(bytes32 _root) public view returns (bool) {
      if (_root == 0) return true; // Celah fatal: 0x0 disahkan sebagai valid secara default
      return confirmAt[_root] > 0 && block.timestamp >= confirmAt[_root];
  }
  ```
- **Dampak Penularan**: Karena *zero-hash* dianggap sah, penyerang cukup menyalin transaksi penyerang pertama, mengganti alamat penerima menjadi milik mereka sendiri, dan memutar ulang (*replay*) transaksi tersebut langsung ke kontrak penampung dana di Ethereum tanpa perlu menghasilkan signature atau proof yang valid.
- **Solusi Arsitektural Enterprise**:
  1. Jangan pernah menetapkan sentinel value bernilai zero hash (`0x0`) sebagai state valid.
  2. Implementasikan pola **Strict Identity Affirmation**: Root harus eksplisit terdaftar dan berada dalam window *timelock* aktif.
  3. Menerapkan desentralisasi permissionless watcher yang memiliki hak menonaktifkan (*unpause/freeze*) modul bridge seketika jika volume out-of-flow melebihi ambang batas toleransi statistik.

---

### 9. Trade-offs

| Dimensi Arsitektur | Model Light-Client (ZK / Merkle) | Model Multi-Entity (CCIP / LZero) | Model Optimistic (Frauds) |
| :--- | :--- | :--- | :--- |
| **Security / Trust** | Maksimal (*Zero-Knowledge/Math*) | Bergantung pada kolusi Relayer/Oracle | Tinggi (selama ada 1 *honest watcher*) |
| **Finality Latency** | Menengah (tergantung generasi proof) | Sangat Cepat (Detik - Menit) | Sangat Lambat (Bisa 1 - 7 hari) |
| **Gas Cost Execution**| Sangat Tinggi (Verifikasi proof on-chain) | Moderat | Rendah pada kondisi normal, Tinggi jika sengketa |
| **Capital Efficiency**| Rendah (Liquidity terikat latensi proof) | Maksimal (Likuiditas segera cair) | Rendah (Pool likuiditas butuh LP intermediari) |

---

### 10. Common Mistakes & Troubleshooting

1. **Unchecked Cross-Chain Message Sender (`msg.sender` vs `sourceSender`)**
   - *Salah*: Memvalidasi `msg.sender` langsung sebagai pembuat transaksi asli dari source chain.
   - *Penyebab*: `msg.sender` pada rantai tujuan selalu berupa kontrak *Bridge Off-Ramp/Relayer*.
   - *Perbaikan*: Dekode payload pengirim asli (`sourceSender`) dari callback function bridge interface yang terverifikasi.
2. **Missing Chain ID Validation (Replay Across Chains)**
   - *Salah*: Merancang payload transaksi tanpa menyematkan `chainId` target.
   - *Penyebab*: Pesan dapat disiarkan ulang (*cross-chain replay attack*) ke rantai lain di mana pengguna memiliki kontrak yang sama.
   - *Perbaikan*: Selalu gunakan EIP-712 domain separator yang menyertakan variabel `block.chainid` unik.
3. **Price Oracle Manipulation via AMM Spot Reserves**
   - *Salah*: Mengambil harga aset untuk likuidasi lintas-rantai dari nilai cadangan `x * y = k` instan (spot price).
   - *Solusi*: Wajib gunakan integrasi TWAP (Time-Weighted Average Price) multi-interval atau orakel terdesentralisasi off-chain ber-latensi rendah (Chainlink/Pyth Core) dengan validasi *heartbeat* dan *deviation threshold*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Dual-Role Pause Control**: Memiliki sistem darurat berjenjang: Sentinel AI Bot hanya dapat mengunci protokol (*pause-only*), sedangkan multisig DAO memegang hak eksklusif membuka kunci (*unpause*).
- [ ] **Sanity Bound Check on Slippage**: Batasi parameter slippage dinamis yang disediakan oleh bot otonom (maksimal toleransi 3-5% tergantung volatilitas token).
- [ ] **Reentrancy Protection**: Seluruh method *external payable* dan pengirim token wajib mengimplementasikan `ReentrancyGuard` (atau Transient Storage variant EIP-1153).
- [ ] **Rate Limiting Engine**: Terapkan limit volume transfer berdasarkan nilai USD per jam/blok (Circuit Breaker).
- [ ] **Automated Fuzzing & Invariant Testing**: Kontrak telah teruji minimal 100.000 run invariant checks via Foundry/Echidna untuk memastikan invariansi saldo kolateral $\ge$ total utang.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── foundry.toml
├── src/
│   ├── OmnichainLiquidityReceiver.sol
│   ├── ReentrancyGuardTransient.sol
│   └── interfaces/
│       └── ICrossChainRouter.sol
├── test/
│   ├── OmnichainReceiver.t.sol
│   └── mocks/
│       ├── MockERC20.sol
│       └── MockRouter.sol
```

#### Langkah-langkah Praktikum:

1. **Inisialisasi Proyek Foundry**:
   ```bash
   mkdir -p hands-on/m02 && cd hands-on/m02
   forge init --no-commit
   forge install OpenZeppelin/openzeppelin-contracts --no-commit
   ```

2. **Konfigurasi `foundry.toml` untuk EVM Cancun**:
   ```toml
   [profile.default]
   src = "src"
   out = "out"
   libs = ["lib"]
   evm_version = "cancun"
   solc_version = "0.8.24"
   optimizer = true
   optimizer_runs = 200
   ```

3. **Buat file Mock dan Test Suite**:
   Tuliskan kode pengujian di `test/OmnichainReceiver.t.sol`:
   ```solidity
   // SPDX-License-Identifier: MIT
   pragma solidity 0.8.24;

   import "forge-std/Test.sol";
   import "../src/OmnichainLiquidityReceiver.sol";
   import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

   contract MockToken is ERC20 {
       constructor() ERC20("Mock USD", "mUSD") {
           _mint(msg.sender, 1_000_000e18);
       }
   }

   contract OmnichainReceiverTest is Test {
       OmnichainLiquidityReceiver receiver;
       MockToken token;
       address router = address(0xAA11);
       address alice = address(0xB0B);
       uint64 constant SOURCE_CHAIN = 16015286601757825753; // Contoh selector Arbitrum Sepolia
       address constant SOURCE_SENDER = address(0xDEAF);

       function setUp() public {
           token = new MockToken();
           receiver = new OmnichainLiquidityReceiver(router, 10_000e18);
           
           // Setup Trust
           receiver.setTrustedRemote(SOURCE_CHAIN, SOURCE_SENDER, true);
           
           // Fund Receiver with Liquidity
           token.transfer(address(receiver), 50_000e18);
       }

       function test_SuccessfulCrossChainTransfer() public {
           bytes memory payload = abi.encode(
               OmnichainLiquidityReceiver.MessagePayload({
                   recipient: alice,
                   token: address(token),
                   amount: 500e18,
                   actionData: ""
               })
           );

           vm.prank(router);
           receiver.receiveCrossChainExecution(bytes32(uint256(1)), SOURCE_CHAIN, SOURCE_SENDER, payload);

           assertEq(token.balanceOf(alice), 500e18);
       }

       function test_RevertWhen_RateLimitExceeded() public {
           bytes memory payload = abi.encode(
               OmnichainLiquidityReceiver.MessagePayload({
                   recipient: alice,
                   token: address(token),
                   amount: 15_000e18, // Melebihi batasan 10,000
                   actionData: ""
               })
           );

           vm.prank(router);
           vm.expectRevert();
           receiver.receiveCrossChainExecution(bytes32(uint256(2)), SOURCE_CHAIN, SOURCE_SENDER, payload);
       }
   }
   ```

4. **Eksekusi Pengujian**:
   ```bash
   forge test -vvvv
   ```

---

### 13. Exercise

#### Level Easy
Implementasikan fungsi view `getAvailableHourlyCapacity()` pada kontrak `OmnichainLiquidityReceiver` yang mengembalikan sisa kapasitas volume transfer yang diizinkan untuk jendela waktu saat ini secara presisi.

#### Level Medium
Tambahkan mekanisme *Emergency Graceful Degradation*: Jika laju harga oracle mati (*stale* lebih dari 3600 detik) atau volume mencurigakan terjadi, kontrak secara otomatis menurunkan batas transfer menjadi maksimal $500 per eksekusi dan mengalihkan status ke *Degraded Mode*.

#### Level Hard
Buat implementasi *Atomic Cross-Chain Flash-Borrow-Repay Mechanism*: Rancang kontrak yang dapat menerima pinjaman *flash-loan* di Rantai A, mengirim instruksi swap arbitrase ke Rantai B melalui payload CCIP, dan mengembalikan pinjaman pokok beserta bunga di Rantai A dalam parameter toleransi transaksi terkontrol (mensimulasikan kegagalan atomik via fallback relayer).

---

### 14. Challenge

**Skenario**: Anda adalah Lead Protocol Architect untuk sebuah Omnichain Money Market. Buatlah rancangan arsitektur dan smart contract untuk sistem **Autonomous Liquidation Protection**.
- **Kondisi**: Pengguna memiliki jaminan aset di Polygon dan utang di Arbitrum. Jika rasio kesehatan (*Health Factor*) akun jatuh di bawah 1.05:
  1. Kontrak di Arbitrum harus mengizinkan AI Agent / Keeper bot yang terotorisasi untuk memicu sinyal likuidasi darurat.
  2. Sinyal dikirimkan lintas-rantai untuk menyita kolateral di Polygon.
  3. Sistem harus menerapkan *Flash-Repayment* untuk melunasi utang di Arbitrum seketika menggunakan likuiditas kolateral yang ditarik, terlindung dari *front-running* dan *sandwich attack* (MEV).
  4. Seluruh proses harus menangani skenario jika eksekusi pesan lintas-rantai gagal atau mengalami reorganisasi blok (*chain reorg*).

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan mendasar antara opcode Cancun `TSTORE` (EIP-1153) dan `SSTORE` standar dalam konteks siklus hidup transaksi DeFi?
2. Mengapa verifikasi `msg.sender` saja tidak cukup untuk mengamankan fungsi callback pada arsitektur bridge cross-chain?
3. Apa fungsi utama *Circuit Breaker* (Rate Limiter) pada kontrak penampung dana cross-chain?
4. Apa yang dimaksud dengan *challenge window* pada protokol jembatan berbasis *Optimistic Verification*?
5. Mengapa manipulasi harga berbasis Cadangan AMM (*Spot Price*) rentan dieksploitasi oleh penyerang yang memanfaatkan Flash Loans?

#### Pertanyaan Intermediate
6. Bagaimana cara mencegah eksploitasi *Cross-Chain Message Replay Attack* ketika sebuah protokol di-deploy pada beberapa rantai EVM dengan bytecode yang identik?
7. Jelaskan alur mitigasi kegagalan eksekusi (*graceful failure handling*) jika payload instruksi cross-chain gagal dijalankan pada Rantai Tujuan akibat kehabisan gas!
8. Apa kelemahan utama dari verifikasi lintas-rantai berbasis *Multi-Entity Attestation* jika dibandingkan dengan *Light-Client / ZK-Proof Verification*?
9. Jelaskan bagaimana integrasi Account Abstraction (ERC-4337) mempermudah agen otonom (AI Bots) dalam mengeksekusi likuidasi multi-transaksi secara atomik!
10. Pada skenario apa penundaan finalitas (*reorg window*) di Source Chain dapat menyebabkan kerugian likuiditas total pada protokol cross-chain bridge?

#### Skenario Kasus Produksi
11. **Skenario 1**: Sebuah protokol cross-chain lending mendapati bahwa relayer utama mereka mengalami *downtime* selama 45 menit saat terjadi crash pasar kripto mendadak. Posisi pinjaman bernilai jutaan dolar terancam *undercollateralized*. Tindakan arsitektural fail-safe apa yang harus disiapkan pada smart contract layer untuk menghadapi kondisi ini?
12. **Skenario 2**: Auditor keamanan menemukan bahwa fungsi `executeOperation()` pada receiver cross-chain Anda menggunakan `low-level call` tanpa memvalidasi *return value* dan *code execution gas limit*. Jelaskan serangan spesifik yang dapat diluncurkan oleh attacker untuk menguras token!
13. **Skenario 3**: Protokol AMM cross-chain Anda mengandalkan push-oracle dari Chainlink. Tiba-tiba terjadi volatilitas ekstrem yang menyebabkan biaya gas melonjak tinggi sehingga oracle node menunda pembaruan harga selama 2 jam (*heartbeat breach*). Bagaimana logika kontrak mendeteksi *staleness* ini dan tindakan defensif apa yang harus diambil secara terprogram?

---

### 16. Summary

- Protokol DeFi enterprise modern menuntut konvergensi antara komputasi efisien di Layer-1/Layer-2 (memanfaatkan EIP-1153 Cancun) dan komunikasi cross-chain yang *trust-minimized*.
- Kelemahan terbesar pada interoperabilitas lintas-rantai bukanlah enkripsi pesan, melainkan asumsi kepercayaan terhadap relayer, validasi batas input (seperti kasus Nomad), serta penanganan finalitas rantai (*chain reorg*).
- Desain arsitektur tangguh wajib mengadopsi prinsip *Defense-in-Depth*: Pembatasan volume (Rate Limiter), transient reentrancy guard, pemisahan mutlak hak akses sentinel bot vs tata kelola DAO, serta verifikasi ganda data pengirim (`sourceChainSelector` dan `sourceSender`).
- Kesiapan integrasi dengan Agen Otonom (Autonomous Execution Layer) menjadi diferensiasi penting dalam menjaga efisiensi likuidasi pasar secara deterministik di tengah fragmentasi likuiditas Web3.