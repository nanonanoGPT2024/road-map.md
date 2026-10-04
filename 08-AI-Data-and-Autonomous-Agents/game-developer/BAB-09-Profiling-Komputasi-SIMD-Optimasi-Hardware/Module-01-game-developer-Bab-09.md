# Bab 09: Profiling Komputasi, SIMD, & Optimasi Hardware

## Module 01: Arsitektur Memori CPU, Vektorisasi SIMD, dan Data-Oriented AI System

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendiagnosis Bottleneck Hardware (Level 4 - Analysis):** Mengidentifikasi *cache misses* (L1, L2, L3), *branch mispredictions*, dan *instruction pipeline stalls* pada sistem simulasi ribuan autonomous agents menggunakan profiler perangkat keras level-rendah (*hardware performance counters*).
- **Mentransformasi Paradigma Data (Level 5 - Synthesis):** Merestrukturisasi arsitektur data agen otonom dari model *Array of Structures* (AoS) berorientasi objek menjadi *Structure of Arrays* (SoA) / *Array of Structures of Arrays* (AoSoA) guna memaksimalkan *spatial* dan *temporal data locality*.
- **Mengimplementasikan Instruksi SIMD Eksplisit (Level 6 - Evaluation & Implementation):** Menulis algoritma evaluasi persepsi dan *steering behavior* ribuan agen menggunakan instruksi intrinsik AVX2/AVX-512 dengan penanganan *memory alignment* dan *loop peeling/tail cleanup* tanpa *undefined behavior*.
- **Mencegah Hardware Execution Hazards (Level 5 - Evaluation):** Memitigasi *false sharing*, *denormal float performance penalties*, dan *SIMD frequency throttling* pada sistem komputasi AI multithreaded real-time.

---

### 2. Concept Overview
Game engine modern menuntut pemrosesan puluhan ribu agen AI otonom (misal: sistem kerumunan/crowd simulation, persepsi sensorik, *spatial queries*) dalam batasan anggaran frame yang ketat (frame budget: $\le 16.6\text{ ms}$ untuk 60 FPS, atau $\le 8.33\text{ ms}$ untuk 120 FPS). Alokasi anggaran untuk modul AI umumnya hanya berkisar antara **1.0 hingga 2.5 ms**.

Secara tradisional, pemrograman AI berakar pada Object-Oriented Programming (OOP) murni:
```cpp
// Tradisional OOP (Array of Structures - AoS)
class AIAgent {
    Vector3 position;     // 12 bytes
    Vector3 velocity;     // 12 bytes
    float health;         // 4 bytes
    BrainTree* brain;     // 8 bytes (pointer)
    Target* currentTarget;// 8 bytes (pointer)
    // ... padding & vtable overhead
};
std::vector<AIAgent*> agents; // Fragmented Heap Allocation
```
Pendekatan ini memicu bencana latensi memori pada CPU modern yang dikenal sebagai **The Memory Wall**. Kecepatan komputasi Arithmetic Logic Unit (ALU) telah berkembang ratusan kali lipat lebih cepat daripada latensi akses Dynamic RAM (DRAM). Ketika CPU mengeksekusi logika persepsi agen:
1. Pointer chasing (`agent->currentTarget`) memaksa CPU berhenti (*stall*) selama 200–300 siklus clock untuk mengambil data dari DRAM ke register.
2. Ukuran satu *cache line* CPU adalah 64 bytes. Mengambil satu atribut agen (misal `position`) membawa serta atribut yang tidak relevan untuk perhitungan saat itu (`brain`, `health`), mencemari L1 Data Cache (*cache pollution*).

**Mental Model: Data-Oriented Design (DOD) & SIMD**
Transformasi ke arah Data-Oriented Design memisahkan data berdasarkan pola komputasi (*hot data* vs *cold data*) menggunakan *Structure of Arrays* (SoA). Dengan SoA, memori ditata secara linear dan contiguous (bersebelahan). 

Hal ini membuka kapabilitas **SIMD (Single Instruction, Multiple Data)**. Alih-alih memproses satu entitas per siklus kalkulasi kalkulus vektor (Scalar Processing), register SIMD (misal: AVX2 256-bit register `ymm0`-`ymm15`) memuat 8 unit data `float` sekaligus dan mengeksekusi operasi aritmatika (seperti kalkulasi jarak Euclidean kuadratik) dalam satu siklus komputasi vector ALU.

---

