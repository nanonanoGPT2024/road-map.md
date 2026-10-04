# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Arsitektur Game Data-Oriented Design (DOD)**
**Kategori: 08-AI-Data-and-Autonomous-Agents / game-developer**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengimplementasikan** arsitektur *Archetype-based* vs *Sparse Set-based* Entity Component System (ECS) pada level representasi memori fisik dan struktur data biner.
- **Mengeliminasi Cache Misses & False Sharing** pada subsistem AI dan simulasi fisika menggunakan alignment memory (`alignas(64)`), mitigasi protokol koherensi cache (MESI/MOESI), dan teknik layout data *Structure of Arrays* (SoA) / *Array of Structures of Arrays* (AoSoA).
- **Merancang Job System Lock-Free berkinerja tinggi** berbasis algoritma *Work-Stealing* (Chase-Lev deque) yang sepenuhnya terintegrasi dengan chunk-based memory paging untuk pemrosesan paralel massal komponen AI/entitas.
- **Mengoptimalkan Pipeline Eksekusi dengan SIMD (AVX-2 / AVX-512)** untuk mengeksekusi operasi batching homogen seperti evaluasi *Utility AI*, *Boids flocking*, dan integrasi numerik gerak otonom pada puluhan ribu agen secara deterministik dalam anggaran frame < 2 ms.
- **Membangun Arsitektur Produksi Berorientasi Data** yang memisahkan mutasi state (*structural changes* melalui *Command Buffers*) dari fase komputasi paralel guna menghindari *race conditions* dan *deadlocks* tanpa pemanggilan *mutex* pada *hot loop*.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Pemrograman Sistem Tingkat Lanjut (C++20 atau Rust):** Manajemen memori manual, pointer arithmetic, *placement new*, template metaprogramming, move semantics, dan *memory barriers/atomics* (`std::atomic`, `memory_order_relaxed`, `memory_order_acquire/release`).
- **Arsitektur Komputer & Mikroarsitektur CPU:** Hirarki memori (Register, L1i/L1d, L2, L3 cache, RAM), Translation Lookaside Buffer (TLB), cache line (64 bytes), hardware prefetcher, branch predictor, dan superscalar pipelining.
- **DOD & ECS Fundamental (Modul 01):** Perbedaan paradigma Object-Oriented Programming (OOP) vs Data-Oriented Design (DOD), layout dasar AoS vs SoA, dan lifecycle dasar entitas/komponen.

---

## 3. Concept & Internal Architecture

Implementasi enterprise dari Data-Oriented Design berpusat pada optimalisasi pemanfaatan bandwidth memori bus dan throughput eksekusi instruksi CPU per cycle (IPC). Arsitektur produksi modern tidak sekadar memisahkan data dari logika; arsitektur ini memetakan tata letak data secara presisi ke dalam struktur fisik silikon CPU.

```
       +-----------------------------------------------------------+
       |               CPU CORE (Register & Execution Units)       |
       |  +-----------------------------------------------------+  |
       |  | SIMD Units (AVX2 / AVX-512: ymm0..ymm15 / zmm0..31) |  |
       +--+-----------------------------------------------------+--+
                                    ^
                       1 cycle latency, ~TB/s
                                    v
       +-----------------------------------------------------------+
       | L1 Data Cache (32-48 KB per Core, 64-byte Cache Lines)   |
       +-----------------------------------------------------------+
                                    ^
                      4-5 cycles latency
                                    v
       +-----------------------------------------------------------+
       | L2 Data Cache (512 KB - 1 MB per Core, Non-inclusive)     |
       +-----------------------------------------------------------+
                                    ^
                     12-14 cycles latency
                                    v
       +-----------------------------------------------------------+
       | L3 Shared Cache (Last Level Cache - LLC, 16-96 MB)        |
       +-----------------------------------------------------------+
                                    ^
                    40-75 cycles latency, ~300 GB/s
                                    v
       +-----------------------------------------------------------+
       | Main Memory (DRAM: DDR4/DDR5) - 60-100ns latency          |
       +-----------------------------------------------------------+
```

### 3.1. Deep Dive: Archetype-based ECS vs Sparse Set-based ECS

Arsitektur penyimpanan entitas menentukan karakteristik throughput iterasi (*read/write*) versus mutasi struktural (*add/remove component*).

```
Sparse Set Architecture:
Entities: [E0, E1, E2, E3, E4, E5]
Sparse:   [ 0 -> 0 | 1 -> 2 | 2 -> null | 3 -> 1 | 4 -> null | 5 -> 3 ]
Dense:    [ E0, E3, E1, E5 ]
Data:     [ D0, D3, D1, D5 ] (Tightly packed, cache-friendly iteration)
Keuntungan: O(1) Add/Remove component, tidak memindahkan entitas antar-tabel.
Kekurangan: Iterasi multi-komponen membutuhkan pengecekan indirection via sparse array.

Archetype Architecture (Unity DOTS, Flecs):
Archetype A: [Position, Velocity] -> Chunks of 16KB
Chunk 0: [P0, P1, P2... | V0, V1, V2...]
Archetype B: [Position, Velocity, AIState] -> Chunks of 16KB
Chunk 0: [P3, P4... | V3, V4... | A3, A4...]
Keuntungan: Zero indirection query, ideal untuk SIMD batch streaming.
Kekurangan: Mutasi struktur (add component) memicu alokasi ulang dan memcpy antar-chunk.
```

Pada skala produksi AI agen otonom (misal: 100.000 agen), iterasi querying komponen (`Position`, `Velocity`, `PerceptionData`) mendominasi frame budget (95% komputasi vs 5% mutasi struktural). Oleh karena itu, **Archetype Chunk-based Storage** menjadi standar industri game AAA.

### 3.2. Memory Layout: Chunk Paging & False Sharing

Sebuah *Archetype Chunk* dialokasikan dalam kelipatan ukuran halaman memori OS (biasanya 16 KB atau 64 KB) menggunakan custom page-aligned allocator (`posix_memalign` atau `_aligned_malloc`).

- **AoSoA (Array of Structures of Arrays):** Untuk memaksimalkan efisiensi vectorization SIMD AVX2 (lebar register 256-bit = 8 nilai `float`), array komponen dibagi menjadi paket-paket berukuran 8 atau 16 float:
  $$\text{Struct } \{ \text{float } x[8], y[8], z[8]; \}$$
  Hal ini mengeliminasi operasi *shuffle/gather* instruksi intrinsik SIMD, memungkinkan *aligned continuous vector load* (`_mm256_load_ps`).
