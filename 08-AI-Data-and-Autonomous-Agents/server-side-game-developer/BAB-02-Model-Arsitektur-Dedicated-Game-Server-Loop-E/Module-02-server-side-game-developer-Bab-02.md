# Kurikulum Server-Side Game Development: Enterprise Grade
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB 02: Model Arsitektur Dedicated Game Server Loop
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis & Mengeliminasi Jitter Loop:** Mengimplementasikan *Fixed Timestep Simulation Loop* dengan algoritma *Accumulator* untuk mencegah *Spiral of Death* pada variasi beban CPU ekstrem.
- **Merancang Zero-Allocation State Buffer:** Membangun *Ring Buffer* dan struktur data *Structure of Arrays* (SoA) guna memaksimalkan *CPU L1/L2 Cache Locality* pada loop berkecepatan tinggi (60 Hz hingga 128 Hz).
- **Mengisolasi Simulation Tick dari Network Tick:** Mengarsiteki pemisahan antara frekuensi komputasi fisika internal (*Physics/Simulation Tick*) dan frekuensi replikasi jaringan (*Replication/Snapshot Tick*).
- **Menangani Time Synchronization & Drift:** Menghitung dan mengompensasi pergeseran waktu (*clock drift*) antar ribuan klien konkuren terhadap *Authoritative Monotonic Clock* server.
- **Mengoptimalkan Kernel & Process Scheduling:** Menerapkan strategi isolasi CPU (*core pinning/affinity*), konfigurasi *Linux Real-Time Kernel Scheduler* (`SCHED_FIFO`/`SCHED_DEADLINE`), serta mitigasi latensi konkurensi lock-free.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada domain berikut:
- **Sistem Operasi Lanjutan:** Konsep interupsi kernel Linux, *process context-switching*, *memory page faults*, *thread affinity*, dan *high-resolution timers* (`clock_gettime(CLOCK_MONOTONIC_RAW)`).
- **Arsitektur Komputer & Memori:** Mekanisme *CPU Cache Hierarchy* (L1i, L1d, L2, L3), *false sharing*, *memory alignment*, dan operasi atomik hardware (*x86/ARM memory models*).
- **Bahasa Pemrograman Tingkat Sistem:** Mahir menggunakan Modern C++ (C++20) atau Rust (kemampuan mengelola *raw pointers*, *smart pointers*, *templates/generics*, *concurrency primitives*, dan *zero-cost abstractions*).
- **Jaringan Komputer:** Pemahaman mendalam protokol transport UDP, socket non-blocking, serta struktur paket data raw (*custom serialization*).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arsitektur Inti: The Authoritative Dedicated Game Server (DGS)
Server game kompetitif modern beroperasi sebagai *Single Source of Truth* absolut. Status dunia game (*world state*) tidak diperbarui semata-mata berdasarkan instruksi klien, melainkan dieksekusi secara deterministik di server menggunakan input mentah (*raw client inputs*) yang divalidasi.

