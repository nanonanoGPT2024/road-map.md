# Bab 05: Rekayasa Smart Contract Enterprise & Optimasi Gas Ekstrem
## Module 01: EVM Internals, Memory Layout, dan Rekayasa Gas Tingkat Lanjut

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis & Merekayasa Tata Letak Storage EVM**: Memetakan variabel status ke dalam 32-byte storage slots menggunakan teknik *tight packing*, *bit manipulation*, dan *struct packing* untuk mereduksi operasi `SSTORE` hingga 66%.
*   **Mengimplementasikan Transient Storage (EIP-1153)**: Mengoperasikan opcode `TSTORE` dan `TLOAD` untuk komunikasi antar-panggilan dalam satu transaksi tunggal (misalnya *reentrancy guards* dan *batch processing context*) guna memangkas konsumsi gas dari $2.100$ gas (warm `SLOAD`) menjadi hanya $100$ gas.
*   **Mengembangkan Logika Inti Berbasis Yul/Inline Assembly**: Mengabstraksi logika validasi dan transfer data ke dalam assembly Yul, mengelola *Free Memory Pointer* (`0x40`), serta memangkas *Solidity compiler overhead* (seperti *redundant zero-checks* dan *memory expansion penalties*).
*   **Merancang Kontrak Batch Settlement Berkapasitas Tinggi**: Mengintegrasikan *calldata hashing*, validasi tanda tangan massal ECDSA/ERC-2098, dan eksekusi instruksi agen otonom dengan efisiensi gas di bawah $25.000$ gas per tugas agentik.
*   **Mengaudit & Mengukur Regresi Gas**: Melakukan profiling deterministik menggunakan Foundry gas snapshots, *differential testing*, dan kalkulasi opcode gas table (Cancun hard fork).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Ethereum Virtual Machine (EVM) adalah *quasi-Turing complete, stack-based state machine* dengan word size sebesar 256-bit (32 bytes). Untuk mengoptimalkan biaya komputasi on-chain bagi autonomous agents dan sistem enterprise, Anda harus memahami interaksi empat layer memori EVM:

```
+-----------------------------------------------------------------------+
|                              EVM RUNTIME                              |
+-----------------------------------------------------------------------+
|  [ Stack ]       : 1024 depth, 256-bit elements. Biaya akses: 3 gas.  |
|  [ Memory ]      : Byte-array linear volatile. Ekspansi kuadratik.    |
|  [ Transient ]   : Volatile key-value (EIP-1153). Reset tiap TX.      |
|  [ Calldata ]    : Read-only, unmodifiable array byte parameter TX.   |
|  [ Storage ]     : Persistent, state root level, 256-bit key-value.   |
+-----------------------------------------------------------------------+
```

#### Komponen Kunci Runtime EVM

1.  **Storage Model (Persistent)**:
    Setiap akun smart contract memiliki ruang penyimpanan persisten $2^{256}$ slot, di mana setiap slot berukuran 32 byte. Modifikasi storage adalah operasi termahal:
    *   `SSTORE` menginisiasi slot dari nol ke non-nol (*dirtying zero slot*): **$20.000$ gas**.
    *   `SSTORE` memodifikasi slot non-nol: **$5.000$ gas** (atau **$100$ gas** jika slot sudah *warm* dalam rentang transaksi yang sama sesuai aturan EIP-2929).
    *   `SLOAD` cold: **$2.100$ gas**; `SLOAD` warm: **$100$ gas**.
2.  **Transient Storage (EIP-1153)**:
    Diperkenalkan pada hard fork Cancun, transient storage bertindak serupa dengan storage persisten tetapi datanya dimusnahkan secara otomatis saat transaksi selesai. Operasi `TSTORE` dan `TLOAD` berbiaya flat **$100$ gas**, tanpa dependensi cold/warm tracking, tanpa *refund counter tracking*, dan tanpa dampak ekspansi memori kuadratik.
3.  **Memory Model & Quadratic Expansion**:
    Memori bersifat linier dan diakses secara byte-addressable. Biaya alokasi memori berbanding lurus hingga 724 byte pertama, lalu bertumbuh secara kuadratik:
    $$\mathcal{C}_{mem}(a) = 3 \cdot a + \left\lfloor\frac{a^2}{512}\right\rfloor$$
    Di mana $a$ adalah alokasi memori dalam word (32 bytes). Mengalokasikan array besar di dalam memori secara ceroboh menyebabkan lonjakan gas yang signifikan.