### 3. Why It Matters
Dalam skala enterprise dan game simulasi skala besar (MMO, RTS, open-world crowd systems):
- **OOM & Latensi Skala Masif:** Mengelola 50.000 agen dengan OOP tradisional menghasilkan fragmentasi heap masif, overhead *virtual table* (vtable), dan destruksi efisiensi *Instruction Cache* (I-Cache) akibat percabangan polimorfik (*virtual call dispatch*).
- **Thermal Throttling & Battery Drain:** Pada platform konsol genggam (Steam Deck, Nintendo Switch) atau mobile, *cache thrashing* memaksa controller memori bekerja terus menerus pada konsumsi daya tinggi. Memaksimalkan efisiensi komputasi per siklus instruksi melalui vector register secara dramatis menekan rasio *Watt-per-agent-update*.
- **Skalabilitas Deterministik:** Algoritma navigasi kerumunan (*boids*, *collision avoidance*, *sight checking*) yang divektorisasi menjamin waktu kalkulasi yang deterministik, menghilangkan *frame-drop spike* tak terduga saat kepadatan agen di layar meningkat.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah diagram alur komparasi antara tata letak memori OOP (AoS) tradisional vs Data-Oriented Design (SoA) yang masuk ke jalur eksekusi CPU Cache dan SIMD Vector Execution Pipeline:

```text
==================================================================================================
TRADISIONAL (Array of Structures / AoS) - Cache Inefficient & Scalar
==================================================================================================
Heap Memory: [ Agent 0 (Pos, Vel, Brain*, HP) ] ---> Pointer Chasing ---> [ Agent 1 (...) ]
             \_______________________________/
                     64-byte Cache Line
  L1 Data Cache:  | Pos0 | Vel0 | Brain* | HP | Pos1 | Vel1 | Brain* | HP |  (Banyak data mubazir)
                         \               /
Scalar Pipeline:          ALU (Pos0) -> Menunggu memory stall -> ALU (Pos1)  (1 agen per siklus)

==================================================================================================
DATA-ORIENTED DESIGN (Structure of Arrays / SoA) - Aligned & Vectorized
==================================================================================================
Contiguous Memory:
  PosX: [ x0, x1, x2, x3, x4, x5, x6, x7, x8, x9, ... ]  (32-Byte Aligned)
  PosY: [ y0, y1, y2, y3, y4, y5, y6, y7, y8, y9, ... ]  (32-Byte Aligned)
  PosZ: [ z0, z1, z2, z3, z4, z5, z6, z7, z8, z9, ... ]  (32-Byte Aligned)

                    | 32-Byte Load (AVX2)
                    v
AVX2 SIMD Reg:  ymm0 = [ x0, x1, x2, x3, x4, x5, x6, x7 ] (8 floats)
                ymm1 = [ tx, tx, tx, tx, tx, tx, tx, tx ] (Target X broadcasted)
                ------------------------------------------
SIMD Vector ALU: _mm256_sub_ps(ymm0, ymm1) -> 8 Kalkulasi Jarak Dikerjakan Simultan (1 Siklus)
==================================================================================================
```

