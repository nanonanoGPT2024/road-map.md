# Bab 02: Pemrograman Sistem Rendah & Manajemen Memori
## Modul 01: Arsitektur Custom Memory Allocator & Cache-Conscious Data Structures untuk Autonomous Game Agents

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mengeliminasi Non-Deterministic Latency:** Mendesain dan mengimplementasikan subsistem alokasi memori khusus (*Linear/Arena* dan *Free-List Pool*) untuk siklus hidup (lifecycle) AI Agent dengan kompleksitas waktu alokasi dan dealokasi $O(1)$.
- **Mengoptimalkan Hardware Cache Utilization:** Menerapkan prinsip *Data-Oriented Design* (DOD) dan penyelarasan memori (*data alignment*) untuk memaksimalkan *L1/L2 data cache hit rate* (mencapai $>90\%$) pada kalkulasi sensorik dan *decision-making* ribuan agen simultan.
- **Mencegah Fragmentasi Memori Eksternal:** Menghilangkan overhead *OS kernel context switch* dan degradasi performa akibat *memory fragmentation* pada *long-running dedicated server* tanpa menggunakan *Garbage Collector*.
- **Membangun Safe Memory Boundaries:** Mengisolasi alokasi transien per-*frame* dari alokasi persisten agen otonom guna mencegah kebocoran memori (*memory leaks*) dan *dangling pointers*.

---

### 2. Concept Overview
Dalam game engine modern dan sistem simulasi *multi-agent*, subsistem kecerdasan buatan (*Autonomous Agents*) mengeksekusi logika frekuensi tinggi (30–120 Hz) yang mencakup evaluasi *Behavior Trees*, *Utility AI*, *NavMesh pathfinding query*, hingga inferensi jaringan saraf tiruan (NN). 

Penggunaan alokator heap umum (*general-purpose allocators*) seperti `malloc` atau `new` standar (berbasis Doug Lea / ptmalloc) menjadi *bottleneck* kritis karena:
1. **Algoritma Pencarian Variabel:** Memerlukan penelusuran struktur metadata (*freelist traversal*) yang berujung pada kompleksitas waktu non-deterministik ($O(n)$ dalam skenario fragmentasi berat).
2. **System Call & Lock Contention:** Melibatkan penguncian *mutex* lintas-thread dan potensi *kernel transition* (`brk`/`mmap`).
3. **Cache Inefficiency:** Menghasilkan alokasi memori yang tersebar secara acak di dalam *Virtual Address Space*, memicu *cache thrashing* dan *TLB (Translation Lookaside Buffer) misses*.

```
+-------------------------------------------------------------------------+
|                              CPU Core                                   |
|  +------------------+  +------------------+  +-----------------------+  |
|  | Registers (<1ns) |  | L1 Cache (~1ns)  |  |   L2 Cache (~3-4ns)   |  |
|  +------------------+  +------------------+  +-----------------------+  |
|                                |                                         |
|                       +------------------+                               |
|                       | L3 Cache (~10ns) |                               |
|                       +------------------+                               |
+--------------------------------|----------------------------------------+
                                 |  Bus Request (Cache Miss Penalty: ~60-100ns)
+--------------------------------v----------------------------------------+
|                          System RAM (DRAM)                              |
|   [ Fragmented Non-contiguous Objects: High Latency & Cache Eviction ]   |
+-------------------------------------------------------------------------+
```

Model mental yang harus dibangun adalah **"Memory as an Array of Contiguous Bytes"**. Memori dialokasikan di awal (*pre-allocated bulk memory*) saat inisialisasi modul, kemudian dipartisi menggunakan dua strategi utama:
- **Arena / Linear Allocator:** Untuk data transien yang hanya bertahan selama satu *tick* atau *frame* (misal: array persepsi musuh, raycast results). Alokasi memajukan offset pointer; dealokasi dilakukan sekaligus dengan mereset offset ke 0.
- **Fixed-Size Pool Allocator:** Untuk entitas agen dan node *behavior tree* yang memiliki ukuran seragam dan waktu hidup bervariasi. Alokasi dan dealokasi memanipulasi *embedded singly-linked freelist* tanpa overhead metadata terpisah.

---

