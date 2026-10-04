# Bab 04: Arsitektur Eksekusi EVM Deep Dive & Bytecode Engineering
## Module 01: Arsitektur Eksekusi EVM, Stack Machine, dan Analisis Bytecode Rendah

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis (C4)** siklus hidup eksekusi Ethereum Virtual Machine (EVM) pada level opcode, mencakup mutasi state pada Stack, Memory, Storage, Transient Storage (EIP-1153), dan Calldata.
*   **Menghitung (C3)** deterministik konsumsi gas untuk setiap operasi opcode, termasuk kalkulasi biaya dinamis pada ekspansi memori kuadratik dan akses storage *warm/cold* (EIP-2929).
*   **Merancang & Mengonstruksi (C6)** bytecode tingkat rendah (*raw bytecode*) tanpa compiler tingkat tinggi untuk pola eksekusi deterministik agen otonom.
*   **Mendiagnosis & Memitigasi (C5)** kegagalan eksekusi tingkat rendah seperti *stack underflow/overflow*, *invalid jump destination*, dan *call stack depth exhaustion* pada *smart contract execution pipeline*.

---

### 2. Concept Overview
Ethereum Virtual Machine (EVM) adalah mesin status abstrak berbasis *stack* (*quasi-Turing complete stack-based state machine*) yang mengeksekusi instruksi deterministik 256-bit. Sifat *quasi-Turing complete* berasal dari batasan komputasi melalui parameter *Gas*: setiap operasi komputasi membutuhkan alokasi bahan bakar yang membatasi eksekusi tak hingga (*halting problem mitigation*).

```
                      +-------------------------------------------------------+
                      |                 EVM Execution Context                 |
                      |                                                       |
                      |  Gas Available: G_rem                                 |
                      |  Program Counter (PC): 0x..                           |
                      +-------------------------------------------------------+
                                     |                     |
             +-----------------------+                     +-----------------------+
             v                                                                     v
   +-------------------+                                                 +-------------------+
   |   ROM (Bytecode)  |                                                 |     Calldata      |
   |   [Read-Only]     |                                                 |    [Read-Only]    |
   +-------------------+                                                 +-------------------+
             |                                                                     |
             +=======================> [ EXECUTION ENGINE ] <======================+
                                        ^        |        ^
                                        |        v        |
           +----------------------------+  +-----------+  +----------------------------+
           |                               |   Stack   |                               |
           v                               | (Max 1024)|                               v
    +--------------+                       +-----------+                        +--------------+
    |    Memory    |                             |                              | Returndata   |
    |  [Volatile]  |                             v                              |  [Volatile]  |
    +--------------+                   +--------------------+                   +--------------+
                                       |      Storage       |
                                       |   [Non-Volatile]   |
                                       +--------------------+
                                                 |
                                       +--------------------+
                                       | Transient Storage  |
                                       |     (EIP-1153)     |
                                       +--------------------+
```

#### Komponen Ruang Data EVM
1.  **Stack**: Struktur data LIFO berkapasitas maksimal 1024 elemen, di mana setiap elemen berukuran 256-bit (32 bytes / 1 word). Hampir seluruh operasi instruksi mengambil operan dari stack dan meletakkan hasil kembali ke stack.
2.  **Memory**: Array byte volatil yang dialokasikan secara linier pada runtime dan dapat diakses per-byte atau per-word (32 bytes). Memori bersifat dinamis dan biayanya meningkat secara kuadratik terhadap ukurannya.
3.  **Storage**: Pemetaan persisten berukuran $2^{256} \rightarrow 2^{256}$ slot kunci-nilai yang tersimpan di state trie global blockchain. Komponen ini memiliki latensi dan biaya gas tertinggi.
4.  **Transient Storage (EIP-1153)**: Ruang kunci-nilai sementara yang berperilaku mirip storage biasa, namun dihapus total saat transaksi selesai (*ephemeral lifetime* antar *internal frame*).
5.  **Calldata**: Ruang heksadesimal *read-only* beralamat linier yang memuat argumen transaksi/pemanggilan fungsi.
6.  **Return Data**: Buffer *read-only* tempat menyimpan data kembalian dari sub-konteks eksekusi (*internal call*).

