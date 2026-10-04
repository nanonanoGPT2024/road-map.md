# BAB-09: Profiling, Komputasi SIMD, & Optimasi Hardware
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
1. **Menganalisis dan Memetakan Hardware Bottlenecks**: Mengidentifikasi *instruction stalls*, *branch mispredictions*, *cache line bouncing*, dan *TLB misses* pada sub-sistem AI agen menggunakan Hardware Performance Counters (PMU) dan profiler modern (Tracy, Intel VTune).
2. **Merancang Transformasi Memori SIMD-Friendly**: Mengonversi arsitektur data AI dari *Array of Structures* (AoS) menjadi *Structure of Arrays* (SoA) dan *Array of Structures of Arrays* (AoSoA) dengan *data alignment* 32-byte (AVX2) dan 64-byte (AVX-512 / Cache Line).
3. **Mengimplementasikan Algoritma AI Menggunakan Intrinsics Vector**: Menulis kernel komputasi persepsi visual (*vision cone query*), kalkulasi jarak multi-target (*Euclidean proximity*), dan evaluasi *Utility AI response curves* secara branchless menggunakan instruksi eksplisit x86-64 SIMD (AVX2/FMA).
4. **Mengeliminasi Concurrency Penalties**: Mendesain buffer data persepsi berbasis *thread-local arena allocators* untuk mencegah *false sharing* dan meminimalisasi latensi sinkronisasi pada arsitektur CPU multi-core heterogen.

---

### 2. Prerequisite

Sebelum mendalami modul ini, peserta wajib menguasai:
* **C++20 Tingkat Mahir**: Pemahaman mendalam tentang *memory model*, *alignment* (`alignas`, `std::aligned_alloc`), *templates*, *type traits*, dan konsep pointer aritmatika tingkat rendah.
* **Arsitektur CPU Modern**: Hierarki cache (L1d, L1i, L2, L3), ukuran *cache line* standar (64 byte), *pipelining*, *superscalar execution*, dan *out-of-order execution engine*.
* **Dasar AI Game**: Komponen representasi matematis vektor 3D, *dot product*, *cone vision checks*, dan arsitektur dasar *Utility AI / Behavior Trees*.
* **Modul Prasyarat**: *BAB-09 Module 01 - Dasar SIMD dan Arsitektur CPU untuk Game Dev*.

---

### 3. Concept & Internal Architecture

Dalam game berskala masif (*Open World*, RTS, *Massive Battle Simulation*), sub-sistem AI agen otonom sering kali menjadi *bottleneck* komputasi utama CPU. Ketika 10.000 agen harus mengevaluasi ancaman di sekitarnya secara bersamaan pada *framerate target* 60 FPS (16.67 ms per frame), anggaran waktu (*frame budget*) untuk AI sering kali dibatasi tidak lebih dari **1.5 hingga 2.0 ms**.

Pendekatan *Object-Oriented Programming* (OOP) tradisional gagal memenuhi batasan ini karena memecah state agen ke dalam alokasi *heap* individual yang berserakan, menyebabkan fenomena *Cache Thrashing* konstan.

```
Pendekatan OOP Tradisional (AoS - Array of Structures):
[Agent 0: Pos(12B), HP(4B), State(4B), Velo(12B)] -> [Agent 1: Pos(12B), HP(4B), State(4B), Velo(12B)] ...
Problem: Saat membaca Posisi untuk perhitungan jarak, 20 Byte data lainnya ditarik ke L1 cache tanpa terpakai.
```

#### 3.1. Register SIMD & Pipeline Execution
SIMD (*Single Instruction, Multiple Data*) memungkinkan eksekusi satu instruksi operasi matematika terhadap beberapa komponen data secara simultan menggunakan register vektor berukuran besar:
* **SSE/NEON**: 128-bit (4x `float` 32-bit).
* **AVX / AVX2**: 256-bit (8x `float` 32-bit).
* **AVX-512**: 512-bit (16x `float` 32-bit).

```
Operasi AVX2 (256-bit register: __m256):
Target 0..7 PosX: [ x0 | x1 | x2 | x3 | x4 | x5 | x6 | x7 ]
Agent   PosX:     [ xa | xa | xa | xa | xa | xa | xa | xa ]
                  ----------------------------------------- (sub_ps)
Hasil dX:         [dx0 |dx1 |dx2 |dx3 |dx4 |dx5 |dx6 |dx7 ]
```

Pada tingkat hardware, prosesor modern mengeksekusi instruksi ini melalui *Fused Multiply-Add* (FMA) unit dalam satu siklus clock instruksional, memberikan *peak throughput* teoritis hingga 16 operasi *single-precision floating point* per siklus per core pada instruksi FMA 256-bit.

#### 3.2. Data Layout Paradigm: AoS vs SoA vs AoSoA

```
1. AoS (Array of Structures):
   [ x y z w | x y z w | x y z w | x y z w ] -> Membutuhkan 'shuffle' instruksi saat dimuat ke register SIMD.

2. SoA (Structure of Arrays):
   X: [ x x x x x x x x ... ]
   Y: [ y y y y y y y y ... ]
   Z: [ z z z z z z z z ... ]
   Ideal untuk SIMD masif murni, tetapi jelek jika kita butuh referensi parsial satu agen individual.

3. AoSoA (Array of Structures of Arrays / Tiled SoA):
   Membagi array menjadi blok/tile selebar register SIMD (e.g., N=8 untuk AVX2):
   [ Block 0 (x0..x7, y0..y7, z0..z7) ] -> [ Block 1 (x8..x15, y8..y15, z8..z15) ]
   Ideal untuk Cache Line (64-byte chunks) dan register vector loads direct-mapped tanpa konversi.
```