### 3. Why It Matters
Pada arsitektur *Dedicated Game Server* berskala masif (misal: simulasi 10.000 NPC otonom pada *tick rate* 60 Hz), setiap frame memiliki anggaran waktu mutlak **16.6 milidetik**. Alokasi AI hanya diberi porsi sekitar **2.0 - 3.5 milidetik**.

Jika 10.000 agen masing-masing melakukan 10 alokasi dinamis per tick menggunakan heap standar:
$$\text{Total Alokasi} = 10.000 \times 10 \times 60 = 6.000.000 \text{ alloc/detik}$$

Dampaknya:
- **Frame Hitching / Spikes:** Latensi alokasi heap melonjak drastis saat terjadi rekonsiliasi *free chunk* atau *page fault*.
- **Out of Memory (OOM) Crash:** Fragmentasi memori menyebabkan alokator gagal menemukan blok kontigu meskipun total memori bebas mencukupi.
- **Thermal Throttling & Battery Drain:** Pada platform mobile/konsol genggam, *memory bus traffic* yang berlebihan akibat *cache misses* mengonsumsi daya listrik jauh lebih besar dibandingkan komputasi ALU murni.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan pembagian *Memory Arena* pre-alokasi untuk subsistem AI:

```
+---------------------------------------------------------------------------------------------------+
|                        Pre-allocated AI Subsystem Memory Chunk (e.g., 64 MB)                      |
+---------------------------------------------------------------------------------------------------+
|               PERSISTENT POOL ZONE               |               FRAME-TRANSIENT ARENA            |
|       (Agent State, Blackboard, BT Nodes)        |           (Sensory Queries, Raycast hits)      |
+--------------------------------------------------+------------------------------------------------+
| [Node][Node][Node][ Free ][Node][ Free ][Node]   | [PerceptionData][PathPoints]...... [UNALLOC]   |
|   |           ^             ^                    |                                    ^           |
|   +-----------+-------------+                    |                                    |           |
|         Embedded Free-List Head                  |                             Current Offset     |
+--------------------------------------------------+------------------------------------------------+
 \________________________ _______________________/ \_______________________ ______________________/
                          v                                                 v
              Fixed-Block Pool Allocator                        Double-Buffered Linear Allocator
               - Complexity: O(1) Alloc/Free                     - Complexity: O(1) Alloc, O(1) Reset
               - Zero External Fragmentation                     - Cache-line Aligned (64 bytes)
```

#### Alur Eksekusi Per Tick (Pipeline Frame):
```
Engine Tick Start
       |
       v
[Clear Frame Arena] ---> Reset Offset = 0 (Gratis / 0 siklus CPU per objek)
       |
       v
[Perception Phase]  ---> Alokasi transien array target visual ke Frame Arena
       |
       v
[Decision Phase]    ---> Node Behavior Tree diambil/dikembalikan dari Persistent Pool
       |
       v
[Pathfinding Phase] ---> Struktur data A* open/closed list menggunakan Frame Arena
       |
       v
Engine Tick End     ---> Tidak ada dekonstruksi per-objek individual
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Memory Alignment & Pointer Arithmetic
Arsitektur prosesor modern (x86_64, ARM64) membaca memori melalui *bus* selebar *cache line* (biasanya 64 byte). Pembacaan data primitif yang tidak sejajar (*misaligned*) dengan batas ukuran tipenya (misal: `uint64_t` tidak berada di alamat kelipatan 8) memicu penalti performa berat atau *hardware fault* (*alignment trap* pada ARM).

Formula penyelarasan ke atas (*round-up alignment*):
$$\text{Aligned Address} = (\text{Address} + (\text{Alignment} - 1)) \ \& \ \sim(\text{Alignment} - 1)$$
*Syarat: `Alignment` harus berupa nilai perpangkatan dua ($2^n$).*

#### B. Free-List Pool Allocator (In-Place / Embedded Pointers)
Alih-alih mengalokasikan node terpisah untuk mencatat memori yang kosong (*free list*), kita memanfaatkan blok memori kosong itu sendiri untuk menyimpan pointer ke blok kosong berikutnya (*singly-linked list*).

```
State 1: Inisialisasi
Offset:    0x00        0x20        0x40        0x60
Memory:  [ Next:0x20 ][ Next:0x40 ][ Next:0x60 ][ Next:nullptr ]
FreeListHead = 0x00

