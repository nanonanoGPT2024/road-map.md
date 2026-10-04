# BAB 05: Rekayasa Smart Contract Enterprise & Optimasi Gas
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Internal Ethereum Virtual Machine (EVM):** Membedah eksekusi bytecode, manipulasi *call stack*, alokasi memori dinamis, serta layout storage 32-byte slot pada level bitwise.
2. **Mengimplementasikan Optimasi Gas Tingkat Lanjut (Yul/Inline Assembly & EIP-1153):** Merancang smart contract hemat gas menggunakan inline assembly (Yul), manipulasi *calldata*, *storage packing*, serta memanfaatkan *transient storage* (`TSTORE`/`TLOAD`) untuk reentrancy guard dan komputasi intra-transaksi.
3. **Membangun Arsitektur Upgradeability Kompleks:** Mengembangkan dan mengaudit pola EIP-2535 (Diamond Standard) serta UUPS (Universal Upgradeable Proxy Standard) dengan teknik isolasi storage (AppStorage / Diamond Storage Pattern) guna mencegah benturan storage (*storage collision*).
4. **Mengintegrasikan Agen Otonom (Autonomous AI Agents) dengan EVM:** Membangun antarmuka eksekusi on-chain yang aman untuk autonomous agent berbasis ERC-4337 (Account Abstraction), skema validasi signature ERC-1271, serta orkestrasi transaksi nir-manusia (*trustless execution*).
5. **Menerapkan Metodologi Testing & Verifikasi Formal Enterprise:** Melakukan fuzzing berbasis properti (Foundry/Echidna), profiling gas diferensial, serta mitigasi serangan tingkat lanjut (MEV/Front-running, Cross-Contract Reentrancy, Signature Malleability).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental Solidity sintaks modern ($\ge 0.8.20$) dan OOP (Inheritance, Interfaces, Abstract Contracts).
* Konsep dasar kriptografi asimetris (ECDSA, secp256k1, keccak256, hash collision resistance).
* Penggunaan CLI Foundry (`forge`, `cast`, `anvil`) untuk siklus deploy dan testing.
* Arsitektur dasar RPC nodes, model transaksi Web3 (nonce, gas limit, base fee, priority fee EIP-1559).

---

### 3. Concept & Internal Architecture

#### 3.1 Model Eksekusi EVM & Memory Layout
EVM adalah mesin state virtual deterministik berbasis stack (*quasi-Turing complete stack-based machine*) dengan ukuran kata (*word size*) 256-bit (32 byte). Model eksekusi EVM dibagi ke dalam empat ruang data utama:

```
+-------------------------------------------------------------------------+
|                                   EVM                                   |
|                                                                         |
|  +--------------------+   +---------------------+   +----------------+  |
|  |     Call Stack     |   |       Memory        |   |    Calldata    |  |
|  |  (Max 1024 words)  |   | (Volatile, Linear)  |   | (Read-Only)    |  |
|  |  [Word 0: 32 bytes]|   | [0x00 - 0x1f: Scratch] | [0x00: 4-byte Sig] |
|  |  [Word 1: 32 bytes]|   | [0x40 - 0x5f: FreePtr] | [0x04: Arguments]  |
|  +--------------------+   +---------------------+   +----------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |                      Persistent State Storage                     |  |
|  |   Slot 0x00 ... Slot 2^256 - 1 (32-byte Key-Value Pair, SSTORE)   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |                Transient Storage (EIP-1153 / Cancun)              |  |
|  |     Slot 0x00 ... Slot 2^256 - 1 (Dibersihkan per TX, TSTORE)     |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

1. **Stack:**
   * Batas kedalaman: 1024 elemen.
   * Hanya 16 elemen teratas yang dapat diakses secara langsung melalui instruksi `SWAP` dan `DUP`. Operasi melebihi batas ini memicu error *Stack Too Deep*.
2. **Memory:**
   * Memori linier yang dapat diperluas (*byte-addressable*).
   * Tata letak memori standar Solidity:
     * `0x00 - 0x3f` (64 bytes): Scratch space untuk hashing methods (keccak256).
     * `0x40 - 0x5f` (32 bytes): Free memory pointer (posisi alokasi memori berikutnya).
     * `0x60 - 0x7f` (32 bytes): Zero slot (nilai awal dinamis/array kosong).
   * **Ekspansi Memori:** Biaya gas bersifat kuadratis:
     $$\text{Cost} = 3 \times a + \frac{a^2}{512}$$
     di mana $a$ adalah jumlah word 32-byte yang dialokasikan.
3. **Storage:**
   * Key-value mapping persisten 256-bit ke 256-bit.
   * Biaya gas:
     * `SSTORE` (alokasi baru / zero ke non-zero): 20.000 gas.
     * `SSTORE` (modifikasi non-zero ke non-zero): 5.000 gas (atau 2.900 gas jika warm slot).
     * `SLOAD`: 2.100 gas (cold slot), 100 gas (warm slot).
4. **Transient Storage (EIP-1153):**
   * Menggunakan opcode `TSTORE` (100 gas) dan `TLOAD` (100 gas).
   * State bertahan selama seluruh siklus transaksi (termasuk *nested execution calls* via `DELEGATECALL`/`STATICCALL`), tetapi secara otomatis dihapus saat transaksi selesai. Menghilangkan kebutuhan alokasi storage persisten untuk variabel sementara seperti reentrancy lock.

#### 3.2 Dynamic Storage Layout & Slot Hashing Mechanism
Variabel storage non-dinamis dipetakan secara berurutan mulai dari slot `0`. Aturan *storage packing* menggabungkan variabel-variabel bertipe data lebih kecil dari 32 byte ke dalam satu slot jika total ukurannya $\le 32$ byte, diurutkan dari kanan ke kiri (*low-order to high-order*).

Untuk tipe dinamis:
* **Dynamic Arrays:** Slot $p$ menyimpan panjang array ($n$). Elemen array disimpan mulai dari slot:
  $$\text{Slot Index} = \text{keccak256}(p) + i$$
* **Mappings:** Nilai dari key $k$ pada mapping di slot $p$ berada di:
  $$\text{Slot Index} = \text{keccak256}(k \cdot p)$$
  (di mana $\cdot$ menandakan konkatenasi byte dari $k$ yang di-pad menjadi 32-byte dan $p$ yang di-pad menjadi 32-byte).

#### 3.3 Arsitektur Proxy & EIP-2535 Diamond Standard
Pada pola Diamond (EIP-2535), sebuah kontrak proxy pusat mendelegasikan eksekusi method ke berbagai kontrak implementasi (*Facets*) menggunakan `DELEGATECALL` berbasis pemetaan selector fungsi (4 byte).

```
[ Client / Agent ]
       |
       | call: swapTokens(...)
       v
