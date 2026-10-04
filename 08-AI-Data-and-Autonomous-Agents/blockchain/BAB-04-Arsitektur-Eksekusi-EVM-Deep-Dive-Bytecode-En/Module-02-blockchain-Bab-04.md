# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Arsitektur Eksekusi EVM: Deep Dive Bytecode Engine**  
**Jalur Pembelajaran: Blockchain Engineering, AI Data Infrastructure & Autonomous Systems**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis siklus hidup eksekusi instruksi EVM (*fetch-decode-execute*) hingga tingkat register virtual, manipulasi *Program Counter* (PC), dan gas-metering engine secara deterministik.
- Membedah dan mengonfigurasi layout memori dinamis (*linear volatile memory*), termasuk kuadrilateral formula kalkulasi biaya ekspansi memori (*memory expansion cost*).
- Menghitung secara deterministik derivasi slot storage persisten untuk struktur data kompleks (dynamic arrays, mappings, nested struct) serta layout pseudo-random storage standar industri (EIP-1967).
- Merancang dan mengimplementasikan smart contract berbasis low-level Yul assembly untuk memanipulasi *execution context* (`CALL`, `DELEGATECALL`, `STATICCALL`) dengan optimasi *zero-copy memory pass-through*.
- Menilai dampak perubahan hard fork Ethereum (EIP-2929 *cold/warm state access*, EIP-3529 *reduction of refunds*) terhadap eksekusi transaksi terdistribusi dan integrasinya dengan autonomous execution agents (ERC-4337).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib memahami:
- **Computer Architecture Dasar**: Von Neumann architecture, stack vs. heap allocation, endianness (big-endian vs little-endian), register machine vs stack machine.
- **Kriptografi & Struktur Data**: Fungsi hash Keccak-256, Merkle Patricia Trie (MPT), state roots, RLP (Recursive Length Prefix) encoding.
- **Solidity Menengah**: Konsep *interfaces*, *inheritance*, ABI encoding/decoding (`abi.encode`, `abi.encodePacked`), serta dasar Yul (`assembly { ... }`).
- **Tooling**: Foundry (`forge`, `cast`), Node.js / Go lingkungan dev chain (seperti Geth EVM runner atau Anvil).

---

## 3. Concept & Internal Architecture

Ethereum Virtual Machine (EVM) adalah mesin virtual turing-complete berbasis stack 256-bit (32 byte word length) yang berjalan di lingkungan terisolasi (*sandboxed*). Tidak seperti CPU arsitektur x86-64 atau ARM yang berbasis register, EVM menggunakan arsitektur stack LIFO (*Last In, First Out*) dengan batas kedalaman maksimal 1024 item.

```
       +-------------------------------------------------------------+
       |                  EVM EXECUTION ENVIRONMENT                  |
       |                                                             |
       |  Caller: 0xAbC...       Origin: 0xDeF...       Gas: 100,000 |
       |  Value: 1.5 Ether       Data: 0x608060...      Address: 0x1 |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |                    EVM STATE PROCESSOR                      |
       |                                                             |
       |     Program Counter (PC) ----> [ Fetch Opcode: 0x54 (SLOAD) ]
       |                                         |                   |
       |                                         v                   |
       |   +-------------------+       +--------------------+        |
       |   | Gas Meter Engine  | <---> | Instruction Decode |        |
       |   +-------------------+       +--------------------+        |
       |             |                           |                   |
       |             v                           v                   |
       |  +-------------------------------------------------------+  |
       |  |                    MEMORY SUBSYSTEMS                  |  |
       |  |                                                       |  |
       |  |  +----------------+  +----------------+  +---------+  |  |
       |  |  |  Stack Engine  |  | Linear Memory  |  | Storage |  |  |
       |  |  |  (Max 1024     |  | (Volatile byte |  | Engine  |  |  |
       |  |  |   words, 32B)  |  |  addressed)    |  | (2^256  |  |  |
       |  |  +----------------+  +----------------+  |  slots) |  |  |
       |  |                                          +---------+  |  |
       |  +-------------------------------------------------------+  |
       +-------------------------------------------------------------+
                                      |
                                      v
                         [ World State Transition ]
                     (Account Storage Merkle Trie Update)
```

### 3.1. Sub-Sistem Memori EVM