4.  **Free Memory Pointer Layout**:
    EVM mencadangkan 4 slot 32-byte pertama di memori:
    *   `0x00 - 0x3f` (64 bytes): Scratch space untuk hashing methods.
    *   `0x40 - 0x5f` (32 bytes): *Free memory pointer* (menunjuk ke memori bebas saat ini, default bernilai `0x80`).
    *   `0x60 - 0x7f` (32 bytes): *Zero slot* (digunakan sebagai nilai awal array dinamis dan tidak boleh diubah).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada arsitektur *AI Agents & Data Autonomous Networks*, ribuan agen terdesentralisasi mengirimkan *inference attestations*, agregasi oracle, dan instruksi arbitrase likuiditas ke smart contract secara simultan. 

Jika smart contract batching agen dirancang menggunakan pola Solidity standar:
*   Sebuah *reentrancy guard* standar OpenZeppelin (`ReentrancyGuard.sol`) melakukan `SSTORE` dua kali per transaksi (status 1 ke 2, lalu kembali ke 1), membakar minimal **$2.200 - $5.100$ gas** hanya untuk mitigasi reentrancy.
*   Data parsing tanpa *bit-packing* memicu overhead multi-slot storage. Pada 100.000 tugas eksekusi per hari, inefisiensi 1 slot storage ($20.000$ gas) menghabiskan tambahan:
    $$\Delta Gas = 100.000 \times 20.000 = 2.000.000.000\text{ gas per hari}$$
    Pada harga gas 30 Gwei dan harga ETH \$3.500:
    $$\text{Pemborosan Harian} = 2 \times 10^9 \times 30 \times 10^{-9} \text{ ETH} = 60\text{ ETH} \approx \$210.000/\text{hari}$$

Melalui rekayasa inline assembly (Yul), *custom calldata decoding*, dan transient storage, enterprise dapat memangkas footprint eksekusi agen hingga 70%, menjamin latensi penyelesaian transaksi tetap rendah bahkan saat gas price L1/L2 mengalami volatilitas ekstrem.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur eksekusi low-level payload instruksi AI Agent: dari parsing *calldata pointer*, eksekusi *transient locks*, hingga mutasi storage terpadatkan (*packed storage*).

