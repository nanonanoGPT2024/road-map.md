# Kurikulum Enterprise: Game AI & Autonomous Systems
## Kategori: 08-AI-Data-and-Autonomous-Agents
## Topik: Game Developer
## BAB 01: Fondasi dan Arsitektur
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengeliminasi Bottleneck Cache**: Mengidentifikasi *cache thrashing*, *pointer chasing*, dan fragmentasi memori pada arsitektur AI konvensional serta mentransformasikannya ke *Data-Oriented Design* (DOD).
- **Merancang Pipeline Sense-Think-Act Skala Masif**: Mengimplementasikan subsistem AI terpisah berbasis ECS (*Entity Component System*) yang mampu mengeksekusi 10.000+ entitas otonom dalam batas *frame budget* $\le 2.5\text{ ms}$ pada 60 FPS (16.6 ms total budget).
- **Membangun Sistem AI LOD (*Level of Detail*) & Time-Slicing**: Mengembangkan *scheduler* deterministik berbasis prioritas jarak, frustum kamera, dan *threat level* untuk mendistribusikan beban komputasi AI secara merata antar-frame.
- **Mengintegrasikan Algoritma *Steering* & Penghindaran Tabrakan Skalabel**: Menerapkan spatial hashing terindeks dan integrasi penghindaran lokal (*Reciprocal Velocity Obstacles* / RVO2) dengan alokasi memori nol (*zero dynamic memory allocation*) pada *hot path*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Sistem Komputer & Model Memori**: Memahami arsitektur CPU modern (L1/L2/L3 *cache line* 64-byte, *instruction pipelining*, *branch prediction*, dan *false sharing* pada arsitektur multi-core).
- **Pemrograman Modern Lanjutan (C++20 / Rust)**: Pointer manipulation, memory alignment (`alignas`), *contiguous memory containers*, RAII, serta *multithreading primitives* (atomics, spinlocks, worker thread pools).
- **Struktur Data Spasial Dasar**: Grid, Quadtree/Octree, dan A* Graph Search.
- **Fondasi Modul 01**: State Machine, Hierarchical State Machine (HSM), dan dasar-dasar Behavior Tree (BT).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Masalah Mendasar Arsitektur OOP Tradisional
Pendekatan Object-Oriented Programming (OOP) klasik dalam Game AI mengemas data dan fungsi ke dalam kelas monolitik (misal: `class Monster : public CActor`). Saat dunia game memiliki ribuan agen, loop pembaruan (*tick loop*) mengeksekusi:

```cpp
// Pola Anti-Performa (Pointer Chasing & Cache Misses)
for (auto* agent : active_agents) {
    agent->Tick(delta_time); // Virtual method call
}
```

Pola ini menghasilkan masalah arsitektural fatal:
1. **Virtual Method Table (vtable) Indirection**: Lompatan instruksi pointer yang memicu *instruction cache (i-cache) misses*.
2. **Scatter-Gather Memory Access**: Data setiap `agent` tersebar acak di *heap memory*. Ketika CPU memuat sebuah `agent` ke *cache line* (64 byte), 90% data yang ditarik tidak terpakai secara langsung oleh subsistem evaluasi (misal data tekstur, string nama, referensi audio).
3. **Branch Misprediction**: Setiap agen memiliki percabangan logika unik di dalam metode `Tick`-nya, menyebabkan CPU *pipeline stall*.

#### Paradigma Data-Oriented AI (ECS Pipeline)
Arsitektur produksi modern memecah AI menjadi tiga lapisan murni: **Sense**, **Think**, dan **Act**, dengan data yang disimpan secara kontigu dalam format *Structure of Arrays* (SoA) atau *packed flat arrays*.

```
[ MEMORY LAYOUT: CONTIGUOUS ARRAYS ]
Spatial Components   : [ Pos0, Pos1, Pos2, Pos3, ... ] -> Cache friendly 
Perception Components: [ Sens0, Sens1, Sens2, Sens3, ... ]
Decision Components  : [ Goal0, Goal1, Goal2, Goal3, ... ]
Blackboard Data      : [ State0, State1, State2, State3, ... ]
```