#### 3.3. Cache Lines, False Sharing, dan Data Alignment
* **Cache Line Alignment**: Ukuran L1/L2 cache line pada x86_64 dan ARM adalah 64 byte. Struktur data yang tidak sejajar (*unaligned*) melintasi batas 64-byte memaksa *memory controller* melakukan dua pembacaan cache line terpisah untuk satu instruksi *load*.
* **False Sharing**: Terjadi ketika Thread A pada Core 1 memodifikasi variabel `AgentData[0]`, sementara Thread B pada Core 2 membaca variabel `AgentData[1]` yang berada dalam satu cache line 64-byte yang sama. Hardware CPU memicu invalidasi cache protokol MESI (*Modified, Exclusive, Shared, Invalid*), memaksa bus memori melakukan sinkronisasi ulang dan menghancurkan skalar performa multi-threading.

---

### 4. Why & What

| Dimensi | Pendekatan Skalar / Tradisional (OOP) | Pendekatan SIMD + DOD (Data-Oriented) |
| :--- | :--- | :--- |
| **Pola Akses Memori** | *Pointer chasing*, data tersebar acak di RAM (*High Cache Misses*). | *Contiguous linear access*, sequential streaming (*HW Prefetcher Friendly*). |
| **Instruksi per Elemen** | 1 instruksi per operasi per elemen data (Scalar SSE/x87). | 1 instruksi per 8 elemen data (AVX2) atau 16 elemen (AVX-512). |
| **Divergensi Percabangan** | Percabangan *if-else* memicu *branch mispredictions* pipeline flush. | *Branchless computing* dengan masks & blend instructions (`_mm256_blendv_ps`). |
| **Throughput (10k Agen)** | ~8.0 - 15.0 ms (kalkulasi jarak & seleksi persepsi). | ~0.15 - 0.45 ms (menggunakan SIMD intrinsics AVX2). |
| **CPU Saturation** | Instruksi CPU sering *stalled* menunggu data dari DRAM (Memory-bound). | Unit eksekusi vector FMA terutilisasi penuh (Compute-bound yang optimal). |

---

### 5. How (Workflow Detail)

Berikut adalah tahapan teknis mentransformasikan pipeline update AI konvensional menjadi engine komputasi vektor berkinerja tinggi:

```
[Tahap 1: Data Structuring]
 Pisahkan data AI Agen menjadi read-only temporal context dan state variables.
 Susun dalam layout AoSoA dengan chunk N=8 (AVX2) beralignment 32/64-byte.
                │
                ▼
[Tahap 2: Memory Prefetching & Streaming]
 Gunakan `_mm_prefetch` ke L1/L2 cache untuk blok memori step N+1.
 Baca data langsung ke register __m256 menggunakan `_mm256_load_ps` (Aligned Load).
                │
                ▼
[Tahap 3: SIMD Math Execution (Fused Ops)]
 Hitung vektor delta (dX, dY, dZ), kalkulasi jarak via _mm256_fmadd_ps.
 Gunakan Reciprocal Square Root (`_mm256_rsqrt_ps`) + 1 iterasi Newton-Raphson refinement.
                │
                ▼
[Tahap 4: Branchless Masking & Filtering]
 Evaluasi kondisi persepsi (Distance < MaxDist && Angle < FOV).
 Bangun mask register via `_mm256_cmp_ps`.
 Eliminasi percabangan runtime menggunakan `_mm256_blendv_ps`.
                │
                ▼
[Tahap 5: Compressed Result Aggregation]
 Konversi hasil mask ke bitmask integer (`_mm256_movemask_ps`).
 Tulis kembali state hasil evaluasi ke memory buffer agen secara streaming tanpa merusak cache line lain.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan sebuah kantor imigrasi bandara yang harus memverifikasi 10.000 paspor.
* **Pendekatan Skalar (AoS / OOP)**: Petugas memanggil 1 turis, menanyakan nama, membuka koper turis untuk memeriksa barang bawaan, meminta paspornya, menstempel paspor, lalu menyuruh turis itu pergi. Kemudian memanggil turis berikutnya. Sebagian besar waktu terbuang untuk menunggu turis membuka koper.
* **Pendekatan SIMD + AoSoA**: Paspor 8 turis dijajarkan bersamaan di atas meja cetak presisi. Mesin stempel raksasa dengan 8 kepala pengetuk jatuh sekaligus dalam 1 detik. Koper turis tidak pernah dibawa ke meja paspor; data koper ditaruh di gudang terpisah.

#### Pemetaan Cache Line & Layout Memori

```
Representasi 1 Blok Cache Line (64 Bytes) pada AoSoA:
========================================================================================
Offset: 0x00                     0x20                                             0x40
Data:   [ PosX (8 x float = 32B) ] [ PosY (8 x float = 32B) ]                     | Cache Line 0
Data:   [ PosZ (8 x float = 32B) ] [ TargetID / Flags (8 x uint32 = 32B) ]        | Cache Line 1
========================================================================================
Register AVX2 Load (Aligned):
ymm0 <--- Aligned Load dari Offset 0x00 (Semua 8 komponen PosX langsung siap di-compute)
ymm1 <--- Aligned Load dari Offset 0x20 (Semua 8 komponen PosY langsung siap di-compute)
Tidak ada penataan ulang byte (zero shuffles), overhead pemindahan memori = 0 cycle!
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Perbandingan Jarak Skalar vs AVX2 (Thresholding Proximity)