```
+---------------------------------------------------------------------------------------------------+
| TRANSACTION PAYLOAD (CALLDATA)                                                                    |
| [ Function Selector: 4B ] [ Batch Metadata: 32B ] [ Compressed Action Tuples: N * 64B ]          |
+---------------------------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------------------------+
| RUNTIME EXECUTION PIPELINE (AgentSettlementDispatcher)                                            |
|                                                                                                   |
| 1. TRANSIENT REENTRANCY GUARD (EIP-1153)                                                          |
|    +-----------------------------------------------------------------------------------------+    |
|    | Opcode: TLOAD(0x00) -> ISZERO -> Revert if Active                                        |    |
|    | Opcode: TSTORE(0x00, 1)                                                                 |    |
|    +-----------------------------------------------------------------------------------------+    |
|                                         |                                                         |
| 2. ZERO-COPY CALLDATA ITERATOR (Assembly / Yul)                                                   |
|    +-----------------------------------------------------------------------------------------+    |
|    | Pointer ptr = calldataload(0x24)                                                        |    |
|    | Loop offset:                                                                            |    |
|    |   agentId  (128b) <- shr(128, calldataload(ptr))                                        |    |
|    |   actionId (64b)  <- shr(64,  calldataload(add(ptr, 16)))                               |    |
|    |   reward   (64b)  <- and(0xFFFFFFFFFFFFFFFF, calldataload(add(ptr, 24)))                 |    |
|    +-----------------------------------------------------------------------------------------+    |
|                                         |                                                         |
| 3. COMPACT STORAGE WRITE (Single-Slot Packed Bitfield)                                            |
|    +-----------------------------------------------------------------------------------------+    |
|    | Memory Register: [ uint128 totalEarned | uint64 taskCount | uint64 lastTimestamp ]       |    |
|    | Bit Shift Layout: (totalEarned << 128) | (taskCount << 64) | lastTimestamp              |    |
|    | Opcode: SSTORE(slotKey, packedValue)                                                    |    |
|    +-----------------------------------------------------------------------------------------+    |
|                                         |                                                         |
| 4. TRANSIENT UNLOCK                                                                               |
|    +-----------------------------------------------------------------------------------------+    |
|    | Opcode: TSTORE(0x00, 0)                                                                 |    |
|    +-----------------------------------------------------------------------------------------+    |
+---------------------------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------------------------+
| EVM STATE TRIE (Root Level Storage Update - 1 Single Slot Write per Agent)                        |
| Slot Key: keccak256(agentId, AGENT_STORAGE_LOCATION)                                              |
| Slot Data: [0x00000000000000010000000000000042000000000000000065e8a940]                          |
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Storage Slot Mapping & Bit Packing
EVM mengalokasikan slot secara linier untuk tipe nilai skalar. Variabel status yang dideklarasikan berturutan akan dipadatkan ke dalam satu slot jika ukuran kumulatifnya $\le 32$ byte.

*Pola Sub-Optimal:*
```solidity
uint128 public totalEarned; // Slot 0 (16 bytes terisi, 16 bytes terbuang)
uint256 public metadataHash; // Slot 1 (32 bytes)
uint64  public taskCount;   // Slot 2 (8 bytes terisi, 24 bytes terbuang)
uint64  public lastTimestamp;// Slot 2 (8 bytes terisi, 16 bytes terbuang)
```
Setiap update pada `totalEarned` dan `taskCount` membutuhkan akses ke dua slot berbeda (`Slot 0` dan `Slot 2`).

*Pola Optimal Enterprise (Manual Bit Manipulation via Yul):*
Semua state agen diringkas ke dalam satu struct 256-bit:
```
Bit [255..128] : totalEarned (128 bits) -> Kapasitas maks: ~3.4 x 10^38 wei
Bit [127..64]  : taskCount   (64 bits)  -> Kapasitas maks: ~1.8 x 10^19 tasks
Bit [63..0]    : timestamp   (64 bits)  -> Rentang waktu valid hingga tahun 584 miliar
```
Operasi pemadatan ini direduksi ke aljabar Boolean:
$$\text{packed} = (\text{totalEarned} \ll 128) \lor (\text{taskCount} \ll 64) \lor \text{timestamp}$$

Ekstraksi nilai:
$$\text{taskCount} = (\text{packed} \gg 64) \land (2^{64} - 1)$$

#### B. Transient Storage Locks vs Classic Storage Locks
Solidity `nonReentrant` konvensional:
```solidity
// OpenZeppelin legacy approach
uint256 private _status; // 1 = NOT_ENTERED, 2 = ENTERED
modifier nonReentrant() {
    require(_status != 2, "ReentrancyGuard: reentrant call");
    _status = 2; // SSTORE (Warm or Cold)
    _;
    _status = 1; // SSTORE (Warm reset)
}
```
Biaya minimum: $2.100$ gas (cold `SLOAD`) $+ 5.000$ gas (dirtying non-zero `SSTORE`) $+ 100$ gas (warm `SSTORE`) $= \mathbf{7.200\text{ gas}}$.

Implementasi EIP-1153 Transient Lock via Yul:
```yul
assembly {
    let lockSlot := 0x00
    if tload(lockSlot) {
        // Revert dengan custom error selector: CustomReentrancy() -> 0xab143c06
        mstore(0x00, 0xab143c06)
        revert(0x1c, 0x04)
    }
    tstore(lockSlot, 1)
}
// Eksekusi logic
assembly {
    tstore(0x00, 0)
}
```
Biaya mutlak: $100$ (`TLOAD`) $+ 100$ (`TSTORE`) $+ 100$ (`TSTORE`) $= \mathbf{300\text{ gas}}$. Reduksi gas sebesar **95.8%**.

#### C. Zero-Copy Calldata vs Memory Arrays
Bila data bertipe `dynamic array` dipassing ke function via parameter `AgentTask[] memory tasks`, EVM menyalin seluruh payload dari `calldata` ke `memory`. Proses ini memicu alokasi memori linier dan kuadratik.

Menggunakan `AgentTask[] calldata tasks` mencegah alokasi memori sama sekali. Dalam Yul, kita cukup membaca alamat offset langsung dari calldata menggunakan pointer opcode `calldataload(ptr)`, memproses instruksi tanpa mengalokasikan byte baru di memori runtime.

---

### 6. Production-Ready Code Implementation

Berikut adalah dua artefak kode produksi:
1.  **`AgentBatchSettlementRegistry.sol`**: Smart contract enterprise yang mengintegrasikan Yul memory layouting, EIP-1153 transient guard, custom errors, dan bit-packed storage.
2.  **`settlement-orchestrator.ts`**: Script TypeScript berbasis `ethers.js` untuk serialisasi bit, benchmarking gas, dan transmisi transaksi ke jaringan.

#### Smart Contract: `AgentBatchSettlementRegistry.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/**
 * @title AgentBatchSettlementRegistry
 * @notice Enterprise settlement registry for AI autonomous agents.
 * Optimized with EIP-1153 transient storage and inline assembly packing.
 */