1. **Stack Subsystem**:
   - Memiliki kedalaman maksimal 1024 slot (`1024 * 32 bytes = 32 KiB`).
   - Hanya 16 elemen teratas stack yang dapat diakses langsung menggunakan opcode `DUP1`-`DUP16` dan `SWAP1`-`SWAP16`. Operasi yang membutuhkan manipulasi elemen di bawah index 16 akan menghasilkan error kompilasi `Stack Too Deep`.
2. **Linear Memory Subsystem**:
   - Array byte volatil dengan pengalamatan terindeks byte (`byte-addressable`).
   - Biaya gas memori bertambah secara kuadratik mengikuti persamaan:
     $$C_{mem}(a) = 3 \cdot a + \left\lfloor \frac{a^2}{512} \right\rfloor$$
     di mana $a$ adalah alokasi ukuran memori dalam satuan word (32-byte).
3. **Storage Engine**:
   - *Key-value store* persisten dengan ruang alamat $2^{256}$ slot. Masing-masing slot menampung nilai 32-byte.
   - Sifat mutasi storage dikontrol oleh mekanisme akses *Cold* (belum tersentuh dalam transaksi) vs *Warm* (sudah tersentuh) berdasarkan EIP-2929.
4. **Calldata & Returndata**:
   - Ruang memori *read-only* terisolasi. `CALLDATA` menampung payload transaksi input. `RETURNDATA` menampung payload hasil pengembalian eksekusi external call terakhir via instruksi `RETURNDATACOPY`.

---

## 4. Why & What

| Fitur / Arsitektur | Mengapa Dibutuhkan (Why) | Apa Karakteristiknya (What) |
| :--- | :--- | :--- |
| **Word Size 256-bit** | Kebutuhan native untuk memproses algoritma hashing kriptografis standard (Keccak-256) dan komputasi skalar kurva eliptik secp256k1 tanpa fragmentasi register. | Setiap operasi aritmatika dasar (`ADD`, `MUL`, `EXP`) beroperasi secara native pada angka integer unsigned/signed 256-bit modular ($2^{256}$). |
| **Volatile Memory Expansion Cost** | Menghindari eksploitasi serangan *Denial-of-Service* (DoS) berbasis konsumsi RAM validator yang tidak terkontrol. | Biaya linear untuk 724 word pertama, lalu biaya kuadratik setelah titik tersebut, membuat konsumsi gigabyte memori dalam satu transaksi mustahil secara ekonomis. |
| **EIP-1967 Storage Slots** | Menghindari tabrakan layout storage (*storage clash*) pada kontrak proksi (*Upgradable Proxy Contracts*). | Slot storage implementation, admin, dan beacon ditentukan oleh kalkulasi formula: `bytes32(uint256(keccak256("eip1967.proxy...")) - 1)`. |
| **Delegatecall Context Switching** | Mengizinkan pemisahan logika komputasi dan *state storage* untuk modularitas enterprise. | Kode dieksekusi dari target address, tetapi mutasi storage, nilai `msg.sender`, dan `msg.value` tetap berada pada konteks kontrak pemanggil (*caller*). |

---

## 5. How: Alur Kerja Eksekusi Instruksi EVM

Siklus eksekusi instansiasi kontrak EVM:

```
[Fetch]      Opcode dibaca dari Contract Bytecode pada indeks PC (Program Counter).
  │
[Cost Calc]  Konsumsi base gas + dynamic gas (memory expansion, cold/warm access).
  │          Jika current_gas < required_gas -> THROW OutOfGas.
  │
[Decode]     Pemeriksaan arity stack (argumen input & return outputs).
  │          Jika stack_depth < inputs -> THROW StackUnderflow.
  │          Jika stack_depth - inputs + outputs > 1024 -> THROW StackOverflow.
  │
[Execute]    Instruksi diproses (contoh: Operasi Stack, Memory write, Storage mutation).
  │
[Advance]    PC bertambah sejumlah 1 byte (atau 1 + N byte untuk opcode PUSH<N>).
```

### 5.1. Logika Perhitungan Alamat Storage Lanjutan

1. **State Variable Sederhana**: Slot terurut dari `0x0`, dipaketkan bersama jika ukuran tipe data $\le 32$ byte dari kanan ke kiri (*little-endian within the big-endian slot*).
2. **Dynamic Arrays**:
   - Slot $p$ menyimpan panjang array ($L$).
   - Data elemen ke-$i$ disimpan pada slot:
     $$\text{Slot}(i) = \text{keccak256}(p) + i \cdot \text{slots\_per\_element}$$