- **Mitigasi False Sharing:** Ketika beberapa thread pada core berbeda memproses potongan chunk terpisah, kedua core dilarang keras menulis ke cache line 64-byte yang sama. Jika Thread 0 memodifikasi elemen di akhir Chunk A, dan Thread 1 menulis ke awal Chunk B yang berada pada cache line yang sama, protokol koherensi cache (MESI) akan memaksa *Cache Line Invalidation* bolak-balik via interconnect bus, melumpuhkan skalabilitas multi-core (fenomena *cache ping-pong*).

---

## 4. Why & What

| Pendekatan OOP Tradisional | Pendekatan DOD Produksi (Archetype ECS + Jobs) | Dampak Rekayasa & Hardware |
| :--- | :--- | :--- |
| Enkapsulasi: `class Agent : public Entity` menyimpan data posisi, pathfinding, dan state machine dalam satu instance heap terisolasi. | Normalisasi Data: Entitas hanyalah ID integer 64-bit (`uint64_t`). Komponen adalah struct murni (POD - Plain Old Data). | Menghilangkan biaya *vtable indirection* (virtual function call = dynamic branch target miss). |
| Pointer-chasing: Menelusuri graf referensi `agent->target->GetPosition()` menyebabkan memory jumping acak di seluruh DRAM. | Linear Memory Streaming: Seluruh array posisi diproses secara sekuensial dari L1/L2 prefetcher. | Mengurangi TLB misses dan menekan latency memori dari ~80ns (DRAM) menjadi ~1ns (L1d). |
| Threading berbasis mutex mengunci instance objek individual untuk mencegah mutasi konkuren. | Lock-free Job Batching: Komponen dipecah per-chunk. Query mendistribusikan chunk unik ke tiap thread worker secara deterministik. | Mengeliminasi *contention*, *priority inversion*, dan overhead OS context-switching. |
| Skalabilitas mentok pada 2.000 - 5.000 entitas aktif sebelum frame time melampaui 16.6ms (60 FPS). | Skalabilitas menembus 100.000+ entitas aktif pada 120 FPS dengan pemanfaatan SIMD penuh. | Efisiensi komputasi maksimal; konsumsi daya (watt) per entitas menurun drastis. |

---

## 5. How: Workflow Detail

Integrasi siklus hidup eksekusi frame berorientasi data terdiri dari beberapa fase terisolasi:

```
[Phase 1: Job Scheduling & Dependency Graph]
                       │
                       ▼
[Phase 2: Parallel Batch Execution (Read/Write Transformasi)]
  ├─ Worker 1: Chunk 00-03 (Perception System - AVX2)
  ├─ Worker 2: Chunk 04-07 (Perception System - AVX2)
  └─ Worker 3: Chunk 08-11 (Movement Physics System - AVX2)
                       │
       Semua mutasi struktural ditunda!
       (Ditulis ke Command Buffer thread-local)
                       │
                       ▼
[Phase 3: Synchronization Barrier (Job Fence Wait)]
                       │
                       ▼
[Phase 4: Structural Mutation Playback (Single-Threaded / Batched)]
  ├─ Flush Thread-Local Command Buffers
  ├─ Migrasi Entitas antar-Archetype Chunks
  └─ Instansiasi & De-alokasi Entitas Massal
```

1. **Scheduling Phase:** Game Loop mengumpulkan dependency antarsistem. Sistem yang tidak memiliki dependensi data baca/tulis yang tumpang tindih (misal: *Perception System* membaca `Position` dan menulis `Target`, sedangkan *Animation System* membaca `Skeleton` dan menulis `Bones`) dijadwalkan secara independen.
2. **Execution Phase (Scatter-Gather Free):** Worker threads mengambil pointer ke blok memori chunk kontinu. Algoritma mengeksekusi instruksi data mentah tanpa alokasi memori internal.
3. **Deferred Commands:** Jika sebuah AI agent mati akibat kalkulasi kesehatan pada Phase 2, entitas **tidak langsung dihapus**. Entitas mencatat perintah penghapusan ke dalam `EntityCommandBuffer` milik thread tersebut untuk mencegah pengrusakan integritas memori chunk yang sedang dibaca worker lain.
4. **Playback Phase:** Frame mencapai safe-point barrier. Semua buffer perintah diputar ulang (*playback*) secara deterministik untuk merestrukturisasi chunk storage.

---

## 6. Analogy & Diagram ASCII

### Analogi Pabrik Perakitan Otomotif

- **OOP Tradisional (Bengkel Individual):** Setiap mekanik (thread) bertanggung jawab membangun satu mobil dari nol. Mekanik harus berjalan melintasi gudang mengambil baut, lalu mengambil ban, lalu mengambil pintu. Mekanik saling bertabrakan di lorong gudang (cache thrashing), menunggu giliran memakai kunci pas (mutex contention).
- **DOD Modern (Pabrik Perakitan Konveyor Ford):** Mobil bergerak di atas ban berjalan melewati stasiun-stasiun khusus. Stasiun 1 hanya berisi nampan 10.000 baut berderet rapi. Robot pneumatik (SIMD) memasang 8 baut sekaligus dalam satu entakan mikrodetik. Pekerja tidak pernah berpindah tempat, perkakas tidak pernah diperebutkan.

### Diagram Layout Memori: Archetype Chunk Paging