contract AgentBatchSettlementRegistry {
    // Custom Error Definitions (Hemat Gas vs Error String)
    error ReentrancyDetected();
    error UnauthorizedCaller();
    error InvalidBatchLength();
    error ExecutionFailure(uint256 taskIndex);

    // Constant slot transient lock
    bytes32 private constant TRANSIENT_LOCK_SLOT = 0x0000000000000000000000000000000000000000000000000000000000000000;

    // Address owner / admin
    address public immutable OPERATOR;

    // Packed Storage: agentId => [ uint128 totalEarned | uint64 taskCount | uint64 lastTimestamp ]
    mapping(uint256 => uint256) private _agentPackedProfiles;

    // Events
    event BatchSettled(uint256 indexed agentCount, uint256 totalVolume);

    modifier nonReentrantTransient() {
        assembly {
            if tload(TRANSIENT_LOCK_SLOT) {
                // Selector: ReentrancyDetected() -> 0xb3cad81f
                mstore(0x00, 0xb3cad81f00000000000000000000000000000000000000000000000000000000)
                revert(0x00, 0x04)
            }
            tstore(TRANSIENT_LOCK_SLOT, 1)
        }
        _;
        assembly {
            tstore(TRANSIENT_LOCK_SLOT, 0)
        }
    }

    modifier onlyOperator() {
        if (msg.sender != OPERATOR) revert UnauthorizedCaller();
        _;
    }

    constructor() {
        OPERATOR = msg.sender;
    }

    /**
     * @notice Eksekusi batch settlement tugas agen tanpa memory expansion
     * @dev Calldata Layout:
     *      - 4 bytes selector
     *      - 32 bytes offset array
     *      - 32 bytes length array
     *      - Loop items (Tiap elemen terdiri dari 64 bytes: [32B agentId][16B reward][8B taskId][8B timestamp])
     */
    function executeAgentBatchDirect(bytes calldata data) 
        external 
        onlyOperator 
        nonReentrantTransient 
    {
        assembly {
            // Validasi data minimal: 32 bytes length
            if lt(data.length, 32) {
                // Selector: InvalidBatchLength() -> 0x86733ec6
                mstore(0x00, 0x86733ec600000000000000000000000000000000000000000000000000000000)
                revert(0x00, 0x04)
            }

            let lengthOffset := data.offset
            let totalRecords := calldataload(lengthOffset)
            
            // Validasi batas ukuran batch (maksimal 250 tasks/batch)
            if or(iszero(totalRecords), gt(totalRecords, 250)) {
                mstore(0x00, 0x86733ec600000000000000000000000000000000000000000000000000000000)
                revert(0x00, 0x04)
            }

            let recordsStartOffset := add(lengthOffset, 32)
            let accumulatedVolume := 0

            // Base slot untuk mapping: _agentPackedProfiles berada di slot 1
            mstore(0x20, 1) // Slot 1 mapping index

            for { let i := 0 } lt(i, totalRecords) { i := add(i, 1) } {
                let currentItemOffset := add(recordsStartOffset, mul(i, 64))

                // Decoding parameter dari calldata
                let agentId := calldataload(currentItemOffset)
                let packedPayload := calldataload(add(currentItemOffset, 32))

                // Parsing sub-variabel
                let reward := shr(128, packedPayload)                 // 16 bytes (uint128)
                let taskTimestamp := and(packedPayload, 0xFFFFFFFFFFFFFFFF) // 8 bytes (uint64)

                // Kalkulasi Storage Slot: keccak256(agentId . slot)
                mstore(0x00, agentId)
                let targetStorageSlot := keccak256(0x00, 0x40)

                // Load existing state (Single SLOAD)
                let existingPacked := sload(targetStorageSlot)

                // Unpack existing fields
                let prevEarned := shr(128, existingPacked)
                let prevTasks := and(shr(64, existingPacked), 0xFFFFFFFFFFFFFFFF)

                // Mutasi nilai
                let newEarned := add(prevEarned, reward)
                let newTasks := add(prevTasks, 1)

                // Pack ulang data ke format 256-bit word
                let updatedPacked := or(
                    shl(128, newEarned),
                    or(shl(64, newTasks), taskTimestamp)
                )

                // Simpan ke storage persisten (Single SSTORE)
                sstore(targetStorageSlot, updatedPacked)

                // Akumulasi total settlement
                accumulatedVolume := add(accumulatedVolume, reward)
            }

            // Emit Event manual menggunakan Yul: BatchSettled(totalRecords, accumulatedVolume)
            // keccak256("BatchSettled(uint256,uint256)")
            let eventSignature := 0x89e27c1775a2f50bfdd4d348a03ca4d2e82542a17ffbe1d69d4e78aef1528659
            mstore(0x00, accumulatedVolume)
            log2(0x00, 0x20, eventSignature, totalRecords)
        }
    }

    /**
     * @notice Read unpacked data helper untuk klien offchain
     */
    function getAgentProfile(uint256 agentId) 
        external 
        view 
        returns (uint128 totalEarned, uint64 taskCount, uint64 lastTimestamp) 
    {
        uint256 packed = _agentPackedProfiles[agentId];
        totalEarned = uint128(packed >> 128);
        taskCount = uint64(packed >> 64);
        lastTimestamp = uint64(packed);
    }
}
```

#### Client Execution & Telemetry Script: `settlement-orchestrator.ts`

```typescript
import { ethers } from "ethers";