3. **Mappings**:
   - Nilai dari kunci $k$ yang berada pada mapping di slot deklarasi $p$ disimpan pada:
     $$\text{Slot}(k) = \text{keccak256}(\text{pad32}(k) \parallel \text{pad32}(p))$$
4. **Nested Mappings**:
   - Untuk mapping ganda `mapping(k1 => mapping(k2 => v))` pada slot deklarasi $p$:
     $$\text{Slot}(k1, k2) = \text{keccak256}(\text{pad32}(k2) \parallel \text{keccak256}(\text{pad32}(k1) \parallel \text{pad32}(p)))$$

---

## 6. Analogi & Diagram Memori

Bayangkan EVM seperti meja kerja mekanik perakitan berpresisi tinggi:
- **Stack**: Rak perkakas vertikal kecil tepat di hadapan mekanik. Hanya muat 1024 alat. Mekanik hanya bisa mengambil atau menaruh alat paling atas.
- **Linear Memory**: Pita kertas putih panjang yang dibeli sesuai kebutuhan. Semakin panjang pita yang ditarik, harga sewanya per milimeter melonjak tajam secara eksponensial (kuadratik). Setelah selesai membuat mobil, pita dibuang ke tempat sampah (hilang total).
- **Storage**: Lemari loker tahan api terbuat dari baja di dinding yang terhubung langsung ke notaris global (World State). Menyimpan dokumen di sana sangat mahal, tetapi tersimpan selamanya.
- **Calldata**: Lembar cetak biru instruksi pesanan yang dibawa kurir; Anda hanya boleh membaca isinya, tidak boleh mencoret-coret lembar tersebut.

### Diagram Layout Memori EVM Standar (Solidity Free Memory Pointer Architecture)

```
0x00               0x40                 0x60            0x80
+--------------------+--------------------+---------------+-------------------------+
| Scratch Space      | Free Memory        | Zero Slot     | Allocated Memory Space  |
| (64 bytes for      | Pointer            | (32 bytes for | (Dynamic alloc starts   |
|  hashing methods)  | (points to >=0x80) | dynamic array)|  here)                  |
+--------------------+--------------------+---------------+-------------------------+
| [0x00 - 0x3F]      | [0x40 - 0x5F]      | [0x60 - 0x7F] | [0x80 - ...]            |
```

---

## 7. Implementasi Kode: Komponen Low-Level Assembly

### 7.1. Simple Example: Decoding Storage Slot & Dynamic Allocation (Yul)