#### Alur Eksekusi Instruksi SIMD & Memory Hierarchy
```text
 +-----------------------------------------------------------------------+
 |                            DRAM (Main Memory)                         |
 +-----------------------------------------------------------------------+
                                    | (64 Bytes Streamed via Prefetcher)
                                    v
 +-----------------------------------------------------------------------+
 |                             L3 Cache                                  |
 +-----------------------------------------------------------------------+
                                    |
                                    v
 +-----------------------------------------------------------------------+
 |                             L2 Cache                                  |
 +-----------------------------------------------------------------------+
                                    |
                                    v
 +-----------------------------------------------------------------------+
 |                       L1 Data Cache (32KB - 48KB)                     |
 +-----------------------------------------------------------------------+
             |                                             |
             v (Aligned 256-bit load: vmovaps)             v
 +-----------------------------+             +---------------------------+
 | Register YMM0..YMM15 (AVX2) |             | Execution Pipeline (FMA)  |
 +-----------------------------+             +---------------------------+
             \                                             /
              \____ Fused Multiply-Add (_mm256_fmadd_ps) _/
                                    |
                                    v
            Hasil 8 Agen Dikalkulasi Simultan per Port ALU
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Hierarki CPU Cache dan Cache Line Mechanics
Ukuran transfer atomik antara sistem memori dan inti CPU adalah **Cache Line** (standar: 64 bytes).
- **Spatial Locality:** Apabila thread membaca data di alamat memori `0x00`, CPU prefetcher memuat blok memory contiguous sebesar 64-byte dari `0x00` hingga `0x3F` langsung ke L1 Data Cache.
- **Temporal Locality:** Data yang baru saja diproses kemungkinan besar akan segera diproses kembali, sehingga dipertahankan pada L1/L2.
- **Cache Hit vs Miss Penalty:**
  - L1 Cache Hit: ~4–5 siklus CPU (~1 ns).
  - L2 Cache Hit: ~12–14 siklus CPU (~3 ns).
  - L3 Cache Hit: ~40–60 siklus CPU (~10–15 ns).
  - DRAM Access (Cache Miss): ~150–300 siklus CPU (~50–80 ns).
  
Ketika AI loop melakukan iterasi berbasis pointer (*pointer chasing*), rasio L1 Data Cache Miss dapat meroket hingga >30%, membuang ratusan siklus CPU dalam kondisi *idle* (*execution stall*).

#### 5.2 Anatomi Register SIMD dan Instruksi Intrinsik
SIMD memanfaatkan register berukuran lebar (*wide registers*) yang bertindak sebagai kontainer array primitif:
- **SSE:** 128-bit (Register `XMM`, memuat $4 \times \text{float 32-bit}$).
- **AVX / AVX2:** 256-bit (Register `YMM`, memuat $8 \times \text{float 32-bit}$).
- **AVX-512:** 512-bit (Register `ZMM`, memuat $16 \times \text{float 32-bit}$).

Operasi intrinsik hardware dipetakan langsung oleh compiler ke assembly opcode satu-ke-satu:
- `_mm256_load_ps`: Memuat 8 float dari memori yang ter-align 32-byte (`vmovaps`).
- `_mm256_loadu_ps`: Memuat 8 float dari memori unaligned (`vmovups`). Menghasilkan penalti latensi jika melintasi batas cache line (*split-load penalty*).
- `_mm256_sub_ps`: Eksekusi pengurangan paralel 8 pasang float (`vsubps`).
- `_mm256_fmadd_ps`: Fused Multiply-Add ($a \cdot b + c$) dengan presisi tunggal dan komputasi 1 siklus throughput (`vfmadd213ps`).
- `_mm256_cmp_ps`: Evaluasi komparasi relasional (e.g., `<TargetDistance`), menghasilkan bitmask (`vcmpps`).
- `_mm256_movemask_ps`: Mengekstraksi bit sign paling signifikan dari tiap jalur 32-bit register YMM ke register integer skalar 8-bit biasa (`vmovmskps`), memungkinkan kondisional AI bercabang tanpa instruksi *scalar branch* per entitas.

#### 5.3 Memory Alignment dan Boundary Traversal
Instruksi SIMD bekerja optimal jika alamat awal memori habis dibagi oleh ukuran register:
- AVX2 menuntut **32-byte alignment** (`alignas(32)`).
- AVX-512 menuntut **64-byte alignment** (`alignas(64)`).

Pelanggaran alignment saat menggunakan instruksi aligned load (`_mm256_load_ps`) akan memicu hardware exception: **General Protection Fault (`#GP`)**. Jika pengembang menggunakan unaligned load fallback (`_mm256_loadu_ps`), CPU tetap dapat mengeksekusi operasi tersebut, tetapi jika buffer melintasi dua cache lines (*cache line split*), performa throughput memori turun hingga 50% untuk operasi tersebut.

#### 5.4 Algoritma Tail Handling (Loop Peeling / Remainder Loop)
Jika simulasi memiliki $N$ agen, dan $N$ bukan kelipatan 8 (pada AVX2):
$$N = 8k + R \quad \text{di mana } R \in \{0, 1, \dots, 7\}$$
Instruksi vektor memproses iterasi utama sebanyak $k = \lfloor N / 8 \rfloor$ kali (memproses $8k$ agen). Sisa $R$ agen (*remainder tail*) harus ditangani melalui skalar loop konvensional atau *masked load/store* (`_mm256_maskload_ps`) untuk mencegah segfault / *out-of-bounds memory corruption*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem pemfilteran sensorik spasial AI (*Proximity & Field-of-View Perception System*) berkinerja tinggi untuk 100.000 agen. Kode ditulis dalam **C++20**, menggunakan arsitektur **Structure of Arrays (SoA)**, alokasi memori aligned via custom RAII allocator, dan eksekusi vektor AVX2 eksplisit.