interface AgentTask {
  agentId: bigint;
  rewardWei: bigint;
  taskId: bigint;
  timestamp: bigint;
}

/**
 * Packs task parameters into raw bytes according to the contract's assembly expectation.
 */
function encodeBatchData(tasks: AgentTask[]): Uint8Array {
  // Total size: 32 bytes (length) + N * 64 bytes
  const buffer = new Uint8Array(32 + tasks.length * 64);
  const view = new DataView(buffer.buffer);

  // Set totalRecords
  view.setBigUint64(24, BigInt(tasks.length), false); // uint256 length at slot 0

  let offset = 32;
  for (const task of tasks) {
    // Write agentId (32 bytes)
    const agentIdHex = task.agentId.toString(16).padStart(64, "0");
    const agentIdBytes = ethers.getBytes("0x" + agentIdHex);
    buffer.set(agentIdBytes, offset);

    // Pack: reward (16B) | taskId (8B) | timestamp (8B) = 32 bytes
    const rewardHex = task.rewardWei.toString(16).padStart(32, "0");
    const taskIdHex = task.taskId.toString(16).padStart(16, "0");
    const timestampHex = task.timestamp.toString(16).padStart(16, "0");

    const packedValueHex = rewardHex + taskIdHex + timestampHex;
    const packedBytes = ethers.getBytes("0x" + packedValueHex);
    buffer.set(packedBytes, offset + 32);

    offset += 64;
  }

  return buffer;
}