State 2: Alokasi 1 Objek (Ukuran 32 Byte)
Return: 0x00
FreeListHead = 0x20

State 3: Dealokasi 0x00
[0x00]->Next = 0x20
FreeListHead = 0x00
```

#### C. Cache Locality: AoS vs SoA
- **Array of Structures (AoS):** `struct Agent { Vector3 pos; float health; AIState state; }; Agent agents[1024];`
  - Jika kalkulasi hanya membaca `pos` untuk jarak sensorik, `health` dan `state` ikut terangkat ke L1 Cache secara percuma (pemborosan bandwidth cache).
- **Structure of Arrays (SoA):** `struct AgentPool { Vector3 pos[1024]; float health[1024]; AIState state[1024]; };`
  - 100% data yang dimuat ke cache-line termanfaatkan sepenuhnya saat iterasi penentuan jarak sensorik.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Linear/Arena Allocator** dan **Fixed-Size Pool Allocator** dalam C++20 yang aman, *type-hinted*, mematuhi *data alignment*, dan tanpa *external library*.

```cpp
#include <cstddef>
#include <cstdint>
#include <new>
#include <utility>
#include <cassert>
#include <span>
#include <concepts>

namespace Core::Memory {

// Helper untuk verifikasi nilai power-of-two
constexpr bool IsPowerOfTwo(std::size_t value) noexcept {
    return (value > 0) && ((value & (value - 1)) == 0);
}

// Menghitung padding yang diperlukan untuk penyelarasan alamat memori
inline std::size_t CalculatePadding(std::uintptr_t baseAddress, std::size_t alignment) noexcept {
    assert(IsPowerOfTwo(alignment));
    const std::size_t multiplier = (baseAddress / alignment) + 1;
    const std::size_t alignedAddress = multiplier * alignment;
    const std::size_t padding = alignedAddress - baseAddress;
    return (padding == alignment) ? 0 : padding;
}

// ============================================================================
// ARENA / LINEAR ALLOCATOR
// ============================================================================
class ArenaAllocator {
public:
    ArenaAllocator(std::span<std::byte> memoryBuffer) noexcept
        : m_buffer(memoryBuffer), m_offset(0) {}

    ~ArenaAllocator() noexcept {
        Reset();
    }

    ArenaAllocator(const ArenaAllocator&) = delete;
    ArenaAllocator& operator=(const ArenaAllocator&) = delete;
    ArenaAllocator(ArenaAllocator&&) noexcept = default;
    ArenaAllocator& operator=(ArenaAllocator&&) noexcept = default;

    [[nodiscard]] void* Allocate(std::size_t size, std::size_t alignment = alignof(std::max_align_t)) noexcept {
        assert(IsPowerOfTwo(alignment));

        const std::uintptr_t currentAddress = reinterpret_cast<std::uintptr_t>(m_buffer.data()) + m_offset;
        const std::size_t padding = CalculatePadding(currentAddress, alignment);

        if (m_offset + padding + size > m_buffer.size()) {
            // Out of Memory untuk buffer ini
            return nullptr;
        }

        m_offset += padding;
        void* const allocatedPtr = static_cast<void*>(m_buffer.data() + m_offset);
        m_offset += size;

        return allocatedPtr;
    }

    template <typename T, typename... Args>
    [[nodiscard]] T* New(Args&&... args) {
        void* const memory = Allocate(sizeof(T), alignof(T));
        if (!memory) {
            throw std::bad_alloc();
        }
        return ::new (memory) T(std::forward<Args>(args)...);
    }

    // O(1) Deallocation untuk seluruh buffer
    void Reset() noexcept {
        m_offset = 0;
    }