```
+-----------------------------------------------------------------------------------+
| ARCHETYPE: [EntityID (8B), Position (12B), Velocity (12B), AgentAI (16B)] = 48B   |
| TOTAL CAPACITY: 16,384 Bytes (16 KB Page)                                         |
| METADATA HEADER: 64 Bytes (Count, Capacity, Version, Mutex-Free State)            |
+-----------------------------------------------------------------------------------+
| [Offset 0x0040] EntityID Array:   [ E0 | E1 | E2 | ... | En ]                     |
|                 (Capacity: 340 entities * 8B = 2,720 Bytes)                       |
+-----------------------------------------------------------------------------------+
| [Offset 0x0AE0] Position.X Array: [ X0 | X1 | X2 | ... | Xn ] (340 * 4B = 1,360B) |
| [Offset 0x1030] Position.Y Array: [ Y0 | Y1 | Y2 | ... | Yn ] (340 * 4B = 1,360B) |
| [Offset 0x1580] Position.Z Array: [ Z0 | Z1 | Z2 | ... | Zn ] (340 * 4B = 1,360B) |
+-----------------------------------------------------------------------------------+
| [Offset 0x1AD0] Velocity.X Array: [ VX0 | VX1 | VX2 | ... ]   (340 * 4B = 1,360B) |
| [Offset 0x2020] Velocity.Y Array: [ VY0 | VY1 | VY2 | ... ]   (340 * 4B = 1,360B) |
| [Offset 0x2570] Velocity.Z Array: [ VZ0 | VZ1 | VZ2 | ... ]   (340 * 4B = 1,360B) |
+-----------------------------------------------------------------------------------+
| [Offset 0x2AC0] AgentAI.State:    [ S0 | S1 | S2 | ... ]      (340 * 4B = 1,360B) |
| [Offset 0x3010] AgentAI.TargetID: [ T0 | T1 | T2 | ... ]      (340 * 8B = 2,720B) |
| [Offset 0x3AB0] AgentAI.Threat:   [ R0 | R1 | R2 | ... ]      (340 * 4B = 1,360B) |
+-----------------------------------------------------------------------------------+
| [Offset 0x4000] PADDING KE 16 KB BOUNDARY                                         |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Komparasi Memory Access Overhead (C++20)

Demonstrasi langsung degradasi performa traversal pointer versus streaming memory array.

```cpp
#include <iostream>
#include <vector>
#include <chrono>
#include <numeric>
#include <random>

struct OOPNode {
    float x, y, z;
    OOPNode* next;
};

void run_simple_benchmark() {
    constexpr size_t N = 1'000'000;
    
    // --- Setup OOP Cache-Trash Layout ---
    std::vector<OOPNode> pool(N);
    std::vector<size_t> indices(N);
    std::iota(indices.begin(), indices.end(), 0);
    std::shuffle(indices.begin(), indices.end(), std::mt19937{42});

    for (size_t i = 0; i < N - 1; ++i) {
        pool[indices[i]].next = &pool[indices[i + 1]];
        pool[indices[i]].x = 1.0f;
    }
    pool[indices[N - 1]].next = nullptr;

    // --- Setup DOD Contiguous Layout ---
    alignas(64) std::vector<float> dod_x(N, 1.0f);

    // Bench OOP Traversal
    auto t1 = std::chrono::high_resolution_clock::now();
    float sum_oop = 0.0f;
    OOPNode* curr = &pool[indices[0]];
    while (curr) {
        sum_oop += curr->x;
        curr = curr->next;
    }
    auto t2 = std::chrono::high_resolution_clock::now();

    // Bench DOD Stream Traversal
    auto t3 = std::chrono::high_resolution_clock::now();
    float sum_dod = 0.0f;
    const float* __restrict ptr = dod_x.data();
    #pragma omp simd reduction(+:sum_dod)
    for (size_t i = 0; i < N; ++i) {
        sum_dod += ptr[i];
    }
    auto t4 = std::chrono::high_resolution_clock::now();

    std::cout << "OOP Time: " << std::chrono::duration_cast<std::chrono::microseconds>(t2 - t1).count() << " us\n";
    std::cout << "DOD Time: " << std::chrono::duration_cast<std::chrono::microseconds>(t4 - t3).count() << " us\n";
}
```

### 7.2. Practical Example: Production-Grade Archetype-Chunk Memory & AVX2 Vectorized Autonomous AI

Implementasi arsitektur produksi menggunakan memory page alignment manual, pure flat array chunks, SIMD intrinsics AVX2 untuk update fisika pergerakan dan evaluasi AI massal.

```cpp
#include <iostream>
#include <vector>
#include <memory>
#include <cstdint>
#include <cstring>
#include <immintrin.h>
#include <chrono>
#include <cassert>

// Alignment constraint untuk AVX-2 (32 bytes) & Cache Line (64 bytes)
constexpr size_t CACHE_LINE_SIZE = 64;
constexpr size_t CHUNK_SIZE = 16384; // 16 KB Page
constexpr size_t SIMD_WIDTH_FLOAT = 8; // AVX2: 8x 32-bit floats

struct EntityID {
    uint32_t index;
    uint32_t generation;
};

// Layout Komponen Berorientasi Data Murni (SoA di dalam Chunk)
struct ChunkHeader {
    uint32_t count;
    uint32_t capacity;
    uint32_t archetype_id;
    uint32_t padding;
};

// Mengelola satu halaman chunk biner 16KB
class alignas(CACHE_LINE_SIZE) ArchetypeChunk {
public:
    ChunkHeader header;
    uint8_t memory[CHUNK_SIZE - sizeof(ChunkHeader)];

    ArchetypeChunk(uint32_t archetype_id, uint32_t capacity) {
        header.count = 0;
        header.capacity = capacity;
        header.archetype_id = archetype_id;
        std::memset(memory, 0, sizeof(memory));
    }

    // Mendapatkan offset array mentah di dalam chunk
    template<typename T>
    T* GetComponentArray(size_t offset_bytes) {
        return reinterpret_cast<T*>(memory + offset_bytes);
    }
};

// Model Chunk Khusus untuk Agen AI: [EntityID, PosX, PosY, PosZ, VelX, VelY, VelZ, TargetX, TargetY]
class AIAgentChunkView {
public:
    static constexpr size_t ENTITY_CAPACITY = (CHUNK_SIZE - sizeof(ChunkHeader)) / 
        (sizeof(EntityID) + (sizeof(float) * 8));

    // Skema Offset Memori Terhitung pada Compile-Time
    static constexpr size_t OFFSET_ENTITIES = 0;
    static constexpr size_t OFFSET_POS_X    = OFFSET_ENTITIES + (ENTITY_CAPACITY * sizeof(EntityID));
    static constexpr size_t OFFSET_POS_Y    = OFFSET_POS_X    + (ENTITY_CAPACITY * sizeof(float));
    static constexpr size_t OFFSET_POS_Z    = OFFSET_POS_Y    + (ENTITY_CAPACITY * sizeof(float));
    static constexpr size_t OFFSET_VEL_X    = OFFSET_POS_Z    + (ENTITY_CAPACITY * sizeof(float));
    static constexpr size_t OFFSET_VEL_Y    = OFFSET_VEL_X    + (ENTITY_CAPACITY * sizeof(float));
    static constexpr size_t OFFSET_VEL_Z    = OFFSET_VEL_Y    + (ENTITY_CAPACITY * sizeof(float));
    static constexpr size_t OFFSET_TGT_X    = OFFSET_VEL_Z    + (ENTITY_CAPACITY * sizeof(float));
    static constexpr size_t OFFSET_TGT_Y    = OFFSET_TGT_X    + (ENTITY_CAPACITY * sizeof(float));