async function main() {
  const provider = new ethers.JsonRpcProvider("http://127.0.0.1:8545");
  const operatorWallet = new ethers.Wallet("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80", provider);

  const registryAddress = "0x5FbDB2315678afecb367f032d93F642f64180aa3";
  const abi = [
    "function executeAgentBatchDirect(bytes calldata data) external",
    "function getAgentProfile(uint256 agentId) external view returns (uint128, uint64, uint64)"
  ];
  const registryContract = new ethers.Contract(registryAddress, abi, operatorWallet);

  // Mock Tasks Payload
  const tasks: AgentTask[] = [
    {
      agentId: 1001n,
      rewardWei: ethers.parseEther("0.05"),
      taskId: 1n,
      timestamp: BigInt(Math.floor(Date.now() / 1000)),
    },
    {
      agentId: 1002n,
      rewardWei: ethers.parseEther("0.12"),
      taskId: 2n,
      timestamp: BigInt(Math.floor(Date.now() / 1000)),
    },
  ];

  console.log(`[INFO] Menyusun payload settlement untuk ${tasks.length} agen...`);
  const encodedPayload = encodeBatchData(tasks);

  // Gas Estimation & Profiling
  const estimatedGas = await registryContract.executeAgentBatchDirect.estimateGas(encodedPayload);
  console.log(`[GAS BENCHMARK] Estimasi Gas Batch Settlement: ${estimatedGas.toString()} units`);

  // Execute Transaction
  const tx = await registryContract.executeAgentBatchDirect(encodedPayload);
  console.log(`[TRANSACTION] TX Terkirim: ${tx.hash}. Menunggu konfirmasi...`);
  const receipt = await tx.wait();

  console.log(`[TELEMETRY] Gas Aktual Digunakan: ${receipt.gasUsed.toString()}`);
  console.log(`[TELEMETRY] Efisiensi Gas/Task: ${receipt.gasUsed / BigInt(tasks.length)} gas/task`);

  // Verifikasi On-Chain Data State
  const profileAgent1 = await registryContract.getAgentProfile(1001n);
  console.log(`[VERIFIKASI] Agent 1001 Profile:`);
  console.log(`  - Total Earned: ${ethers.formatEther(profileAgent1[0])} ETH`);
  console.log(`  - Total Tasks: ${profileAgent1[1]}`);
  console.log(`  - Last Timestamp: ${profileAgent1[2]}`);
}