+-------------------------------------------------------------+
| Diamond Proxy Contract (Storage Owner)                      |
|                                                             |
|  Fallback () -> Yul Delegatecall                            |
|    1. Ambil 4-byte selector dari msg.sig                   |
|    2. Cari facet address di DiamondStorage                  |
|       selectorToFacet[msg.sig] -> FacetB                    |
|    3. delegatecall(gas(), FacetB, calldata, out, outsize)   |
+-------------------------------------------------------------+
          |                                  |
   delegatecall                       delegatecall
          |                                  |
          v                                  v
+-----------------------+          +-----------------------+
|  FacetA (Auth/Admin)  |          |  FacetB (Trading/Swap)|
|  - updateFacet()      |          |  - swapTokens()       |
|  - withdrawFees()     |          |  - provideLiquidity() |
+-----------------------+          +-----------------------+
          \                                  /
           \                                /
            v                              v
      +------------------------------------------+
      |  Shared AppStorage / DiamondStorage      |
      |  (Struct disimpan pada slot keccak256)   |
      +------------------------------------------+
```

Untuk menghindari tabrakan layout storage konvensional, Diamond Standard menggunakan **Diamond Storage Pattern** (EIP-1967 atau EIP-2535), di mana data disimpan di slot hasil hash string unik:
```solidity
bytes32 constant STORAGE_POSITION = keccak256("enterprise.storage.agent.vault");
```

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production-Grade | Rasional Rekayasa |
| :--- | :--- | :--- | :--- |
| **Upgradeability** | Immutable Contract / Monolithic Monoproxy (ERC-1967) | EIP-2535 Diamond Pattern + AppStorage Isolation | Melewati batas 24.576 KB bytecode (EIP-170), memungkinkan modularitas fitur, hotfix granular per modul tanpa redeploy state. |
| **Reentrancy Mitigation** | Storage variable `uint256 private _status` (OpenZeppelin ReentrancyGuard non-transient) | EIP-1153 `TSTORE`/`TLOAD` Reentrancy Lock | Memangkas biaya gas dari ~5000/20000 gas (`SSTORE`) menjadi 100 gas (`TSTORE`), mencegah eksekusi rekursif lintas fungsi dan multi-kontrak. |
| **Data Encoding** | Standar Solidity ABI Encoding (`abi.encode`) | Custom packed calldata decoding via Yul Assembly | Menghilangkan overhead padding 32-byte pada struktur data besar; menghemat bandwidth calldata dan gas eksekusi per byte. |
| **Autonomous Agent Access** | Private Key Signer langsung via Relayer (Terkendala Nonce Synchronization) | ERC-4337 Account Abstraction + ERC-1271 Signature Validation | Memisahkan execution rights dari fund ownership; batch transaksi; AI agent dapat mengeksekusi arbitrage/rebalance secara non-custodial via validasi session key. |
| **Error Handling** | `require(condition, "Descriptive String Error")` | Custom Errors (`error Unauthorized(); revert Unauthorized();`) | String literal memakan slot runtime code dan parsing runtime mahal. Custom error hanya memakan 4 byte selector hash. |

---

### 5. How (Workflow Detail)

#### Alur Eksekusi Transaksi Berkelanjutan dengan EIP-1153 Transient Guard & Diamond Routing

```
[Agent Tx] 
   --> 1. DiamondProxy::fallback()
   --> 2. [Yul] Calldataload selector (4 byte pertama)
   --> 3. Lookup: Slot DiamondStorage -> Dapatkan Facet Address
   --> 4. delegatecall ke Facet Logic
            |
            +--> 5. Modifier: nonReentrantTransient
            |       - Yul: TLOAD(LOCK_SLOT)
            |       - Cek jika == 1 -> Revert ReentrancyGuardLocked()
            |       - Yul: TSTORE(LOCK_SLOT, 1)
            |
            +--> 6. Eksekusi Business Logic & Storage Update (AppStorage)
            |
            +--> 7. Modifier Exit:
                    - Yul: TSTORE(LOCK_SLOT, 0)
   --> 8. Return data ke Agent