    [[nodiscard]] std::size_t GetAllocatedSize() const noexcept { return m_offset; }
    [[nodiscard]] std::size_t GetTotalCapacity() const noexcept { return m_buffer.size(); }

private:
    std::span<std::byte> m_buffer;
    std::size_t m_offset{0};
};

// ============================================================================
// FIXED-SIZE POOL ALLOCATOR (Embedded Free-List)
// ============================================================================
class PoolAllocator {
private:
    struct FreeNode {
        FreeNode* next{nullptr};
    };

public:
    PoolAllocator(std::span<std::byte> memoryBuffer, std::size_t objectSize, std::size_t objectAlignment) noexcept
        : m_buffer(memoryBuffer),
          m_objectSize(objectSize < sizeof(FreeNode) ? sizeof(FreeNode) : objectSize),
          m_alignment(objectAlignment),
          m_freeList(nullptr) {
        assert(IsPowerOfTwo(m_alignment));
        assert(m_buffer.size() >= m_objectSize);
        InitializePool();
    }

    PoolAllocator(const PoolAllocator&) = delete;
    PoolAllocator& operator=(const PoolAllocator&) = delete;

    [[nodiscard]] void* Allocate() noexcept {
        if (m_freeList == nullptr) {
            return nullptr; // Pool Exhaustion
        }

        FreeNode* head = m_freeList;
        m_freeList = m_freeList->next;
        return static_cast<void*>(head);
    }

    void Deallocate(void* ptr) noexcept {
        if (!ptr) return;

        // Validasi boundary memori
        assert(ptr >= m_buffer.data() && ptr < (m_buffer.data() + m_buffer.size()));

        FreeNode* node = static_cast<FreeNode*>(ptr);
        node->next = m_freeList;
        m_freeList = node;
    }

    template <typename T, typename... Args>
    requires std::is_destructible_v<T>
    [[nodiscard]] T* Create(Args&&... args) {
        assert(sizeof(T) <= m_objectSize);
        assert(alignof(T) <= m_alignment);

        void* memory = Allocate();
        if (!memory) {
            return nullptr;
        }
        return ::new (memory) T(std::forward<Args>(args)...);
    }

    template <typename T>
    void Destroy(T* object) noexcept {
        if (object) {
            object->~T();
            Deallocate(static_cast<void*>(object));
        }
    }

private:
    void InitializePool() noexcept {
        std::uintptr_t currentAddress = reinterpret_cast<std::uintptr_t>(m_buffer.data());
        const std::size_t initialPadding = CalculatePadding(currentAddress, m_alignment);

        std::size_t usableBytes = m_buffer.size() - initialPadding;
        std::byte* alignedStart = m_buffer.data() + initialPadding;

        const std::size_t totalBlocks = usableBytes / m_objectSize;
        assert(totalBlocks > 0);

        for (std::size_t i = 0; i < totalBlocks; ++i) {
            std::byte* blockAddress = alignedStart + (i * m_objectSize);
            Deallocate(static_cast<void*>(blockAddress));
        }
    }

    std::span<std::byte> m_buffer;
    const std::size_t m_objectSize;
    const std::size_t m_alignment;
    FreeNode* m_freeList;
};

} // namespace Core::Memory

// ============================================================================
// SIMULATION PIPELINE: GAME AI DOMAIN
// ============================================================================
#include <iostream>
#include <vector>

struct alignas(16) AgentPerceptionTarget {
    std::uint32_t targetId;
    float distanceSquared;
    float threatLevel;
    float padding; // Memastikan alignment terprediksi
};

class alignas(32) AutonomousAgent {
public:
    AutonomousAgent(std::uint32_t id, float posX, float posY) 
        : m_agentId(id), m_x(posX), m_y(posY), m_state(0) {}

    void Tick(Core::Memory::ArenaAllocator& frameArena) {
        // Alokasi transien per-frame menggunakan Arena
        constexpr std::size_t MAX_TARGETS = 16;
        auto* detectedTargets = static_cast<AgentPerceptionTarget*>(
            frameArena.Allocate(sizeof(AgentPerceptionTarget) * MAX_TARGETS, alignof(AgentPerceptionTarget))
        );

        if (!detectedTargets) {
            // Fallback: Skip scanning jika frame arena penuh
            return;
        }

        // Simulasi populate data sensorik
        detectedTargets[0] = AgentPerceptionTarget{101, 24.5f, 0.9f, 0.0f};
        
        // Eksekusi logic internal...
        if (detectedTargets[0].threatLevel > 0.5f) {
            m_state = 1; // Evasion State
        }
    }