```
+-----------------------------------------------------------------------------------+
|                        DEDICATED GAME SERVER PROCESS                              |
|                                                                                   |
|  +--------------------+        +---------------------+        +----------------+  |
|  | Network I/O Thread |        | Main Sim Thread     |        | Physics Worker |  |
|  | (Kernel epoll/kqueue)       | (Authoritative Loop)|        | Threads (Pool) |  |
|  +---------+----------+        +----------+----------+        +-------+--------+  |
|            |                              |                           |           |
|   UDP Pkts | [Lock-Free SPSC Queue]       |                           | OpenMP /  |
|   Received |----------------------------> |                           | Job System|
|            |                              v                           |           |
|            |                  +-----------------------+               |           |
|            |                  | Accumulator Processing|<--------------+           |
|            |                  +-----------+-----------+                           |
|            |                              |                                       |
|            |                              v                                       |
|            |                  +-----------------------+                           |
|            |                  | Fixed Timestep Sim    |                           |
|            |                  | (ECS / Systems Phase) |                           |
|            |                  +-----------+-----------+                           |
|            |                              |                                       |
|            |                              v                                       |
|   UDP Pkts | [Lock-Free MPSC Queue]   +-----------------------+                   |
|   Transmit | <------------------------| Snapshot Serializer   |                   |
|            |                          +-----------------------+                   |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kritis Loop Server:

1. **Monotonic Clocks & Timers:**
   Menggunakan `std::chrono::steady_clock` atau pemanggilan kernel langsung `clock_gettime(CLOCK_MONOTONIC_RAW)`. Waktu tidak boleh mundur (*non-decreasing*), tidak boleh terpengaruh oleh penyesuaian NTP (*Network Time Protocol slewing/stepping*), dan harus memiliki presisi sub-mikrodetik.

2. **The Discrete Simulation Loop (Fixed Timestep with Accumulator):**
   Model komputasi game server membagi waktu menjadi irisan diskrit yang seragam ($\Delta t$). Persamaan diferensial gerak dan dinamika status diproses menggunakan integrasi numerik diskrit (misal: Verlet, Symplectic Euler). 
   $$\text{accumulator} = \text{accumulator} + \Delta t_{\text{real}}$$
   $$\text{while } (\text{accumulator} \ge \Delta t_{\text{fixed}}) \implies \text{Simulate}(\Delta t_{\text{fixed}}), \quad \text{accumulator} = \text{accumulator} - \Delta t_{\text{fixed}}$$

3. **Mitigasi Spiral of Death:**
   Jika satu langkah simulasi (*Tick*) memakan waktu komputasi lebih lama dari jatah waktu alaminya ($T_{\text{execution}} > \Delta t_{\text{fixed}}$), `accumulator` akan membengkak secara eksponensial. Pada iterasi berikutnya, server akan mencoba mengejar ketertinggalan dengan menjalankan multi-step tick, yang justru memperparah beban CPU dan menyebabkan server membeku total (*crash* atau *time out*). Solusinya: Penerapan *Frame Clamping* atau *Maximum Dynamic Sub-steps*.

4. **Data-Oriented Simulation (ECS Integration):**
   Pendekatan Object-Oriented tradisional (*Array of Structures* - AoS) menyebabkan polusi L1 Cache karena membawa data non-fisik (misal: `player_name`, `inventory_ids`) saat eksekusi pergerakan. Pendekatan produksi menggunakan *Structure of Arrays* (SoA) dalam model Entity Component System (ECS), di mana array berisi koordinat posisi `[X, Y, Z]` disimpan secara contiguous di memori, memaksimalkan *prefetching hardware* dan *SIMD vectorization*.

---

### 4. Why & What

| Dimensi | Mengapa Arsitektur Ini Dipilih? | Apa Konsekuensi Jika Diabaikan? |
| :--- | :--- | :--- |
| **Fixed Timestep** | Memastikan komputasi status game (vektor posisi, tabrakan, akselerasi) selalu menghasilkan nilai identik di semua kondisi hardware. | Game state menjadi non-deterministik; desinkronisasi fatal antara server dan simulasi lokal klien (*rubberbanding* parah). |
| **Separated Net/Sim Ticks** | Menghemat siklus CPU server dan alokasi *egress bandwidth* transmisi jaringan. | Menjalankan network serialization pada frekuensi 128 Hz untuk 64 pemain membakar CPU untuk enkripsi paket dan menghabiskan bandwidth jaringan. |
| **Zero-Allocation Loop** | Mempertahankan deterministic frame budget; mencegah interupsi heap allocator (`malloc`/`free` lock contention). | Terjadi *micro-stuttering* periodik (latensi spiking dari 7ms melonjak ke 45ms) akibat fragmentasi heap dan *kernel locks*. |
| **Authoritative Input Queue** | Menjamin keadilan kompetitif; validasi cheat berbasis kecepatan, teleportasi, dan eksploitasi fisika. | Rawan terhadap manipulasi memori lokal klien; eksploitasi *speedhack* dan *packet injection*. |

---

### 5. How (Workflow Detail)

Alur siklus tunggal (*single frame lifecycle*) pada Dedicated Game Server Loop skala enterprise:

```
[START TICK N]
  │
  ├── 1. Poll High-Res Clock ──> Hitung frameDeltaTime (t_now - t_last)
  │
  ├── 2. Accumulator Update ───> Clamp frameDeltaTime (Max 100ms)
  │                              accumulator += frameDeltaTime
  │
  ├── 3. Ingest Inbound Packets
  │      ├── Non-blocking drain RingBuffer dari Network Thread
  │      ├── Deserialisasi packet buffer ke Command RingBuffer
  │      └── Validasi Timestamp & Sequence ID (Tolak input basi/invalid)
  │
  ├── 4. While (accumulator >= FIXED_DELTA_TIME)
  │      │
  │      ├── a. Ingestion Phase: Ambil input klien terverifikasi untuk Tick N
  │      ├── b. System Phase: Eksekusi Gameplay Logic (Movement, AI, Combat)
  │      ├── c. Physics Integration: Collision Resolution (Broadphase -> Narrowphase)
  │      ├── d. State Commit: Update authoritative memory buffer
  │      ├── e. accumulator -= FIXED_DELTA_TIME
  │      └── f. current_tick_count++
  │
  ├── 5. Replication Phase Check
  │      └── If (t_now - t_last_network_tick >= NET_DELTA_TIME)
  │             ├── Hitung Delta Compression State (Tick N vs Tick Last Acked)
  │             ├── Serialisasi snapshot ke UDP send-buffer
  │             └── Enqueue ke Network Egress Thread
  │
  ├── 6. Metrics & Telemetry
  │      ├── Tick execution time profiling (sim_time, phys_time, net_time)
  │      └── Update moving average tick-budget consumption
  │
  └── 7. Precision Sleep / Active Spin-lock
         └── Yield ke OS via clock_nanosleep(CLOCK_MONOTONIC) hingga Tick N+1
[END TICK N]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Studio Animasi Layar Lebar Klasik
Bayangkan studio film proyektor 60 FPS:
- **Variable Frame Rate (Buruk):** Animator menggambar lembaran kertas tergantung seberapa cepat tangannya bergerak saat itu. Hasilnya gambar berjalan cepat-lambat tidak stabil.
- **Fixed Timestep Loop (Ideal):** Proyektor film memiliki roda gigi (*gear clockwork*) mekanis yang berputar pasti pada interval 16.66 milidetik. Jika asisten animator terlambat mengantarkan tumpukan gambar baru (input lag), proyektor tidak berhenti berputar atau berputar panik, melainkan terus mengeksekusi frame berikutnya dari kalkulasi deterministik yang telah terverifikasi, menjaga kontinuitas pergerakan objek secara konstan.

#### Diagram Layout Memori (Cache Line Alignment & ECS Data Layout)
Penataan data di memori untuk menghindari *cache miss* pada loop game server:

```
AoS (Array of Structures) - Buruk untuk Cache L1/L2:
[Entity 0: PosX, PosY, PosZ, Health, PlayerName, InventoryPtr] -> Cache Line (64 Bytes) memuat data tak terpakai
[Entity 1: PosX, PosY, PosZ, Health, PlayerName, InventoryPtr] 

SoA (Structure of Arrays) - Optimal untuk High-Rate SIMD/Cache:
Position X Buffer: [P0_x][P1_x][P2_x][P3_x][P4_x][P5_x][P6_x][P7_x] ... Contiguous
Position Y Buffer: [P0_y][P1_y][P2_y][P3_y][P4_y][P5_y][P6_y][P7_y] ... Contiguous
Position Z Buffer: [P0_z][P1_z][P2_z][P3_z][P4_z][P5_z][P6_z][P7_z] ... Contiguous
Velocity Buffer:   [V0_x][V1_x][V2_x][V3_x][V4_x][V5_x][V6_x][V7_x] ... Contiguous
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Akumulator Fixed Timestep Sederhana (C++20)
Kode dasar yang menunjukkan cara menangani akumulasi delta time dan mitigasi spiral of death secara presisi:

```cpp
#include <iostream>
#include <chrono>
#include <thread>
#include <algorithm>