```cpp
#include <immintrin.h>
#include <iostream>
#include <vector>
#include <chrono>

// Evaluasi jarak skalar
void ProximityScalar(const float* __restrict x, const float* __restrict y, 
                     const float* __restrict z, uint8_t* __restrict results, 
                     float thresholdSq, size_t count) 
{
    for (size_t i = 0; i < count; ++i) {
        float distSq = x[i] * x[i] + y[i] * y[i] + z[i] * z[i];
        results[i] = (distSq <= thresholdSq) ? 1 : 0;
    }
}

// Evaluasi jarak AVX2 (Memproses 8 agen per iterasi)
void ProximityAVX2(const float* __restrict x, const float* __restrict y, 
                    const float* __restrict z, uint8_t* __restrict results, 
                    float thresholdSq, size_t count) 
{
    __m256 vThresholdSq = _mm256_set1_ps(thresholdSq);

    for (size_t i = 0; i < count; i += 8) {
        // Load aligned 32-byte chunks
        __m256 vx = _mm256_load_ps(&x[i]);
        __m256 vy = _mm256_load_ps(&y[i]);
        __m256 vz = _mm256_load_ps(&z[i]);

        // FMA: distSq = (x*x) + (y*y) + (z*z)
        __m256 vDistSq = _mm256_mul_ps(vx, vx);
        vDistSq = _mm256_fmadd_ps(vy, vy, vDistSq);
        vDistSq = _mm256_fmadd_ps(vz, vz, vDistSq);

        // Bandingkan distSq <= vThresholdSq
        __m256 vMask = _mm256_cmp_ps(vDistSq, vThresholdSq, _CMP_LE_OQ);

        // Ekstraksi 8-bit mask (1 bit per float result)
        int mask = _mm256_movemask_ps(vMask);

        for (int b = 0; b < 8; ++b) {
            results[i + b] = (mask & (1 << b)) ? 1 : 0;
        }
    }
}
```

#### 7.2. Practical Example: Production-Grade Agent Sensory Vision & Utility AI Evaluator

Contoh industri di bawah mengimplementasikan *AoSoA batch query perception system* teroptimasi AVX2/FMA, lengkap dengan branchless vision-cone checks, evaluasi utilitas kuadratik, serta alokasi memori aligned 64-byte.

```cpp
#include <iostream>
#include <vector>
#include <memory>
#include <immintrin.h>
#include <cstdint>
#include <cassert>

// Custom Allocator untuk menjamin alokasi memory aligned 64-byte (Cache Line friendly)
template <typename T, size_t Alignment = 64>
struct AlignedAllocator {
    using value_type = T;

    AlignedAllocator() noexcept = default;
    template <typename U> AlignedAllocator(const AlignedAllocator<U, Alignment>&) noexcept {}

    T* allocate(size_t n) {
        if (n == 0) return nullptr;
        size_t bytes = n * sizeof(T);
        // Memastikan kelipatan alignment
        size_t space = bytes + Alignment;
        void* ptr = std::aligned_alloc(Alignment, space);
        if (!ptr) throw std::bad_alloc();
        return static_cast<T*>(ptr);
    }

    void deallocate(T* p, size_t) noexcept {
        std::free(p);
    }
};

// Struktur Data AoSoA Tiled Packet (8 Agen per Tile untuk register 256-bit AVX2)
struct alignas(64) AgentSensorTile {
    float posX[8];
    float posY[8];
    float posZ[8];
    float forwardX[8];
    float forwardY[8];
    float forwardZ[8];
    float utilityScore[8];
    uint32_t agentID[8];
};

class PerceptionSystemAVX2 {
public:
    static void EvaluateVisionConeAndUtility(
        const AgentSensorTile* __restrict tiles,
        size_t numTiles,
        float targetX, float targetY, float targetZ,
        float maxRangeSq,
        float cosFovThreshold,
        float* __restrict outScores,
        uint8_t* __restrict outDetectionMask)
    {
        // Broadcast data target dan parameter konfigurasi ke register AVX2
        const __m256 vTargetX = _mm256_set1_ps(targetX);
        const __m256 vTargetY = _mm256_set1_ps(targetY);
        const __m256 vTargetZ = _mm256_set1_ps(targetZ);
        const __m256 vMaxRangeSq = _mm256_set1_ps(maxRangeSq);
        const __m256 vCosFov = _mm256_set1_ps(cosFovThreshold);
        const __m256 vZero = _mm256_setzero_ps();
        const __m256 vOne = _mm256_set1_ps(1.0f);
        const __m256 vHalf = _mm256_set1_ps(0.5f);
        const __m256 vThreeHalfs = _mm256_set1_ps(1.5f);

        for (size_t t = 0; t < numTiles; ++t) {
            // Software prefetching untuk tile berikutnya (stride L1/L2 prefetch)
            _mm_prefetch(reinterpret_cast<const char*>(&tiles[t + 1]), _MM_HINT_T0);

            const AgentSensorTile& tile = tiles[t];

            // 1. Load Aligned Vector Components (Semua pointer tile dijamin 64-byte aligned)
            __m256 px = _mm256_load_ps(tile.posX);
            __m256 py = _mm256_load_ps(tile.posY);
            __m256 pz = _mm256_load_ps(tile.posZ);

            // 2. Vector Delta (Target - Agent)
            __m256 dx = _mm256_sub_ps(vTargetX, px);
            __m256 dy = _mm256_sub_ps(vTargetY, py);
            __m256 dz = _mm256_sub_ps(vTargetZ, pz);

            // 3. Distance Squared = dx*dx + dy*dy + dz*dz
            __m256 distSq = _mm256_mul_ps(dx, dx);
            distSq = _mm256_fmadd_ps(dy, dy, distSq);
            distSq = _mm256_fmadd_ps(dz, dz, distSq);

            // Jarak < Jarak Maksimum Filter
            __m256 rangeMask = _mm256_cmp_ps(distSq, vMaxRangeSq, _CMP_LT_OQ);

            // 4. Fast Reciprocal Square Root (rsqrt) + 1-iteration Newton-Raphson untuk invDist
            // Formula NR: y_n+1 = y_n * (1.5 - 0.5 * x * y_n^2)
            __m256 invDistApprox = _mm256_rsqrt_ps(distSq);
            __m256 muls = _mm256_mul_ps(_mm256_mul_ps(distSq, invDistApprox), invDistApprox);
            __m256 invDist = _mm256_mul_ps(invDistApprox, _mm256_sub_ps(vThreeHalfs, _mm256_mul_ps(vHalf, muls)));

            // 5. Normalisasi vektor arah (DirToTarget = Delta * invDist)
            __m256 dirX = _mm256_mul_ps(dx, invDist);
            __m256 dirY = _mm256_mul_ps(dy, invDist);
            __m256 dirZ = _mm256_mul_ps(dz, invDist);

            // 6. Dot Product dengan Forward Vector (DirToTarget . ForwardVector)
            __m256 fx = _mm256_load_ps(tile.forwardX);
            __m256 fy = _mm256_load_ps(tile.forwardY);
            __m256 fz = _mm256_load_ps(tile.forwardZ);

            __m256 dot = _mm256_mul_ps(dirX, fx);
            dot = _mm256_fmadd_ps(dirY, fy, dot);
            dot = _mm256_fmadd_ps(dirZ, fz, dot);

            // Angle check: Dot >= CosFovThreshold
            __m256 angleMask = _mm256_cmp_ps(dot, vCosFov, _CMP_GE_OQ);

            // Gabungkan kriteria deteksi visual
            __m256 detectMask = _mm256_and_ps(rangeMask, angleMask);

            // 7. Evaluasi Response Curve Utility AI (Quadratic falloff berdasarkan kedekatan):
            // score = (1.0 - (distSq / maxRangeSq))^2 jika terdeteksi, 0.0 jika tidak.
            __m256 normalizedDist = _mm256_mul_ps(distSq, _mm256_rcp_ps(vMaxRangeSq));
            __m256 baseScore = _mm256_max_ps(vZero, _mm256_sub_ps(vOne, normalizedDist));
            __m256 utility = _mm256_mul_ps(baseScore, baseScore);

            // Terapkan deteksi mask (Branchless Blend)
            __m256 finalScore = _mm256_blendv_ps(vZero, utility, detectMask);

            // 8. Tulis hasil kembali ke output buffer
            size_t outOffset = t * 8;
            _mm256_storeu_ps(&outScores[outOffset], finalScore);

            // Store byte mask
            int bitMask = _mm256_movemask_ps(detectMask);
            for (int i = 0; i < 8; ++i) {
                outDetectionMask[outOffset + i] = (bitMask & (1 << i)) ? 1 : 0;
            }
        }
    }
};

int main() {
    constexpr size_t TOTAL_AGENTS = 8000;
    constexpr size_t NUM_TILES = TOTAL_AGENTS / 8;

    std::vector<AgentSensorTile, AlignedAllocator<AgentSensorTile, 64>> tiles(NUM_TILES);
    std::vector<float, AlignedAllocator<float, 64>> outScores(TOTAL_AGENTS);
    std::vector<uint8_t, AlignedAllocator<uint8_t, 64>> outMasks(TOTAL_AGENTS);

    // Inisialisasi Mock Data
    for (size_t t = 0; t < NUM_TILES; ++t) {
        for (int i = 0; i < 8; ++i) {
            tiles[t].posX[i] = static_cast<float>(t * 8 + i) * 0.1f;
            tiles[t].posY[i] = 0.0f;
            tiles[t].posZ[i] = 5.0f;
            tiles[t].forwardX[i] = 0.0f;
            tiles[t].forwardY[i] = 0.0f;
            tiles[t].forwardZ[i] = -1.0f; // Menghadap -Z
        }
    }

    PerceptionSystemAVX2::EvaluateVisionConeAndUtility(
        tiles.data(), NUM_TILES,
        0.0f, 0.0f, 0.0f, // Target di origin
        1000.0f,           // RangeSq (31.62 radius)
        0.707f,            // Cos(45 deg) FOV
        outScores.data(),
        outMasks.data()
    );

    std::cout << "[INFO] Evaluasi AI Perception Berhasil Dieksekusi untuk " 
              << TOTAL_AGENTS << " Agen." << std::endl;
    std::cout << "Tile 0, Agen 0 Score: " << outScores[0] 
              << " | Detected: " << static_cast<int>(outMasks[0]) << std::endl;

    return 0;
}
```