```cpp
#include <iostream>
#include <vector>
#include <memory>
#include <chrono>
#include <immintrin.h>
#include <cstdlib>
#include <new>
#include <cassert>
#include <cstdint>
#include <cmath>

// ============================================================================
// 1. MEMORY MANAGEMENT: Cache-Aligned Custom Allocator (64-byte Boundary)
// ============================================================================
template <typename T, std::size_t Alignment = 64>
struct AlignedAllocator {
    using value_type = T;
    static constexpr std::size_t alignment = Alignment;

    AlignedAllocator() noexcept = default;
    template <typename U> AlignedAllocator(const AlignedAllocator<U, Alignment>&) noexcept {}

    [[nodiscard]] T* allocate(std::size_t n) {
        if (n == 0) return nullptr;
        if (n > std::size_t(-1) / sizeof(T)) throw std::bad_array_new_length();
        
        std::size_t bytes = n * sizeof(T);
        // Memastikan alokasi memenuhi constraint alignment AVX2/AVX-512
        void* ptr = nullptr;
#if defined(_MSC_VER) || defined(__MINGW32__)
        ptr = _aligned_malloc(bytes, Alignment);
        if (!ptr) throw std::bad_alloc();
#else
        if (posix_memalign(&ptr, Alignment, bytes) != 0) {
            throw std::bad_alloc();
        }
#endif
        return static_cast<T*>(ptr);
    }

    void deallocate(T* p, std::size_t) noexcept {
        if (!p) return;
#if defined(_MSC_VER) || defined(__MINGW32__)
        _aligned_free(p);
#else
        free(p);
#endif
    }

    template <typename U>
    bool operator==(const AlignedAllocator<U, Alignment>&) const noexcept { return true; }
    template <typename U>
    bool operator!=(const AlignedAllocator<U, Alignment>&) const noexcept { return false; }
};

// ============================================================================
// 2. DATA-ORIENTED AGENT SYSTEM (Structure of Arrays)
// ============================================================================
struct alignas(64) AIAgentSystemSoA {
    using AlignedFloatVector = std::vector<float, AlignedAllocator<float, 32>>;
    using AlignedUInt8Vector = std::vector<uint8_t, AlignedAllocator<uint8_t, 32>>;

    size_t count{0};

    // Parallel Arrays (Hot Data)
    AlignedFloatVector posX;
    AlignedFloatVector posY;
    AlignedFloatVector posZ;
    AlignedFloatVector velX;
    AlignedFloatVector velY;
    AlignedFloatVector velZ;

    // Perceptual Output / Target Flag (1 = Target Detected within Range, 0 = Otherwise)
    AlignedUInt8Vector isWithinPerceptionRange;

    explicit AIAgentSystemSoA(size_t agentCount) : count(agentCount) {
        posX.resize(count);
        posY.resize(count);
        posZ.resize(count);
        velX.resize(count);
        velY.resize(count);
        velZ.resize(count);
        isWithinPerceptionRange.resize(count, 0);

        // Verifikasi keselarasan memori saat inisialisasi
        assert(reinterpret_cast<uintptr_t>(posX.data()) % 32 == 0);
        assert(reinterpret_cast<uintptr_t>(posY.data()) % 32 == 0);
        assert(reinterpret_cast<uintptr_t>(posZ.data()) % 32 == 0);
    }
};

// ============================================================================
// 3. EXECUTION KERNEL: AVX2 Vectorized Perception Engine
// ============================================================================
class PerceptionSystemPipeline {
public:
    // Mengevaluasi kuadrat jarak terhadap sensor origin (misal: posisi Player)
    static void UpdatePerceptionAVX2(
        AIAgentSystemSoA& agents,
        float targetX, float targetY, float targetZ,
        float perceptionRadius
    ) noexcept {
        const size_t totalAgents = agents.count;
        const size_t simdWidth = 8; // AVX2 memproses 8 float (256-bit)
        const size_t vectorBatchCount = totalAgents / simdWidth;
        const size_t tailAgentsOffset = vectorBatchCount * simdWidth;

        const float radiusSquared = perceptionRadius * perceptionRadius;

        // Broadcast parameter target skalar ke seluruh jalur SIMD Register
        const __m256 vTargetX = _mm256_set1_ps(targetX);
        const __m256 vTargetY = _mm256_set1_ps(targetY);
        const __m256 vTargetZ = _mm256_set1_ps(targetZ);
        const __m256 vRadiusSq = _mm256_set1_ps(radiusSquared);

        // Raw pointers yang terjamin 32-byte aligned
        const float* const __restrict pX = agents.posX.data();
        const float* const __restrict pY = agents.posY.data();
        const float* const __restrict pZ = agents.posZ.data();
        uint8_t* const __restrict pResults = agents.isWithinPerceptionRange.data();

        // --------------------------------------------------------------------
        // SIMD Vector Loop Processing (AVX2 + FMA3)
        // --------------------------------------------------------------------
        for (size_t i = 0; i < tailAgentsOffset; i += simdWidth) {
            // Aligned Vector Loads
            __m256 x = _mm256_load_ps(&pX[i]);
            __m256 y = _mm256_load_ps(&pY[i]);
            __m256 z = _mm256_load_ps(&pZ[i]);

            // Delta computation: (AgentPos - TargetPos)
            __m256 dx = _mm256_sub_ps(x, vTargetX);
            __m256 dy = _mm256_sub_ps(y, vTargetY);
            __m256 dz = _mm256_sub_ps(z, vTargetZ);

            // Distance Squared via FMA: distSq = (dx*dx) + (dy*dy) + (dz*dz)
            __m256 distSq = _mm256_mul_ps(dx, dx);
            distSq = _mm256_fmadd_ps(dy, dy, distSq);
            distSq = _mm256_fmadd_ps(dz, dz, distSq);

            // Relational Comparison: distSq <= vRadiusSq
            // Hasil: Bitmask 0xFFFFFFFF jika true, 0x00000000 jika false
            __m256 cmpResult = _mm256_cmp_ps(distSq, vRadiusSq, _CMP_LE_OQ);

            // Ekstraksi 8-bit sign mask ke integer general-purpose register
            int mask = _mm256_movemask_ps(cmpResult);

            // Unrolled Bitmask Unpack ke Array Boolean Output
            pResults[i + 0] = static_cast<uint8_t>((mask >> 0) & 1);
            pResults[i + 1] = static_cast<uint8_t>((mask >> 1) & 1);
            pResults[i + 2] = static_cast<uint8_t>((mask >> 2) & 1);
            pResults[i + 3] = static_cast<uint8_t>((mask >> 3) & 1);
            pResults[i + 4] = static_cast<uint8_t>((mask >> 4) & 1);
            pResults[i + 5] = static_cast<uint8_t>((mask >> 5) & 1);
            pResults[i + 6] = static_cast<uint8_t>((mask >> 6) & 1);
            pResults[i + 7] = static_cast<uint8_t>((mask >> 7) & 1);
        }

        // --------------------------------------------------------------------
        // Scalar Tail Remainder Handling
        // --------------------------------------------------------------------
        for (size_t i = tailAgentsOffset; i < totalAgents; ++i) {
            float dx = pX[i] - targetX;
            float dy = pY[i] - targetY;
            float dz = pZ[i] - targetZ;
            float distSq = (dx * dx) + (dy * dy) + (dz * dz);
            pResults[i] = (distSq <= radiusSquared) ? 1 : 0;
        }
    }
};

// ============================================================================
// 4. BENCHMARK & VERIFIKASI (Baseline vs AVX2)
// ============================================================================
void RunScalarBaseline(
    const AIAgentSystemSoA& agents,
    float targetX, float targetY, float targetZ,
    float perceptionRadius,
    std::vector<uint8_t>& results
) {
    const float radiusSquared = perceptionRadius * perceptionRadius;
    const float* const pX = agents.posX.data();
    const float* const pY = agents.posY.data();
    const float* const pZ = agents.posZ.data();
    uint8_t* const pOut = results.data();

    for (size_t i = 0; i < agents.count; ++i) {
        float dx = pX[i] - targetX;
        float dy = pY[i] - targetY;
        float dz = pZ[i] - targetZ;
        float distSq = dx * dx + dy * dy + dz * dz;
        pOut[i] = (distSq <= radiusSquared) ? 1 : 0;
    }
}

int main() {
    constexpr size_t NUM_AGENTS = 131'077; // Angka non-kelipatan 8 guna menguji tail-handling
    constexpr float PERCEPTION_RADIUS = 25.0f;
    constexpr float TARGET_X = 100.0f;
    constexpr float TARGET_Y = 0.0f;
    constexpr float TARGET_Z = 100.0f;

    std::cout << "[INFO] Mengalokasikan & menginisialisasi " << NUM_AGENTS << " agen...\n";
    AIAgentSystemSoA agents(NUM_AGENTS);

    // Dummy initialization
    for (size_t i = 0; i < NUM_AGENTS; ++i) {
        agents.posX[i] = static_cast<float>(i % 200);
        agents.posY[i] = static_cast<float>((i / 200) % 50);
        agents.posZ[i] = static_cast<float>((i / 10000) % 200);
    }

    std::vector<uint8_t> baselineResults(NUM_AGENTS, 0);

    // 1. Eksekusi Skalar
    auto startScalar = std::chrono::high_resolution_clock::now();
    RunScalarBaseline(agents, TARGET_X, TARGET_Y, TARGET_Z, PERCEPTION_RADIUS, baselineResults);
    auto endScalar = std::chrono::high_resolution_clock::now();
    double scalarMs = std::chrono::duration<double, std::milli>(endScalar - startScalar).count();

    // 2. Eksekusi AVX2 SIMD
    auto startSIMD = std::chrono::high_resolution_clock::now();
    PerceptionSystemPipeline::UpdatePerceptionAVX2(agents, TARGET_X, TARGET_Y, TARGET_Z, PERCEPTION_RADIUS);
    auto endSIMD = std::chrono::high_resolution_clock::now();
    double simdMs = std::chrono::duration<double, std::milli>(endSIMD - startSIMD).count();

    // 3. Verifikasi Konsistensi Data Output
    size_t mismatches = 0;
    for (size_t i = 0; i < NUM_AGENTS; ++i) {
        if (baselineResults[i] != agents.isWithinPerceptionRange[i]) {
            mismatches++;
        }
    }

    std::cout << "========================================================\n";
    std::cout << "HASIL BENCHMARK OPTIMASI SIMD PERSEPSI AGEN AI\n";
    std::cout << "========================================================\n";
    std::cout << "Jumlah Entitas Agen     : " << NUM_AGENTS << "\n";
    std::cout << "Waktu Skalar Baseline   : " << scalarMs << " ms\n";
    std::cout << "Waktu AVX2 Vectorized   : " << simdMs << " ms\n";
    std::cout << "Speedup Factor          : " << (scalarMs / simdMs) << "x\n";
    std::cout << "Status Validasi Bitmask : " << (mismatches == 0 ? "PASSED (IDENTIK)" : "FAILED (DATA CORRUPTED)") << "\n";
    std::cout << "========================================================\n";

    return (mismatches == 0) ? 0 : 1;
}
```