```
               +-------------------------------------------------+
               |             MAIN TICK SCHEDULER                 |
               +-------------------------------------------------+
                                       |
                   [ Phase 1: Spatial Partitioning Sync ]
                                       |
                                       v
               +-------------------------------------------------+
               | Parallel Spatial Hash Ingestion (SIMD-Friendly) |
               +-------------------------------------------------+
                                       |
                   [ Phase 2: AI Level of Detail (LOD) ]
                                       |
                                       v
               +-------------------------------------------------+
               | Priority Binning & Time-Slicing Scheduler       |
               | - High Priority: Every Tick (16.6ms)            |
               | - Medium Priority: Every 2 Ticks (33.3ms)       |
               | - Low Priority: Every 4 Ticks (66.6ms)          |
               +-------------------------------------------------+
                                       |
                   [ Phase 3: Sense (Perception System) ]
                                       |
                                       v
               +-------------------------------------------------+
               | Broadphase Raycast Batching + Stimulus RingBuf  |
               +-------------------------------------------------+
                                       |
                   [ Phase 4: Think (Decision System) ]
                                       |
                                       v
               +-------------------------------------------------+
               | Utility Function Evaluator / HTN Expansion      |
               | (Vectorized math, Zero heap allocation)         |
               +-------------------------------------------------+
                                       |
                   [ Phase 5: Act (Locomotion & Steering) ]
                                       |
                                       v
               +-------------------------------------------------+
               | ORCA/RVO2 Avoidance System -> Velocity Outputs  |
               +-------------------------------------------------+
```

#### Komponen Kunci Arsitektur Produksi
1. **Spatial Hashing**: Struktur data spasial tanpa pohon (*tree-less*) berbasis flat array berukuran tetap. Menghindari *pointer traversal* Quadtree/Octree dengan memetakan koordinat 3D ke 1D Hash Index:
   $$\text{Hash}(x, y, z) = ((x \cdot p_1) \oplus (y \cdot p_2) \oplus (z \cdot p_3)) \pmod M$$
   di mana $p_1, p_2, p_3$ adalah bilangan prima besar, dan $M$ adalah kapasitas buffer sel.
2. **Linear Perception Queries**: Penginderaan (penglihatan, pendengaran) tidak dilakukan dengan melempar *physics raycast* seketika. Stimulus dicatat ke dalam *Stimulus Queue* sirkular, lalu diproses serentak menggunakan operasi dot-product ter-vektorisasi (SIMD AVX-2 / NEON) untuk kalkulasi *field of view* (FoV).
3. **Decoupled Planning vs Execution**: Modul evaluasi perilaku (misal: Utility AI atau Hierarchical Task Network / HTN) berjalan secara asinkron atau menggunakan penjadwalan *budgeted time-slice*, terpisah dari *locomotion controller* yang wajib berjalan stabil di setiap frame rendering/fisika.

---

### 4. Why & What

| Fitur / Karakteristik | OOP Behavior Tree Tradisional | Data-Oriented Hierarchical AI (Production) |
| :--- | :--- | :--- |
| **Penyimpanan Memori** | *Node graph* berbasis pointer (*heap-allocated*) | Contiguous memory arrays (SoA/AoS terkontrol) |
| **Karakteristik Cache** | Sangat buruk; $60\text{--}80\%$ *cache miss rate* | Mendekati optimal; *linear sequential read prefetching* |
| **Alokasi Memori** | Sering terjadi `new`/`delete` saat *action state change* | Nol alokasi pada *runtime* (pre-allocated arena buffers) |
| **Multi-threading** | Rentan *race condition*; membutuhkan penguncian (mutex) | *Data parallelism* masif melalui Job System tanpa locks |
| **Skalabilitas Agen** | Terdegradasi pada 500–1.000 agen | Mampu menangani 20.000+ agen secara stabil |
| **Pengujian & Debug** | Sulit diisolasi; dependensi state saling silang | Sangat deterministik; mudah di-*replay* dengan data snapshot |

---

### 5. How (Workflow Detail)

1. **Spatial Ingestion**: 
   Setiap agen memperbarui posisi ke dalam *Dense Spatial Hash Grid*. Transformasi spasial dihitung sekali per frame untuk seluruh populasi.
2. **LOD & Execution Classification**:
   Scheduler mengevaluasi signifikansi entitas terhadap *Viewport* kamera dan *Gameplay Context*:
   - **LOD 0 (Kritis, Jarak $\le 15\text{m}$, Dalam Frustum)**: Tick penuh setiap frame. Sense, Think, Act aktif.
   - **LOD 1 (Menengah, Jarak $15\text{--}40\text{m}$)**: Tick diperbarui tiap 2 frame sekali. Interpolasi posisi aktif.
   - **LOD 2 (Latar Belakang, Jarak $> 40\text{m}$)**: Tick diperbarui tiap 10 frame sekali. Logika sensor dinonaktifkan, pergerakan berbasis jalur makro (*dead reckoning*).
3. **Batch Perception Evaluation**:
   Pencarian target (*target acquisition*) mengevaluasi kerucut penglihatan:
   $$\vec{V}_{\text{norm}} = \frac{\vec{P}_{\text{target}} - \vec{P}_{\text{agent}}}{\|\vec{P}_{\text{target}} - \vec{P}_{\text{agent}}\|}$$
   $$\text{Dot} = \vec{F}_{\text{agent}} \cdot \vec{V}_{\text{norm}}$$
   Jika $\text{Dot} \ge \cos(\theta / 2)$ dan jarak $\le R_{\text{max}}$, tandai visibilitas sebelum melempar batch raycast ke physics engine.