---

### 8. Real World Case Study

#### Skenario: AAA Tactical Open-World Game (Project Titan)
* **Konteks**: Sistem crowd AI militer yang terdiri dari 32.000 infanteri AI yang bertempur dalam peta sandbox 8x8 km.
* **Problem**: Profiler internal menunjukkan AI update memakan waktu **14.2 ms per frame** pada CPU AMD Ryzen 7 3700X, menghabiskan 85% dari total frame budget 60 FPS (16.6 ms).
* **Investigasi PMU (Intel VTune / AMD μProf)**:
  * IPC (*Instructions Per Cycle*): Sangat rendah, hanya **0.42** (Idealnya > 2.0).
  * L1d Cache Hit Rate: Hanya **68%**; L3 Cache Miss Rate tinggi akibat dereference polimorfik pointer `std::vector<IAgentBehavior*>`.
  * Branch Misprediction Rate: **18.4%** karena evaluasi *if-else* mendalam pada pohon keputusan (*Decision Trees*) dalam loop jarak dekat.
* **Solusi Enterprise**:
  1. *Memory Restructuring*: Mengubah seluruh entitas AI dari inheritance tree berbasis heap menjadi blok data **AoSoA (Tile 8)** yang dialokasikan dalam *Thread-Local Linear Arena Allocator*.
  2. *Vectorized Spatial Pruning*: Menerapkan spatial hashing 2D di mana sel-sel yang berdekatan dievaluasi menggunakan AVX2 vectorized AABB checks.
  3. *Branchless Scoring*: Menggantikan evaluasi keputusan berbasis percabangan dengan polinomial response curves yang dieksekusi via `_mm256_fmadd_ps`.
* **Hasil**:
  * AI Frame Execution Time turun dari **14.2 ms** menjadi **0.86 ms** (Peningkatan performa **~16.5x**).
  * IPC meningkat menjadi **2.38**.
  * L1d Cache Hit Rate melonjak ke **99.1%**.
  * Konsumsi memori menurun drastis sebesar 42% karena eliminasi overhead *vtable pointers* (8 byte per instance) dan fragmentasi heap.