---

### 7. Edge Cases & Failure Modes

1. **Unaligned Memory Segfaults (`#GP Exception`):**
   *Mekanisme Kegagalan:* Memanggil `_mm256_load_ps` pada pointer yang tidak memiliki kelipatan alamat 32-byte menghasilkan crash instan operating system (`EXC_BAD_ACCESS` atau `Segmentation Fault`).
   *Mitigasi:* Gunakan `alignas(32)` pada struktur statis atau implementasikan `posix_memalign` / `_aligned_malloc` terenkapsulasi dalam modern C++ allocator. Pastikan runtime testing memvalidasi:
   `assert(reinterpret_cast<uintptr_t>(ptr) % 32 == 0);`.

2. **Denormal / Subnormal Floats Throttling:**
   *Mekanisme Kegagalan:* Ketika kalkulasi jarak mendekati `0.0f` dan menghasilkan float subnormal ($< 1.175494 \times 10^{-38}$), ALU floating-point SIMD internal beralih ke microcode emulation mode. Hal ini dapat memperlambat throughput instruksi hingga **100x lipat**.
   *Mitigasi:* Aktifkan bit **Flush-To-Zero (FTZ)** dan **Denormals-Are-Zero (DAZ)** pada Control/Status Register MXCSR CPU saat startup engine thread:
   ```cpp
   #include <immintrin.h>
   _mm_setcsr(_mm_getcsr() | _MM_FLUSH_ZERO_ON | _MM_DENORMALS_ZERO_ON);
   ```