```

#### Alur Interaksi AI Agent via ERC-1271 & Dynamic Session Keys
1. **Delegasi State:** User memberikan otorisasi waktu terbatas (*session key*) kepada AI Agent dengan batasan parameter (misal: max slippage 1%, max drawdown 5 ETH).
2. **Kalkulasi Off-chain:** AI Agent menghitung rute likuiditas optimal secara off-chain.
3. **Dispatch Payload:** Agen membuat signature payload menggunakan session key privat miliknya dan memanggil smart contract account via EntryPoint (ERC-4337).
4. **Validasi On-chain:** Smart contract melakukan verifikasi menggunakan interface ERC-1271 (`isValidSignature(hash, signature)`):
   * Validasi expiration timestamp.
   * Validasi batasan kuota volume eksekusi.
   * Memastikan hash signature cocok dengan public key agent terdaftar.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kernel OS dan Modular Dynamic Linking
EVM beroperasi mirip dengan sistem operasi:
* **Storage** adalah *Hard Disk Drive (NVMe)*: Sangat lambat dan mahal untuk ditulis/dibaca, tetapi data bertahan setelah sistem mati (transaksi selesai).
* **Transient Storage** adalah *RAM Cache*: Cepat dan murah, data dibersihkan secara instan begitu siklus proses/transaksi berakhir.
* **Memory** adalah *L1/L2 Cache*: Sangat cepat, namun biaya ekspansinya meningkat secara kuadratis jika ukurannya membengkak.
* **Diamond Facets** adalah *Shared Dynamic Link Libraries (.so / .dll)*: Inti proxy (*Kernel*) memanggil modul eksternal secara dinamis menggunakan pointer selector fungsi, sementara konteks memori dan status disk tetap berada di dalam kontrol Kernel.

```
       +-----------------------------------------------------------+
       |                  DIAMOND STORAGE MAP                      |
       |                                                           |
       |  Key: keccak256("diamond.standard.diamond.storage")       |
       |  Slot: 0xc8fcad8db34d3cc5414bc042383a1780b8280...        |
       +-----------------------------------------------------------+
                                     |
                                     v
       +-----------------------------------------------------------+
       | struct FacetAddressAndPosition {                          |
       |     address facetAddress;  // 20 bytes                    |
       |     uint96 functionSelectorPosition; // 12 bytes          |
       | } // Packed persis 32 bytes (1 Slot!)                     |
       +-----------------------------------------------------------+
                                     |
                +--------------------+--------------------+
                |                                         |
                v                                         v
       Selector: 0xa9059cbb                     Selector: 0x23b872dd
       Facet: LiquidityPoolFacet                Facet: SwapExecutionFacet
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: High-Performance Transient Reentrancy Guard (Yul & EIP-1153)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Reentrancy Guard berbasis EIP-1153 Transient Storage
abstract contract TransientReentrancyGuard {
    // bytes32(uint256(keccak256("eip1153.reentrancy.guard")) - 1)
    bytes32 private constant REENTRANCY_GUARD_SLOT = 
        0x5c60ede37b3334f19b222b8d568349273a5596e254291a910de29366542ab48a;

    error ReentrantCallDetected();

    modifier nonReentrant() {
        assembly {
            // Cek apakah slot transient bernilai 1 (LOCKED)
            if tload(REENTRANCY_GUARD_SLOT) {
                // Revert signature: ReentrantCallDetected() -> 0x4642ab67
                mstore(0x00, 0x4642ab67)
                revert(0x1c, 0x04)
            }
            // Set flag LOCKED (1)
            tstore(REENTRANCY_GUARD_SLOT, 1)
        }
        _;
        assembly {
            // Reset flag UNLOCKED (0) setelah eksekusi selesai
            tstore(REENTRANCY_GUARD_SLOT, 0)
        }
    }
}
```

#### 7.2 Practical Example: Enterprise AI-Agent Vault dengan Diamond Storage & ERC-1271

Berikut adalah arsitektur brankas multi-aset perusahaan yang memvalidasi instruksi eksekusi agen terdesentralisasi menggunakan penyimpanan terisolasi dan assembly decoding:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC1271 {
    // Magic value returned by valid ERC-1271 implementations: bytes4(keccak256("isValidSignature(bytes32,bytes)"))
    function isValidSignature(bytes32 _hash, bytes memory _signature) external view returns (bytes4 magicValue);
}

library LibAgentVaultStorage {
    bytes32 internal constant VAULT_STORAGE_POSITION = 
        keccak256("enterprise.storage.agent.vault.v1");

    struct AgentConfig {
        bool isActive;
        uint64 dailyGasAllowance;
        uint64 gasConsumedToday;
        uint128 maxExecutionValue;
    }

    struct Layout {
        mapping(address => AgentConfig) agentConfigs;
        mapping(address => uint256) balances;
        uint256 totalEscrowed;
        address complianceOracle;
    }

    function layout() internal pure returns (Layout storage l) {
        bytes32 slot = VAULT_STORAGE_POSITION;
        assembly {
            l.slot := slot
        }
    }
}

contract EnterpriseAgentExecutionEngine is IERC1271 {
    using LibAgentVaultStorage for LibAgentVaultStorage.Layout;

    // Selector magic value ERC-1271
    bytes4 internal constant MAGICVALUE = 0x1626ba7e;
    bytes4 internal constant INVALID_SIGNATURE = 0xffffffff;

    event AgentRegistered(address indexed agent, uint128 maxValue);
    event ExecutionDispatched(address indexed agent, address indexed target, uint256 value, bytes actionData);

    error UnauthorizedAgent();
    error ExecutionLimitExceeded();
    error ExecutionFailed();
    error InvalidSignature();

    // bytes32(uint256(keccak256("eip1153.reentrancy.vault")) - 1)
    bytes32 private constant LOCK_SLOT = 
        0x78a56209a8bfdf8eb723ffcbbd9bfb826ff6417fb7bb9a4a7541f8713f019f2e;

    modifier nonReentrant() {
        assembly {
            if tload(LOCK_SLOT) {
                mstore(0x00, 0x8a92021c) // Hash custom error ExecutionFailed()
                revert(0x1c, 0x04)
            }
            tstore(LOCK_SLOT, 1)
        }
        _;
        assembly {
            tstore(LOCK_SLOT, 0)
        }
    }

    function registerAgent(
        address agent, 
        uint64 gasAllowance, 
        uint128 maxExecutionValue
    ) external {
        LibAgentVaultStorage.Layout storage l = LibAgentVaultStorage.layout();
        l.agentConfigs[agent] = LibAgentVaultStorage.AgentConfig({
            isActive: true,
            dailyGasAllowance: gasAllowance,
            gasConsumedToday: 0,
            maxExecutionValue: maxExecutionValue
        });
        emit AgentRegistered(agent, maxExecutionValue);
    }

    /// @notice Mengeksekusi instruksi arbitrase/rebalance on behalf dari AI Autonomous Agent
    function executeActionByAgent(
        address target,
        uint256 value,
        bytes calldata actionPayload,
        bytes calldata signature
    ) external nonReentrant returns (bytes memory result) {
        LibAgentVaultStorage.Layout storage l = LibAgentVaultStorage.layout();
        LibAgentVaultStorage.AgentConfig memory config = l.agentConfigs[msg.sender];

        if (!config.isActive) revert UnauthorizedAgent();
        if (value > config.maxExecutionValue) revert ExecutionLimitExceeded();

        // Validasi Payload Signature menggunakan ERC-1271
        bytes32 executionDigest = keccak256(
            abi.encodePacked(
                block.chainid,
                address(this),
                msg.sender,
                target,
                value,
                keccak256(actionPayload)
            )
        );

        if (this.isValidSignature(executionDigest, signature) != MAGICVALUE) {
            revert InvalidSignature();
        }

        // Low-level assembly call untuk memangkas overhead gas dan menangani arbitrary return data
        bool success;
        assembly {
            // Ambil pointer memori bebas
            let ptr := mload(0x40)
            
            // Salin calldata actionPayload ke scratch memory
            calldatacopy(ptr, actionPayload.offset, actionPayload.length)

            // Eksekusi pemanggilan target contract
            success := call(
                gas(),                  // Teruskan sisa gas
                target,                 // Target kontrak
                value,                  // Ether value
                ptr,                    // Input pointer
                actionPayload.length,   // Input size
                0x00,                   // Output pointer dinamis
                0x00                    // Output size (diambil dinamis nanti)
            )

            let retSize := returndatasize()
            // Alokasikan memori untuk byte array output
            mstore(0x40, add(add(ptr, retSize), 0x20))
            
            // Format dynamic bytes: panjang diikuti payload
            mstore(ptr, retSize)
            returndatacopy(add(ptr, 0x20), 0x00, retSize)
            result := ptr
        }

        if (!success) revert ExecutionFailed();

        emit ExecutionDispatched(msg.sender, target, value, actionPayload);
        return result;
    }

    /// @inheritdoc IERC1271
    function isValidSignature(
        bytes32 _hash, 
        bytes memory _signature
    ) external view override returns (bytes4) {
        if (_signature.length != 65) return INVALID_SIGNATURE;

        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(_signature, 0x20))
            s := mload(add(_signature, 0x40))
            v := byte(0, mload(add(_signature, 0x60)))
        }

        // Proteksi Signature Malleability (EIP-2)
        if (uint256(s) > 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E735E5A37777777777777777777) {
            return INVALID_SIGNATURE;
        }

        if (v != 27 && v != 28) {
            return INVALID_SIGNATURE;
        }

        address recovered = ecrecover(_hash, v, r, s);
        LibAgentVaultStorage.Layout storage l = LibAgentVaultStorage.layout();

        // Validasi apakah signer terdaftar sebagai AI Agent resmi
        if (recovered != address(0) && l.agentConfigs[recovered].isActive) {
            return MAGICVALUE;
        }
        return INVALID_SIGNATURE;
    }

    receive() external payable {}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Protokol Manajemen Perbendaharaan Otonom (Autonomous Treasury Rebalancer)
* **Konteks:** Perusahaan pengelola aset kripto institutional grade (AUM > $500M) menerapkan bot arbitrage dan market rebalancer bertenaga AI yang mengeksekusi re-weighting portofolio antar Automated Market Makers (Uniswap V3, Balancer, Curve).
* **Kendala Arsitektur Awal:**
  * Kontrak monolithic melebihi 24 KB limits (Spurious Dragon EIP-170 limit).
  * Penggunaan standard OpenZeppelin Proxy menelan gas terlalu tinggi pada high-frequency transactions.
  * Reentrancy guard standar via persistent storage membuang biaya rata-rata $18.000 USD/bulan hanya untuk *state writing/clearing*.
  * Risiko MEV front-running dan sandwich attacks akibat signature dispatch latency.
* **Solusi Enterprise:**
  1. **Migrasi ke Diamond Pattern (EIP-2535):** Memecah modul ke dalam 4 Facets terpisah: `MarketAnalysisFacet`, `LiquidityRouterFacet`, `RiskEngineFacet`, dan `AssetAdminFacet`. Semua membaca storage yang sama via Diamond Storage struct.
  2. **Implementasi EIP-1153 Transient Reentrancy Guard:** Menurunkan overhead gas per eksekusi dari 20.000 gas menjadi 200 gas per interaksi loop.
  3. **Direct Private RPC & Flashbots Auction Integration:** Autonomous agent mem-bypass public mempool dan mengirimkan bundle transaksi terenkripsi yang memvalidasi *slippage on-chain* via dynamic Yul decoding.
* **Hasil Metrik Produksi:**
  * Penghematan Gas State: Efisiensi meningkat 31.4% per siklus rebalance.
  * Modular Upgrade: Tim Quant dapat memperbarui algoritma routing swap pada `LiquidityRouterFacet` tanpa migrasi likuiditas $500M.

---

### 9. Trade-offs

```
+------------------------------------+--------------------------------------+
| PENDEKATAN DESIGN                  | KEUNTUNGAN VS KERUGIAN               |
+------------------------------------+--------------------------------------+
| Inline Assembly (Yul)              | [+] Gas super efisien (no ABI check) |
|                                    | [-] Bypass safety compiler; bahaya   |
|                                    |     memory corruption & dirty bits   |
+------------------------------------+--------------------------------------+
| EIP-2535 Diamond Standard          | [+] Bypass limit 24KB; granular hotfix|
|                                    | [-] Kompleksitas audit tinggi; rentan|
|                                    |     storage collision jika salah slot|
+------------------------------------+--------------------------------------+
| EIP-1153 (Transient Storage)       | [+] Menghemat ribuan gas per call    |
|                                    | [-] Membutuhkan hardfork Cancun;     |
|                                    |     tidak kompatibel L2 non-Cancun   |
+------------------------------------+--------------------------------------+
| Packed Struct vs Dynamic Calldata  | [+] Mengurangi calldata gas (16/byte)|
|                                    | [-] Decoding logika kompleks di klien|
|                                    |     dan smart contract               |
+------------------------------------+--------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Storage Collision pada Pola Proxy
* **Gejala:** Variabel state di proxy secara acak tertimpa nilai baru yang di-set oleh facet logika, menyebabkan perubahan address `owner` atau terkurasnya saldo.
* **Penyebab Utama:** Facet mendeklarasikan variabel storage biasa di slot `0` alih-alih menggunakan isolated dynamic diamond pointer.
* **Solusi/Debugging:** Wajib mengisolasi data ke dalam hash pointer struct unik:
  ```solidity
  // SALAH
  contract VulnerableFacet {
      address public owner; // Menginjak slot 0 proxy!
  }

  // BENAR
  library CustomStorage {
      bytes32 constant SLOT = keccak256("enterprise.unique.slot.v1");
      struct Layout { address owner; }
      function get() internal pure returns (Layout storage l) {
          assembly { l.slot := SLOT }
      }
  }
  ```