---

### 9. Trade-offs

Mengoptimalkan AI menggunakan SIMD tingkat rendah menuntut kompromi arsitektural yang signifikan:

```
Performa Komputasi (Raw Throughput)
      ▲
      │            [AVX2 / AVX-512 AoSoA]
      │                   ▲
      │                  ╱ ╲
      │                 ╱   ╲
      │   [ISPC / DOD] ╱     ╲
      │               ╱       ╲
      │              ╱         ╲
      │             ╱           ▼ [Maintainability & Portability]
      │            ▼
      │    [OOP Tradisional]
      └────────────────────────────────────────► Portabilitas & Readability
```

| Parameter | Pendekatan Skalar OOP | SIMD Intrinsics (AVX2/NEON) | Solusi Antara (e.g., Highway/ISPC) |
| :--- | :--- | :--- | :--- |
| **Throughput Puncak** | Rendah (Baseline 1x) | Sangat Tinggi (8x - 16x) | Tinggi (6x - 14x) |
| **Portabilitas Kode** | Sangat Tinggi (Standard C++) | Rendah (Arsitektur-spesifik ISA) | Tinggi (Abstraksi multi-ISA) |
| **Thermal & Throttling** | Minimal | Pada AVX-512, dapat memicu *core frequency downclocking* | Tergantung vector width |
| **Waktu Maintenance** | Rendah (Mudah dibaca) | Sangat Tinggi (Butuh skill SIMD) | Moderat |
| **Ukuran Binary** | Kompak | Membengkak jika banyak *loop unrolling* | Moderat |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Segfault Akibat Unaligned SIMD Memory Loads
* **Gejala**: Program crash secara instan dengan sinyal `SIGSEGV` / `STATUS_ACCESS_VIOLATION` saat instruksi load dieksekusi.
* **Penyebab**: Menggunakan `_mm256_load_ps` pada pointer yang tidak beralignment 32-byte (misal: memori hasil `malloc` standar atau `new` biasa yang hanya 8-byte/16-byte aligned).
* **Troubleshooting & Fix**:
  ```cpp
  // SALAH (Menyebabkan runtime crash acak):
  float* ptr = new float[8];
  __m256 val = _mm256_load_ps(ptr); // CRASH jika ptr % 32 != 0

  // BENAR:
  // Opsi A: Alokasi eksplisit beralignment
  float* ptr = static_cast<float*>(std::aligned_alloc(32, 8 * sizeof(float)));
  __m256 val = _mm256_load_ps(ptr);

  // Opsi B: Gunakan unaligned load jika alignment tidak dapat dijamin (sedikit lebih lambat)
  __m256 val = _mm256_loadu_ps(ptr); 
  ```

#### 10.2. False Sharing pada Multi-threaded Gather
* **Gejala**: Saat memparalelkan loop evaluasi AI ke 16 thread via OpenMP/Task System, performa justru anjlok dibanding 4 thread (*negative scaling*).
* **Penyebab**: Output array `uint8_t outFlags[N]` ditulis langsung oleh masing-masing worker thread untuk indeks yang berdekatan. Karena 1 cache line menampung 64 elemen `uint8_t`, thread saling membatalkan cache line L1 satu sama lain (*Cache line invalidation storm*).
* **Solusi**: Setiap thread menulis ke *thread-local buffer* tersendiri beralignment 64 byte, lalu hasil akhir disalin (*coalesced*) secara blok ke array utama.

#### 10.3. Register Spilling
* **Gejala**: Performa SIMD drop 50% dari kalkulasi estimasi teoritis.
* **Penyebab**: Kode SIMD menggunakan lebih dari 16 register `__m256` secara bersamaan dalam satu scope. Kompiler terpaksa melakukan *register spilling* (memindahkan isi register ke stack memory dan memuatnya kembali berulang-ulang).
* **Solusi**: Periksa assembly output (`-S` atau Compiler Explorer). Pisahkan kalkulasi besar menjadi sub-kernel yang memanfaatkan maksimal 12–14 register untuk menyisakan ruang bagi compiler register allocation.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist arsitektur berikut sebelum mengintegrasikan kode komputasi hardware-level ke production trunk:

- [ ] **Alokasi Selalu Memenuhi Boundary Memory**:
  - [ ] Setiap alokasi persistent menggunakan custom allocator dengan alignment minimum 64 byte (`alignas(64)`).
  - [ ] Validasi statis ukuran struct: `static_assert(sizeof(TileStruct) % 64 == 0, "Ukuran tile harus kelipatan 64-byte!");`.
- [ ] **Branchless Math Guarantee**:
  - [ ] Tidak ada conditional branch (`if`, `switch`) di dalam inner loop vektorisasi.
  - [ ] Semua conditional diganti dengan mask-select primitives (`_mm256_blendv_ps`, bitwise operations).
- [ ] **Compiler Optimization Flags Verifikasi**:
  - [ ] Target ISA ditentukan secara eksplisit pada level modul: `-mavx2 -mfma` (GCC/Clang) atau `/arch:AVX2` (MSVC).
  - [ ] Mengaktifkan loop vectorizer logging: `-Rpass=loop-vectorize -Rpass-analysis=loop-vectorize` (Clang) untuk memastikan tidak ada *unintentional fallback*.
- [ ] **Prefetching Policy**:
  - [ ] Prefetching tidak dilakukan berlebihan (*over-prefetching* membuang bandwidth memory bus). Idealnya prefetch diatur pada rentang 2-4 cache line ke depan.
- [ ] **Profiling Hooks**:
  - [ ] Zona evaluasi kritis diapit marker profiler mikro (e.g., `TracyZoneScopedNC("SIMD_Perception", 0x0000FF)`).

---

### 12. Hands-on Practice

Buat dan simpan praktikum ini di direktori project: `hands-on/m02/`