Kode Yul murni berikut menunjukkan cara membaca dan menulis dynamic array langsung tanpa abstraksi Solidity compiler:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract LowLevelStorageEngine {
    // Slot 0: Array length
    uint256[] public rawVector;

    function pushElementDirect(uint256 value) external {
        assembly {
            // 1. Ambil posisi slot deklarasi (slot 0)
            let arraySlot := rawVector.slot
            
            // 2. Baca panjang array saat ini
            let currentLength := sload(arraySlot)
            
            // 3. Hitung slot target: keccak256(arraySlot) + currentLength
            mstore(0x00, arraySlot)
            let arrayDataStart := keccak256(0x00, 0x20)
            let targetSlot := add(arrayDataStart, currentLength)
            
            // 4. Tulis value ke slot target
            sstore(targetSlot, value)
            
            // 5. Update panjang array (currentLength + 1)
            sstore(arraySlot, add(currentLength, 1))
        }
    }

    function readElementDirect(uint256 index) external view returns (uint256 value) {
        assembly {
            let arraySlot := rawVector.slot
            let currentLength := sload(arraySlot)
            
            // Revert jika out of bounds
            if iszero(lt(index, currentLength)) {
                // Revert signature Panic(uint256) -> 0x4e487b71
                mstore(0x00, 0x4e487b71)
                mstore(0x04, 0x32) // Array index out of bounds code
                revert(0x00, 0x24)
            }
            
            mstore(0x00, arraySlot)
            let arrayDataStart := keccak256(0x00, 0x20)
            value := sload(add(arrayDataStart, index))
        }
    }
}
```

### 7.2. Practical Example: Production EIP-1967 Zero-Copy Forwarding Proxy

Implementasi transparent proxy tingkat produksi menggunakan Yul assembly murni untuk meminimalkan *call overhead* dan konsumsi gas:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/**
 * @title UltraOptimizedProxy
 * @dev Mengimplementasikan pola forwarder proxy zero-copy berbasis EIP-1967.
 */
contract UltraOptimizedProxy {
    // bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1)
    bytes32 private constant IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    // bytes32(uint256(keccak256("eip1967.proxy.admin")) - 1)
    bytes32 private constant ADMIN_SLOT =
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    event Upgraded(address indexed newImplementation);
    event AdminChanged(address previousAdmin, address newAdmin);

    modifier onlyAdmin() {
        address currentAdmin;
        assembly {
            currentAdmin := sload(ADMIN_SLOT)
        }
        if (msg.sender != currentAdmin) {
            assembly {
                // Signature: Unauthorized() -> 0x82b42900
                mstore(0x00, 0x82b42900)
                revert(0x1c, 0x04)
            }
        }
        _;
    }

    constructor(address logicAddress, address adminAddress) {
        assembly {
            sstore(IMPLEMENTATION_SLOT, logicAddress)
            sstore(ADMIN_SLOT, adminAddress)
        }
        emit Upgraded(logicAddress);
        emit AdminChanged(address(0), adminAddress);
    }

    function upgradeTo(address newImplementation) external onlyAdmin {
        assembly {
            // Validasi non-zero address
            if iszero(newImplementation) {
                mstore(0x00, 0xd92e233d) // ZeroAddress() error signature
                revert(0x1c, 0x04)
            }
            sstore(IMPLEMENTATION_SLOT, newImplementation)
        }
        emit Upgraded(newImplementation);
    }

    fallback() external payable {
        _delegate();
    }

    receive() external payable {
        _delegate();
    }

    function _delegate() internal {
        assembly {
            // Muat alamat implementasi dari immutable storage slot
            let impl := sload(IMPLEMENTATION_SLOT)
            
            // Salin calldata langsung ke scratchpad memory (slot 0)
            // calldatacopy(t, f, s) -> copy s bytes from calldata offset f to mem offset t
            calldatacopy(0x00, 0x00, calldatasize())

            // Eksekusi DELEGATECALL
            // delegatecall(g, a, in, insize, out, outsize)
            // Menggunakan 0 untuk out dan outsize karena kita akan menangkap returndata secara dinamis
            let result := delegatecall(gas(), impl, 0x00, calldatasize(), 0x00, 0x00)

            // Salin returned data ke memory offset 0
            returndatacopy(0x00, 0x00, returndatasize())

            switch result
            case 0 {
                // Jika eksekusi gagal (revert), teruskan revert reason yang identik
                revert(0x00, returndatasize())
            }
            default {
                // Jika sukses, kembalikan return data ke pemanggil
                return(0x00, returndatasize())
            }
        }
    }
}
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Skenario: Gas-Exhaustion Attack pada ERC-4337 Bundler Mempool

*Latar Belakang*: Sebuah engine autonomous execution agent ERC-4337 memproses *UserOperations* dalam batch ke entrypoint smart contract. Agen validator mengeksekusi operasi simulasi off-chain menggunakan `debug_traceCall` untuk memvalidasi limit gas.

*Insiden*: Penyerang mendistribusikan ratusan `UserOperation` yang memanggil `DELEGATECALL` ke kontrak yang secara agresif mengakses storage slot dingin (*cold access*) yang sengaja didistribusikan secara acak melalui dynamic memory expansion. Akibatnya, estimasi statis bundler meloloskan transaksi, namun saat di bundle on-chain, memori bertambah hingga 128 KiB per call:
- Biaya $C_{mem}(128\text{ KiB})$ melompat dari $\sim 12.000$ gas menjadi lebih dari $1.800.000$ gas per batch.
- Ini memicu `OutOfGas` (OOG) pada level root transaction, membakar modal gas native bundler tanpa eksekusi transaksi target (*griefing attack*).

```
[Bundler Off-chain]  Calculates gas based on shallow tracing: ~45,000 gas
        │
        ▼