#### 10.2 Memory Pointer Overwrite pada Yul
* **Gejala:** Hash `keccak256` menghasilkan output tidak terduga atau array dynamic korup setelah operasi inline assembly.
* **Penyebab Utama:** Lupa memperbarui free memory pointer (`0x40`) setelah mengalokasikan data baru di atas memory address yang ditunjuk pointer.
* **Solusi/Mitigasi:**
  ```solidity
  assembly {
      let freeMemPtr := mload(0x40)
      // Tulis data di sini...
      // WAJIB: Update 0x40 pointer ke batas atas memori baru
      mstore(0x40, add(freeMemPtr, 0x40)) // Mengalokasikan 64 bytes
  }
  ```

#### 10.3 Dirty Upper Bits pada Type Casting
* **Gejala:** Tipe data `address` atau `uint8` di assembly menghasilkan kecocokan perbandingan yang gagal (*false negative*) saat diuji dengan operator `eq`.
* **Penyebab Utama:** Opcodes calldata seperti `calldataload` mengambil 32 byte penuh. Jika variabel berukuran 20 byte (address), bit atas memuat sampah (*dirty bits*).
* **Solusi:** Bersihkan bit atas menggunakan bitwise AND mask:
  ```solidity
  assembly {
      let rawAddress := calldataload(0x04)
      // Bersihkan 12 byte atas (96 bits) dengan mask address 160-bit
      let cleanAddress := and(rawAddress, 0xffffffffffffffffffffffffffffffffffffffff)
  }
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Compiler Configuration:** Aktifkan optimizer Solidity dengan runs tinggi untuk contract runtime-heavy (`runs: 1000000`). Gunakan EVM Version `cancun` untuk mengaktifkan EIP-1153.
- [ ] **Custom Errors:** Hapus semua `require(cond, "string")`. Gantikan secara eksklusif dengan `error ErrorName();` + `revert ErrorName();`.
- [ ] **EIP-2 Nonce & Malleability:** Selalu validasi bahwa nilai $s$ pada signature ECDSA berada di batas separuh kurva bawah ($s \le \text{secp256k1n}/2$).
- [ ] **Unchecked Math Blocks:** Bungkus operasi aritmatika yang tidak mungkin overflow (contoh: iterator array index `for (uint256 i; i < len; ++i)`) ke dalam blok `unchecked { ++i; }`.
- [ ] **Diamond Loupe & Introspection:** Pastikan kontrak Diamond mengimplementasikan `IERC165` dan EIP-2535 Loupe interface (`facets()`, `facetFunctionSelectors()`, `facetAddresses()`, `facetAddress()`).
- [ ] **Transient Cleanup Assurance:** Pastikan setiap branch alur kode (termasuk error conditional) memulihkan transient slot ke nilai netral jika digunakan lintas fungsi logic yang kompleks.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Project Foundry
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
forge init . --no-commit
```