class BasicGameServer {
public:
    static constexpr std::chrono::nanoseconds TICK_INTERVAL{16'666'667}; // ~60 Hz (16.66ms)
    static constexpr std::chrono::nanoseconds MAX_ACCUMULATOR_TIME{100'000'000}; // 100ms Clamp

    void Run() {
        using Clock = std::chrono::steady_clock;
        auto previous_time = Clock::now();
        std::chrono::nanoseconds accumulator{0};
        uint64_t current_tick = 0;

        bool is_running = true;
        while (is_running && current_tick < 180) { // Menjalankan simulasi 3 detik (180 ticks)
            auto current_time = Clock::now();
            auto delta_time = current_time - previous_time;
            previous_time = current_time;

            // Spiral of Death Mitigation: Clamp akumulasi waktu
            if (delta_time > MAX_ACCUMULATOR_TIME) {
                delta_time = MAX_ACCUMULATOR_TIME;
            }

            accumulator += delta_time;

            while (accumulator >= TICK_INTERVAL) {
                SimulateTick(current_tick);
                accumulator -= TICK_INTERVAL;
                current_tick++;
            }

            // Hindari CPU spinning 100% pada logic sederhana
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }

private:
    void SimulateTick(uint64_t tick) {
        // Deterministic state step
        std::cout << "[SIM] Executing Tick: " << tick << std::endl;
    }
};

int main() {
    BasicGameServer server;
    server.Run();
    return 0;
}
```

#### B. Practical Enterprise Example: Multi-Threaded Authoritative Simulation Loop dengan Lock-Free Queue & SoA (C++20)
Implementasi produksi yang menerapkan arsitektur *producer-consumer lock-free*, mitigasi *spiral-of-death*, isolasi memori SoA, dan *precision timing loop*.

```cpp
#include <iostream>
#include <vector>
#include <chrono>
#include <thread>
#include <atomic>
#include <array>
#include <cmath>
#include <span>
#include <cstring>

// Definisi batas kapasitas data game server
constexpr size_t MAX_PLAYERS = 1000;
constexpr uint32_t SERVER_TICK_RATE = 128; // Competitive 128-tick
constexpr std::chrono::nanoseconds TICK_DURATION_NS{1'000'000'000 / SERVER_TICK_RATE}; // ~7.8125 ms
constexpr std::chrono::nanoseconds MAX_CYCLE_BUDGET{TICK_DURATION_NS};
constexpr std::chrono::nanoseconds SPIRAL_CLAMP_THRESHOLD{50'000'000}; // 50ms

#pragma pack(push, 1)
struct ClientInputPayload {
    uint32_t client_id;
    uint64_t client_tick;
    float move_x;
    float move_y;
    uint32_t buttons;
};
#pragma pack(pop)

// Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer untuk input jaringan
template<typename T, size_t Capacity>
class SPSCQueue {
public:
    bool Enqueue(const T& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t next_tail = (current_tail + 1) % Capacity;
        if (next_tail == head_.load(std::memory_order_acquire)) {
            return false; // Queue Penuh
        }
        buffer_[current_tail] = item;
        tail_.store(next_tail, std::memory_order_release);
        return true;
    }

    bool Dequeue(T& item) {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        if (current_head == tail_.load(std::memory_order_acquire)) {
            return false; // Queue Kosong
        }
        item = buffer_[current_head];
        head_.store((current_head + 1) % Capacity, std::memory_order_release);
        return true;
    }

private:
    std::array<T, Capacity> buffer_;
    alignas(64) std::atomic<size_t> head_{0};
    alignas(64) std::atomic<size_t> tail_{0};
};

// State Data-Oriented (Structure of Arrays)
class EntityManager {
public:
    alignas(64) std::array<float, MAX_PLAYERS> pos_x;
    alignas(64) std::array<float, MAX_PLAYERS> pos_y;
    alignas(64) std::array<float, MAX_PLAYERS> vel_x;
    alignas(64) std::array<float, MAX_PLAYERS> vel_y;
    alignas(64) std::array<bool, MAX_PLAYERS> is_active;

    EntityManager() {
        pos_x.fill(0.0f);
        pos_y.fill(0.0f);
        vel_x.fill(0.0f);
        vel_y.fill(0.0f);
        is_active.fill(false);
    }
};

class DedicatedGameServer {
public:
    DedicatedGameServer() : is_running_(false), current_tick_(0) {}

    void Start() {
        is_running_.store(true, std::memory_order_release);
        sim_thread_ = std::thread(&DedicatedGameServer::SimulationLoop, this);
        net_thread_ = std::thread(&DedicatedGameServer::NetworkIngestionLoop, this);
    }

    void Stop() {
        is_running_.store(false, std::memory_order_release);
        if (sim_thread_.joinable()) sim_thread_.join();
        if (net_thread_.joinable()) net_thread_.join();
    }

    SPSCQueue<ClientInputPayload, 16384>& GetInputQueue() { return input_queue_; }

private:
    std::atomic<bool> is_running_;
    uint64_t current_tick_;
    std::thread sim_thread_;
    std::thread net_thread_;
    SPSCQueue<ClientInputPayload, 16384> input_queue_;
    EntityManager entity_mgr_;

    void NetworkIngestionLoop() {
        // Simulasi ingress socket: menerima input dari jaringan dan dorong ke SPSC queue
        uint32_t fake_packet_counter = 0;
        while (is_running_.load(std::memory_order_relaxed)) {
            ClientInputPayload dummy_input{
                .client_id = static_cast<uint32_t>(fake_packet_counter % MAX_PLAYERS),
                .client_tick = current_tick_,
                .move_x = 1.0f,
                .move_y = 0.5f,
                .buttons = 1
            };
            input_queue_.Enqueue(dummy_input);
            fake_packet_counter++;
            // Frekuensi ingress jaringan
            std::this_thread::sleep_for(std::chrono::microseconds(250));
        }
    }

    void SimulationLoop() {
        using HighResClock = std::chrono::steady_clock;
        auto last_time = HighResClock::now();
        std::chrono::nanoseconds accumulator{0};

        std::cout << "[DGS] Authoritative Engine running at " << SERVER_TICK_RATE 
                  << " Hz (" << TICK_DURATION_NS.count() << " ns/tick)\n";

        while (is_running_.load(std::memory_order_acquire)) {
            auto frame_start_time = HighResClock::now();
            auto delta_time = frame_start_time - last_time;
            last_time = frame_start_time;

            // Spiral of Death Safeguard
            if (delta_time > SPIRAL_CLAMP_THRESHOLD) {
                std::cerr << "[WARN] Spike terdeteksi (" << delta_time.count() / 1'000'000 
                          << " ms). Clamping accumulator.\n";
                delta_time = SPIRAL_CLAMP_THRESHOLD;
            }

            accumulator += delta_time;

            // Eksekusi tick diskrit
            while (accumulator >= TICK_DURATION_NS) {
                auto tick_start_time = HighResClock::now();

                // 1. Drain & Parse input dari Network Queue
                ProcessIncomingInputs();

                // 2. State Simulation (Deterministic Movement Update via ECS/SoA)
                UpdatePhysics(0.0078125f); // 1.0f / 128

                // 3. Increment State Tick
                current_tick_++;
                accumulator -= TICK_DURATION_NS;

                auto tick_end_time = HighResClock::now();
                auto tick_duration = tick_end_time - tick_start_time;

                if (tick_duration > MAX_CYCLE_BUDGET) {
                    std::cerr << "[CRITICAL] Tick budget overrun! Process time: "
                              << tick_duration.count() / 1'000'000.0f << " ms\n";
                }
            }

            // Thread Execution Relaxation (Hybrid spin-wait untuk presisi Linux)
            auto time_to_next_tick = TICK_DURATION_NS - accumulator;
            if (time_to_next_tick > std::chrono::milliseconds(1)) {
                std::this_thread::sleep_for(std::chrono::microseconds(500));
            }
        }
    }

    void ProcessIncomingInputs() {
        ClientInputPayload input;
        size_t processed_count = 0;
        constexpr size_t MAX_BATCH = 256;

        while (processed_count < MAX_BATCH && input_queue_.Dequeue(input)) {
            if (input.client_id < MAX_PLAYERS) {
                entity_mgr_.is_active[input.client_id] = true;
                // Anti-Cheat Sanity Check: Movement clamping
                float magnitude = std::sqrt(input.move_x * input.move_x + input.move_y * input.move_y);
                if (magnitude > 1.0f) {
                    input.move_x /= magnitude;
                    input.move_y /= magnitude;
                }
                entity_mgr_.vel_x[input.client_id] = input.move_x * 5.0f; // Speed constant
                entity_mgr_.vel_y[input.client_id] = input.move_y * 5.0f;
            }
            processed_count++;
        }
    }

    void UpdatePhysics(float dt) {
        // Compiler auto-vectorization (SIMD friendly loop)
        #pragma omp simd
        for (size_t i = 0; i < MAX_PLAYERS; ++i) {
            if (entity_mgr_.is_active[i]) {
                entity_mgr_.pos_x[i] += entity_mgr_.vel_x[i] * dt;
                entity_mgr_.pos_y[i] += entity_mgr_.vel_y[i] * dt;
            }
        }
    }
};

int main() {
    DedicatedGameServer server;
    server.Start();
    std::cout << "[SYSTEM] Game loop running. Press Enter to shutdown.\n";
    std::cin.get();
    server.Stop();
    std::cout << "[SYSTEM] Clean shutdown completed.\n";
    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: 128-Tick Competitive Shooter Engine Overrun (Insiden Serupa Insfrastruktur Agones di Valorant / CS:GO)
- **Konteks Masalah:** Sebuah game First-Person Shooter (FPS) kompetitif menargetkan tick rate server pada 128 Hz. Ini berarti total alokasi waktu per loop komputasi (*Tick Budget*) adalah tepat **7.8125 milidetik**. Pada saat pengujian beban skala penuh (64 pemain dalam 1 cluster arena tertutup), terjadi lonjakan frame rate time server (*tick drops*) ke 15-25 milidetik, menyebabkan server menjatuhkan koneksi pemain secara massal.
- **Root Cause Analysis (RCA):**
  1. **OS Preemption:** Proses game server dijalankan pada Linux standar dengan scheduler bawaan (`SCHED_OTHER`). CFS (*Completely Fair Scheduler*) menginterupsi game loop thread untuk mengeksekusi daemon logging dan metrik sistem.
  2. **Cache Thrashing (False Sharing):** Arsitektur penanganan entity menggunakan *Array of Structures* polymorphism (`std::vector<std::shared_ptr<IEntity>>`). Saat 64 pointer didereferensikan setiap 7.81 ms, CPU Core mengalami *L1 Data Cache Miss* rate di atas 38%.
  3. **Blocking I/O:** Snapshot serializer melakukan transmisi paket synchronous via library logging/analytics pada thread loop yang sama.
- **Solusi Arsitektur Produksi:**
  1. Mengalihkan thread simulasi ke scheduler real-time Linux:
     ```bash
     chrt -f -p 99 <PID> # Set SCHED_FIFO dengan prioritas 99
     taskset -cp 2,3 <PID> # Pinning CPU Core sim thread terisolasi
     ```
  2. Restrukturisasi total entity layout dari OOP polymorphic pointer ke Data-Oriented Flat Memory buffers (ECS SoA). Penurunan L1 cache-miss dari 38% menjadi < 1.8%.
  3. Mengalokasikan Ring Buffer terpisah untuk modul Network dan Analytics; thread utama *sim loop* strictly zero I/O and zero allocations.
- **Hasil:** Waktu eksekusi rata-rata turun dari 9.2 ms ke **2.1 ms per tick** (tersisa buffer 73% dari batas 7.8125 ms budget), zero packet drops, jitter < 0.05 ms.

---

### 9. Trade-offs Matrix

| Parameter Desain | Opsi A: High Tick Rate (128 Hz) | Opsi B: Low Tick Rate (30 Hz - 60 Hz) | Implikasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **CPU Budget per Tick** | 7.81 milidetik | 16.66 ms (60Hz) - 33.33 ms (30Hz) | 128 Hz membutuhkan algoritma $\mathcal{O}(N)$ atau $\mathcal{O}(1)$ spatial partitioning, zero-allocation, serta CPU core pinning. |
| **Bandwidth (Egress)** | Sangat Tinggi (~150-250 Kbps/player) | Rendah hingga Moderat (~40-80 Kbps) | Tick rate tinggi membutuhkan *delta compression* ketat dan *interest management* (spatial relevancy) agar biaya cloud tidak melonjak. |
| **Input Responsiveness** | Presisi sub-frame (Latency minimum) | Membutuhkan interpolasi & ekstrapolasi agresif | Pada 30 Hz, client prediction harus bekerja jauh lebih keras, meningkatkan resiko koreksi rollback visual (*teleporting artifacts*). |
| **Server Consolidation** | Rendah (Maks. 1-2 container instance per physical host core) | Tinggi (Hingga 4-8 container instance per core) | Biaya infrastruktur server cloud melonjak drastis pada 128 Hz dibanding 60/30 Hz. |

---

### 10. Common Mistakes & Troubleshooting

1. **Floating Point Non-Determinism Lintas Arsitektur:**
   - *Gejala:* Perhitungan gerak fisika antara server berbasis Linux x86-64 berbeda sedikit dengan klien Apple Silicon (ARM64), memicu koreksi posisi permanen.
   - *Solusi:* Hindari `float` bawaan jika determinisme mutlak dibutuhkan; gunakan library *Fixed-Point Arithmetic* (misal: Q32.32 atau Q16.16) atau pastikan compiler flag `-fno-fast-math`, `-fp-model=precise`, dan gunakan instruksi SSE2/AVX secara konsisten.

2. **Penggunaan Clock Wall-Time (`std::chrono::system_clock`):**
   - *Gejala:* Loop server tiba-tiba melompat ratusan detik atau mengalami freeze saat sistem operasi menyinkronkan waktu dengan NTP server.
   - *Solusi:* Gunakan secara eksklusif `std::chrono::steady_clock` atau `CLOCK_MONOTONIC_RAW` pada lingkungan POSIX.

3. **Memory Allocations dalam Active Simulation Loop:**
   - *Gejala:* Lonjakan latensi acak (*jitter spikes*) yang terjadi setiap beberapa puluh detik.
   - *Penyebab:* Pemanggilan implisit `new`, `malloc`, ekspansi `std::vector::push_back`, atau *smart pointer ref-count updates* yang memicu *heap lock contention*.
   - *Solusi:* Alokasikan seluruh struktur data di awal (*pre-allocate at initialization / object pooling*), gunakan linear arena allocators untuk memori transient.

4. **Dynamic Timestep dalam Loop Server:**
   - *Kesalahan:* Menerapkan `pos += vel * dt` di mana `dt` berasal dari frame rate OS yang berubah-ubah secara bebas pada server authoritatif.
   - *Penyebab:* Fisika menjadi non-deterministik dan mustahil divalidasi silang secara adil terhadap input klien yang berjalan pada frame rate berbeda.
   - *Solusi:* Kunci server tick hanya pada integrasi *fixed timestep*.

---

### 11. Best Practices & Production Checklist

#### Checklist Arsitektur Game Server:
- [ ] **Timing Primitives:** Menggunakan raw monotonic hardware clock tanpa NTP stepping adjustments.
- [ ] **Deterministic Accumulator:** Mengimplementasikan fixed timestep $\Delta t$ dengan dynamic clamp batas atas spiral of death.
- [ ] **Memory Layout:** Mengonversi entitas kritis ke Data-Oriented SoA; validasi alignment 64-byte untuk menghindari *false sharing* antar core.
- [ ] **Thread Concurrency:** Thread loop simulasi tidak memanggil blocking primitives (`std::mutex`, `read`, `write`, `recv`). Semua transfer state via SPSC lock-free queues.
- [ ] **Kernel Optimizations (Linux):**
  - Isolasi Core via parameter boot kernel `isolcpus`.
  - Nonaktifkan CPU Frequency Scaling (`cpupower frequency-set -g performance`).
  - Set parameter socket network buffer: `sysctl -w net.core.rmem_max=16777216`.
- [ ] **Profiling Metric Instrumentation:** Melakukan capture metric durasi microsecond: `sim_time_us`, `ingest_time_us`, `replication_time_us`.

---

### 12. Hands-on Practice

Buatlah direktori praktikum dengan hierarki berikut:
```
hands-on/m02/
├── CMakeLists.txt
├── src/
│   ├── main.cpp
│   ├── EngineLoop.hpp
│   └── EngineLoop.cpp
└── scripts/
    └── test_jitter.py
```

#### Langkah 1: Siapkan `CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(DGS_CoreLoop LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra -pthread")

add_executable(dgs_node src/main.cpp src/EngineLoop.cpp)
```

#### Langkah 2: Kode `src/EngineLoop.hpp`
```cpp
#pragma once
#include <chrono>
#include <atomic>
#include <cstdint>

class EngineLoop {
public:
    explicit EngineLoop(uint32_t target_tick_rate);
    void Start();
    void Stop();

private:
    void Run();
    void Tick(uint64_t tick_number, double dt);

    uint32_t tick_rate_;
    std::chrono::nanoseconds tick_step_ns_;
    std::atomic<bool> running_{false};
    uint64_t total_ticks_executed_{0};
};
```

#### Langkah 3: Kode `src/EngineLoop.cpp`
```cpp
#include "EngineLoop.hpp"
#include <iostream>
#include <thread>

EngineLoop::EngineLoop(uint32_t target_tick_rate) 
    : tick_rate_(target_tick_rate),
      tick_step_ns_(1'000'000'000 / target_tick_rate) {}

void EngineLoop::Start() {
    running_.store(true, std::memory_order_release);
    Run();
}

void EngineLoop::Stop() {
    running_.store(false, std::memory_order_release);
}

void EngineLoop::Tick(uint64_t tick_number, double dt) {
    // Simulasi beban kerja game loop (e.g., entity validation, rigid body physics)
    // Jangan gunakan alokasi heap di sini
    if (tick_number % tick_rate_ == 0) {
        std::cout << "[TICK METRIC] Heartbeat Tick #" << tick_number 
                  << " Delta: " << dt << " s" << std::endl;
    }
}

void EngineLoop::Run() {
    using Clock = std::chrono::steady_clock;
    auto previous_time = Clock::now();
    std::chrono::nanoseconds accumulator{0};
    const std::chrono::nanoseconds max_accumulator_clamp{50'000'000}; // 50 ms

    while (running_.load(std::memory_order_relaxed)) {
        auto current_time = Clock::now();
        auto frame_time = current_time - previous_time;
        previous_time = current_time;

        if (frame_time > max_accumulator_clamp) {
            frame_time = max_accumulator_clamp;
        }

        accumulator += frame_time;

        while (accumulator >= tick_step_ns_) {
            Tick(total_ticks_executed_++, std::chrono::duration<double>(tick_step_ns_).count());
            accumulator -= tick_step_ns_;
        }

        // Precision spin/sleep hybrid
        std::this_thread::sleep_for(std::chrono::microseconds(200));
    }
}
```

#### Langkah 4: Kode Driver `src/main.cpp`
```cpp
#include "EngineLoop.hpp"
#include <csignal>
#include <iostream>
#include <memory>

std::unique_ptr<EngineLoop> g_engine;

void HandleSigint(int) {
    std::cout << "\nTerminating Engine Loop...\n";
    if (g_engine) g_engine->Stop();
}

int main() {
    std::signal(SIGINT, HandleSigint);
    std::cout << "Starting DGS Simulation Node at 60 Hz...\n";
    g_engine = std::make_unique<EngineLoop>(60);
    g_engine->Start();
    return 0;
}
```

#### Langkah 5: Kompilasi dan Eksekusi
```bash
cd hands-on/m02/
mkdir build && cd build
cmake ..
make
./dgs_node
```

---

### 13. Exercise

#### Level Easy
- **Tugas:** Tambahkan telemetri pengukuran variasi delta time antar frame (*tick jitter*) pada `EngineLoop.cpp`.
- **Target:** Hitung standar deviasi waktu tick dari 1000 iterasi pertama dan cetak hasilnya ke terminal saat server dihentikan.

#### Level Medium
- **Tugas:** Implementasikan deteksi *Stall Detection Safeguard*.
- **Target:** Jika satu panggilan fungsi `Tick()` memakan waktu lebih dari $1.5 \times \Delta t_{\text{fixed}}$, catat peringatan log instan beserta durasi *overrun* dalam mikrodetik, lalu turunkan prioritas kalkulasi subsistem non-kritis (misal: AI tick di-skip satu putaran).

#### Level Hard
- **Tugas:** Modifikasi `EntityManager` pada contoh praktis C++20 untuk mengintegrasikan instruksi AVX2/SIMD intrinsics (`immintrin.h`).
- **Target:** Tulis loop update pergerakan vektor 2D/3D menggunakan operasi vectorized float `_mm256_load_ps`, `_mm256_add_ps`, dan `_mm256_store_ps` untuk 4096 entitas dummy. Pastikan memori teralokasi dengan alignment 32-byte (`alignas(32)`).

---

### 14. Challenge

**Skenario Kasus:** Anda adalah Lead Engine Architect pada studio game extraction shooter skala besar. Server mengalami desinkronisasi fatal saat terjadi *Airstrike Event* yang memunculkan 500 ledakan proyektil dan 200 partikel pecahan granat dalam interval 500 milidetik, sementara kapasitas network broadcast jenuh.
- **Batasan Masalah:**
  1. Tick rate server harus bertahan stabil di **60 Hz $\pm 1\%$**.
  2. Alokasi memori heap baru sama sekali dilarang selama simulasi ledakan berjalan (*zero dynamic allocation in tick context*).
  3. Client yang memiliki paket latency tinggi (RTO/packet loss hingga 10%) tidak boleh menyebabkan server memblokir thread eksekusi simulasi pemain lain.
- **Rancang dan Berikan Blueprint Arsitektur:**
  - Struktur data antrean transient entity untuk menangani lonjakan entity ledakan tersebut.
  - Mekanisme *Tick Budget Slicing* (pembagian jatah kuota waktu eksekusi antarsubsistem: Fisika, Jaringan, AI, Gameplay).
  - Skema degradasi terkontrol (*Graceful Degradation*) ketika accumulator terancam overflow melampaui batas toleransi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. **Mengapa game server authoritative wajib menggunakan `std::chrono::steady_clock` dibandingkan `std::chrono::system_clock`?**
   - A. `steady_clock` memiliki representasi string yang lebih mudah dibaca log.
   - B. `system_clock` dapat melompat maju atau mundur jika terjadi sinkronisasi NTP, merusak kalkulasi delta time.
   - C. `system_clock` secara native berjalan pada thread terpisah.
   - D. `steady_clock` mengonsumsi daya baterai CPU lebih rendah.

2. **Apa yang secara definitif memicu fenomena *Spiral of Death* pada game server loop?**
   - A. Koneksi internet pemain terputus secara massal dalam satu waktu.
   - B. Waktu komputasi untuk menyelesaikan satu *tick* melebihi alokasi durasi waktu *tick* itu sendiri, menyebabkan akumulasi sisa waktu membengkak tanpa batas.
   - C. Terjadi kegagalan penulisan snapshot ke persistent database (PostgreSQL/Redis).
   - D. Bandwidth uplink kartu jaringan server (NIC) telah mencapai 100% utilitas.

3. **Berapa budget durasi waktu per tick untuk game server yang beroperasi pada frekuensi 128 Hz?**
   - A. Tepat 16.666 milidetik.
   - B. Tepat 33.333 milidetik.
   - C. Tepat 7.8125 milidetik.
   - D. Tepat 1.000 milidetik.

4. **Struktur data mana yang paling direkomendasikan untuk mentransfer payload paket jaringan dari thread network I/O ke thread simulasi game loop tanpa *lock contention*?**
   - A. `std::vector` yang diproteksi oleh `std::mutex`.
   - B. Single-Producer Single-Consumer (SPSC) Lock-Free Ring Buffer.
   - C. Global Shared Pointer bertipe `std::map<uint32_t, Packet>`.
   - D. Linked List dengan mutex spinlock granular.

5. **Apa tujuan utama penerapan memori bertipe Structure of Arrays (SoA) pada game server?**
   - A. Mempermudah serialisasi data ke format JSON.
   - B. Memaksimalkan prinsip OOP (Object-Oriented Programming) dan polymorphism.
   - C. Memastikan cache-line CPU memuat hanya data yang relevan dengan kalkulasi iteratif, meminimalkan cache miss.
   - D. Menghemat ruang hard disk server.

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. **Pada pola accumulator fixed-timestep, apa fungsi dari operasi *clamping* terhadap variabel `delta_time`?**
   - A. Mencegah eksekusi tick yang terlalu cepat saat server dalam kondisi idle.
   - B. Membatasi akumulasi sisa waktu agar server tidak mencoba mengeksekusi sub-step yang terlalu banyak sekaligus akibat lag spike mendadak.
   - C. Mengurangi resolusi frame rate grafis di sisi klien secara otomatis.
   - D. Memaksa tick time menjadi bernilai nol jika terjadi koneksi lambat.

7. **Mengapa pemisahan antara Simulation Tick (e.g., 60 Hz) dan Network Broadcast Tick (e.g., 20 Hz) sangat umum dilakukan pada arsitektur game skala besar (seperti MMORPG atau Survival Game)?**
   - A. Karena kernel Linux tidak mendukung socket I/O di atas 30 Hz.
   - B. Untuk menjaga kalkulasi fisika tetap akurat dan halus secara internal, sambil menghemat kuota CPU server dan biaya egress bandwidth jaringan.
   - C. Klien game tidak memiliki kemampuan interpolasi visual.
   - D. Menghindari cheat speedhack yang dilakukan dengan memodifikasi packet timing.

8. **Apa bahaya dari fenomena *False Sharing* dalam arsitektur Dedicated Game Server multi-threaded?**
   - A. Dua thread mencoba menulis ke file hard disk yang sama tanpa izin I/O.
   - B. Dua variabel independen yang digunakan oleh core CPU yang berbeda berada dalam baris cache (Cache Line) yang sama, menyebabkan invalidasi cache berulang kali dan degradasi performa drastis.
   - C. Client memalsukan data identitas dirinya (*identity spoofing*) saat transmisi UDP.
   - D. Memory allocator menduplikasi memori pointer yang telah di-free.

9. **Jika server game Anda mengalami stuttering periodik yang terjadi setiap kali pemain baru memasuki arena, penyebab paling probabel dalam konteks arsitektur memori adalah:**
   - A. Server loop mengeksekusi alokasi heap dinamis (`malloc`/`new`) untuk menginisialisasi entitas pemain di tengah tick aktif alih-alih mengambil dari Object Pool.
   - B. Database redis mengalami crash total.
   - C. Algoritma enkripsi AES paket UDP kehabisan bit kunci.
   - D. OS mematikan thread jaringan akibat socket buffer starvation.

10. **Metode sinkronisasi waktu mana yang paling andal untuk menentukan urutan input dari klien ke server authoritative?**
    - A. Membaca waktu `Date.now()` dari OS klien lokal.
    - B. Menggunakan Tick Sequence Number diskrit yang di-increment secara deterministik oleh server dan disematkan pada setiap respons state snapshot.
    - C. Melakukan ping NTP setiap 5 detik ke time.google.com langsung dari klien.
    - D. Mengandalkan atribut waktu timestamp pada header paket TCP.

---

#### Bagian 3: Production Scenario Analysis (Studi Kasus Esai Singkat)

11. **Skenario Kasus A:**
    Game Battle Royale Anda (100 pemain per instance) berjalan di container Docker pada cluster Kubernetes. Saat pertandingan mendekati akhir (lingkaran zona akhir menyusut dan 20 pemain tersisa berada dalam radius 50 meter), metrik CPU usage server turun dari 80% ke 40%, tetapi durasi tick execution melonjak hingga melanggar batas budget tick 16.6 ms. Analisis anomali ini: mengapa pemakaian CPU turun tetapi waktu pemrosesan tick loop justru memburuk?

12. **Skenario Kasus B:**
    Tim QA melaporkan bahwa granat yang dilempar oleh pemain pada perangkat mobile terkadang memantul menembus dinding (*tunneling effect*) di sisi klien, namun di sisi server granat memantul dengan benar. Jelaskan mengapa hal ini terjadi ditinjau dari perbedaan arsitektur loop simulasi antara klien dan server, serta tindakan arsitektural apa yang wajib diambil!

13. **Skenario Kasus C:**
    Anda ditugaskan merancang game server loop yang mampu menampung simulasi fisika 10.000 entitas boids/NPC secara simultan dengan target frekuensi minimal 30 Hz. Namun profil memory profiler menunjukkan bahwa throughput pemrosesan CPU tercekik pada memory bandwidth bottleneck, bukan pada instruksi aritmatika ALU. Susun tiga langkah restrukturisasi arsitektur data cache-friendly untuk mengatasi masalah ini!

---

### Kunci Jawaban & Pembahasan Quiz

#### Kunci Bagian 1: Basic
1. **B** - `steady_clock` menjamin nilai waktu selalu bertambah secara monotonik dan kebal terhadap perubahan manual/NTP waktu sistem operasi.
2. **B** - Spiral of death terjadi murni karena siklus feedback loop di mana beban tick yang berat menambah beban akumulasi waktu untuk tick berikutnya secara tak terbatas.
3. **C** - $\frac{1000\text{ ms}}{128} = 7.8125\text{ ms}$.
4. **B** - SPSC lock-free buffer menjamin throughput tinggi antar satu thread reader dan satu thread writer tanpa interupsi OS mutex contention.
5. **C** - Layout SoA menempatkan data sejenis secara berurutan di memori, memaksimalkan penggunaan bandwidth CPU cache line (64 byte) tanpa membawa data mati.

#### Kunci Bagian 2: Intermediate
6. **B** - Clamping mengorbankan kontinuitas simulasi jangka pendek (menjatuhkan frame lama) demi menyelamatkan server dari crash akibat penumpukan tick tak terkejar.
7. **B** - Replikasi visual gerak dapat dihaluskan klien melalui interpolasi, sehingga server tidak perlu membakar bandwidth dan CPU mengirim snapshot pada frekuensi setara simulasi fisika.
8. **B** - False sharing terjadi pada level hardware L1/L2 cache line (biasanya 64 bytes) ketika dua core berebut hak tulis atas cache line yang sama meskipun variabelnya berbeda.
9. **A** - Alokasi heap di tengah tick memicu page fault dan penguncian tabel kernel heap memori, merusak determinisme waktu komputasi fixed frame.
10. **B** - Server-authoritative sequence ticks merupakan satu-satunya acuan mutlak yang kebal terhadap manipulasi jam lokal perangkat pengguna.

#### Pembahasan Bagian 3: Production Scenario Analysis
11. **Analisis Skenario A:**
    Penurunan utilitas CPU disertai lonjakan durasi tick mengindikasikan terjadinya **Lock Contention** atau **Thread Stalling / Serialization Bottleneck**. Ketika 20 pemain berkumpul di area sempit, sistem deteksi tabrakan (*Narrowphase Collision*) atau sistem spatial lock (misalnya *octree/grid cell lock*) memicu thread-thread worker berebut mutex yang sama (*high lock contention*), menyebabkan core CPU banyak beralih ke kondisi *idle/sleep wait* (sehingga persentase penggunaan CPU turun), sementara wall-clock time eksekusi meledak.

12. **Analisis Skenario B:**
    Penyebab utamanya adalah perbedaan timestep kalkulasi pergerakan: Klien menjalankan simulasi menggunakan *variable delta time* yang mengalami frame drop mendadak sehingga $\Delta t$ besar, memicu objek meloncat melewati batas collider tipis (*discrete tunneling*), atau klien tidak mengimplementasikan *Continuous Collision Detection (CCD)*. Solusi: Klien harus dipaksa menggunakan sub-stepping fixed-physics step untuk objek cepat, dan otoritas trajektori pantulan akhir wajib mutlak diputuskan oleh server snapshot (*server authoritative reconciliation*).

13. **Analisis Skenario C:**
    Tiga langkah mitigasi memory bottleneck:
    1. **Transformasi ke Pure SoA Data Alignment:** Pisahkan komponen `Position`, `Velocity`, dan `Acceleration` ke dalam array contiguous yang terpisah, dialokasikan dengan alignment 32 atau 64 byte untuk memicu SIMD auto-vectorization.
    2. **Spatial Hash Grid Linearization:** Hilangkan struktur data tree dinamis berdasar node pointer (seperti pointer-based KD-Tree/Octree) dan ganti dengan *Linear Uniform Spatial Hash Grid* berbasis integer index contiguous array.
    3. **Cold/Hot Data Separation:** Pisahkan atribut yang sering dibaca per frame (koordinat, vektor kecepatan) dari atribut statis/jarang dibaca (ID entitas, tipe entity, level AI state) agar Cache Line terisi 100% data aktif simulasi.

---

### 16. Summary

- **Fixed Timestep Simulation** adalah pondasi tak ternegosiasikan dari Dedicated Game Server kompetitif modern guna memastikan konsistensi matematika state game.
- Algoritma **Accumulator** memetakan variasi waktu kedatangan frame fisik ke dalam langkah komputasi diskrit yang seragam, di mana teknik **Accumulator Clamping** adalah rem darurat mutlak terhadap bencana **Spiral of Death**.
- Kecepatan komputasi 64 Hz hingga 128 Hz tidak dapat dicapai semata-mata dengan algoritma cepat; arsitektur data harus dirancang adaptif terhadap **Hardware Caching (L1/L2/L3)** melalui paradigma **Data-Oriented Design (SoA / ECS)** dan penghapusan total dynamic memory allocation selama game loop berjalan.
- Pola konkurensi produksi memisahkan secara ketat tanggung jawab pemrosesan I/O jaringan dengan simulasi fisik menggunakan struktur data **Lock-Free SPSC/MPSC Ring Buffers**, menjamin bahwa thread game loop utama dapat berjalan deterministik mendekati batas *bare-metal performance*.