[On-Chain Execution] UserOp invokes Dynamic Bytecode Engine
        │
        ├──> Memory expands from 0x80 to 0x20000 (131,072 bytes / 4096 words)
        ├──> Quadratic Cost Formula triggers:
        │      Cost = (3 * 4096) + floor(4096^2 / 512)
        │      Cost = 12,288 + 32,768 = 45,056 gas JUST FOR MEMORY EXPANSION!
        │
        └──> Exceeds bundler-allocated UserOp Gas Limit -> REVERT -> Bundler loses ETH.
```

*Solusi Arsitektur EVM Hardened*:
1. Mengubah kontrak eksekutor untuk membatasi *free memory pointer* secara tegas menggunakan Yul guardrail.
2. Membatasi returndata buffer menggunakan `STATICCALL` dengan parameter limit memory `outsize` yang terikat statis, bukan dinamis 0-byte dynamic copy jika target tidak dipercaya.

---

## 9. Trade-Off Analysis

| Aspek Desain | Pendekatan A: Native Solidity High-Level | Pendekatan B: Low-Level Yul Assembly Inline | Analisis Rekayasa & Trade-off |
| :--- | :--- | :--- | :--- |
| **Konsumsi Gas** | Lebih tinggi (rata-rata 15-40% overhead akibat safety checks: overflow, bounds check, clean memory initialization). | Sangat minimal. Hanya opcode esensial yang dieksekusi. | **Keuntungan Mutlak:** Yul. Pada eksekusi berfrekuensi tinggi (seperti arbitrageur bots atau L2 rollups sequencers), pemotongan 2.000 gas per tx menghemat ribuan dolar per hari. |
| **Keamanan & Verifikasi** | Compiler Solidity menyuntikkan sanitasi tipe data, pemeriksaan ABI, dan proteksi overflow arithmetic native (0.8.x+). | Nihil proteksi internal. Developer bertanggung jawab penuh atas manipulasi stack/pointer. | **Kompromi:** Yul memiliki risiko *undefined behavior*, eksploitasi overwriting memory penting (seperti pointer 0x40), dan manipulasi stack pointer liar. |
| **Keterbacaan & Audit** | Sangat terbaca, kompatibel dengan tool static analysis standard (Slither, Mythril, Aderyn). | Sulit diaudit. Banyak tool symbolic execution gagal melacak invariants pada arbitrary assembly blocks. | **Maintainability:** Penggunaan Yul mempersempit jumlah engineer yang mampu memvalidasi kode di level audit enterprise. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: Mengabaikan Free Memory Pointer (0x40)

```solidity
// SALAH: Menimpa slot memori 0x40 secara langsung tanpa menggesernya
assembly {
    // Alokasi sembarangan pada offset 0x80 tanpa memperbarui 0x40
    mstore(0x80, myData)
    // Solidity selanjutnya akan mengalokasikan data baru tepat di atas 0x80! Data rusak ter-overwrite!
}

// BENAR: Membaca, menggunakan, dan memperbarui Free Memory Pointer
assembly {
    let freeMem := mload(0x40) // Baca pointer alokasi bebas
    mstore(freeMem, myData)    // Tulis data kita di pointer tersebut
    // Geser pointer sejauh 32 bytes (atau sesuai kebutuhan padding 32-byte)
    mstore(0x40, add(freeMem, 0x20))
}
```

### 10.2. Kesalahan Fatal: Delegatecall pada Target Tidak Terpercaya

- **Gejala**: Saldo native token atau kontrol kepemilikan kontrak terkuras seketika.
- **Akar Masalah**: Menggunakan `DELEGATECALL` ke alamat kontrak arbitrer yang dikirim melalui parameter eksternal. Target kontrak dapat mengeksekusi `sstore(0, attackerAddress)` yang menimpa variable pemilik (biasanya di slot 0) dari kontrak pemanggil.
- **Solusi**: Hanya izinkan `DELEGATECALL` ke implementasi hash bytecode yang telah di-whitelist secara immutable atau dikunci melalui cryptographic registry.

---

## 11. Best Practices & Production Checklist

1. **Storage Layout Caching**: Simpan slot storage dalam register lokal (`sload` sekali ke stack) jika digunakan lebih dari satu kali dalam fungsi yang sama untuk menghemat *warm storage read* ($100$ gas per bacaan berulang).
2. **Byte Packing Optimization**: Susun variable global state agar mengisi slot 32-byte secara kompak:
   ```solidity
   // OPTIMAL (1 Slot - 32 Bytes)
   uint128 public reserveA; // 16 bytes
   uint64  public timestamp; // 8 bytes
   address public operator;  // 20 bytes -> TIDAK MUAT, pindah slot!
   
   // BENAR:
   uint128 public reserveA; // 16 bytes
   uint96  public reserveB; // 12 bytes
   uint32  public blockNum; // 4 bytes
   // Total: 16 + 12 + 4 = 32 bytes (Tepat 1 slot persisten)
   ```
3. **Pembersihan Scratch Space**: Scratch space (`0x00` - `0x3F`) dapat digunakan secara bebas untuk hash Keccak-256 temporer, tetapi jangan pernah berasumsi bahwa isinya bernilai `0x0` sebelum digunakan.
4. **Validasi Zero-Address pada Low-Level Calls**: Fungsi native `call` dan `delegatecall` ke address `0x0` akan mengembalikan nilai *boolean status* `true` (karena EVM menganggap eksekusi ke empty account adalah no-op). Selalu periksa `extcodesize(target) > 0` sebelum `delegatecall`.

---

## 12. Hands-on Practice: Hands-on/m02/

### Step 1: Inisialisasi Proyek Testing Bytecode EVM
Buka terminal dan buat workspace menggunakan framework Foundry:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
forge init --no-commit
```