#### Langkah 2: Konfigurasi `foundry.toml`
Pastikan compiler mengaktifkan hardfork Cancun dan optimizer:
```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.24"
evm_version = "cancun"
optimizer = true
optimizer_runs = 20000
```

#### Langkah 3: Implementasi Gas-Optimized Diamond Facet
Buat file `src/OptimizationLab.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract OptimizationLab {
    bytes32 private constant T_LOCK = keccak256("t_lock");

    error Reentrancy();

    modifier nonReentrant() {
        bytes32 slot = T_LOCK;
        assembly {
            if tload(slot) {
                mstore(0x00, 0xab143c06) // Reentrancy()
                revert(0x1c, 0x04)
            }
            tstore(slot, 1)
        }
        _;
        assembly {
            tstore(slot, 0)
        }
    }

    /// @notice Unoptimized standard summation
    function standardSum(uint256[] memory data) external pure returns (uint256 total) {
        for (uint256 i = 0; i < data.length; i++) {
            total += data[i];
        }
    }

    /// @notice Assembly-optimized summation with direct memory layout navigation
    function optimizedSum(uint256[] calldata data) external pure returns (uint256 total) {
        assembly {
            let len := data.length
            let ptr := data.offset
            let end := add(ptr, mul(len, 0x20))

            for { } lt(ptr, end) { ptr := add(ptr, 0x20) } {
                total := add(total, calldataload(ptr))
            }
        }
    }
}
```