---

### 3. Why It Matters: Real-World & Autonomous Agents
Dalam ekosistem *AI Data & Autonomous Agents*, agen otonom bertindak sebagai entitas otonom yang menandatangani, menyusun, dan mengeksekusi transaksi on-chain secara otomatis tanpa intervensi manusia. Memahami arsitektur EVM internal sangat kritikal karena:

1.  **Safety & Sandboxing**: Agen AI yang memanggil smart contract arbitrer dapat terkena perangkap *malicious fallback*, *gas draining attack*, atau *reentrancy*. Agen harus memvalidasi struktur calldata dan bytecode target secara deterministik sebelum mengeksekusi instruksi.
2.  **Deterministic Gas Estimation**: Kegagalan transaksi akibat *Out-of-Gas* (OOG) menyebabkan kerugian finansial langsung bagi autonomous runner. Model simulasi internal berbasis pemahaman opcode presisi mencegah *underestimation* maupun *overcollateralization* gas.
3.  **High-Frequency Micro-execution**: Agen otonom yang mengeksekusi ribuan arbitrase atau restaking batch membutuhkan optimasi ekstrem. Menulis adapter via raw bytecode atau Yul (melewati abstraksi overhead Solidity) dapat menghemat 15–40% gas per transaksi.

---

### 4. Arsitektur & Diagram Komponen EVM

Berikut adalah visualisasi alur instruksi mesin eksekusi EVM:

```
                    Fetch Opcode at Bytecode[PC]
                                 |
                                 v
               Decode Instruction (Validate Valid Opcode)
                                 |
           +---------------------+---------------------+
           |                                           |
    [Stack Underflow /                  [Invalid Opcode / Bad Jump]
     Overflow Check]                                   |
           |                                           v
           v                                    REVERT / HALT
    Consume Base Gas                               (Consume all gas)
           |
           v
    Calculate Dynamic Gas -----------------> Check: Gas Available >= Gas Needed
    (Memory Expansion, Cold Access)                    |
                                                       +---> [No] -> Out-of-Gas (HALT)
                                                       |
                                                      [Yes]
                                                       |
                                                       v
                                            Deduct Gas from Context
                                                       |
                                                       v
                                              Execute State Mutation:
                                        (Stack / Mem / Storage / Context)
                                                       |
                                                       v
                                             Advance PC (or JUMP)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Program Counter (PC) dan Loop Eksekusi
Mesin eksekusi memulai *Instruction Cycle* dengan PC bernilai `0x00`. EVM membaca 1 byte opcode pada posisi `Bytecode[PC]`.
*   Jika opcode berupa keluarga `PUSHn` (0x60 - 0x7F), PC melompat sejauh $n + 1$ byte karena data literal diletakkan langsung setelah opcode.
*   Jika opcode berupa `JUMP` (0x56) atau `JUMPI` (0x57), target lompatan diambil dari puncak stack. EVM mewajibkan target lompatan berada tepat pada opcode `JUMPDEST` (0x5B). Melompat ke selain `JUMPDEST` memicu eksekusi *Revert* instan (*Invalid Jump Destination*).

#### 5.2 Gas Accounting & Dynamic Memory Expansion
Biaya gas total suatu transaksi dinyatakan sebagai:
$$\text{Gas}_{\text{Total}} = \text{Gas}_{\text{Base}} + \text{Gas}_{\text{Dynamic}}$$

*   **Base Gas**: Didefinisikan secara statis per opcode (misalnya `ADD` = 3 gas, `PUSH1` = 3 gas).
*   **Dynamic Gas (Memory)**: Ketika memori diperluas melampaui alokasi sebelumnya, EVM membebankan biaya ekspansi kuadratik untuk membatasi ukuran memori node validator.
    Biaya memori total untuk mengalokasikan $a$ word (32-byte) adalah:
    $$C_{\text{mem}}(a) = G_{\text{memory}} \times a + \left\lfloor \frac{a^2}{512} \right\rfloor$$
    Di mana $G_{\text{memory}} = 3$ gas. Biaya ekspansi adalah $C_{\text{mem}}(a_{\text{baru}}) - C_{\text{mem}}(a_{\text{lama}})$.

#### 5.3 Storage Access Costs (EIP-2929 & EIP-2200)
Akses ke storage (`SLOAD`, `SSTORE`) bergantung pada status *Warm/Cold* address dan storage key dalam transaksi:
*   **Cold SLOAD**: 2100 Gas (akses pertama kali ke key tertentu dalam transaksi).
*   **Warm SLOAD**: 100 Gas (akses berikutnya ke key yang sama).
*   **SSTORE Rules**: Modifikasi slot dari `0 -> non-zero` berharga 20,000 gas; modifikasi `non-zero -> non-zero` berharga 2,900 gas (atau 5,000 gas tergantung status asli); penghapusan data (`non-zero -> 0`) memberikan *gas refund* maksimal sebesar seperlima total gas transaksi ($20\%$).

#### 5.4 Transient Storage (EIP-1153)
Diperkenalkan pada Hard Fork Dencun. Opcodes: `TSTORE` (0x5D) dan `TLOAD` (0x5C).
*   Biaya flat: 100 Gas (baik read maupun write).
*   Tidak memerlukan tracking status warm/cold.
*   Data tersimpan per-kontrak dan otomatis hilang di akhir transaksi, menghilangkan kebutuhan pembersihan slot untuk gas refund pada pola seperti *reentrancy locks*.

---

### 6. Production-Ready Code Implementation

Berikut implementasi production-grade mesin inspeksi dan emulator mini-EVM berbasis Python. Modul ini digunakan oleh sistem pertahanan agen AI untuk melakukan simulasi byte-level instruksi sebelum calldata dikirim ke blockchain RPC.

```python
"""
EVM Low-Level Inspection & Bytecode Disassembler Engine
Dirancang untuk analisis deterministik bytecode oleh Agen Otonom.
"""