### Step 2: Implementasi Custom Optimized Yul Dispatcher
Buat file `src/YulDispatcher.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract YulDispatcher {
    // Mapping internal: slot index 0
    mapping(uint256 => uint256) private idToValue;

    function rawWrite(uint256 id, uint256 val) external {
        assembly {
            // Memory layout untuk hash mapping: key (0x00) + slot (0x20)
            mstore(0x00, id)
            mstore(0x20, idToValue.slot)
            let targetSlot := keccak256(0x00, 0x40)
            sstore(targetSlot, val)
        }
    }

    function rawRead(uint256 id) external view returns (uint256 val) {
        assembly {
            mstore(0x00, id)
            mstore(0x20, idToValue.slot)
            let targetSlot := keccak256(0x00, 0x40)
            val := sload(targetSlot)
        }
    }
}
```

### Step 3: Implementasi Test Runner untuk Analisis Opcode Gas
Buat file `test/YulDispatcher.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/YulDispatcher.sol";

contract YulDispatcherTest is Test {
    YulDispatcher internal dispatcher;

    function setUp() public {
        dispatcher = new YulDispatcher();
    }

    function testGasEfficiencyWriteRead() public {
        uint256 key = 0xbeef;
        uint256 value = 0xcafe;

        // Test Write Cold Slot
        dispatcher.rawWrite(key, value);

        // Test Read Warm Slot
        uint256 retrieved = dispatcher.rawRead(key);
        assertEq(retrieved, value, "Value storage mapping mismatch!");
    }
}
```

Jalankan test dengan trace verbosity:
```bash
forge test -vvvv --gas-report
```

---

## 13. Exercises

### Level Easy
Tuliskan blok assembly Yul yang memuat dua nilai integer 256-bit dari calldata pada byte offset 4 dan 36, menjumlahkannya, dan menyimpannya ke memory offset 0x00, lalu mengembalikan nilainya ke caller via instruksi `return(0x00, 0x20)`.

### Level Medium
Buat smart contract yang mengimplementasikan fungsi membaca nilai variable bertipe `string` dinamis yang berada pada slot storage persisten `1` tanpa menggunakan high-level variable accessor, dengan mempertimbangkan logika layout *short string* ($length < 32$ byte) vs *long string* ($length \ge 32$ byte) sesuai standar Solidity storage specification.

### Level Hard
Buat implementasi custom dispatcher function selector menggunakan binary search berbasis Yul inline assembly, alih-alih linear IF-ELSE scanning default Solidity. Bandingkan efisiensi gas executionnya jika kontrak memiliki 16 public function selectors.

---

## 14. Complex Production Challenge