#### Langkah 1: Setup Direktori dan File CMake
Buat file `hands-on/m02/CMakeLists.txt`:
```cmake
cmake_minimum_required(VERSION 3.20)
project(SIMD_Agent_Perception CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if (MSVC)
    add_compile_options(/arch:AVX2 /O2 /Oi)
else()
    add_compile_options(-mavx2 -mfma -O3 -march=native)
endif()

add_executable(simd_perception main.cpp)
```

#### Langkah 2: Implementasi Benchmarking Komparatif
Buat file `hands-on/m02/main.cpp`:
```cpp
#include <iostream>
#include <vector>
#include <chrono>
#include <random>
#include <immintrin.h>

constexpr size_t AGENT_COUNT = 65536; // 64K agen
constexpr size_t ITERATIONS = 100;

struct AoSAgent {
    float x, y, z;
    float dirX, dirY, dirZ;
    float score;
    bool detected;
};

struct alignas(32) SoAAgent {
    std::vector<float> x;
    std::vector<float> y;
    std::vector<float> z;
    std::vector<float> dirX;
    std::vector<float> dirY;
    std::vector<float> dirZ;
    std::vector<float> score;
    std::vector<uint8_t> detected;

    SoAAgent(size_t n) {
        x.resize(n); y.resize(n); z.resize(n);
        dirX.resize(n); dirY.resize(n); dirZ.resize(n);
        score.resize(n); detected.resize(n);
    }
};

int main() {
    std::mt19937 rng(1337);
    std::uniform_real_decay<float> dist(-100.0f, 100.0f);

    // Init AoS
    std::vector<AoSAgent> aosAgents(AGENT_COUNT);
    for (auto& a : aosAgents) {
        a.x = dist(rng); a.y = dist(rng); a.z = dist(rng);
        a.dirX = 0.0f; a.dirY = 0.0f; a.dirZ = 1.0f;
        a.score = 0.0f; a.detected = false;
    }

    // Init SoA
    SoAAgent soaAgents(AGENT_COUNT);
    for (size_t i = 0; i < AGENT_COUNT; ++i) {
        soaAgents.x[i] = aosAgents[i].x;
        soaAgents.y[i] = aosAgents[i].y;
        soaAgents.z[i] = aosAgents[i].z;
        soaAgents.dirX[i] = 0.0f; soaAgents.dirY[i] = 0.0f; soaAgents.dirZ[i] = 1.0f;
    }

    float targetX = 10.0f, targetY = 10.0f, targetZ = 10.0f;
    float maxDistSq = 2500.0f; // 50 unit

    // 1. Benchmark AoS Skalar
    auto startAoS = std::chrono::high_resolution_clock::now();
    for (size_t iter = 0; iter < ITERATIONS; ++iter) {
        for (size_t i = 0; i < AGENT_COUNT; ++i) {
            float dx = targetX - aosAgents[i].x;
            float dy = targetY - aosAgents[i].y;
            float dz = targetZ - aosAgents[i].z;
            float dsq = dx*dx + dy*dy + dz*dz;
            if (dsq < maxDistSq) {
                aosAgents[i].detected = true;
                aosAgents[i].score = 1.0f - (dsq / maxDistSq);
            } else {
                aosAgents[i].detected = false;
                aosAgents[i].score = 0.0f;
            }
        }
    }
    auto endAoS = std::chrono::high_resolution_clock::now();
    double timeAoS = std::chrono::duration<double, std::milli>(endAoS - startAoS).count() / ITERATIONS;

    // 2. Benchmark SoA SIMD (AVX2)
    __m256 tx = _mm256_set1_ps(targetX);
    __m256 ty = _mm256_set1_ps(targetY);
    __m256 tz = _mm256_set1_ps(targetZ);
    __m256 maxD = _mm256_set1_ps(maxDistSq);
    __m256 vOne = _mm256_set1_ps(1.0f);
    __m256 vZero = _mm256_setzero_ps();

    auto startSIMD = std::chrono::high_resolution_clock::now();
    for (size_t iter = 0; iter < ITERATIONS; ++iter) {
        for (size_t i = 0; i < AGENT_COUNT; i += 8) {
            __m256 x = _mm256_loadu_ps(&soaAgents.x[i]);
            __m256 y = _mm256_loadu_ps(&soaAgents.y[i]);
            __m256 z = _mm256_loadu_ps(&soaAgents.z[i]);

            __m256 dx = _mm256_sub_ps(tx, x);
            __m256 dy = _mm256_sub_ps(ty, y);
            __m256 dz = _mm256_sub_ps(tz, z);

            __m256 dsq = _mm256_mul_ps(dx, dx);
            dsq = _mm256_fmadd_ps(dy, dy, dsq);
            dsq = _mm256_fmadd_ps(dz, dz, dsq);

            __m256 mask = _mm256_cmp_ps(dsq, maxD, _CMP_LT_OQ);
            __m256 sc = _mm256_sub_ps(vOne, _mm256_div_ps(dsq, maxD));
            __m256 finalSc = _mm256_blendv_ps(vZero, sc, mask);

            _mm256_storeu_ps(&soaAgents.score[i], finalSc);
        }
    }
    auto endSIMD = std::chrono::high_resolution_clock::now();
    double timeSIMD = std::chrono::duration<double, std::milli>(endSIMD - startSIMD).count() / ITERATIONS;

    std::cout << "--- Benchmark Hasil (" << AGENT_COUNT << " Agen) ---" << std::endl;
    std::cout << "AoS Skalar Time : " << timeAoS << " ms" << std::endl;
    std::cout << "SoA AVX2 Time   : " << timeSIMD << " ms" << std::endl;
    std::cout << "Speedup Factor  : " << (timeAoS / timeSIMD) << "x" << std::endl;

    return 0;
}
```