from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import enum


class Opcode(enum.IntEnum):
    STOP = 0x00
    ADD = 0x01
    MUL = 0x02
    SUB = 0x03
    DIV = 0x04
    LT = 0x10
    GT = 0x11
    EQ = 0x14
    ISZERO = 0x15
    POP = 0x50
    MLOAD = 0x51
    MSTORE = 0x52
    MSTORE8 = 0x53
    SLOAD = 0x54
    SSTORE = 0x55
    JUMP = 0x56
    JUMPI = 0x57
    PC = 0x58
    MSIZE = 0x59
    JUMPDEST = 0x5B
    TLOAD = 0x5C
    TSTORE = 0x5D
    PUSH0 = 0x5F
    PUSH1 = 0x60
    PUSH32 = 0x7F
    DUP1 = 0x80
    SWAP1 = 0x90
    REVERT = 0xFD
    INVALID = 0xFE


@dataclass
class ExecutionContext:
    pc: int = 0
    stack: List[int] = field(default_factory=list)
    memory: bytearray = field(default_factory=bytearray)
    storage: Dict[int, int] = field(default_factory=dict)
    transient_storage: Dict[int, int] = field(default_factory=dict)
    gas_consumed: int = 0
    gas_limit: int = 1_000_000
    reverted: bool = False
    halted: bool = False
    return_data: bytes = b""


class EVMExecutionError(Exception):
    """Base exception untuk kegagalan eksekusi mesin EVM."""
    pass


class StackUnderflowError(EVMExecutionError):
    pass


class StackOverflowError(EVMExecutionError):
    pass


class OutOfGasError(EVMExecutionError):
    pass


class InvalidJumpDestinationError(EVMExecutionError):
    pass