### Skenario Kasus: Dynamic Bytecode Interceptor untuk Autonomous AI Agent
Anda diminta merancang sistem eksekusi transaksi terdelegasi (*Meta-Transaction Executor*) untuk agent otonom (AI Data Crawler). Agent ini memiliki limitasi otorisasi yang sangat ketat:
1. Agen hanya boleh mengeksekusi instruksi `CALL` ke kontrak oracle data tertentu.
2. Agen **dilarang keras** memicu instruksi state-changing berbahaya: bytecode payload calldata tidak boleh memuat pemanggilan opcode `SELFDESTRUCT`, `CREATE`, `CREATE2`, maupun pemanggilan fungsi yang memodifikasi approval ERC20 (`0x095ea7b3`).
3. Seluruh proses validasi calldata dan eksekusi instruksi wajib dilakukan secara in-line menggunakan assembly Yul murni dalam satu kali siklus transaksi, tanpa melakukan unpacking array calldata ke high-level Solidity memory guna menjaga efisiensi gas di bawah 30.000 gas per intersep.

*Tugas*: Bangun sistem smart contract `AgentExecutionGuard.sol` yang memvalidasi *function selector* calldata secara native via bit-shifting low level dan mengeksekusi payload menggunakan `STATICCALL` secara strictly scoped, serta mengembalikan data mentah ke caller secara transparan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda & Konseptual Singkat)
1. Berapa ukuran lebar data native (word size) pada EVM Stack?
2. Mengapa ekspansi memori EVM dihitung menggunakan rumus polinomial kuadratik, bukan linier murni?
3. Di mana pointer alamat memori bebas (*free memory pointer*) disimpan secara konvensional pada arsitektur compiler Solidity?
4. Apa status gas cost untuk operasi `SLOAD` yang mengakses storage slot yang sama untuk kedua kalinya dalam satu transaksi (berdasarkan EIP-2929)?
5. Opcode apa yang bertindak sebagai pemanggil eksternal yang mempertahankan `msg.sender` dan `msg.value` dari caller sebelumnya?

### Bagian B: Intermediate (Deep-Dive Analysis)
6. Jelaskan apa yang terjadi pada *execution context* jika instruksi `STATICCALL` mengeksekusi bytecode yang di dalamnya terdapat opcode `SSTORE`.
7. Mengapa kompilator Solidity menggunakan offset `0x00` - `0x3F` sebagai scratch space dan bagaimana cara kerjanya?
8. Bagaimana EVM membedakan penyimpanan mapping `mapping(uint256 => uint256)` dengan dynamic array `uint256[]` jika keduanya dideklarasikan pada indeks slot 0?
9. Mengapa instruksi `extcodesize` pada target address yang sedang menjalankan fungsi `constructor` bernilai 0?
10. Terangkan perbedaan mendasar antara opcode `CALLCODE` (deprecated) dan `DELEGATECALL`.

### Bagian C: Kasus Arsitektur Produksi
11. **Kasus 1**: Sebuah protokol yield aggregator mendapati biaya gas penarikan reward tiba-tiba melonjak 5 kali lipat setelah mengupgrade kontrak implementasi proksi. Setelah diaudit, struktur urutan variabel global diubah: variable `bool isInitialized` dipindahkan dari urutan paling bawah menjadi paling atas di antara dua variabel `uint256`. Jelaskan secara mendalam akar masalah arsitektural EVM-nya.
12. **Kasus 2**: Suatu bot arbitrase cross-DEX mengeksekusi swap menggunakan Flashloan. Pada tahap eksekusi terakhir, bot mengeksekusi instruksi `returndatacopy` sebesar `returndatasize()`. Transaksi tiba-tiba revert dengan error `OutOfGas`. Analisis kemungkinan skenario eksploitasi atau anomali memori yang terjadi pada DEX target.
13. **Kasus 3**: Rancang skema mitigasi pada level bytecode Yul untuk mencegah eksploitasi serangan read-only reentrancy saat membaca cadangan balance storage dari external pool yang belum disinkronisasi (*unsettled state*).

---

## 16. Kunci Jawaban & Panduan Evaluasi Quiz

### Bagian A
1. **32 byte (256-bit)**.
2. Untuk mencegah serangan **Denial-of-Service (DoS)** terhadap node validator akibat konsumsi alokasi RAM yang berlebihan dan masif dalam waktu singkat.
3. Pada offset memori **`0x40`** (berisi pointer yang menunjuk ke address memori kosong berikutnya, default awal adalah `0x80`).
4. **Warm access cost (100 gas)**, karena slot sudah dimasukkan ke dalam `accessed_storage_keys` set transaksi.
5. **`DELEGATECALL`** (opcode `0xF4`).