    static bool PushEntity(ArchetypeChunk& chunk, EntityID id, float px, float py, float pz, float tx, float ty) {
        if (chunk.header.count >= ENTITY_CAPACITY) return false;
        
        uint32_t idx = chunk.header.count;
        chunk.GetComponentArray<EntityID>(OFFSET_ENTITIES)[idx] = id;
        chunk.GetComponentArray<float>(OFFSET_POS_X)[idx] = px;
        chunk.GetComponentArray<float>(OFFSET_POS_Y)[idx] = py;
        chunk.GetComponentArray<float>(OFFSET_POS_Z)[idx] = pz;
        chunk.GetComponentArray<float>(OFFSET_VEL_X)[idx] = 0.0f;
        chunk.GetComponentArray<float>(OFFSET_VEL_Y)[idx] = 0.0f;
        chunk.GetComponentArray<float>(OFFSET_VEL_Z)[idx] = 0.0f;
        chunk.GetComponentArray<float>(OFFSET_TGT_X)[idx] = tx;
        chunk.GetComponentArray<float>(OFFSET_TGT_Y)[idx] = ty;

        chunk.header.count++;
        return true;
    }
};

// Sistem Pemrosesan Ter-vektorisasi (SIMD AVX-2)
class AutonomousAgentSystem {
public:
    static void UpdateChunkSIMD(ArchetypeChunk& chunk, float delta_time, float speed_factor) {
        const uint32_t count = chunk.header.count;
        if (count == 0) return;

        float* __restrict px = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_POS_X);
        float* __restrict py = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_POS_Y);
        float* __restrict vx = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_VEL_X);
        float* __restrict vy = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_VEL_Y);
        const float* __restrict tx = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_TGT_X);
        const float* __restrict ty = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_TGT_Y);

        const __m256 dt_vec = _mm256_set1_ps(delta_time);
        const __m256 spd_vec = _mm256_set1_ps(speed_factor);
        const __m256 epsilon = _mm256_set1_ps(1e-5f);

        // Eksekusi per batch berukuran 8 floats
        uint32_t i = 0;
        for (; i + SIMD_WIDTH_FLOAT <= count; i += SIMD_WIDTH_FLOAT) {
            // Load Position & Target
            __m256 current_px = _mm256_loadu_ps(&px[i]);
            __m256 current_py = _mm256_loadu_ps(&py[i]);
            __m256 target_x   = _mm256_loadu_ps(&tx[i]);
            __m256 target_y   = _mm256_loadu_ps(&ty[i]);

            // Direction vector: dir = target - pos
            __m256 dir_x = _mm256_sub_ps(target_x, current_px);
            __m256 dir_y = _mm256_sub_ps(target_y, current_py);

            // Distance squared: dist_sq = dir_x^2 + dir_y^2
            __m256 dist_sq = _mm256_add_ps(_mm256_mul_ps(dir_x, dir_x), _mm256_mul_ps(dir_y, dir_y));
            
            // Fast inverse square root: rsqrt(dist_sq + epsilon)
            __m256 inv_dist = _mm256_rsqrt_ps(_mm256_add_ps(dist_sq, epsilon));

            // Normalize and scale by speed: new_vel = (dir * inv_dist) * speed
            __m256 new_vx = _mm256_mul_ps(_mm256_mul_ps(dir_x, inv_dist), spd_vec);
            __m256 new_vy = _mm256_mul_ps(_mm256_mul_ps(dir_y, inv_dist), spd_vec);

            // Store new velocities
            _mm256_storeu_ps(&vx[i], new_vx);
            _mm256_storeu_ps(&vy[i], new_vy);

            // Euler integration: pos = pos + (vel * dt)
            __m256 updated_px = _mm256_fmadd_ps(new_vx, dt_vec, current_px);
            __m256 updated_py = _mm256_fmadd_ps(new_vy, dt_vec, current_py);

            _mm256_storeu_ps(&px[i], updated_px);
            _mm256_storeu_ps(&py[i], updated_py);
        }

        // Scalar Tail Processing untuk entitas yang tersisa (< 8)
        for (; i < count; ++i) {
            float dx = tx[i] - px[i];
            float dy = ty[i] - py[i];
            float dist = std::sqrt(dx * dx + dy * dy) + 1e-5f;
            vx[i] = (dx / dist) * speed_factor;
            vy[i] = (dy / dist) * speed_factor;
            px[i] += vx[i] * delta_time;
            py[i] += vy[i] * delta_time;
        }
    }
};