#### Langkah 4: Tulis Fuzz & Gas Benchmark Test
Buat file `test/OptimizationLab.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/OptimizationLab.sol";

contract OptimizationLabTest is Test {
    OptimizationLab public lab;

    function setUp() public {
        lab = new OptimizationLab();
    }

    function testGasDifferential() public view {
        uint256[] memory data = new uint256[](100);
        for (uint256 i = 0; i < 100; i++) {
            data[i] = i + 1;
        }

        uint256 gasStart = gasleft();
        uint256 res1 = lab.standardSum(data);
        uint256 gasStandard = gasStart - gasleft();

        gasStart = gasleft();
        uint256 res2 = lab.optimizedSum(data);
        uint256 gasOptimized = gasStart - gasleft();

        assertEq(res1, res2);
        emit log_named_uint("Standard Loop Gas", gasStandard);
        emit log_named_uint("Optimized Yul Gas", gasOptimized);
        assertTrue(gasOptimized < gasStandard);
    }
}
```

#### Langkah 5: Eksekusi Test Foundry
Jalankan benchmark dan analisis konsumsi gas:
```bash
forge test -vv --gas-report
```

---

### 13. Exercise

#### Tingkat: Easy
1. Modifikasi contract `OptimizationLab.sol` dengan menambahkan sebuah fungsi berbasis Yul `bitExtract(uint256 value, uint8 startBit, uint8 length)` yang mengambil nilai bit spesifik menggunakan masking bitwise dan return berupa `uint256`.

#### Tingkat: Medium
1. Buat contract `TransientAllowance.sol` berbasis EIP-1153 yang menyediakan fungsi *intra-transaction approval*. Token allowance hanya valid dalam blok transaksi yang sama dan secara otomatis bernilai `0` saat dipanggil pada transaksi berikutnya, tanpa melakukan `SSTORE` nol.

#### Tingkat: Hard
1. Implementasikan sebuah Diamond Facet yang memvalidasi transfer token terkompresi. Calldata tidak menggunakan ABI encoding standar melainkan format raw binary compact (20 bytes token address, 20 bytes recipient address, 12 bytes packed uint96 amount). Tulis decoder fungsi di Yul assembly untuk mendistribusikan token dan update state pada AppStorage.

---

### 14. Challenge

**Skenario Tantangan:**
Perusahaan Anda meluncurkan platform likuidasi otomatis lintas AI-Agent bernama *Project Aegis*. Setiap agen memiliki session key untuk melikuidasi posisi pinjaman bermasalah dalam protokol pinjaman terdesentralisasi (DeFi Lending).

**Spesifikasi Persyaratan:**
1. Rancang arsitektur smart contract menggunakan EIP-2535 Diamond Pattern.
2. Wajib menggunakan **AppStorage Pattern** untuk state management agar facet tidak mengalami collision.
3. Seluruh alur kalkulasi kalkulasi likuidasi harus dilindungi oleh **Transient Reentrancy Guard (EIP-1153)**.
4. Payload transaksi dikirimkan dalam format batch yang dikompresi: `AgentAddress (20 bytes) | Nonce (8 bytes) | Deadline (4 bytes) | EncodedSubCalls[]`.
5. Eksekusi call dispatching harus dilakukan via assembly `delegatecall` atau `call` terproteksi, menangani revert bubbling secara dinamis tanpa menghentikan sub-call lain (*fault-tolerant sub-execution*).
6. Susun test suite Foundry yang memverifikasi skenario benturan state dan uji fuzzing minimal 500 iterasi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Berapa ukuran kata standar (*word size*) pada Ethereum Virtual Machine (EVM)?**
   * A. 64-bit (8 bytes)
   * B. 128-bit (16 bytes)
   * C. 256-bit (32 bytes)
   * D. 512-bit (64 bytes)
   * *Jawaban:* C. EVM didesain natively untuk memproses word sebesar 256-bit (32 bytes), yang dirancang kompatibel dengan hashing keccak256 dan kurva kriptografi secp256k1.