### Bagian B
6. EVM akan langsung memicu eksekusi **REVERT (State Violation)** dan mengembalikan flag kegagalan `0` ke stack caller, karena `STATICCALL` secara ketat melarang seluruh operasi mutasi state (`SSTORE`, `LOG0`-`LOG4`, `CREATE`, `SELFDESTRUCT`).
7. Offset `0x00`-`0x3F` (total 64 byte) dialokasikan sebagai ruang kerja sementara (*scratch space*) untuk kalkulasi hashing cepat, seperti menghitung key slot mapping. Area ini tidak terikat dengan jaminan free memory pointer dan dapat ditimpa secara bebas antar operasi instruksi kompilasi.
8. Dynamic array pada slot 0 menyimpan **panjang array** pada slot 0 itu sendiri, dan elemen aktualnya berada di `keccak256(0) + index`. Sedangkan mapping pada slot 0 **mengosongkan slot 0** (berisi 0x0) dan nilainya didistribusikan pada slot `keccak256(key . 0)`.
9. Karena status runtime bytecode akun target belum resmi tersimpan ke dalam state trie database sampai proses eksekusi kode *initialization/constructor* selesai mengembalikan *runtime deployment code* via instruksi `RETURN`.
10. `CALLCODE` mempertahankan nilai `msg.sender` dan `msg.value` dari pemanggil sebelumnya ke target, namun mengubah konteks `address(this)` menjadi kontrak pemanggil. Sementara `DELEGATECALL` mempertahankan seluruh konteks eksekusi lingkungan secara absolut (`msg.sender`, `msg.value`, dan storage slot), berperilaku seolah kode target dicangkokkan langsung ke tubuh kontrak pemanggil.

### Bagian C
11. **Akar Masalah**: Terjadi fenomena pergeseran layout penyimpanan (*Storage Slot Misalignment / Clash*). Ketika tipe `bool` (1 byte) dipindahkan ke posisi paling atas di depan tipe `uint256` (32 byte), kompilator tidak dapat lagi memadatkan slot 0 secara penuh. Tipe `bool` menempati Slot 0 (1 byte terpakai, 31 byte padding kosong), dan variable `uint256` berikutnya dipaksa pindah ke Slot 1. Akibatnya, seluruh mapping dan state variable di bawahnya mengalami offset slot index yang menyebabkan fungsi-fungsi membaca slot yang salah dan memaksa engine melakukan multi-slot cold load berturut-turut.
12. **Analisis Anomali**: DEX target yang dipanggil kemungkinan mengeksekusi serangan malicious gas-griefing atau memicu data return raksasa (misal: mengembalikan array dynamic berukuran jutaan byte yang berisi *junk memory*). Saat bot memanggil `returndatacopy(0, 0, returndatasize())`, EVM dipaksa memperluas linear memory bot seketika hingga ratusan kilobyte/megabyte. Rumus ekspansi kuadratik memicu konsumsi gas instan yang melampaui sisa gas limit bot, memicu `OutOfGas`.
13. **Mitigasi Yul**: Sebelum membaca balance, periksa status reentrancy flag dari pool target secara low-level. Jika target adalah proxy atau vault berstandar, baca slot reentrancy lock (misal slot 1 yang menyimpan status non-reentrant 0x01 vs 0x02) via low-level `staticcall`. Jika nilai lock menandakan sedang dalam kondisi terkunci (`0x02`), segera batalkan eksekusi (`revert(0, 0)`) dan jangan gunakan nilai cadangan yang belum settlement.

---

## 17. Summary

- EVM adalah mesin virtual berarsitektur stack 256-bit terisolasi di mana optimasi sistem bergantung pada efisiensi interaksi antara Stack (LIFO, 1024 deep), Linear Memory (kuadratik gas), dan Persisten Storage (Merkle Patricia Trie backed).
- Storage layout EVM bersifat deterministik. Pengetahuan mendalam terkait hashing key-to-slot (`keccak256(key . slot)`) memfasilitasi pembangunan kontrak proksi berkinerja tinggi dan bypass overhead kompilator.
- Manipulasi konteks eksekusi melalui opcode tingkat rendah (`DELEGATECALL`, `STATICCALL`) membuka kapabilitas arsitektur modern seperti *Account Abstraction* (ERC-4337) dan *Minimal Proxy Factory* (EIP-1167 / EIP-1967), namun mewajibkan penanganan free memory pointer (`0x40`) secara presisi untuk menghindari *memory corruption*.