    [[nodiscard]] std::uint32_t GetId() const noexcept { return m_agentId; }
    [[nodiscard]] std::uint32_t GetState() const noexcept { return m_state; }

private:
    std::uint32_t m_agentId;
    float m_x;
    float m_y;
    std::uint32_t m_state;
};
```

---

### 7. Edge Cases & Failure Modes

#### 1. Arena Out-of-Memory (Allocation Exhaustion)
- **Skenario:** AI mendadak mendeteksi anomali ledakan objek, memicu ledakan jumlah node pencarian pathfinding yang melebihi kapasitas arena statis.
- **Dampak:** `Allocate()` mengembalikan `nullptr`. Jika kode klien tidak defensif, terjadi *Dereference Null Pointer Trap* (Segmentation Fault).
- **Mitigasi:**
  - Fallback ke *Virtual Memory Paging*: Sediakan secondary overflow allocator yang meminjam memori heap general secara terkontrol dan menembakkan *warning log* telemetry ke dashboard profiling.
  - Terapkan strategi *Graceful Degradation*: Jika arena sensorik penuh, turunkan resolusi sensori (misal: hanya mendeteksi 4 target terdekat).

#### 2. Dangling Pointers Setelah `Reset()`
- **Skenario:** Pointer objek di dalam Arena disimpan ke dalam struktur data persisten (misal: referensi musuh disimpan di Blackboard antar-frame).
- **Dampak:** *Use-After-Free* terselubung. Nilai pointer valid secara alamat, tetapi datanya tertimpa oleh alokasi frame berikutnya (*silent memory corruption*).
- **Mitigasi:** Gunakan pola **Index-based Handles** atau *generational IDs* daripada *raw pointer* langsung untuk semua referensi silang data.

#### 3. Unaligned SIMD Instruction Access
- **Skenario:** Alokasi data vektor untuk instruksi AVX2/AVX-512 (`__m256` butuh 32-byte alignment) menggunakan alokator yang secara default memakai `alignof(std::max_align_t)` (biasanya 8 atau 16 byte).
- **Dampak:** Prosesor melempar interupsi `#GP (General Protection Fault)` yang mematikan proses game secara instan.
- **Mitigasi:** Validasi mutlak nilai alignment via `static_assert` dan `assert(IsPowerOfTwo(alignment))`.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | General Heap (`malloc`) | Linear/Arena Allocator | Fixed-Block Pool |
| :--- | :--- | :--- | :--- |
| **Waktu Alokasi** | Variabel $O(n)$ / Lock bound | Deterministik $O(1)$ | Deterministik $O(1)$ |
| **Waktu Dealokasi** | Variabel $O(n)$ | $O(1)$ (Seluruh buffer) | Deterministik $O(1)$ |
| **Fragmentasi Eksternal** | Sangat Tinggi seiring waktu | **Nol** | **Nol** |
| **Fragmentasi Internal** | Rendah | Sedang (Tergantung Alignment) | Sedang jika ukuran objek dinamis |
| **Kemudahan Pemakaian** | Otomatis | Perlu tracking lifecycle | Terikat satu ukuran seragam |
| **Multi-threading** | Scalable via thread caches | Butuh *Thread-Local Arena* | Butuh lock-free list / TLS |

#### Kapan Menggunakan Solusi Lain?
- **High-Performance Scalable Heap (mimalloc / jemalloc):** Gunakan untuk modul loading resource (tekstur, audio) di mana ukuran objek berfluktuasi masif dan tidak terikat pada *frame tick*.
- **Stack-based Allocator (`std::byte stackBuffer[N]`):** Gunakan untuk kalkulasi lokal dalam satu blok fungsi yang sempit daripada menaruh beban pada Arena global.

---

### 9. Best Practices & Standard Industri