2. **Berapa biaya gas opcode `TSTORE` (EIP-1153) dibandingkan `SSTORE` (alokasi slot baru)?**
   * A. 100 gas vs 20.000 gas
   * B. 2.100 gas vs 5.000 gas
   * C. 0 gas vs 100 gas
   * D. 100 gas vs 2.600 gas
   * *Jawaban:* A. Opcode `TSTORE` pada Cancun hardfork dipatok flat 100 gas, sedangkan alokasi storage baru non-zero (`SSTORE`) menelan biaya 20.000 gas.

3. **Di slot memori manakah free memory pointer Solidity disimpan pada awal eksekusi transaksi?**
   * A. `0x00`
   * B. `0x20`
   * C. `0x40`
   * D. `0x80`
   * *Jawaban:* C. Slot memori `0x40 - 0x5f` dialokasikan secara konvensional oleh Solidity untuk menyimpan free memory pointer.

4. **Apa batasan utama ukuran bytecode contract yang ditentukan oleh EIP-170?**
   * A. 12.288 bytes
   * B. 24.576 bytes
   * C. 49.152 bytes
   * D. 65.536 bytes
   * *Jawaban:* B. EIP-170 membatasi ukuran maksimal runtime bytecode smart contract sebesar 24.576 bytes guna mencegah serangan denial-of-service pada pembacaan disk node.

5. **Apa fungsi dari opcode `DELEGATECALL` dibanding `CALL` biasa?**
   * A. Menjalankan kode pada contract target dengan storage dan caller context milik contract caller.
   * B. Mengirimkan Ether langsung ke contract target tanpa eksekusi kode.
   * C. Mengeksekusi kode target tanpa membolehkan modifikasi storage (read-only).
   * D. Mengalihkan kepemilikan kontrak secara permanen ke contract target.
   * *Jawaban:* A. `DELEGATECALL` mempertahankan identitas pemanggil (`msg.sender`), nilai (`msg.value`), dan menulis langsung ke persistent storage milik contract pemanggil (*caller context*).

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Pada Diamond Standard (EIP-2535), bagaimana cara mengatasi potensi storage collision antar facet?**
   * A. Mendeklarasikan seluruh variabel sebagai variabel immutable.
   * B. Menggunakan storage layout sequential berbasis pewarisan inheritance klasik.
   * C. Menempatkan struct storage pada posisi slot hasil hash keccak256 unik (AppStorage/Diamond Storage).
   * D. Menyimpan seluruh data di calldata runtime.
   * *Jawaban:* C. Dengan menetapkan posisi struct pada slot hasil hashing string unik (`keccak256("namespace.storage")`), probabilitas tabrakan slot secara matematis menjadi nol ($1/2^{256}$).

7. **Mengapa validasi signature ECDSA wajib memeriksa apakah nilai $s \le \text{secp256k1n}/2$?**
   * A. Mencegah buffer overflow pada kalkulasi elliptic curve.
   * B. Menghindari Signature Malleability, di mana penyerang dapat memodifikasi signature valid tanpa private key.
   * C. Memastikan signature kompatibel dengan format enkripsi RSA.
   * D. Mengurangi gas cost operasi `ecrecover` sebesar 50%.
   * *Jawaban:* B. Untuk setiap tanda tangan ECDSA $(r, s)$, pasangan $(r, -s \pmod n)$ juga valid untuk pesan yang sama. Membatasi $s$ ke paruh bawah kurva mengeliminasi celah manipulasi transaksi (*malleability*).

8. **Apa konsekuensi dari kegagalan memperbarui Free Memory Pointer (`0x40`) saat memanipulasi memori di blok Yul?**
   * A. Transaksi langsung mengalami opcode revert tak dikenal.
   * B. Kode eksekusi Solidity berikutnya dapat menimpa data yang telah ditulis di memori, menyebabkan korupsi data.
   * C. Gas limit transaksi seketika habis (*Out of Gas*).
   * D. Kompiler menolak mengompilasi bytecode contract.
   * *Jawaban:* B. Solidity mengasumsikan area setelah alamat yang ditunjuk `0x40` adalah memori kosong. Jika pointer tidak dimajukan, alokasi array atau struct berikutnya oleh Solidity akan menimpa data buatan Yul Anda.

9. **Apa perbedaan mendasar antara alokasi variabel dynamic array di Memory vs Storage?**
   * A. Memory array menyimpan datanya di slot hash `keccak256`, sedangkan storage array linier.
   * B. Storage array menyimpan panjang di slot utama dan elemen di `keccak256(slot) + i`, sedangkan memory array bersifat contiguous flat buffer dengan panjang di awal buffer.
   * C. Memory array dapat di-resize menggunakan method `.push()`, sedangkan storage array tidak bisa.
   * D. Tidak ada perbedaan struktur layout antara keduanya.
   * *Jawaban:* B. Di storage, elemen dipetakan di lokasi hash agar tidak tumpang tindih dengan variabel lain. Di memory, ukuran array bersifat linear contiguous buffer dan tidak mendukung ekspansi ukuran (.push()) pasca alokasi awal.