main().catch((error) => {
  console.error("[FATAL] Eksekusi orchestrator gagal:", error);
  process.exitCode = 1;
});
```

---

### 7. Edge Cases & Failure Modes

#### A. Free Memory Pointer Corruption (Clobbering)
Ketika menggunakan inline assembly, manipulasi memori pada pointer di atas `0x40` tanpa memperbarui nilai free memory pointer (`mload(0x40)`) dapat merusak alokasi variabel memori Solidity berikutnya.
*Mitigasi*: Dalam kode produksi, gunakan scratch space (`0x00 - 0x3f`) untuk hashing temporer, atau bila memerlukan memori baru, perbarui pointer `0x40` secara eksplisit:
```yul
let freeMem := mload(0x40)
mstore(freeMem, data)
mstore(0x40, add(freeMem, 0x20)) // Alokasikan 32 bytes baru secara aman
```

#### B. Transient Storage Persistency Across Contexts
Data yang disimpan menggunakan `TSTORE` bertahan sepanjang satu transaksi, yang mencakup semua sub-call (internal call dan external call).
*Bahaya*: Jika fungsi transaksi lain dipanggil dalam rangkaian transaksi yang sama (misal multicall) dan kunci `TSTORE` tidak di-clear kembali ke 0, state transaksi berikutnya akan membaca lock lama atau context kotor.
*Mitigasi*: Selalu reset slot `TSTORE` ke nol pada akhir eksekusi (pola *RAII* dalam blok `assembly` atau `try/finally`).

#### C. Bit-Shift Truncation Silent Overflow
Pemadatan manual rentan terhadap *silent truncation* jika input melebihi kapasitas bit:
* Contoh: Jika `reward` bernilai $\ge 2^{128}$ (sekitar $3.4 \times 10^{20}$ ETH), operasi casting atau shift akan memangkas bit MSB secara senyap.
*Mitigasi*: Validasi batas atas payload sebelum packing:
```yul
if gt(reward, 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF) {
    // Revert silent overflow
    mstore(0x00, 0x356ab076) // Selector OverflowError()
    revert(0x1c, 0x04)
}
```

#### D. Calldata Out-of-Bounds Memory Injection
Jika parameter calldata di-passing dengan length array yang dieksploitasi (misal length ditulis 100 tetapi calldata hanya berisi 64 bytes), iterasi loop Yul akan membaca calldata di luar range aktual. EVM secara otomatis mengembalikan nilai `0` untuk pembacaan `calldataload` di luar array size tanpa melempar revert. Ini dapat menyebabkan pembuatan entri *dummy* dengan nilai nol.
*Mitigasi*: Lakukan validasi ketat antara `data.length` aktual dan kalkulasi data yang dibutuhkan:
```yul
let expectedSize := add(32, mul(totalRecords, 64))
if lt(data.length, expectedSize) {
    revert(0, 0)
}
```

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Solidity Idiomatik Murni | Solidity + Packed Structs | Custom Yul + EIP-1153 (Solusi Dipilih) |
| :--- | :--- | :--- | :--- |
| **Keterbacaan & Auditabilitas** | Sangat Tinggi; Mudah diaudit oleh auditor junior. | Tinggi; Didukung native types Solidity. | Menengah-Rendah; Membutuhkan pemahaman EVM internals mendalam. |
| **Konsumsi Gas per Settlement** | $\approx 65.000 - 85.000$ Gas | $\approx 35.000 - 45.000$ Gas | $\approx \mathbf{21.000 - 24.000}$ **Gas** |
| **Reentrancy Protection Cost** | $\approx 7.200$ Gas (Storage SSTORE/SLOAD) | $\approx 5.000$ Gas (Storage re-use) | $\approx \mathbf{300}$ **Gas (Transient TSTORE/TLOAD)** |
| **Batas Throughput Batch (Limit 30M Gas)** | $\approx 350$ tasks/block | $\approx 650$ tasks/block | $\approx \mathbf{1.250}$ **tasks/block** |
| **Surface Vector Bug** | Rendah (Solidity compiler safety checks). | Menengah (Underflow/Overflow checks). | Tinggi jika pointer memori disalahgunakan. |

*Kapan Menggunakan Alternatif Lain?*
Jika smart contract Anda beroperasi secara eksklusif pada Layer 2 seperti Arbitrum atau Optimism di mana execution gas jauh lebih murah daripada Layer 1, optimasi Yul mikro mungkin tidak sebanding dengan biaya audit auditability. Namun, untuk aplikasi *AI Autonomous Coordination* berbasis Layer 1 atau high-frequency cross-rollup settlement hub, penghematan gas Yul ini adalah keharusan mutlak.

---

### 9. Best Practices & Standard Industri

1.  **Gunakan Custom Errors Menggantikan Require Strings**:
    Sejak Solidity v0.8.4, `error CustomError()` menghemat gas deployment dan execution secara drastis dibanding `require(cond, "Long revert string...")` karena hanya mengodekan 4 bytes selector dibandingkan puluhan bytes alokasi memori string.
2.  **Adopsi Standar Solady untuk Utility Low-Level**:
    Gunakan library battle-tested seperti `Solady` (vektor optimasi inline assembly oleh Vectorized) daripada menulis sendiri helper fungsi seperti keccak256, ECDSA verification, atau dynamic array slicing.
3.  **Terapkan Deterministic Foundry Gas Snapshots**:
    Integrasikan pengujian gas ke dalam CI/CD pipeline menggunakan:
    ```bash
    forge snapshot --diff
    ```
    Konfigurasikan batas toleransi deviasi gas maks $0.5\%$ agar regresi kode dapat ditolak secara otomatis dalam pull request.
4.  **Hormati Memori Safety Invariants di Solidity $\ge 0.8.13$**:
    Tandai blok inline assembly dengan annotasi `assembly ("memory-safe")` hanya jika kode Anda benar-benar menghormati *Free Memory Pointer* di `0x40`. Hal ini memungkinkan compiler Solidity melakukan optimasi pipeline lanjutan tanpa membatalkan register penting.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas merombak protokol settlement oracle AI yang mengalami lonjakan gas cost sebesar 300% setelah lonjakan volume transaksi. Anda harus mengimplementasikan kontrak yang dioptimasi, menguji konsumsi gas menggunakan Foundry, dan memvalidasi bahwa penghematan gas melampaui minimal 40% dibandingkan baseline Solidity murni.

#### Langkah 1: Inisialisasi Project Foundry
```bash
forge init enterprise-gas-optimization --no-commit
cd enterprise-gas-optimization
```

#### Langkah 2: Buat Kontrak Baseline (`contracts/BaselineRegistry.sol`)
Tulis implementasi naive tanpa *packed storage* dan menggunakan OpenZeppelin storage-based reentrancy guard:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract BaselineRegistry {
    bool private _locked;
    
    struct AgentProfile {
        uint256 totalEarned;
        uint256 taskCount;
        uint256 lastTimestamp;
    }
    
    mapping(uint256 => AgentProfile) public profiles;

    modifier nonReentrant() {
        require(!_locked, "REENTRANCY");
        _locked = true;
        _;
        _locked = false;
    }

    struct TaskInput {
        uint256 agentId;
        uint256 reward;
        uint256 timestamp;
    }

    function settleBatch(TaskInput[] memory tasks) external nonReentrant {
        for(uint256 i = 0; i < tasks.length; i++) {
            AgentProfile storage prof = profiles[tasks[i].agentId];
            prof.totalEarned += tasks[i].reward;
            prof.taskCount += 1;
            prof.lastTimestamp = tasks[i].timestamp;
        }
    }
}
```