class EVMBytecodeEmulator:
    """
    Emulator eksekusi opcode terbatas untuk validasi keamanan calldata agen AI.
    Mendukung verifikasi deterministik mutasi stack, gas kuadratik, dan jumpdest checking.
    """
    MAX_STACK_DEPTH: int = 1024
    WORD_SIZE: int = 32
    MAX_UINT256: int = (1 << 256) - 1

    def __init__(self, bytecode: bytes, gas_limit: int = 1_000_000) -> None:
        self.bytecode: bytes = bytecode
        self.context: ExecutionContext = ExecutionContext(gas_limit=gas_limit)
        self.jumpdests: set[int] = self._index_jumpdests()

    def _index_jumpdests(self) -> set[int]:
        valid_destinations: set[int] = set()
        idx: int = 0
        bytecode_len: int = len(self.bytecode)
        
        while idx < bytecode_len:
            byte = self.bytecode[idx]
            if byte == Opcode.JUMPDEST:
                valid_destinations.add(idx)
                idx += 1
            elif Opcode.PUSH1 <= byte <= Opcode.PUSH32:
                # Lewati data literal PUSH
                n_bytes = byte - Opcode.PUSH1 + 1
                idx += 1 + n_bytes
            else:
                idx += 1
        return valid_destinations

    def _consume_gas(self, amount: int) -> None:
        self.context.gas_consumed += amount
        if self.context.gas_consumed > self.context.gas_limit:
            self.context.halted = True
            raise OutOfGasError(
                f"Alokasi gas terlampaui: {self.context.gas_consumed} > {self.context.gas_limit}"
            )

    def _calculate_memory_expansion(self, offset: int, length: int) -> int:
        if length == 0:
            return 0
        new_size: int = offset + length
        current_words: int = (len(self.context.memory) + 31) // self.WORD_SIZE
        new_words: int = (new_size + 31) // self.WORD_SIZE

        if new_words <= current_words:
            return 0

        def mem_cost(w: int) -> int:
            return (3 * w) + ((w * w) // 512)

        return mem_cost(new_words) - mem_cost(current_words)

    def _ensure_stack(self, req: int) -> None:
        if len(self.context.stack) < req:
            raise StackUnderflowError(f"Stack underflow pada PC: 0x{self.context.pc:X}")

    def step(self) -> None:
        if self.context.pc >= len(self.bytecode):
            self.context.halted = True
            return

        op: int = self.bytecode[self.context.pc]
        initial_pc: int = self.context.pc

        # PUSH0 (EIP-3855)
        if op == Opcode.PUSH0:
            self._consume_gas(2)
            if len(self.context.stack) >= self.MAX_STACK_DEPTH:
                raise StackOverflowError("Stack overflow pada PUSH0")
            self.context.stack.append(0)
            self.context.pc += 1

        # PUSH1..PUSH32
        elif Opcode.PUSH1 <= op <= Opcode.PUSH32:
            n_bytes = op - Opcode.PUSH1 + 1
            self._consume_gas(3)
            data_slice = self.bytecode[initial_pc + 1 : initial_pc + 1 + n_bytes]
            val = int.from_bytes(data_slice, byteorder="big")
            
            if len(self.context.stack) >= self.MAX_STACK_DEPTH:
                raise StackOverflowError("Stack overflow pada PUSH")
            self.context.stack.append(val)
            self.context.pc += 1 + n_bytes

        elif op == Opcode.ADD:
            self._consume_gas(3)
            self._ensure_stack(2)
            a = self.context.stack.pop()
            b = self.context.stack.pop()
            self.context.stack.append((a + b) & self.MAX_UINT256)
            self.context.pc += 1

        elif op == Opcode.SUB:
            self._consume_gas(3)
            self._ensure_stack(2)
            a = self.context.stack.pop()
            b = self.context.stack.pop()
            self.context.stack.append((a - b) & self.MAX_UINT256)
            self.context.pc += 1

        elif op == Opcode.MSTORE:
            self._consume_gas(3)
            self._ensure_stack(2)
            offset = self.context.stack.pop()
            val = self.context.stack.pop()

            mem_gas = self._calculate_memory_expansion(offset, self.WORD_SIZE)
            self._consume_gas(mem_gas)

            # Ekspansi bytearray memori
            required_len = offset + self.WORD_SIZE
            if len(self.context.memory) < required_len:
                self.context.memory.extend(b"\x00" * (required_len - len(self.context.memory)))

            val_bytes = val.to_bytes(self.WORD_SIZE, byteorder="big")
            self.context.memory[offset : offset + self.WORD_SIZE] = val_bytes
            self.context.pc += 1

        elif op == Opcode.JUMP:
            self._consume_gas(8)
            self._ensure_stack(1)
            target = self.context.stack.pop()
            if target not in self.jumpdests:
                raise InvalidJumpDestinationError(f"Target tidak valid: 0x{target:X}")
            self.context.pc = target

        elif op == Opcode.JUMPI:
            self._consume_gas(10)
            self._ensure_stack(2)
            target = self.context.stack.pop()
            condition = self.context.stack.pop()
            if condition != 0:
                if target not in self.jumpdests:
                    raise InvalidJumpDestinationError(f"Target kondisional tidak valid: 0x{target:X}")
                self.context.pc = target
            else:
                self.context.pc += 1

        elif op == Opcode.JUMPDEST:
            self._consume_gas(1)
            self.context.pc += 1

        elif op == Opcode.TSTORE:
            self._consume_gas(100)
            self._ensure_stack(2)
            key = self.context.stack.pop()
            val = self.context.stack.pop()
            self.context.transient_storage[key] = val
            self.context.pc += 1

        elif op == Opcode.TLOAD:
            self._consume_gas(100)
            self._ensure_stack(1)
            key = self.context.stack.pop()
            self.context.stack.append(self.context.transient_storage.get(key, 0))
            self.context.pc += 1

        elif op == Opcode.STOP:
            self.context.halted = True

        elif op == Opcode.REVERT:
            self.context.reverted = True
            self.context.halted = True

        else:
            raise EVMExecutionError(f"Opcode tidak didukung atau ilegal: 0x{op:02X}")

    def execute_all(self, max_steps: int = 10_000) -> ExecutionContext:
        steps = 0
        while not self.context.halted and self.context.pc < len(self.bytecode):
            self.step()
            steps += 1
            if steps > max_steps:
                raise EVMExecutionError("Infinite loop terdeteksi pada emulator agen.")
        return self.context


# --- Contoh Penggunaan Verifikasi Bytecode Calldata ---
if __name__ == "__main__":
    # Bytecode untuk menghitung: (10 + 20) -> Simpan di Memory[0x00] -> JUMP ke JUMPDEST -> STOP
    # 0x00: PUSH1 0x0A (10)
    # 0x02: PUSH1 0x14 (20)
    # 0x04: ADD        (30)
    # 0x05: PUSH1 0x00
    # 0x07: MSTORE     (Store 30 di Memory 0x00)
    # 0x08: PUSH1 0x0D (Target PC: 13)
    # 0x0A: JUMP
    # 0x0B: INVALID    (Harus dilewati)
    # 0x0C: INVALID    (Harus dilewati)
    # 0x0D: JUMPDEST
    # 0x0E: STOP
    raw_bytecode = bytes([
        0x60, 0x0A,
        0x60, 0x14,
        0x01,
        0x60, 0x00,
        0x52,
        0x60, 0x0D,
        0x56,
        0xFE,
        0xFE,
        0x5B,
        0x00
    ])

    emulator = EVMBytecodeEmulator(raw_bytecode)
    final_context = emulator.execute_all()

    print("Status Eksekusi Sukses!")
    print(f"Gas Terkonsumsi: {final_context.gas_consumed}")
    print(f"Memori [0x00:0x20] (Hex): {final_context.memory[:32].hex()}")
    assert int.from_bytes(final_context.memory[:32], "big") == 30
    print("Verifikasi Nilai Memori Tervalidasi (30).")
```

---

### 7. Edge Cases & Failure Modes

Pada level eksekusi EVM, kegagalan beroperasi secara atomik (*all-or-nothing state transitions*). Agen otonom wajib menangani skenario batas berikut:

| Failure Mode | Mekanisme Penyebab | Dampak pada Sistem | Strategi Mitigasi Agen |
| :--- | :--- | :--- | :--- |
| **Stack Overflow** | Melebihi batas kedalaman 1024 elemen stack (`PUSH`, `DUP`). | Eksekusi langsung *Halt* & seluruh gas dalam sub-call hangus. | Static bytecode inspection sebelum menandatangani transaksi; audit kedalaman stack. |
| **Memory Expansion Bomb** | Akses offset memori sangat tinggi (misal `0xFFFFFFFF`) secara sengaja/tidak sengaja. | Biaya kalkulasi kuadratik membengkak drastis $\rightarrow$ Seketika *Out-of-Gas*. | Validasi batas parameter offset calldata $\le 2^{16}$ byte sebelum diproses. |
| **Invalid Jumpdest** | Eksekusi `JUMP` ke alamat yang bukan opcode `0x5B`, atau melompat ke area data di dalam parameter `PUSH`. | VM melempar instruksi ilegal, seluruh context frame *Revert*. | Peta kanonikal valid jumpdest (`_index_jumpdests`) harus diverifikasi lewat simulator offline. |
| **Call Stack Depth (1024)** | Panggilan bersarang (`CALL`, `DELEGATECALL`) melebihi limit 1024 level. | Sub-call mengembalikan `0` (gagal) tanpa reverting konteks induk secara otomatis. | Cek eksplisit nilai return boolean hasil pemanggilan level rendah pada stack (`ISZERO`). |

---

### 8. Trade-offs & Alternatif Solusi

Dalam rekayasa level eksekusi, arsitektur EVM memaksakan kompromi desain yang harus dipertimbangkan:

```
                      Trade-off Abstraksi vs Efisiensi Kontrak

        Rendah                                              Tinggi
  Abstraksi / Ergonomi                                Abstraksi / Ergonomi
  [ Raw Bytecode / Huff ] <---> [ Yul ] <---> [ Solidity / Vyper ]
        Tinggi                                              Rendah
   Kontrol & Efisiensi                                 Kontrol & Efisiensi
```

1.  **Raw Bytecode / Huff vs Yul vs Solidity**:
    *   *Solidity*: Memiliki overhead keamanan bawaan (ekstra runtime check, pembagian bit dinamis, selector dispatch table) yang mengonsumsi gas lebih besar.
    *   *Yul*: Bahasa perantara (*intermediate*) yang mengekspos opcode secara langsung namun tetap memiliki struktur blok kontrol.
    *   *Huff/Raw Bytecode*: Mengontrol susunan stack secara manual, mengeliminasi komputasi overhead, namun rawan *memory corruption* dan cacat *jump destination*.
2.  **Storage vs Transient Storage vs Calldata**:
    *   *Storage*: Permanen, sinkron ke Merkle State Trie global, sangat mahal ($2.100 - 20.000$ gas).
    *   *Transient Storage*: Bertahan hanya dalam siklus transaksi, mengabaikan cold/warm state, murah ($100$ gas), ideal untuk pipeline *multicall* agen otonom.
    *   *Calldata*: Tidak dapat dimutasi (*immutable*), ideal untuk payload ingestion data AI terkompresi.

---

### 9. Best Practices & Standard Industri

1.  **Pemanfaatan EIP-3855 (`PUSH0`)**:
    *   Gunakan opcode `PUSH0` (0x5F) daripada `PUSH1 0x00` untuk meletakkan angka nol ke stack. Menghemat 1 byte ruang bytecode dan 1 unit gas per instruksi.
2.  **Optimasi Layout Storage Slot (Packing)**:
    *   EVM membaca dan menulis dalam word 32-byte. Deklarasikan variabel state yang sering diakses bersama dalam batas 32-byte untuk dieksekusi dalam satu kali `SLOAD`/`SSTORE`.
3.  **Strict Calldata Slicing**:
    *   Gunakan parameter calldata secara langsung melalui offset tanpa memuat semuanya ke memori volatile (`CALLDATACOPY`), menghindari penalti ekspansi memori kuadratik.
4.  **Reentrancy Guard via EIP-1153 (TSTORE/TLOAD)**:
    *   Gantikan guard tradisional berbasis storage slot dengan Transient Storage untuk mengurangi gas proteksi dari ~5000 gas menjadi 200 gas per interaksi external call.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Agen AI Anda perlu memverifikasi apakah contract swap target memodifikasi flag reentrancy dengan aman tanpa memboroskan gas storage permanen. Anda diminta menyusun *raw bytecode* minimalis yang menguji fungsionalitas `TSTORE` dan `TLOAD` secara mandiri.

#### Langkah 1: Rancang Logika Opcode
Logika yang akan diimplementasikan:
1. Simpan nilai `0x42` ke Transient Storage pada key `0x01`.
2. Baca nilai dari key `0x01` kembali ke stack.
3. Bandingkan apakah hasilnya `0x42` (`EQ`).
4. Jika sama, lompat ke `JUMPDEST` dan akhiri dengan aman (`STOP`). Jika tidak sama, tabrak instruksi `INVALID` (`0xFE`).

#### Langkah 2: Pemetaan Bytecode Manual
*   `0x60, 0x42` $\rightarrow$ PUSH1 0x42 (Value)
*   `0x60, 0x01` $\rightarrow$ PUSH1 0x01 (Key)
*   `0x5D`       $\rightarrow$ TSTORE
*   `0x60, 0x01` $\rightarrow$ PUSH1 0x01 (Key)
*   `0x5C`       $\rightarrow$ TLOAD
*   `0x60, 0x42` $\rightarrow$ PUSH1 0x42 (Expected)
*   `0x14`       $\rightarrow$ EQ (Hasil: 1 jika valid)
*   `0x60, 0x11` $\rightarrow$ PUSH1 0x11 (Target PC: 17)
*   `0x57`       $\rightarrow$ JUMPI
*   `0xFE`       $\rightarrow$ INVALID
*   `0x5B`       $\rightarrow$ JUMPDEST (Alamat 0x11 / 17)
*   `0x00`       $\rightarrow$ STOP

#### Langkah 3: Eksekusi dan Verifikasi Menggunakan Emulator Python

Jalankan skrip berikut menggunakan emulator yang telah didefinisikan pada Bagian 6:

```python
from typing import cast

def run_lab():
    lab_bytecode = bytes([
        0x60, 0x42,        # [0x00] PUSH1 0x42
        0x60, 0x01,        # [0x02] PUSH1 0x01
        0x5D,              # [0x04] TSTORE
        0x60, 0x01,        # [0x05] PUSH1 0x01
        0x5C,              # [0x07] TLOAD
        0x60, 0x42,        # [0x08] PUSH1 0x42
        0x14,              # [0x0A] EQ
        0x60, 0x10,        # [0x0B] PUSH1 0x10 (Target: 16)
        0x57,              # [0x0D] JUMPI
        0xFE,              # [0x0E] INVALID (Trigger jika EQ gagal)
        0xFE,              # [0x0F] PADDING
        0x5B,              # [0x10] JUMPDEST
        0x00               # [0x11] STOP
    ])

    print("--- MEMULAI LAB EKSEKUSI TRANSIENT STORAGE ---")
    emu = EVMBytecodeEmulator(lab_bytecode)
    ctx = emu.execute_all()

    print(f"Status Selesai: Halted={ctx.halted}, Reverted={ctx.reverted}")
    print(f"Transient Storage State: {ctx.transient_storage}")
    print(f"Total Gas yang Dikonsumsi: {ctx.gas_consumed}")
    
    assert ctx.transient_storage.get(1) == 0x42, "Validasi gagal: Data Transient Storage tidak cocok!"
    assert not ctx.reverted, "Validasi gagal: Eksekusi me-revert transaksi!"
    print("HASIL: Sukses! Bytecode tervalidasi dan berhasil dieksekusi tanpa error.")

if __name__ == "__main__":
    run_lab()
```

#### Langkah 4: Verifikasi Hasil Pembelajaran
Pastikan output konsol menunjukkan bahwa:
1. `TSTORE` mencatat key `0x01` dengan nilai `0x42` (66 desimal).
2. `EQ` bernilai `1`, sehingga `JUMPI` berhasil melompati opcode `0xFE` langsung ke alamat `0x10` (`JUMPDEST`).
3. Total gas mencakup: 2x PUSH1 (6 gas) + TSTORE (100 gas) + PUSH1 (3 gas) + TLOAD (100 gas) + PUSH1 (3 gas) + EQ (3 gas) + PUSH1 (3 gas) + JUMPI (10 gas) + JUMPDEST (1 gas) + STOP (0 gas) = **229 Gas**.