3. **AVX-512 Frequency Throttling (Clock Downclocking):**
   *Mekanisme Kegagalan:* Pada CPU arsitektur Intel era terdahulu (Skylake-X / Cascade Lake), mengeksekusi instruksi 512-bit vector kontinu pada unit FP menyebabkan penarikan arus daya besar, memaksa seluruh core CPU menurunkan *base clock frequency* (sebesar 10–20%), mendegradasi throughput thread non-SIMD lainnya.
   *Mitigasi:* Untuk komputasi AI game kontemporer, gunakan **AVX2 (256-bit)** sebagai standar target umum cross-platform (didukung seragam pada AMD Zen 1–4, Intel Core modern, dan arsitektur konsol PS5/Xbox Series via Zen 2).

4. **False Sharing pada Multithreaded AI Updates:**
   *Mekanisme Kegagalan:* Dua thread worker mengupdate array boolean hasil yang berdekatan. Jika Thread A menulis ke `results[0..31]` dan Thread B menulis ke `results[32..63]`, kedua slice tersebut berada pada satu 64-byte Cache Line yang sama. CPU core akan terus menerus melempar sinyal *cache invalidation bus traffic* via protocol MESI, melumpuhkan performa multicore.
   *Mitigasi:* Lakukan partisi batch komputasi AI multithreading minimal dalam blok kelipatan 64 bytes (atau alokasikan thread-local buffer sementara sebelum digabungkan).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Array of Structures (AoS) | Structure of Arrays (SoA) | Array of Structures of Arrays (AoSoA) | Compute Shader / GPGPU |