int main() {
    // Alokasi 100.000 Agen dalam beberapa Archetype Chunks
    constexpr size_t TOTAL_AGENTS = 100'000;
    const size_t capacity_per_chunk = AIAgentChunkView::ENTITY_CAPACITY;
    const size_t total_chunks = (TOTAL_AGENTS + capacity_per_chunk - 1) / capacity_per_chunk;

    std::vector<std::unique_ptr<ArchetypeChunk>> world_chunks;
    world_chunks.reserve(total_chunks);

    for (size_t c = 0; c < total_chunks; ++c) {
        world_chunks.push_back(std::make_unique<ArchetypeChunk>(1, capacity_per_chunk));
    }

    // Inisialisasi populasi agen
    size_t assigned = 0;
    for (size_t c = 0; c < total_chunks; ++c) {
        while (assigned < TOTAL_AGENTS) {
            EntityID id = { static_cast<uint32_t>(assigned), 1 };
            if (!AIAgentChunkView::PushEntity(*world_chunks[c], id, 0.0f, 0.0f, 0.0f, 100.0f, 100.0f)) {
                break; // Chunk penuh, lanjut ke chunk berikutnya
            }
            assigned++;
        }
    }

    std::cout << "Berhasil mengalokasikan " << TOTAL_AGENTS << " agen di dalam " 
              << total_chunks << " chunks (" 
              << (total_chunks * CHUNK_SIZE) / 1024 << " KB)." << std::endl;

    // Benchmark SIMD execution
    constexpr int ITERATIONS = 100;
    auto start_time = std::chrono::high_resolution_clock::now();

    for (int iter = 0; iter < ITERATIONS; ++iter) {
        for (auto& chunk_ptr : world_chunks) {
            AutonomousAgentSystem::UpdateChunkSIMD(*chunk_ptr, 0.016f, 5.0f);
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto total_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    double avg_frame_ms = static_cast<double>(total_ms) / ITERATIONS;

    std::cout << "Rata-rata waktu eksekusi: " << avg_frame_ms << " ms per frame." << std::endl;
    std::cout << "Kapasitas throughput: " << (TOTAL_AGENTS / avg_frame_ms) * 1000.0 << " agen/detik." << std::endl;

    return 0;
}
```

---

## 8. Real World Case Study: Skala Enterprise

### Konteks Kasus
Sebuah studio game mengembangkan game simulasi perang ruang angkasa berbasis MMO (*Planetary Battle Simulation*) dengan target **150.000 drone otonom tempur simultan** pada 60 FPS di server dedicated (spesifikasi: Dual AMD EPYC 7763, 128 Core, 256 Threads).

### Masalah Arsitektur Awal (OOP-Heavy)
- Setiap drone direpresentasikan sebagai objek turunan `class Drone : public Actor`.
- Komponen AI Navigation menggunakan pointer ke graph node navigation, evaluasi raycast diskret, dan panggilan virtual `virtual void Tick(float dt)` pada setiap tick engine.
- Profiling awal menunjukkan:
  - Utilisasi CPU Core hanya 35% karena *thread lock contention* pada memory allocator (`malloc`/`free` heap trashing).
  - L3 Cache Miss Rate mencapai **68%** akibat memory fragmentation.
  - Waktu pemrosesan server frame: **84.3 ms** (Target: 16.6 ms) -> Mengakibatkan kegagalan server tick rate dan *rubber-banding* masif bagi ribuan pemain.

### Solusi Desain Berorientasi Data
1. **DOD Refactor ke Chunk Archetypes:**
   - Objek `Drone` dieliminasi. Seluruh state diubah menjadi kumpulan komponen: `TransformSoA`, `PhysicsVelocity`, `TargetGoal`, `CombatStats`.
   - Chunk dialokasikan secara statis per page memory (64 KB Chunk Page).
2. **Perception Grid Berbasis Flattened Morton-Order Grid:**
   - Pencarian tetangga terdekat (*spatial query*) diubah dari KD-Tree/Octree berbasis pointer menjadi *Dense Spatial Hash Uniform Grid* yang disimpan dalam continuous array. ID entitas disimpan dalam *Z-order curve (Morton code)* kontinu untuk menjamin bahwa lokasi spasial yang berdekatan di dunia fisik 3D berada pada cache line yang berdekatan di RAM.
3. **Execution Pipeline SIMD & Work-Stealing Job System:**
   - 150.000 entitas dipecah menjadi batch berisi 512 entitas per Job task.
   - Loop internal dikompilasi menggunakan instruksi target AVX-512 (`_mm512_fmadd_ps`).

### Hasil Metrik Produksi

| Parameter Profiler | Arsitektur Awal (OOP) | Arsitektur Baru (Enterprise DOD) | Peningkatan / Efisiensi |
| :--- | :--- | :--- | :--- |
| **Frame Processing Time** | 84.30 ms | **1.82 ms** | **46.3x Lebih Cepat** |
| **L1d Cache Misses** | 41.2% | **1.4%** | Penurunan drastis |
| **L3 Cache Misses** | 68.0% | **4.1%** | Pengurangan dramatis trip DRAM |
| **CPU Core Scalability** | Mentok pada 16 threads | Linear hingga **128 threads** | Tanpa global lock contention |
| **Throughput Entitas** | 1.770 entitas / ms | **82.417 entitas / ms** | Siap untuk skala 250k+ unit |

---

## 9. Trade-offs: Architectural Decision Matrix

```
       Kompensasi Kompleksitas Rekayasa DOD
  Tinggi ▲
         │                                       * Archetype ECS
         │                                         (Maksimal Throughput SIMD,
         │                                          Kompleksitas Mutasi Tinggi)
         │
         │                  * Sparse Set ECS
         │                    (Ergonomi Seimbang,
         │                     O(1) Add/Remove, SIMD Terbatas)
         │
         │  * Flat SoA Arrays Manual
         │    (Performa Ekstrem, Sangat Kaku)
         │
  Rendah ┼──────────────────────────────────────────────────────────►
         Rendah                                             Tinggi
                   Kebutuhan Ergonomi & Akselerasi Fitur Dev
```

### Analisis Komparasi Mendalam

1. **Throughput Iterasi vs Mutasi Struktural:**
   - *Archetype-based ECS:* Menawarkan iterasi sekuensial tercepat di industri, mendukung streaming SIMD tanpa translasi index pointer. Namun, operasi menambahkan komponen ke entitas secara dinamis (*Structural Change*) mengharuskan penyalinan seluruh data entitas dari chunk lama ke chunk baru ($O(N)$ data movement).
   - *Sparse Set-based ECS:* Penambahan dan penghapusan komponen berlangsung instan ($O(1)$ pointer/index swap), sangat cocok untuk sistem dengan lifecycle komponen yang dinamis (misal: penambahan buff/debuff status game RPG). Namun, iterasi multi-komponen melibatkan memory hopping pada *sparse array*, menurunkan pemanfaatan SIMD prefetcher.
2. **Ergonomi Pengembang vs Kompleksitas Rekayasa:**
   - DOD menuntut penghapusan konsep OOP seperti *inheritance*, *polimorfisme via virtual function*, dan enkapsulasi klasik.
   - Kurva belajar tim game programmer menjadi curam. Debugging memory dump biner mentah memerlukan custom natvis visualizer di Visual Studio / GDB.
3. **Biaya Memori vs Biaya Waktu CPU (Memory-Footprint Trade-off):**
   - Archetype chunks mengalokasikan kapasitas blok tertentu secara tetap (paged alignment). Jika terdapat ribuan kombinasi archetype unik dengan hanya 1 atau 2 entitas per archetype, fragmentasi internal (*wasted memory slack*) akan meningkat drastis.

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan Fatal: False Sharing pada Multi-threaded Loops
- **Gejala:** Utilisasi CPU menunjukkan 100% pada semua core, namun total frame time meningkat drastis ketika jumlah worker thread ditambah.
- **Penyebab:** Thread-thread menulis ke elemen array yang posisinya berdampingan di memori dan berada dalam satu batas 64-byte cache line yang sama.
```cpp
// SALAH: Terjadi False Sharing
struct ThreadOutput {
    float agent_min_distance; // 4 bytes
};
ThreadOutput worker_results[16]; // Semua berada dalam 1 atau 2 cache line (64 bytes)!

// BENAR: Mengisolasi Cache Line per Worker
struct alignas(64) ThreadOutput {
    float agent_min_distance;
    uint8_t padding[60];
};
ThreadOutput worker_results[16]; // Masing-masing terisolasi pada cache line tersendiri
```

### 10.2. Kesalahan: Melakukan Dynamic Allocation di Hot Loops
- **Gejala:** Profiler engine (misal: Tracy Profiler atau Superluminal) menampilkan waktu eksekusi tersita di fungsi `ntdll.dll!RtlAllocateHeap` atau `malloc`.
- **Troubleshooting:** Larang penggunaan `std::vector::push_back`, `std::map`, `new`, atau `make_shared` di dalam *Tick/Update Systems*. Gunakan fixed-size stack arrays, arena/linear allocators, atau chunk reservation yang dialokasikan satu kali pada saat inisialisasi boot level.

### 10.3. Kesalahan: Pointer Invalidation akibat Mutasi Komponen
- **Gejala:** Crash acak dengan error `ACCESS_VIOLATION` (Segmentation Fault) saat iterasi chunk.
- **Penyebab:** Programmer menyimpan pointer ke sebuah komponen (`Position* p = ...`), kemudian sistem lain memanggil fungsi penghapusan entitas atau penambahan komponen di tengah loop. Penghapusan entitas menggunakan teknik *swap-and-pop* memindahkan data entitas terakhir ke slot yang kosong, membuat pointer lama menunjuk ke entitas yang salah atau data sampah biner.
- **Solusi Arsitektural:** Komponen dilarang saling menyimpan pointer langsung. Komponen hanya boleh menyimpan `EntityID`. Akses data dilakukan melalui lookup terpusat, dan semua mutasi struktural diwajibkan melewati `EntityCommandBuffer`.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis modul komputasi gameplay/AI ke build staging:

- [ ] **Alokasi Aligned:** Seluruh buffer data chunk dialokasikan dengan batas alignment minimal 32-byte (untuk AVX2) atau 64-byte (untuk AVX-512 & Cache Line).
- [ ] **Zero Pointer Inside Data Component:** Struct komponen murni POD (Plain Old Data), dapat dipindahkan menggunakan `std::memcpy`, tanpa virtual method, tanpa non-trivial destructor, dan bebas pointer heap tersembunyi (`std::string`, `std::vector`).
- [ ] **SIMD Invariant Validation:** Loop SIMD memiliki penanganan *remainder/tail loop* untuk jumlah data yang bukan kelipatan 8 atau 16 float guna mencegah pemrosesan memori tak terdefinisi (*out-of-bounds access*).
- [ ] **Buffer Aliasing Prevention:** Semua pointer array input/output yang independen ditandai dengan keyword keyword non-standar compiler namun didukung luas: `__restrict` (C++) atau pointer terisolasi mutlak (Rust) untuk mengizinkan auto-vectorizer melakukan registrasi register maksimal.
- [ ] **Strict Phase Decoupling:** Pipeline game memisahkan sistem secara kaku: *Read Phase* $\rightarrow$ *Write Simulation Phase* $\rightarrow$ *Playback Structural Buffers*. Tidak ada mutasi topologi archetype selama iterasi job paralel berlangsung.
- [ ] **Deterministik Floating-Point Flags:** Flag kompilasi matematika presisi (`-ffast-math` vs `/fp:precise`) distandardisasi di seluruh environment build untuk mencegah desinkronisasi evaluasi floating point pada sistem deterministik lockstep jaringan.

---

## 12. Hands-on Practice: Implementasi Manual Chunk Archetype & SIMD Movement

Buat direktori baru `hands-on/m02/` dan implementasikan proyek berbasis CMake berikut untuk menguji pemahaman arsitektur secara riil.

### Langkah Praktikum:
1. Masuk ke direktori: `mkdir -p hands-on/m02 && cd hands-on/m02`
2. Buat file `CMakeLists.txt`:
```cmake
cmake_minimum_required(VERSION 3.20)
project(DOD_Advanced_Engine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if (MSVC)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} /O2 /arch:AVX2")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -mavx2 -mfma")
endif()

add_executable(dod_simd_bench main.cpp)
```
3. Salin kode praktikal dari seksi **7.2** ke dalam `main.cpp`.
4. Tambahkan implementasi *Bounding Box Collision System* ter-vektorisasi AVX-2 ke dalam `main.cpp` yang mendeteksi tabrakan 100.000 partikel terhadap batas arena $[-500, +500]$ dan membalikkan arah vektor kecepatannya jika menabrak:
```cpp
// Tambahkan fungsi berikut ke dalam class AutonomousAgentSystem di main.cpp
static void ResolveArenaBoundariesSIMD(ArchetypeChunk& chunk, float min_bound, float max_bound) {
    const uint32_t count = chunk.header.count;
    if (count == 0) return;

    float* __restrict px = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_POS_X);
    float* __restrict vx = chunk.GetComponentArray<float>(AIAgentChunkView::OFFSET_VEL_X);

    const __m256 v_min = _mm256_set1_ps(min_bound);
    const __m256 v_max = _mm256_set1_ps(max_bound);
    const __m256 v_neg_one = _mm256_set1_ps(-1.0f);

    for (uint32_t i = 0; i + SIMD_WIDTH_FLOAT <= count; i += SIMD_WIDTH_FLOAT) {
        __m256 p = _mm256_loadu_ps(&px[i]);
        __m256 v = _mm256_loadu_ps(&vx[i]);

        // Cek pelanggaran: p < min_bound || p > max_bound
        __m256 mask_under = _mm256_cmp_ps(p, v_min, _CMP_LT_OQ);
        __m256 mask_over  = _mm256_cmp_ps(p, v_max, _CMP_GT_OQ);
        __m256 collision_mask = _mm256_or_ps(mask_under, mask_over);

        // Pantulkan kecepatan: v = collision ? (v * -1.0f) : v
        __m256 v_inverted = _mm256_mul_ps(v, v_neg_one);
        __m256 final_v = _mm256_blendv_ps(v, v_inverted, collision_mask);

        _mm256_storeu_ps(&vx[i], final_v);
    }
}
```
5. Kompilasi dan jalankan:
```bash
cmake -B build
cmake --build build --config Release
./build/dod_simd_bench
```

---

## 13. Exercises

### Level Easy
Modifikasi implementasi praktikum di `hands-on/m02/` untuk menambahkan komponen baru berukuran 4-byte: `AgentHealth` (`float`). 
- Sesuaikan kalkulasi kapasitas maksimal chunk `ENTITY_CAPACITY`.
- Buat sistem scalar yang mengurangi `AgentHealth` sebesar `0.1f` per tick frame.

### Level Medium
Ubah tail processing (skalar) pada sistem `UpdateChunkSIMD` menjadi **Masked SIMD Execution**:
- Jika sisa data entitas pada chunk bernilai 3 (kurang dari lebar AVX2 yakni 8), gunakan instruksi `_mm256_maskload_ps` dan `_mm256_maskstore_ps` menggunakan bitmask khusus untuk memproses tail loop tanpa fallback ke komputasi skalar primitif.

### Level Hard
Rancang dan implementasikan struktur data **`EntityCommandBuffer`** thread-safe berbasis alokasi memori linear ring:
- Buffer harus mampu merekam operasi: `DestroyEntity(EntityID)` dan `AddComponent<T>(EntityID, T data)` dari beberapa worker thread paralel tanpa memicu *heap allocation lock*.
- Buat fungsi sinkronisasi `Flush(World& world)` yang mengeksekusi semua mutasi struktural secara sekuensial dan efisien, meminimalkan pergeseran chunk via sortasi `EntityID` sebelum operasi mutasi dijalankan.

---

## 14. Challenge: Planetary Autonomous Swarm Synchronization

Sebuah game simulasi skala enterprise menuntut sistem navigasi AI untuk **200.000 agen predator-prey otonom** di ruang toroidal 2D. 

**Kriteria Tantangan:**
1. **Aturan Perilaku (Boids / Flocking):** Setiap agen mengevaluasi 3 hukum Reynolds (Separation, Alignment, Cohesion) terhadap 16 tetangga spasial terdekatnya.
2. **Kekakuan Performa:** Total alokasi frame budget untuk pembaruan seluruh 200.000 agen adalah **maksimal 3.0 milidetik** pada prosesor 8-core kelas konsumen modern.
3. **Batasan Teknis:**
   - Dilarang keras menggunakan library eksternal (murni C++20 standard library dan AVX-2 intrinsics).
   - Memori heap tidak boleh dialokasikan/didealokasikan kembali setelah inisialisasi boot frame (Zero Dynamic Allocations inside Tick).
   - Wajib menggunakan struktur data **Uniform Spatial Grid terindeks secara contiguous** yang terintegrasi langsung dengan chunk layout.
4. **Deliverable Arsitektur:** 
   - Tuliskan dokumentasi rancangan layout memori biner (alignment, layout byte per chunk).
   - Sediakan implementasi modul C++ lengkap yang lolos uji stress test 200k entitas dengan frame time logger stabil tanpa lonjakan *garbage collection* atau *stutter latency*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Berapakah ukuran standar sebuah CPU cache line pada mayoritas arsitektur x86-64 modern?
   - A. 16 bytes
   - B. 32 bytes
   - C. 64 bytes
   - D. 128 bytes

2. Fenomena di mana beberapa thread pada core terpisah menulis ke variabel berbeda yang kebetulan berada dalam satu cache line yang sama disebut:
   - A. Data Race
   - B. False Sharing
   - C. Cache Pollution
   - D. Pointer Aliasing

3. Mengapa paradigma *Structure of Arrays* (SoA) jauh lebih unggul dibandingkan *Array of Structures* (AoS) untuk akselerasi SIMD?
   - A. Membutuhkan instruksi inline assembly manual.
   - B. Mengizinkan data homogen kontinu dimuat langsung ke register vektor tanpa instruksi shuffle/gather.
   - C. Mengurangi ukuran executable binary file game.
   - D. Mengubah floating point menjadi integer otomatis.

4. Apa dampak utama dari operasi mutasi struktural (*menambahkan komponen baru ke entitas*) pada arsitektur Archetype-based ECS?
   - A. Menghapus entitas dari memori secara permanen.
   - B. Menyebabkan fragmentasi disk OS.
   - C. Memindahkan data entitas dari chunk archetype lama ke chunk archetype baru (data copying overhead).
   - D. Memicu eksepsi segmentation fault yang tidak dapat ditangani.

5. Apa tujuan utama dari penggunaan keyword compiler `__restrict` pada parameter fungsi kalkulasi biner?
   - A. Mengunci akses pointer agar hanya bisa dibaca oleh satu thread.
   - B. Menjamin kepada compiler bahwa area memori pointer tersebut tidak tumpang tindih (*no alias*), membuka optimasi auto-vectorization.
   - C. Mencegah modifikasi data pointer secara runtime.
   - D. Memaksa pointer disimpan di Register L1.

---

### Bagian 2: Intermediate (Analisis Singkat)
6. Jelaskan mengapa instruksi pencarian percabangan (*branching `if-else`*) di dalam hot loop komputasi vektor SIMD dapat merusak performa throughput secara signifikan!
7. Dalam arsitektur Archetype ECS, apa tujuan mendasar dari penerapan teknik penundaan mutasi menggunakan `EntityCommandBuffer` daripada mengeksekusinya secara instan saat sistem berjalan?
8. Analisis trade-off performa antara alokasi chunk berukuran 16 KB versus 2 MB (Huge Pages) dalam konteks pemrosesan cache L2 CPU dan utilisasi TLB (Translation Lookaside Buffer)!
9. Jelaskan bagaimana protokol koherensi cache MESI (Modified, Exclusive, Shared, Invalid) merespons insiden False Sharing pada saat dua core independen melakukan operasi tulis konkuren!
10. Mengapa polymorphic function dispatching melalui pointer `vtable` (C++ virtual method) dikategorikan sebagai antipattern fatal dalam rekayasa Game Berorientasi Data?

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario A:** Profiler engine Anda mendeteksi bahwa sistem pathfinding AI mengalami lonjakan L1d cache misses sebesar 45% setelah desainer menambahkan komponen `FactionReputation` (berukuran 128 bytes) ke dalam archetype tentara. Padahal, sistem pathfinding hanya membutuhkan komponen `Position` dan `Velocity`. Rancang solusi arsitektural untuk mengeliminasi cache pollution tersebut tanpa membatasi kebutuhan fitur desainer!
12. **Skenario B:** Server multiplayer game Anda berjalan pada tickrate 60 Hz. Terdapat sistem fisika tabrakan partikel yang diproses secara multithreaded menggunakan 16 worker jobs. Meskipun beban komputasi terbagi rata, FPS drop parah setiap kali ratusan partikel hancur bersamaan dalam sebuah ledakan besar. Identifikasi akar masalah konkurensi tersebut dan buat rancangan perbaikannya!
13. **Skenario C:** Anda memiliki 50.000 agen otonom. Anda mengimplementasikan SIMD AVX2 pada algoritma *Flocking Cohesion*. Namun, hasil benchmark menunjukkan bahwa versi SIMD AVX2 berjalan **lebih lambat** dibandingkan kode skalar murni dengan optimasi `-O3`. Sebutkan 3 kemungkinan penyebab mikroarsitektur yang melatarbelakangi anomali ini dan bagaimana langkah verifikasinya!

---

## Kunci Jawaban & Panduan Evaluasi Quiz

### Bagian 1: Basic
1. **C** (64 bytes).
2. **B** (False Sharing).
3. **B** (Mengizinkan data homogen kontinu dimuat langsung ke register vektor tanpa shuffle/gather).
4. **C** (Memindahkan data entitas dari chunk archetype lama ke chunk archetype baru).
5. **B** (Menjamin kepada compiler bahwa memori pointer tidak tumpang tindih / no aliasing).

### Bagian 2: Intermediate
6. **Jawaban:** SIMD bekerja serempak pada jalur data yang sama (*Single Instruction, Multiple Data*). Percabangan logis memaksa SIMD mengeksekusi kedua cabang (*divergence execution*) dengan masking bitwise, melipatgandakan cycle instruksi dan mematikan unit eksekusi yang tidak memenuhi kondisi mask.
7. **Jawaban:** Menjaga determinisme dan kontinuitas struktur memori. Jika entitas langsung dihapus/dipindahkan di tengah iterasi worker paralel, layout memori chunk yang sedang dibaca worker thread lain akan corrupt atau bergeser seketika (*race condition/dangling memory offset*).
8. **Jawaban:** Chunk 16 KB pas di dalam L1d cache (32-48 KB) menjamin latency terendah (4 cycles), namun memperbanyak entry tabel OS. Chunk 2 MB mengurangi TLB cache misses untuk data berukuran masif, namun berisiko membuang banyak ruang jika archetype memiliki sedikit entitas (*memory footprint bloat*).
9. **Jawaban:** Core A menulis $\rightarrow$ Cache line ditandai *Modified*. Core B mencoba menulis ke data sebelahnya $\rightarrow$ Core B mengalami hit/miss, memicu invalidasi pada Core A via bus interkoneksi (*Invalid state*), memaksa sinkronisasi tulis ke RAM/L3. Siklus ini berulang terus menerus (*cache ping-pong*), melumpuhkan bandwidth bus.
10. **Jawaban:** Virtual call memaksa CPU membaca pointer instance $\rightarrow$ membaca pointer vtable $\rightarrow$ loncat ke memory address instruksi fungsi (Double Indirection). Hal ini menghancurkan pipeline branch predictor CPU dan mencegah auto-vectorization compiler secara total.

### Bagian 3: Skenario Kasus Produksi
11. **Solusi:** Pecah komponen menjadi sub-archetype atau gunakan pola pemisahan frekuensi akses: Pindahkan `FactionReputation` ke archetype terpisah atau simpan di sparse set sekunder yang jarang diiterasi (*cold data segregation*). Pastikan archetype yang dibaca oleh hot loop pathfinding hanya memuat komponen *hot data* (`Position`, `Velocity`).
12. **Solusi:** Penghancuran partikel masif mengeksekusi dealokasi atau penghapusan memori langsung dari thread worker secara simultan, memicu *contention lock* pada shared memory allocator atau chunk metadata. Perbaikan: Seluruh event destruksi partikel hanya mencatat ID ke dalam Thread-Local Linear Buffer. Pada akhir frame, satu thread melakukan batch delete menggunakan operasi mutasi massal swap-and-pop terkonsolidasi.
13. **Solusi Analisis:**
    1. Data yang dimuat tidak memory-aligned (menggunakan `_mm256_loadu_ps` unaligned crossing cache lines yang terkena penalty siklus tinggi).
    2. Adanya instruksi *gather/scatter* acak karena data input tidak disimpan dalam format murni SoA melainkan AoS (menghancurkan throughput eksekusi SIMD).
    3. Auto-vectorizer compiler pada versi skalar `-O3` telah melakukan unrolling loop optimal dan menggunakan register FMA secara efisien, sedangkan kode AVX2 manual Anda memuat overhead register spill/reload ke stack memory secara berulang.

---

## 16. Summary

- **Data-Oriented Design (DOD)** pada level enterprise adalah rekayasa mekanis perangkat lunak yang tunduk pada realitas fisik mikroarsitektur CPU: cache lines, latency DRAM, alignment memori, dan lebar register SIMD.
- **Archetype Chunk Memory Architecture** menawarkan performa iterasi komputasi linear tertinggi untuk AI dan simulasi game berskala masif dengan mengelompokkan data secara homogen di dalam page blok kontinu.
- **Kombinasi Maut DOD Produksi:** SoA memory chunking + AVX-2/AVX-512 vectorization + Work-Stealing Job System + Deferred Structural Command Buffers memungkinkan skalabilitas komputasi puluhan hingga ratusan ribu agen otonom secara deterministik dalam batasan frame time industri (< 2 milidetik).
- **Disiplin Rekayasa Mutlak:** Hilangkan pointer indirection, segregasikan cold data dari hot data, cegah False Sharing dengan alignment cache line yang presisi, dan hindari alokasi memori dinamis di dalam core loop pemrosesan game.