#### Langkah 3: Eksekusi dan Kompilasi
Jalankan di terminal Anda:
```bash
cd hands-on/m02/
mkdir build && cd build
cmake ..
cmake --build . --config Release
./simd_perception
```

---

### 13. Exercise

#### Tingkat Easy: Vectorized Dot Product 3D Batch
* **Instruksi**: Tulis fungsi C++ menggunakan intrinsics AVX2 yang menerima 3 array komponen vektor A (`ax`, `ay`, `az`) dan 3 array komponen B (`bx`, `by`, `bz`), lalu menghitung dot product untuk 8 pasang vektor secara simultan.
* **Input**: Masing-masing array memiliki panjang 8 float.
* **Batasan**: Dilarang menggunakan loop; seluruh komputasi harus selesai dalam operasi register AVX2 murni (`_mm256_mul_ps`, `_mm256_fmadd_ps`).

#### Tingkat Medium: Fast Path Vision Cone Query
* **Instruksi**: Perluas latihan Easy untuk melakukan filtering field-of-view (FOV).
* **Spesifikasi**:
  * Input: Posisi target tunggal $(X_t, Y_t, Z_t)$ dan 1 tile agen (8 posisi + 8 forward vectors).
  * Output: Mask unsigned 8-bit integer tunggal di mana bit ke-$i$ bernilai 1 jika target berada dalam rentang jarak $< 30.0$ unit DAN sudut $\theta \le 60^\circ$ relative terhadap orientasi agen.

#### Tingkat Hard: AoSoA Utility AI Decision Engine dengan Branchless Selection
* **Instruksi**: Bangun engine evaluasi untuk 3 pilihan aksi agen (*Attack*, *Flee*, *Patrol*).
* **Spesifikasi**:
  * Masing-masing aksi memiliki rumus kuadratik berbobot terhadap parameter *Health*, *DistanceToPlayer*, dan *AmmoCount*.
  * Lakukan komputasi untuk 1024 agen (128 tiles) menggunakan AVX2.
  * Tentukan ID aksi dengan skor tertinggi untuk setiap agen tanpa menggunakan percabangan `if` skalar, simpan ID terpilih dalam array `uint8_t selectedAction[1024]`.

---

### 14. Challenge

**Skenario Tantangan Produksi Nyata**: *Asymmetric Multi-Platform SIMD Perception Kernel*

Arsitektur engine game enterprise Anda harus mendukung dua platform target utama secara simultan: PC (x86-64 dengan AVX2/FMA) dan Mobile/Console (ARM64 dengan Neon 128-bit). 

**Tugas Arsitektural**:
1. Buat layer abstraksi C++ template/metaprogramming generic tanpa virtual overhead (*zero-cost abstraction*) yang memetakan tipe vektor generic `SimdVec<float>` ke `__m256` pada x86-64 dan `float32x4_t` pada ARM64.
2. Kernel harus mengevaluasi *Flocking / Boids Algorithm* (Separation, Alignment, Cohesion) untuk 16.384 boids.
3. Batasan:
   * Alokasi heap dinamis di tengah frame dilarang keras (wajib *zero-allocation* per-frame loop).
   * Pada x86-64, kernel harus otomatis fallback ke SSE4.1 secara aman jika CPU lama tidak mendukung AVX2 (gunakan runtime CPUID feature detection via function pointers / dynamic dispatch).
   * Tidak boleh ada regresi performa intrinsics murni melebihi 3%.

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1. Pertanyaan Basic
1. Berapa byte data yang dapat ditampung dalam satu register AVX2 (`__m256`), dan berapa jumlah variabel float 32-bit yang dapat diproses secara simultan?
2. Mengapa instruksi `_mm256_load_ps` membutuhkan alamat memori yang beralignment 32-byte, dan apa konsekuensinya pada level CPU jika alignment tersebut dilanggar?
3. Apa perbedaan mendasar antara representasi memori *Array of Structures* (AoS) dan *Structure of Arrays* (SoA) terkait efisiensi penarikan data ke L1 Cache?
4. Mengapa instruksi `_mm256_rsqrt_ps` jauh lebih cepat daripada menghitung `1.0f / sqrt(x)` menggunakan pipeline skalar biasa?
5. Berapa ukuran standar sebuah *Cache Line* pada arsitektur prosesor desktop x86_64 modern?

#### 15.2. Pertanyaan Intermediate
6. Jelaskan fenomena *False Sharing* dan bagaimana hal tersebut menghancurkan skalabilitas performa multithreaded pada batch processing AI!
7. Apa fungsi dari instruksi `_mm256_blendv_ps`, dan bagaimana instruksi ini membantu dalam mengeliminasi *Branch Misprediction*?
8. Mengapa komputasi menggunakan instruksi AVX-512 terkadang justru dapat memperlambat frame rate keseluruhan game pada prosesor Intel generasi tertentu (*Core frequency downclocking*)?
9. Jelaskan peran *Hardware Stream Prefetcher* pada CPU dan mengapa layout memori *contiguous* sangat krusial agar komponen ini bekerja optimal!
10. Kapan Anda harus memilih layout *Array of Structures of Arrays* (AoSoA) dibandingkan *Structure of Arrays* (SoA) murni dalam simulasi entitas game berskala besar?