4. **Behavior Evaluation**:
   State agen dievaluasi menggunakan *Utility Scoring* berbasis polinomial atau *Chebyshev curve*:
   $$U = \prod_{i=1}^n S_i(m_i)$$
   Skor dinilai secara paralel dalam array contigu tanpa alokasi memori dinamis.
5. **Steering & Dynamic Avoidance**:
   Menerapkan *Reciprocal Velocity Obstacles* (RVO2) untuk menyelesaikan pergerakan bebas tabrakan dalam kelompok padat, menghasilkan vektor kecepatan akhir $\vec{V}_{\text{new}}$.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan arsitektur OOP klasik seperti **Restoran dengan 1.000 Pelayan Pribadi**. Setiap pelanggan dilayani satu pelayan yang harus bolak-balik ke dapur untuk mengambil satu sendok garam, lalu kembali lagi mengambil satu garpu. Dapur menjadi kacau, lorong tersumbat (*memory bus bottleneck*), dan operasional melambat drastis.

Sebaliknya, Arsitektur Data-Oriented seperti **Pabrik Katering Otomatis**. Seluruh wadah makanan diletakkan dalam ban berjalan (*contiguous memory*). Satu mesin mengisikan nasi ke 1.000 kotak sekaligus secara berurutan (*SIMD/Vectorized cache execution*), mesin berikutnya menambahkan lauk, dan mesin ketiga menutup kemasan. Efisiensi throughput mencapai batas maksimal perangkat keras.

#### Diagram Layout Memori (Cache Line Alignment)

```
        64-Byte Cache Line 0                64-Byte Cache Line 1
+-----------------------------------+-----------------------------------+
| Pos.X | Pos.Y | Pos.Z | Radius    | Pos.X | Pos.Y | Pos.Z | Radius    |  <-- Contiguous Positions
| Agent 0                           | Agent 1                           |
+-----------------------------------+-----------------------------------+
  Direct Sequential Fetch -> ZERO Cache Misses

VS.

OOP Pointer Indirection:
[Agent 0 Ptr] ---> Heap Chunk A [ vtable | Name | TextureRef | Pos... ] (Thrashing!)
[Agent 1 Ptr] ---> Heap Chunk B [ vtable | Name | TextureRef | Pos... ] (Thrashing!)
```

---

### 7. Code Examples

Berikut implementasi sistem AI inti produksi berbasis C++20 yang mengedepankan performa: *Linear Contiguous Spatial Hash*, *Zero-Allocation Time-Slicing Scheduler*, dan *Vectorized Utility AI Evaluator*.

#### Simple Example: Vectorized Utility Scoring (Data-Oriented)

```cpp
#include <iostream>
#include <vector>
#include <cmath>
#include <algorithm>
#include <span>

struct AgentSensoryData {
    float health_normalized; // 0.0 to 1.0
    float target_distance;    // Meters
    float ammo_normalized;    // 0.0 to 1.0
};

enum class ActionDecision : uint8_t {
    Idle = 0,
    Attack,
    Flee,
    Reload
};

// Evaluator murni: Tanpa alokasi dinamis, SIMD-friendly loop
void EvaluateDecisions(
    std::span<const AgentSensoryData> sensor_inputs,
    std::span<ActionDecision> decisions_out) 
{
    const size_t count = sensor_inputs.size();
    for (size_t i = 0; i < count; ++i) {
        const auto& sense = sensor_inputs[i];
        
        // Response curve calculation
        float flee_score = (1.0f - sense.health_normalized) * 1.5f;
        float attack_score = (sense.target_distance < 20.0f ? 1.0f : 0.1f) * sense.ammo_normalized;
        float reload_score = (1.0f - sense.ammo_normalized) * 0.8f;
        
        if (flee_score > attack_score && flee_score > reload_score && flee_score > 0.5f) {
            decisions_out[i] = ActionDecision::Flee;
        } else if (attack_score >= flee_score && attack_score >= reload_score && attack_score > 0.3f) {
            decisions_out[i] = ActionDecision::Attack;
        } else if (reload_score > 0.4f) {
            decisions_out[i] = ActionDecision::Reload;
        } else {
            decisions_out[i] = ActionDecision::Idle;
        }
    }
}
```

#### Practical Example: Arsitektur Scheduler & Spatial Engine Produksi