| :--- | :--- | :--- | :--- | :--- |
| **Pola Akses Memori** | Dispersed / Random Cache Misses | Linear Contiguous Streaming | Block-Contiguous Tile Streaming | Massively Parallel Coalesced |
| **Kapasitas SIMD** | Sulit (Butuh `_mm256_shuffle` overhead) | Sempurna untuk vektorisasi instruksi | Optimal untuk Register Fitting (e.g., blok 8/16) | Native hardware SIMT execution |
| **Kompleksitas Kode** | Rendah (Natural OOP, Encapsulated) | Tinggi (Pemisahan array & refactoring) | Sangat Tinggi (Membutuhkan metaprogramming) | Tinggi (Pemisahan konteks CPU-GPU & PCIe bus) |
| **Latensi Transfer** | 0 ns (Data residing on host CPU) | 0 ns (Data residing on host CPU) | 0 ns (Data residing on host CPU) | Signifikan (Perjalanan buffer via bus PCIe 1–5 ms) |
| **Use Case Terbaik** | AI State logic kompleks & deep branching (<500 agen) | Algoritma crowds, steering, boids, & spatial perception (5k - 200k agen) | Sistem ECS ultra-low-level cache tile | AI skala masif (>200k entitas tanpa feedback latency ketat) |

#### AoS vs SoA vs AoSoA (Tiled SIMD)
SoA memiliki satu kekurangan struktural: jika ukuran array melebihi ukuran L1/L2 cache, *strided loading* dari beberapa array terpisah (X, Y, Z, Vx, Vy, Vz) dapat melebihi kapasitas **TLB (Translation Lookaside Buffer)** dan hardware prefetch stream limiters (biasanya 8–16 stream hardware per core). 
Solusi enterprise hybrid mutakhir adalah **AoSoA**:
```cpp
template <size_t SIMD_WIDTH = 8>
struct AgentChunk {
    float x[SIMD_WIDTH];
    float y[SIMD_WIDTH];
    float z[SIMD_WIDTH];
};
// Alokasi memori berukuran tepat sebesar pecahan L1 cache tile
std::vector<AgentChunk<8>> agentChunks;
```

---

### 9. Best Practices & Standard Industri

1. **Profiling-Guided Verification:**
   - Gunakan **Intel VTune** atau **AMD µProf** untuk melacak metrik perangkat keras:
     - `CPI Rate` (Cycles Per Instruction): Targetkan $< 0.75$.
     - `L1 Data Cache Hit Rate`: Targetkan $> 95\%$.
     - `Vectorization Intensity`: Pastikan persentase instruksi vector floating-point berada di atas $80\%$ pada loop kernel AI.
   - Sematkan profiler frame realtime bertaraf industri seperti **Tracy Profiler** (`FrameMark`, `ZoneScopedN`) untuk mengukur latensi frame budget secara deterministik tanpa interferensi sampling overhead.
2. **Kompiler Flag & Auto-Vectorization Hygiene:**
   - Gunakan `-O3` (GCC/Clang) atau `/O2 /arch:AVX2` (MSVC).
   - Selalu tambahkan flag `-fopt-info-vec-optimized` atau `-fopt-info-vec-missed` pada GCC/Clang guna memverifikasi apakah compiler berhasil meng-autovektorisasi loop skalar Anda sebelum memutuskan menulis manual SIMD intrinsics.
3. **Keyword `__restrict`:**
   - Selalu berikan compiler petunjuk eksplisit pointer aliasing via `float* __restrict ptr`. Tanpa `__restrict`, compiler dipaksa berasumsi bahwa memori input dapat saling bertumpukan (*pointer aliasing*), sehingga menolak melakukan reordering instruksi dan vektorisasi otomatis.