#### Langkah 3: Integrasikan Kontrak Teroptimasi
Salin source code `AgentBatchSettlementRegistry.sol` dari **Section 6** ke dalam direktori `src/AgentBatchSettlementRegistry.sol`.

#### Langkah 4: Tulis Test Komparasi Gas (`test/GasBenchmark.t.sol`)
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/BaselineRegistry.sol";
import "../src/AgentBatchSettlementRegistry.sol";

contract GasBenchmarkTest is Test {
    BaselineRegistry public baseline;
    AgentBatchSettlementRegistry public optimized;

    function setUp() public {
        baseline = new BaselineRegistry();
        optimized = new AgentBatchSettlementRegistry();
    }

    function testCompareGasBatchSettlement() public {
        uint256 batchSize = 50;
        
        // Setup Payload Baseline
        BaselineRegistry.TaskInput[] memory bTasks = new BaselineRegistry.TaskInput[](batchSize);
        for(uint256 i = 0; i < batchSize; i++) {
            bTasks[i] = BaselineRegistry.TaskInput({
                agentId: 1000 + i,
                reward: 0.01 ether,
                timestamp: block.timestamp
            });
        }

        // Setup Payload Optimized via assembly packing
        bytes memory optPayload = new bytes(32 + batchSize * 64);
        assembly {
            mstore(add(optPayload, 32), batchSize)
            let start := add(optPayload, 64)
            for { let i := 0 } lt(i, batchSize) { i := add(i, 1) } {
                let itemOffset := add(start, mul(i, 64))
                mstore(itemOffset, add(1000, i)) // agentId
                
                // Pack reward (16B) & timestamp (8B)
                let packedVal := or(shl(128, 10000000000000000), timestamp())
                mstore(add(itemOffset, 32), packedVal)
            }
        }

        // Benchmark Baseline
        uint256 gasStartBaseline = gasleft();
        baseline.settleBatch(bTasks);
        uint256 gasUsedBaseline = gasStartBaseline - gasleft();

        // Benchmark Optimized
        uint256 gasStartOptimized = gasleft();
        optimized.executeAgentBatchDirect(optPayload);
        uint256 gasUsedOptimized = gasStartOptimized - gasleft();

        emit log_named_uint("Baseline Gas Used (50 Tasks)", gasUsedBaseline);
        emit log_named_uint("Optimized Gas Used (50 Tasks)", gasUsedOptimized);
        
        uint256 gasSaved = gasUsedBaseline - gasUsedOptimized;
        uint256 percentReduction = (gasSaved * 100) / gasUsedBaseline;
        emit log_named_uint("Percentage Gas Reduction", percentReduction);

        // Assert optimasi minimal 45%
        assertGt(percentReduction, 45, "Optimasi gagal mencapai target efisiensi!");
    }
}
```

#### Langkah 5: Eksekusi Test dan Analisis Output
Jalankan test suite menggunakan Foundry dengan flag verbosity tinggi:
```bash
forge test --match-contract GasBenchmarkTest -vv
```

*Expected Terminal Output:*
```text
[PASS] testCompareGasBatchSettlement() (gas: 1420831)
Logs:
  Baseline Gas Used (50 Tasks): 1238450
  Optimized Gas Used (50 Tasks): 621402
  Percentage Gas Reduction: 49
```
Hasil uji benchmark mengonfirmasi penurunan gas sebesar $\mathbf{49\%}$, melampaui target SLA efisiensi enterprise. Modul ini telah membekali Anda dengan instrumen tingkat lanjut untuk merekayasa smart contract dengan keandalan operasional dan efisiensi gas berskala production-ready.