```cpp
#include <iostream>
#include <vector>
#include <cmath>
#include <cstdint>
#include <chrono>
#include <cstring>
#include <span>

// Structure-of-Arrays (SoA) data packing untuk 64-byte boundary optimization
struct alignas(64) AIAgentCrowd {
    std::vector<float> pos_x;
    std::vector<float> pos_y;
    std::vector<float> pos_z;
    std::vector<float> vel_x;
    std::vector<float> vel_y;
    std::vector<float> vel_z;
    std::vector<uint8_t> lod_tier;     // 0: High, 1: Medium, 2: Low
    std::vector<uint8_t> update_phase; // Modulo counter untuk time-slicing

    void Resize(size_t size) {
        pos_x.resize(size, 0.0f);
        pos_y.resize(size, 0.0f);
        pos_z.resize(size, 0.0f);
        vel_x.resize(size, 0.0f);
        vel_y.resize(size, 0.0f);
        vel_z.resize(size, 0.0f);
        lod_tier.resize(size, 0);
        update_phase.resize(size, 0);
    }

    size_t Size() const { return pos_x.size(); }
};

// Spatial Hash Grid 3D berbasis Dense Array tanpa Heap allocations pada hot path
class SpatialHashGrid {
public:
    static constexpr uint32_t TABLE_SIZE = 65536; // 2^16 buckets
    static constexpr float CELL_SIZE = 4.0f;
    static constexpr float INV_CELL_SIZE = 1.0f / CELL_SIZE;

    SpatialHashGrid() {
        m_head.resize(TABLE_SIZE, -1);
        m_next.reserve(100000);
        m_agent_indices.reserve(100000);
    }

    void Clear() {
        std::fill(m_head.begin(), m_head.end(), -1);
        m_next.clear();
        m_agent_indices.clear();
    }

    void Insert(uint32_t agent_index, float x, float y, float z) {
        uint32_t hash = ComputeHash(x, y, z);
        m_agent_indices.push_back(agent_index);
        m_next.push_back(m_head[hash]);
        m_head[hash] = static_cast<int32_t>(m_agent_indices.size() - 1);
    }

    template <typename Func>
    void QueryNeighbors(float x, float y, float z, float radius, Func&& callback) const {
        int32_t min_x = static_cast<int32_t>(std::floor((x - radius) * INV_CELL_SIZE));
        int32_t max_x = static_cast<int32_t>(std::floor((x + radius) * INV_CELL_SIZE));
        int32_t min_y = static_cast<int32_t>(std::floor((y - radius) * INV_CELL_SIZE));
        int32_t max_y = static_cast<int32_t>(std::floor((y + radius) * INV_CELL_SIZE));
        int32_t min_z = static_cast<int32_t>(std::floor((z - radius) * INV_CELL_SIZE));
        int32_t max_z = static_cast<int32_t>(std::floor((z + radius) * INV_CELL_SIZE));

        for (int32_t xi = min_x; xi <= max_x; ++xi) {
            for (int32_t yi = min_y; yi <= max_y; ++yi) {
                for (int32_t zi = min_z; zi <= max_z; ++zi) {
                    uint32_t hash = HashCoords(xi, yi, zi);
                    int32_t entry = m_head[hash];
                    while (entry != -1) {
                        callback(m_agent_indices[entry]);
                        entry = m_next[entry];
                    }
                }
            }
        }
    }

private:
    static inline uint32_t HashCoords(int32_t x, int32_t y, int32_t z) {
        return (static_cast<uint32_t>(x * 73856093) ^ 
                static_cast<uint32_t>(y * 19349663) ^ 
                static_cast<uint32_t>(z * 83492791)) % TABLE_SIZE;
    }

    static inline uint32_t ComputeHash(float x, float y, float z) {
        return HashCoords(
            static_cast<int32_t>(std::floor(x * INV_CELL_SIZE)),
            static_cast<int32_t>(std::floor(y * INV_CELL_SIZE)),
            static_cast<int32_t>(std::floor(z * INV_CELL_SIZE))
        );
    }

    std::vector<int32_t> m_head;
    std::vector<int32_t> m_next;
    std::vector<uint32_t> m_agent_indices;
};

// Production Tick Controller
class ProductionAISubsystem {
public:
    explicit ProductionAISubsystem(size_t max_agents) {
        m_crowd.Resize(max_agents);
        m_frame_counter = 0;
    }

    void InitializePositionsRandomly() {
        for (size_t i = 0; i < m_crowd.Size(); ++i) {
            m_crowd.pos_x[i] = static_cast<float>(rand() % 1000) - 500.0f;
            m_crowd.pos_y[i] = 0.0f;
            m_crowd.pos_z[i] = static_cast<float>(rand() % 1000) - 500.0f;
            m_crowd.update_phase[i] = static_cast<uint8_t>(i % 4); // Desinkronisasi phase
        }
    }

    void Update(float delta_time, float camera_x, float camera_z) {
        m_spatial_grid.Clear();
        const size_t total_agents = m_crowd.Size();

        // Step 1: Spatial Grid Update & Compute Distance-based LOD
        for (size_t i = 0; i < total_agents; ++i) {
            m_spatial_grid.Insert(static_cast<uint32_t>(i), m_crowd.pos_x[i], m_crowd.pos_y[i], m_crowd.pos_z[i]);

            float dx = m_crowd.pos_x[i] - camera_x;
            float dz = m_crowd.pos_z[i] - camera_z;
            float dist_sq = dx * dx + dz * dz;

            if (dist_sq < 30.0f * 30.0f) {
                m_crowd.lod_tier[i] = 0; // High Priority
            } else if (dist_sq < 100.0f * 100.0f) {
                m_crowd.lod_tier[i] = 1; // Medium Priority
            } else {
                m_crowd.lod_tier[i] = 2; // Low Priority
            }
        }

        // Step 2: Time-sliced Sensory & Logic Tick
        for (size_t i = 0; i < total_agents; ++i) {
            uint8_t lod = m_crowd.lod_tier[i];
            bool should_tick = false;

            switch (lod) {
                case 0:
                    should_tick = true; // Every frame
                    break;
                case 1:
                    should_tick = ((m_frame_counter + m_crowd.update_phase[i]) % 2 == 0);
                    break;
                case 2:
                    should_tick = ((m_frame_counter + m_crowd.update_phase[i]) % 4 == 0);
                    break;
            }

            if (!should_tick) {
                // Dead reckoning integrasi sederhana untuk agen yang di-skip
                m_crowd.pos_x[i] += m_crowd.vel_x[i] * delta_time;
                m_crowd.pos_z[i] += m_crowd.vel_z[i] * delta_time;
                continue;
            }

            // Eksekusi Logika Berpikir & Penghindaran Spasial (Neighborhood Query)
            float separation_x = 0.0f;
            float separation_z = 0.0f;
            uint32_t neighbor_count = 0;

            m_spatial_grid.QueryNeighbors(
                m_crowd.pos_x[i], m_crowd.pos_y[i], m_crowd.pos_z[i], 5.0f,
                [&](uint32_t neighbor_idx) {
                    if (neighbor_idx == i) return;
                    float sep_dx = m_crowd.pos_x[i] - m_crowd.pos_x[neighbor_idx];
                    float sep_dz = m_crowd.pos_z[i] - m_crowd.pos_z[neighbor_idx];
                    float d2 = sep_dx * sep_dx + sep_dz * sep_dz;
                    if (d2 > 0.0001f && d2 < 25.0f) {
                        float inv_d = 1.0f / std::sqrt(d2);
                        separation_x += sep_dx * inv_d;
                        separation_z += sep_dz * inv_d;
                        neighbor_count++;
                    }
                }
            );

            if (neighbor_count > 0) {
                m_crowd.vel_x[i] += separation_x * 0.5f;
                m_crowd.vel_z[i] += separation_z * 0.5f;
            }

            // Clamp velocity
            float speed_sq = m_crowd.vel_x[i] * m_crowd.vel_x[i] + m_crowd.vel_z[i] * m_crowd.vel_z[i];
            if (speed_sq > 25.0f) {
                float inv_speed = 5.0f / std::sqrt(speed_sq);
                m_crowd.vel_x[i] *= inv_speed;
                m_crowd.vel_z[i] *= inv_speed;
            }

            m_crowd.pos_x[i] += m_crowd.vel_x[i] * delta_time;
            m_crowd.pos_z[i] += m_crowd.vel_z[i] * delta_time;
        }

        m_frame_counter++;
    }

private:
    AIAgentCrowd m_crowd;
    SpatialHashGrid m_spatial_grid;
    uint32_t m_frame_counter;
};

int main() {
    constexpr size_t AGENT_COUNT = 20000;
    ProductionAISubsystem ai_system(AGENT_COUNT);
    ai_system.InitializePositionsRandomly();

    std::cout << "[Enterprise AI] Benchmarking " << AGENT_COUNT << " Data-Oriented Agents...\n";

    auto start_time = std::chrono::high_resolution_clock::now();
    for (int frame = 0; frame < 60; ++frame) {
        ai_system.Update(0.016f, 0.0f, 0.0f);
    }
    auto end_time = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double, std::milli> total_duration = end_time - start_time;
    std::cout << "[Benchmark Result] Total Time (60 Frames): " << total_duration.count() << " ms\n";
    std::cout << "[Benchmark Result] Average Time per Frame: " << (total_duration.count() / 60.0) << " ms\n";

    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: MMORPG / Battle Royale Server Skala 2.000 Agen Cerdas Per Zona
- **Masalah Produksi**: Pada peluncuran game battle-royale dengan 100 pemain manusia dan 900 bot tempur taktis per server shard, tick rate server turun drastis dari 30 Hz ($33.3\text{ ms}$) ke 8 Hz ($125\text{ ms}$). Profiling menunjukkan bahwa **72% durasi frame** dihabiskan pada evaluasi *Behavior Tree* dan *Sight Raycasts* bawaan engine konvensional.
- **Analisis Root Cause**:
  1. *Raycast Flood*: Setiap bot menembakkan 16 raycast per detik ke arah seluruh bot lain di sekitarnya tanpa pengecekan frustum, menyebabkan Physics Engine thread jenuh (*lock contention*).
  2. *Behavior Tree Node Traversal Overhead*: Setiap entitas mengalokasikan memori saat memasuki Composite/Decorator node baru, memicu *Garbage Collection / Heap Fragmentation*.
- **Solusi Rekayasa**:
  1. **Dual-Layer Spatial Broadphase**: Raycast ditiadakan secara total kecuali jika jarak bot sudah memenuhi radius bahaya dan target berada di kerucut penglihatan $\pm 45^\circ$ via SIMD dot-product check.
  2. **Migration to Flat Utility State Arrays**: Behavior Tree diganti dengan *Linear Utility Action Scoring* yang diproses dalam chunk berukuran 256 agen per job thread.
  3. **Staggered Perception Tick**: Perception bot dipartisi menjadi 4 bucket fase. Tiap bucket diperbarui setiap 133 ms alih-alih 33 ms, sementara steering lokal tetap berjalan setiap 33 ms.
- **Hasil**:
  Penggunaan CPU AI drop sebesar **84%** (dari $24\text{ ms}$ menjadi $3.8\text{ ms}$ per server tick). Server mampu mempertahankan kecepatan konstan 30 Hz di bawah beban tempur penuh.

---

### 9. Trade-offs

```
                         [Arsitektur AI]
                               /\
                              /  \
                             /    \
                            /      \
      [Memory Footprint]  /________\  [Tick Throughput]
                     \                  /
                      \                /
                       [Determinism]