4. **Isolasi Logika Branching Kompleks:**
   - Pisahkan logika deterministik murni (*Linear Algebra*, *Steering Behaviors*, *Physics Integrators*) dari pohon logika kompleks (*Behavior Trees*, *Utility AI*). Jalankan komputasi deterministik massal secara batch via SIMD, dan simpan hasilnya dalam bentuk status bitmask yang dievaluasi secara asinkron oleh thread pengambilan keputusan.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan mengoptimalkan sistem navigasi *Boids Flocking Separation* untuk armada 65.536 drone tempur musuh yang mengalami bottleneck kritis pada game prototype engine. Sistem skalar saat ini memakan waktu $22.4\text{ ms}$ CPU time (melebihi seluruh frame budget 60 FPS).

#### Langkah 1: Persiapan Environment
1. Siapkan file source C++ baru bernama `simd_boids_lab.cpp`.
2. Pastikan compiler Anda mendukung C++20 dan ekstensi AVX2 (GCC 10+, Clang 11+, atau MSVC 2019+).
3. Flag kompilasi yang wajib digunakan:
   - GCC/Clang: `g++ -O3 -mavx2 -mfma -std=c++20 simd_boids_lab.cpp -o simd_boids`
   - MSVC: `cl /O2 /arch:AVX2 /std:c++20 simd_boids_lab.cpp`

#### Langkah 2: Implementasi Task
Lengkapi stub kode berikut untuk mengimplementasikan *Boids Separation Force Kernel*:
Formula kalkulasi separation per agen $i$ terhadap titik ancaman $T$:
$$\vec{F} = \begin{cases} \frac{\vec{P}_i - \vec{T}}{\|\vec{P}_i - \vec{T}\|^2} & \text{jika } \|\vec{P}_i - \vec{T}\|^2 < R^2 \\ \vec{0} & \text{lainnya} \end{cases}$$

Gunakan operasi reciprocal square root AVX: `_mm256_rcp_ps` atau gabungan `_mm256_rsqrt_ps` untuk efisiensi komputasi ekstrem.

```cpp
#include <iostream>
#include <immintrin.h>
#include <vector>
#include <chrono>

// Alokasikan buffer aligned 32-byte
alignas(32) float posX[65536];
alignas(32) float posY[65536];
alignas(32) float forceX[65536];
alignas(32) float forceY[65536];

void ComputeSeparationAVX2(size_t n, float threatX, float threatY, float radius) {
    const float radiusSq = radius * radius;
    const __m256 vThreatX = _mm256_set1_ps(threatX);
    const __m256 vThreatY = _mm256_set1_ps(threatY);
    const __m256 vRadiusSq = _mm256_set1_ps(radiusSq);
    const __m256 vZero = _mm256_setzero_ps();

    for (size_t i = 0; i < n; i += 8) {
        // TUGAS ANDA:
        // 1. Muat 8 elemen posX dan posY menggunakan _mm256_load_ps.
        // 2. Hitung delta vector (dx, dy) terhadap (vThreatX, vThreatY).
        // 3. Hitung distSq = dx*dx + dy*dy via _mm256_fmadd_ps.
        // 4. Lakukan evaluasi boolean mask (distSq < vRadiusSq).
        // 5. Hitung inverse distSq menggunakan perkiraan cepat _mm256_rcp_ps(distSq).
        // 6. Terapkan masking via _mm256_blendv_ps: jika di dalam radius, simpan (dx * invDistSq), jika tidak set ke 0.0f.
        // 7. Simpan output ke array forceX dan forceY menggunakan _mm256_store_ps.
        
        // --- TULIS IMPLEMENTASI AVX2 ANDA DI SINI ---
    }
}

int main() {
    constexpr size_t TOTAL_DRONES = 65536;
    for (size_t i = 0; i < TOTAL_DRONES; ++i) {
        posX[i] = static_cast<float>(i % 500);
        posY[i] = static_cast<float>((i / 500) % 500);
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    ComputeSeparationAVX2(TOTAL_DRONES, 250.0f, 250.0f, 50.0f);
    auto t2 = std::chrono::high_resolution_clock::now();

    std::cout << "Kalkulasi SIMD Boids selesai dalam: " 
              << std::chrono::duration<double, std::milli>(t2 - t1).count() 
              << " ms\n";
    return 0;
}
```

#### Validasi Sukses Lab
Eksekusi program berhasil apabila:
1. Waktu komputasi untuk 65.536 unit drone turun dari $>20.0\text{ ms}$ ke **$< 0.8\text{ ms}$** pada mesin uji modern (speedup minimal $\ge 15\times$ dibanding skalar murni non-SIMD).
2. Tidak terjadi *Crash Segmentation Fault* akibat unaligned load/store.
3. Nilai gaya dorong pada indeks terluar yang berada di luar radius bernilai tepat `0.0f`.