1. **Rule of Zero Dynamic Allocations During Tick:** Tidak boleh ada pemanggilan `new`, `malloc`, `std::vector::push_back` (yang memicu realokasi heap), atau pembuatan `std::string` di dalam thread simulasi game yang sedang berjalan.
2. **Double-Buffered Frame Arenas:** Implementasikan dua arena per-frame ($Arena_A$ dan $Arena_B$). Frame saat ini membaca hasil *asynchronous task* dari frame sebelumnya yang ada di $Arena_A$, sementara *worker threads* menulis data baru ke $Arena_B$.
3. **Explicit Memory Budgets:** Beri batas tegas konsumsi memori per subsistem (misal: AI Navigation: 32MB, AI Perception: 16MB, AI State Trees: 16MB).
4. **Cache Line Alignment Enforcement:** Selaraskan semua struktur data agen penting ke batas 64-byte (`alignas(64)`) untuk menghindari fenomena *False Sharing* saat multi-threading.
5. **Memory Tagging & Tracy Profiler Integration:** Pasang *profiling zone* untuk melacak watermarking offset arena guna mendeteksi tren kebocoran alokasi secara real-time.

---

### 10. Hands-on Lab Exercise: Mengukur Latensi & Efisiensi Cache Allocator

#### Deskripsi Lab
Anda diminta untuk mengukur performa alokasi 100.000 entity state *Behavior Tree Node* antara alokator heap standar (`std::vector` of pointers via `new`) melawan `PoolAllocator` yang telah dibuat.

#### Langkah-langkah Implementasi

1. **Setup File (`benchmark_main.cpp`):**
   Salin implementasi `PoolAllocator` dan `ArenaAllocator` di atas.

2. **Tuliskan Skenario Uji Benchmark:**
```cpp
#include <chrono>
#include <iostream>
#include <vector>

struct BehaviorNode {
    std::uint64_t nodeId;
    float status;
    float threshold;
    char debugTag[16];
};

int main() {
    constexpr std::size_t AGENT_COUNT = 100'000;
    
    // ==========================================
    // Skenario 1: Heap Allocation (Standard new)
    // ==========================================
    {
        auto start = std::chrono::high_resolution_clock::now();
        std::vector<BehaviorNode*> heapNodes;
        heapNodes.reserve(AGENT_COUNT);

        for (std::size_t i = 0; i < AGENT_COUNT; ++i) {
            heapNodes.push_back(new BehaviorNode{i, 1.0f, 0.5f, "TaskNode"});
        }

        for (auto* node : heapNodes) {
            delete node;
        }
        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> duration = end - start;
        std::cout << "[Standard Heap] Time taken: " << duration.count() << " ms\n";
    }

    // ==========================================
    // Skenario 2: Pool Allocator
    // ==========================================
    {
        // Alokasikan memori pool mentah terlebih dahulu (Bulk allocation)
        constexpr std::size_t BUFFER_SIZE = AGENT_COUNT * sizeof(BehaviorNode) + 4096;
        std::vector<std::byte> poolMemory(BUFFER_SIZE);

        auto start = std::chrono::high_resolution_clock::now();
        
        Core::Memory::PoolAllocator pool(poolMemory, sizeof(BehaviorNode), alignof(BehaviorNode));
        std::vector<BehaviorNode*> poolNodes;
        poolNodes.reserve(AGENT_COUNT);

        for (std::size_t i = 0; i < AGENT_COUNT; ++i) {
            BehaviorNode* node = pool.Create<BehaviorNode>(i, 1.0f, 0.5f, "TaskNode");
            poolNodes.push_back(node);
        }

        for (auto* node : poolNodes) {
            pool.Destroy(node);
        }

        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> duration = end - start;
        std::cout << "[Pool Allocator] Time taken: " << duration.count() << " ms\n";
    }

    return 0;
}
```

3. **Kompilasi dengan Optimasi Maksimal:**
```bash
g++ -O3 -std=c++20 -march=native benchmark_main.cpp -o memory_benchmark
./memory_benchmark
```

4. **Verifikasi Output:**
- Amati perbedaan durasi eksekusi: Implementasi `PoolAllocator` umumnya memberikan percepatan sebesar **$4\times$ hingga $10\times$** dibandingkan alokasi heap individual.
- *(Opsional)* Jalankan profiling cache menggunakan Linux `perf`:
```bash
perf stat -e L1-dcache-load-misses,L1-dcache-loads ./memory_benchmark
```
- Buktikan bahwa alokasi via contiguous block menghasilkan rasio *L1-dcache-load-misses* yang jauh lebih kecil dibandingkan *standard heap*.