```

1. **Memory Pre-Allocation vs Dynamic Scaling**:
   - *Trade-off*: Mengalokasikan arena memori statis (misal 50 MB di awal) untuk menampung data kontigu menjamin $0\text{ alokasi}$ pada hot path dan throughput maksimal.
   - *Konsekuensi*: Memori terikat meskipun jumlah agen di dunia game sedang sedikit (pemborosan footprint RAM pada skenario minim agen).
2. **AI LOD Time-Slicing vs Behavioral Responsiveness**:
   - *Trade-off*: Menurunkan frekuensi tick agen jauh (LOD 2) menghemat siklus CPU secara masif.
   - *Konsekuensi*: Agen di batas jarak pandang terlihat mengalami keterlambatan reaksi (*reaction latency*) jika pemain mendekatinya secara tiba-tiba menggunakan kendaraan cepat (sniper shot/teleport).
3. **Continuous Collision vs Discrete Grid Approximation**:
   - *Trade-off*: Spatial hash berbasis grid seragam memberikan kompleksitas $O(1)$ untuk insersi dan kueri lingkungan terdekat.
   - *Konsekuensi*: Membutuhkan penyesuaian ukuran sel (*cell size tuning*). Jika sel terlalu kecil, agen melintasi banyak batas sel; jika terlalu besar, algoritma terdegradasi menjadi $O(N^2)$ dalam sel yang padat.

---

### 10. Common Mistakes & Troubleshooting

#### 1. Dynamic Allocation pada Hot Path AI
- **Gejala**: FPS drop sporadis setiap beberapa ratus frame (terjadi *hiccups* atau *stuttering*).
- **Penyebab**: Penggunaan container seperti `std::vector::push_back` tanpa `reserve`, penggunaan `std::shared_ptr` di dalam loop evaluasi, atau pembuatan instansiasi aksi baru menggunakan operator `new`.
- **Solusi**: Gunakan *Fixed-size Ring Buffers*, *Arena Allocators*, atau `std::span` yang memetakan array yang sudah dialokasikan sejak inisialisasi level.

#### 2. Pathfinding Stampede (Thundering Herd)
- **Gejala**: Server atau client *freeze* selama 500 ms saat sebuah jembatan runtuh atau rintangan dinamis baru tercipta di arena.
- **Penyebab**: Seluruh 2.000 agen mendeteksi kegagalan path secara simultan dan meminta kalkulasi ulang $A^*$ pada frame yang sama.
- **Solusi**: Terapkan **Request Coalescing** dan antrean pencarian jalur terdistribusi (*Token-Bucket Request Queue*): batasi maksimal 50 path request per frame, prioritaskan entitas dengan jarak terdekat dari rintangan.

#### 3. Spatial Hash False Sharing pada Sistem Multithread
- **Gejala**: Kinerja multithreaded AI scaling buruk saat jumlah core CPU ditambah dari 4 menjadi 16 core.
- **Penyebab**: Beberapa thread pekerja menulis ke struktur data sel spatial hash yang berdampingan pada *cache line* yang sama (64 byte), memicu protokol koherensi cache (*cache invalidation cascade*).
- **Solusi**: Gunakan teknik *Double Buffering* atau partisi spasial berbasis domain (*Spatial Domain Decomposition*) di mana setiap thread hanya bertanggung jawab atas kuadran geografis tertentu.

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Contiguity**: Komponen pergerakan dan status agen tersimpan dalam format linear memory array (AoS terkontrol atau SoA), bukan pointer terfragmentasi.
- [ ] **Zero Dynamic Allocations**: Tidak ada pemanggilan `malloc`, `new`, atau resizing container dinamis pada fase *Sense-Think-Act*.
- [ ] **Explicit Alignment**: Struktur data AI di-align pada boundary cache line (`alignas(64)` pada arsitektur x86_64).
- [ ] **SIMD Optimization**: Loop perhitungan jarak dan dot-product frustum bebas dari percabangan (*branchless computation*) agar compiler dapat melakukan auto-vectorization.
- [ ] **LOD AI Matrix**: Memiliki minimal 3 tingkatan LOD AI yang memisahkan update rate logika, sensor, dan pergerakan.
- [ ] **Budget Cap Enforcer**: Tick AI dipagari oleh *High-Resolution Timer*. Jika eksekusi melebihi budget ($2.5\text{ ms}$), tunda pemrosesan sisa entitas LOD rendah ke frame berikutnya.
- [ ] **Deterministic Desynchronization**: Agen diberi phase offset acak berbasis ID uniknya untuk mencegah semua agen mengeksekusi tick berat pada nomor frame yang sama.

---

### 12. Hands-on Practice
Simpan seluruh artefak praktikum pada direktori: `hands-on/m02/`

#### Langkah Praktikum:
1. **Setup File**: Buat berkas `hands-on/m02/spatial_ai_benchmark.cpp`.
2. **Kompilasi**: Gunakan flag optimasi compiler enterprise:
   ```bash
   g++ -O3 -std=c++20 -march=native -Wall -Wextra -pthread spatial_ai_benchmark.cpp -o spatial_ai_benchmark
   ```
3. **Eksekusi & Profiling**:
   - Jalankan program dan perhatikan output throughput frame time.
   - Gunakan profiler Linux `perf` untuk memverifikasi rasio cache misses:
   ```bash
   perf stat -e L1-dcache-load-misses,L1-dcache-loads,instructions,cycles ./spatial_ai_benchmark
   ```
4. **Verifikasi Target**: Pastikan rasio *L1-dcache-load-misses* di bawah **5%** dari total *L1-dcache-loads*.

---

### 13. Exercise

#### Level Easy
Ubah implementasi `SpatialHashGrid` pada kode praktikum agar mendukung penghapusan dan pembaruan posisi entitas individual secara dinamis tanpa membersihkan (*Clear*) seluruh grid setiap frame.

#### Level Medium
Tambahkan sistem **Vision Cone Filtering** pada pipeline. Sebelum agen mengeksekusi *neighborhood separation*, agen harus mengevaluasi apakah tetangga berada di sudut pandang penglihatan $120^\circ$ menggunakan operasi perkalian titik (*dot product*) tanpa memanggil fungsi trigonometri berat (`acos`).

#### Level Hard
Rancang dan implementasikan **Asynchronous Budgeted Pathfinding Queue**. Buat worker thread terpisah yang memproses antrean pencarian jalur $A^*$ dengan batas budget waktu maksimal $1.5\text{ ms}$ per pemanggilan. Jika waktu habis, proses di-suspend dan dilanjutkan pada tick thread berikutnya menggunakan coroutines (C++20 `std::coroutine`) atau struktur *State Resumption Context*.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Destruksi Lingkungan Skala Masif (Dynamic NavMesh Invalidation)
Anda adalah Lead Engine Programmer pada game perang taktis perkotaan berskala masif. Dalam permainan, terdapat **5.000 agen otonom** (infanteri) yang bermanuver di dalam reruntuhan kota. 

Pemain meluncurkan serangan udara yang menghancurkan gedung pencakar langit setinggi 40 lantai. Gedung tersebut tumbang melintasi 4 blok kota, mengubah topologi navigasi secara instan:
1. Ribuan poligon NavMesh lama menjadi tidak valid (*invalidated*).
2. Timbunan puing menciptakan rintangan baru setinggi 10 meter.
3. Sebanyak 1.800 agen yang sedang bergerak melintasi rute tersebut mendadak memiliki jalur yang terputus.

**Tantangan Arsitektural**:
Rancang arsitektur sistem respons AI dan navigasi tanpa solusi instan:
- Sistem tidak boleh mengalami *hitch* atau *frame spike* lebih dari $2.0\text{ ms}$ di atas thread navigasi/AI.
- Rancang mekanisme penanganan instan untuk 1.800 agen yang jalurnya terputus agar mereka tidak mematung (*frozen*), tidak menembus puing (*clipping*), dan tidak melakukan *repathing stampede* yang melumpuhkan CPU.
- Tentukan bagaimana representasi data spasial lokal, *local steering avoidance*, dan *hierarchical pathfinding* saling berkoordinasi selama masa regenerasi NavMesh global yang membutuhkan waktu 500 ms di thread latar belakang (*asynchronous background thread*).

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Mengapa pemanggilan metode virtual (`virtual void Tick()`) dalam loop jutaan kali per detik menjadi bottleneck utama pada arsitektur Game AI OOP konvensional?
2. Apa yang dimaksud dengan *false sharing* dalam konteks pemrosesan AI secara paralel di CPU multi-core?
3. Sebutkan ukuran standar dari sebuah CPU Cache Line pada prosesor modern x86_64 dan ARM64!
4. Apa perbedaan mendasar antara representasi data *Array of Structures* (AoS) dan *Structure of Arrays* (SoA)?
5. Mengapa algoritma Spatial Hashing berbasis Dense Array umumnya lebih dipilih dibandingkan Octree untuk game dengan kepadatan agen sangat tinggi yang bergerak dinamis di ruang terbuka?

#### Pertanyaan Intermediate
6. Bagaimana cara kerja teknik *Deterministic Desynchronization* dalam meratakan beban kerja AI antar-frame pada sistem time-slicing?
7. Dalam kalkulasi *Vision Cone*, mengapa perhitungan $\vec{A} \cdot \vec{B} \ge \cos(\theta / 2)$ jauh lebih efisien dibandingkan menggunakan $\arccos(\vec{A} \cdot \vec{B}) \le \theta / 2$?
8. Bagaimana struktur data sirkular (*Ring Buffer*) membantu mencapai target alokasi memori dinamis nol (*zero dynamic allocation*) pada subsistem persepsi?
9. Apa risiko terbesar membiarkan subsistem *Steering Locomotion* diturunkan frekuensinya (*down-ticked*) pada agen yang berada di kategori LOD 2 (jarak jauh)?
10. Bagaimana algoritma *Reciprocal Velocity Obstacles* (RVO2) menjamin stabilitas pergerakan gerombolan (*crowd oscillation reduction*) dibandingkan pendekatan *Repulsion Vector* sederhana?

#### Skenario Kasus Produksi
11. **Kasus A**: Profiler menunjukkan bahwa thread AI menghabiskan waktu komputasi yang sangat rendah ($1.2\text{ ms}$), namun GPU mengalami *underutilization* dan frame rate game tidak stabil. Setelah diteliti, CPU menghabiskan $10\text{ ms}$ menunggu di fase sinkronisasi data transform agen ke engine rendering. Di mana letak kegagalan arsitektur data AI tersebut?
12. **Kasus B**: Pada sebuah game simulasi koloni dengan 10.000 agen, implementasi Spatial Hash menghasilkan performa prima pada fase eksplorasi. Namun, ketika pemain mengumpulkan seluruh 10.000 agen ke satu titik sempit (misal gerbang benteng), frame time melonjak dari $2\text{ ms}$ menjadi $80\text{ ms}$. Apa kelemahan algoritmik yang terpicu, dan bagaimana mengatasinya tanpa mengorbankan performa kondisi normal?
13. **Kasus C**: Sistem AI LOD Anda mematikan evaluasi penginderaan pada musuh di luar frustum kamera. Akibatnya, pemain melaporkan bahwa musuh di belakang mereka tidak pernah menembak atau mengejar, bahkan ketika pemain berada di jarak yang sangat dekat. Bagaimana Anda mendesain ulang arsitektur klasifikasi prioritas LOD untuk memperbaiki kecacatan gameplay ini?

---

### 16. Summary
- Performa arsitektur AI modern pada skala enterprise tidak ditentukan oleh kecerdasan algoritma semata, melainkan oleh **keselarasan struktur data terhadap arsitektur perangkat keras** (*Hardware-Aware Design*).
- Menghilangkan *pointer chasing*, meminimalkan *cache miss*, dan menghapus alokasi dinamis (*zero dynamic allocation*) pada *hot path* adalah prasyarat mutlak untuk menjalankan puluhan ribu agen otonom secara *real-time*.
- Kombinasi antara **Spatial Partitioning Flat Array**, **Sistem AI LOD Dinamis Berbasis Prioritas**, dan **Time-Slicing Deterministik** memungkinkan sistem mendistribusikan beban komputasi secara presisi dalam batas toleransi *frame budget* game engine modern.