10. **Bagaimana interface ERC-1271 menentukan bahwa sebuah signature valid untuk smart contract wallet?**
    * A. Mengembalikan nilai boolean `true`.
    * B. Mengembalikan hash keccak256 dari address target.
    * C. Mengembalikan magic value spesifik `bytes4(0x1626ba7e)`.
    * D. Memancarkan event event `SignatureVerified()`.
    * *Jawaban:* C. Standar ERC-1271 mensyaratkan fungsi `isValidSignature(bytes32,bytes)` mengembalikan magic value `0x1626ba7e` jika signature dinyatakan valid secara logika on-chain kontrak.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus 1: Reentrancy Exploitation Pasca-Cancun**
    Sebuah protokol pinjaman mengimplementasikan transient storage reentrancy guard (`TSTORE`/`TLOAD`) pada fungsi `deposit` dan `withdraw`. Namun, protokol mengintegrasikan DEX eksternal yang mengeksekusi token transfer callback ke kontrak peminjam pihak ketiga. Audit menemukan penyerang tetap dapat menguras likuiditas via reentrancy. Apa celah spesifik yang mungkin terabaikan oleh developer?
    * A. Transient storage otomatis reset di tengah-tengah nested execution call.
    * B. Reentrancy guard diterapkan secara lokal pada masing-masing fungsi, tetapi tidak menggunakan slot kunci transient yang seragam secara cross-function atau cross-contract (*Cross-function/Cross-contract Transient Reentrancy*).
    * C. Opcode `TLOAD` memicu out-of-gas saat dieksekusi di dalam low-level call.
    * D. Compiler Solidity secara otomatis mengganti `TSTORE` menjadi `SSTORE` bila terdapat eksekusi callback.
    * *Jawaban:* B. Jika fungsi `deposit` dan `withdraw` menggunakan slot transient yang berbeda atau hanya menjaga internal function secara terisolasi tanpa global protocol lock, attacker dapat memanggil reentrancy silang (`deposit` memanggil `withdraw` atau sebaliknya) saat status kunci fungsi pertama belum membersihkan eksekusi.

12. **Skenario Kasus 2: Out of Gas pada Loop Batch Settlement Agen AI**
    Bot Agen AI Anda bertugas mengeksekusi settlement trading terkompresi untuk 500 pengguna dalam satu transaksi array payload. Pada pengujian lokal transaksi sukses, namun di mainnet transaksi konsisten gagal dengan pesan *Transaction Exceeded Block Gas Limit*, padahal total gas limit diestimasi hanya 12.000.000 gas. Analisis bytecode menunjukkan penggunaan array dinamis konvensional di memory. Mengapa ini terjadi?
    * A. Block gas limit mainnet lebih kecil daripada hardhat node.
    * B. Biaya kuadratis ekspansi memory EVM ($a^2 / 512$) membengkak drastis saat mengalokasikan ratusan objek decoding memory dynamic di Solidity ABI decoder.
    * C. Base fee EIP-1559 membatalkan transaksi yang memiliki lebih dari 100 array items.
    * D. RPC node sengaja menolak array dinamis di atas 256 elemen.
    * *Jawaban:* B. ABI decoder konvensional di Solidity mengalokasikan memory baru secara boros. Saat array besar dialokasikan di memory, total memori yang digunakan melintasi ribuan byte, memicu biaya kuadratis ekspansi memori EVM yang melipatgandakan gas hingga menembus block limit. Solusinya adalah memproses calldata secara in-place via pointer assembly tanpa decoding memori penuh.

13. **Skenario Kasus 3: Diamond Storage Facet Overwrite Pasca Upgrade**
    Sebuah tim menambahkan fitur baru pada Diamond Facet dengan menambahkan field variabel baru di posisi tengah struct `AppStorage`:
    ```solidity
    struct AppStorage {
        uint256 balance;
        address newRiskOracle; // VARIABEL BARU DILETAKKAN DI SINI
        uint256 feeRate;
    }
    ```
    Seketika pasca upgrade, fungsi perhitungan fee menghasilkan transaksi bernilai anomali ekstrem. Apa kesalahan fatal yang dilakukan?
    * A. Diamond Facet tidak mendukung variabel bertipe `address`.
    * B. Penambahan variabel di tengah struct merusak alignment offset slot storage variabel-variabel berikutnya (`feeRate`), menyebabkan pointer membaca slot address oracle sebagai nilai fee.
    * C. Proxy contract harus di-redeploy secara penuh jika ada penambahan variabel.
    * D. Penambahan storage struct hanya dapat dilakukan pada memory stack.
    * *Jawaban:* B. Storage struct mengalokasikan slot secara sequential deterministik berdasarkan urutan deklarasi. Menyisipkan variabel baru di tengah struct menggeser memory offset seluruh variabel di bawahnya. Field baru **wajib** selalu ditambahkan di bagian paling akhir struct (*append-only pattern*).

---

### 16. Summary

1. **Model Eksekusi EVM:** Menuntut pemahaman mendalam atas batas arsitektural: kedalaman stack (1024), ekspansi memori kuadratis, persistensi slot storage (32-byte), serta sifat non-volatil transient storage.
2. **Optimasi Gas Tingkat Tinggi:** Memanfaatkan kombinasi Yul inline assembly, calldata packing, memory management terukur, dan opcode modern `TSTORE`/`TLOAD` (EIP-1153) yang memangkas overhead gas state hingga tingkat minimum.
3. **Pola Modular Enterprise (EIP-2535):** Diamond Pattern membebaskan arsitektur dari batas 24 KB bytecode, memisahkan logika ke dalam multi-facet, serta menjamin integritas state melalui Diamond Storage isolation.
4. **Autonomous AI Integration:** Eksekusi transaksi otomatis oleh agen cerdas dimediasi secara aman melalui Account Abstraction (ERC-4337) dan validasi cryptographic signature fleksibel (ERC-1271) dengan proteksi anti-malleability ketat.
5. **Keamanan & Skalabilitas Produksi:** Keandalan smart contract enterprise dijamin bukan hanya oleh fungsionalitas logika bisnis, melainkan oleh mitigasi eksplisit terhadap storage collision, dynamic pointer corruption, MEV leakage, serta validasi ekstensif berbasis Fuzzing Foundry.