#### 15.3. Skenario Kasus Produksi
11. **Kasus 1**: Profiler game engine Anda melaporkan bahwa eksekusi kernel AVX2 Anda menghasilkan metrik IPC hanya 0.6 dengan persentase *Memory Bound* mencapai 72%. Namun, setelah dicek, semua data Anda sudah dikonversi ke format SoA. Masalah arsitektur memori apa yang paling mungkin terjadi di balik fenomena ini?
12. **Kasus 2**: Anda mengimplementasikan sistem *Vision Cone Detection* menggunakan AVX2. Ketika dijalankan di target PC development (Intel Core i9-13900K), frame time berada di angka 0.3 ms. Namun, ketika dipindahkan ke perangkat pengujian berbasis AMD Zen 1, terjadi penurunan performa drastis hingga 2.8 ms (hampir 10x lebih lambat). Analisis instruksi intrinsics apa yang menyebabkan divergensi performa ini pada mikroarsitektur Zen 1!
13. **Kasus 3**: Tim Anda mengintegrasikan multi-threading menggunakan Job System untuk memproses 100.000 partikel AI crowd. Masing-masing job memproses 64 agen via AVX2. Namun, total waktu komputasi justru berfluktuasi liar (*spikes* hingga 30 ms) setiap kali frame budget tercapai, terutama di thread sekunder. Profiling menunjukkan OS thread context switches sangat tinggi. Solusi korektif apa yang harus diambil pada scheduler dan alignment data?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic
1. 32 byte (256 bit), menampung 8 variabel `float` 32-bit secara simultan.
2. Instruksi *aligned load* (`vmovaps`) mensyaratkan 5-bit terbawah dari pointer adalah 0 (kelipatan 32 byte). Jika dilanggar, CPU akan melempar *Hardware General Protection Fault* (GP-fault) yang berujung pada crash aplikasi (`SIGSEGV`).
3. AoS menyimpan semua field entitas secara berselang-seling; saat satu field dibaca, sisa field lain yang tidak terpakai ikut ditarik ke cache line (pemborosan bandwidth cache). SoA memisahkan field ke array contiguous mandiri; seluruh isi cache line 100% berisi data yang dibutuhkan untuk operasi saat itu.
4. `_mm256_rsqrt_ps` menggunakan hardware lookup table terdedikasi pada core CPU yang menghitung aproksimasi nilai invers akar kuadrat dalam 3–5 siklus clock, tanpa pembagian floating-point panjang yang biasanya memakan 14–20 siklus.
5. 64 byte.

#### Jawaban Intermediate
6. Terjadi saat dua thread berbeda memodifikasi variabel berbeda yang berada di dalam satu blok 64-byte cache line yang sama. Protokol koherensi cache (MESI) memaksa cache line di-flush dan disinkronkan bolak-balik antar-core L1 cache (*cache bouncing*), melumpuhkan utilisasi paralelisme multi-core.
7. `_mm256_blendv_ps` memilih byte dari dua register sumber (Register A dan Register B) secara kondisional berdasarkan nilai bit sign dari register mask. Ini memungkinkan pengambilan keputusan biner tanpa menggunakan instruksi jump (`jmp`, `jne`) sehingga pipeline instruction prosesor tidak pernah mengalami flush.
8. AVX-512 mengaktifkan unit eksekusi yang sangat masif dan membutuhkan voltase tinggi. Untuk mencegah TDP melebihi ambang batas termal, CPU Intel (khususnya Skylake-X / Xeon awal) menurunkan frekuensi base clock seluruh core (*frequency downclocking*) sebesar 10-20%, memperlambat eksekusi kode skalar thread lain.
9. *Hardware Prefetcher* menganalisis pola pembacaan memori. Jika alamat memori diakses secara sekuensial linear (stride konstan), prefetcher secara spekulatif menyalin blok data berikutnya dari RAM ke L2/L1 cache sebelum instruksi load CPU dieksekusi, memangkas latensi memori hingga 0 cycle stall.
10. Dipilih ketika entitas memiliki puluhan atribut berbeda, tetapi sering kali dimanipulasi atau di-stream dalam kelompok/cluster kecil (chunk). AoSoA menjaga alignment cache line (64 byte) lokal per chunk (misal: 8 atau 16 agen per blok), mencegah konsumsi *virtual memory footprint* berlebih yang dialami SoA raksasa saat alokasi sporadis.

#### Panduan Kasus Produksi
11. **Analisis**: Penyebab utama adalah pola akses memori non-linear tidak langsung (*indirect indexing / Gather operations*) atau alokasi SoA yang terlalu besar melebihi kapasitas L3 cache (DRAM trashing). Jika operasi AVX2 menggunakan `_mm256_i32gather_ps` alih-alih sequential load `_mm256_load_ps`, eksekusi gather terurai kembali menjadi multiple scalar loads di tingkat mikroarsitektur, mengubah compute kernel menjadi memory latency stall.
12. **Analisis**: Arsitektur AMD Zen 1 memiliki 128-bit internal data paths. Ketika instruksi AVX2 256-bit dijalankan, Zen 1 memecah (*splits*) setiap instruksi 256-bit menjadi dua micro-ops 128-bit terpisah. Jika kode mengandalkan instruksi broadcast atau unaligned load ganda, latency penanganan split register dan FMA Zen 1 berlipat ganda dibanding Intel Core modern yang memiliki data path native 256-bit penuh.
13. **Analisis**: Granularitas task terlalu kecil (64 agen per job) memicu *job scheduling overhead* dan *thread contention* berlebihan pada OS thread pool. Solusi: Tingkatkan granularity batch per job (misal: minimal 2.048 - 4.096 agen per task chunk), terapkan static work stealing, dan pastikan data output untuk masing-masing thread dialokasikan pada memory arena terpisah dengan alignment minimum 64-byte untuk mengeliminasi false sharing.

---

### 16. Summary

Optimalisasi komputasi hardware untuk sistem AI agen modern menuntut pergeseran paradigma dari rekayasa perangkat lunak berbasis relasi objek ke rekayasa mekanika data (*Data-Oriented Design*). Dengan memahami batasan fisik CPU modern—seperti ukuran cache line 64-byte, lebar register vektor SIMD (AVX2/AVX-512), dan mekanisme branchless prediction—arsitek game dapat mengonversi kalkulasi persepsi agen masif dari hitungan puluhan milidetik menjadi sub-milidetik. Kunci produksi performa tinggi terletak pada disiplin penataan struktur data (AoSoA), pemanfaatan SIMD intrinsics yang tepat guna, serta eliminasi total terhadap divergensi instruksi dan cache bouncing pada pipeline multi-core heterogen.