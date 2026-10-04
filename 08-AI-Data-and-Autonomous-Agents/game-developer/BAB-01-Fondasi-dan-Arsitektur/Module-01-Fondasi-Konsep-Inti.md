# Bab 01: Fondasi Arsitektur Engine & Game Programming
## Modul 01: Arsitektur Game Loop & Real-Time Simulation

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis (C4)** perbedaan mekanisme eksekusi antara *variable time step*, *semi-fixed time step*, dan *fixed time step with interpolation* dalam simulasi *real-time*.
*   **Mengimplementasikan (C3)** arsitektur *core game loop* deterministik menggunakan pola *accumulator* untuk mengisolasi logika fisika dari fluktuasi *rendering frame rate*.
*   **Mengevaluasi (C5)** trade-off latensi *input*, *temporal aliasing*, dan konsumsi CPU/GPU pada skenario *spiral of death*.
*   **Mendiagnosis dan Memitigasi (C4)** masalah numerik seperti akumulasi *floating-point error* dan *temporal jitter* pada sistem simulasi berbasis delta waktu ($\Delta t$).

---

### 2. Introduction & Conceptual Hook
Bayangkan sebuah proyektor bioskop dan sebuah jam mekanik kuno. Proyektor bioskop menampilkan citra statis berkecepatan 24 bingkai per detik (FPS) untuk menciptakan ilusi gerak di mata manusia (*visual presentation*). Sebaliknya, jam mekanik bergerak secara presisi berdasarkan osilasi roda gigi penyeimbang (*pendulum/escapement*) yang tak peduli apakah ada manusia yang melihatnya atau tidak (*state update*). 

Dalam pengembangan game, program Anda harus menjadi proyektor sekaligus jam mekanik tersebut secara bersamaan. Perangkat lunak konvensional (seperti aplikasi CRUD web atau desktop berbasis GUI) bersifat *event-driven*: sistem tertidur (*idle*) sampai sistem operasi mengirimkan interupsi (klik mouse, tombol keyboard, atau paket jaringan masuk). 

Game engine beroperasi dengan paradigma yang berkebalikan: **active polling and continuous simulation**. Loop utama berjalan ratusan kali per detik, menghitung dinamika fluida, trajektori proyektil, kecerdasan buatan, dan animasi secara matematis tanpa menunggu instruksi dari luar, sembari terus menggambar kondisi dunia terkini ke layar. Menyatukan simulasi fisika kontinu ke dalam diskritisasi waktu digital tanpa menimbulkan artefak visual atau simulasi yang meledak adalah tantangan paling fundamental seorang arsitek game engine.

---

### 3. Why This Matters
Dalam industri game, kegagalan mengisolasi logika waktu simulasi dari kecepatan rendering adalah penyebab utama bencana rilis:

```
[Simulasi Terikat FPS: Bad Design]
Frame Rate Tinggi (144 FPS) ---> Karakter bergerak secepat kilat / Fisika glitch
Frame Rate Rendah (20 FPS)  ---> Gerakan lambat / Karakter menembus dinding (tunneling)
```

1.  **Kasus Klasik Kerusakan Logika Fisika:** Pada sejumlah game PC lawas yang di-*porting* buruk, kalkulasi fisika dikalikan langsung dengan asumsi siklus monitor 60Hz. Ketika dijalankan di monitor modern 144Hz atau 240Hz, laju karakter meningkat drastis, gravitasi berlipat ganda, dan collision detection gagal bekerja sehingga objek jatuh menembus lantai (efek *tunneling*).
2.  **Desinkronisasi Jaringan (*Multiplayer Desync*):** Pada arsitektur jaringan *deterministic lockstep* (seperti pada game RTS *StarCraft* atau fighting game berbasis *rollback* seperti *Guilty Gear Strive*), setiap mesin pemain harus mensimulasikan frame yang identik secara biner. Perbedaan sekecil $10^{-6}$ unit akibat variasi durasi frame akan memecah konkurensi data simulasi (*state desynchronization*).
3.  **Determinisme:** Mengabaikan kontrol loop waktu menyebabkan bug yang *non-reproducible*: bug hanya terjadi jika GPU mengalami *thermal throttling* di perangkat tertentu.

---

### 4. Theoretical Foundation
Game engine mendiskretisasi aliran waktu kontinu ($t$) menjadi irisan waktu diskrit ($t_0, t_1, \dots, t_n$). Transformasi dinamika dunia game didekati menggunakan kalkulus numerik integrasi diferensial.

Persamaan gerak Newton:
$$\mathbf{v}(t) = \frac{d\mathbf{x}}{dt}, \quad \mathbf{a}(t) = \frac{d\mathbf{v}}{dt} = \frac{\mathbf{F}(t)}{m}$$

Pendekatan integrasi waktu Euler eksplisit (Explicit Euler) untuk langkah waktu $\Delta t$:
$$\mathbf{v}_{n+1} = \mathbf{v}_n + \mathbf{a}_n \cdot \Delta t$$
$$\mathbf{x}_{n+1} = \mathbf{x}_n + \mathbf{v}_n \cdot \Delta t$$

#### Masalah $\Delta t$ Variabel pada Stabilitas Numerik
Jika $\Delta t$ bergantung langsung pada waktu eksekusi rendering satu frame:
$$\Delta t_n = t_{\text{render}, n} - t_{\text{render}, n-1}$$

Kestabilan integrasi numerik dibatasi oleh kondisi stabilitas sistem (seperti kriteria *Courant-Friedrichs-Lewy*). Apabila sebuah frame mengalami lonjakan beban (*frame spike/hitch*) sehingga $\Delta t$ melonjak secara drastis:
$$\Delta t \to \text{besar} \implies \|\mathbf{v}_n \cdot \Delta t\| > \text{ketebalan collider}$$
Hal ini mengakibatkan objek teleportasi melewati batas tumbukan (*tunneling*).

#### Solusi Deterministik: Fixed Timestep dengan Accumulator
Solusi standar industri memisahkan konsumsi waktu simulasi dengan laju sampling visual. Logika fisika/simulasi diupdate dengan langkah waktu konstan yang telah ditentukan ($\Delta t_{\text{fixed}}$, misal $1/60$ detik $\approx 16.66\text{ ms}$), sementara waktu nyata yang berlalu ditampung dalam sebuah variabel *accumulator*.

Sisa waktu yang belum cukup untuk membentuk satu $\Delta t_{\text{fixed}}$ digunakan untuk interpolasi visual:
$$\alpha = \frac{t_{\text{accumulator}}}{\Delta t_{\text{fixed}}}, \quad \alpha \in [0.0, 1.0)$$
$$\mathbf{x}_{\text{render}} = \mathbf{x}_{n} \cdot \alpha + \mathbf{x}_{n-1} \cdot (1.0 - \alpha)$$

---

### 5. Architecture & Mental Model

Struktur eksekusi game loop modern terdiri dari tiga domain terpisah:
1.  **Platform Event Polling & Raw Input:** Pengambilan sinyal interupsi OS tanpa latensi buffer.
2.  **Deterministic Simulation Step (Ticked Fixed Step):** Logika game, AI, physics, animation state updates yang dieksekusi secara deterministik.
3.  **Render State Generation & Presentation:** Ekstrapolasi/Interpolasi transformasi visual yang dikirimkan ke graphics queue (GPU).

```
+-------------------------------------------------------------------------------+
|                             OS Window Message Queue                           |
+-------------------------------------------------------------------------------+
                                      |
                                      v
                        [ 1. Process System Events ]
                        - Window resize, Input polling
                                      |
                                      v
           +---------> [ 2. Calculate Elapsed Frame Time ]
           |            CurrentTime = PlatformHighResClock()
           |            FrameTime   = CurrentTime - LastTime
           |            Accumulator += FrameTime
           |                          |
           |                          v
           |             /-------------------------\
           |            | Accumulator >= FIXED_DT?  | <------+
           |             \-------------------------/         |
           |                    |               |            |
           |             YES    |               | NO         |
           |                    v               |            |
           |       [ 3. Deterministic Update ]  |            |
           |       - Physics Tick               |            |
           |       - Game Logic / Rules         |            |
           |       - Accumulator -= FIXED_DT    |            |
           |                    +---------------+            |
           |                                                 |
           |                                                 |
           |                                v                |
           |                    [ 4. Compute Alpha ] --------+
           |                    Alpha = Accumulator / FIXED_DT
           |                                |
           |                                v
           |                    [ 5. Interpolate Transform ]
           |                    RenderState = Current*(Alpha) + Prev*(1-Alpha)
           |                                |
           |                                v
           |                    [ 6. Graphics Render & Flip ]
           |                    Submit to CommandBuffer -> Present()
           |                                |
           +--------------------------------+
```

---

### 6. ASCII Diagram: Siklus Waktu dan Interpolasi

Diagram berikut mengilustrasikan relasi antara *Variable Display Refresh* (garis atas) dengan *Fixed Physics Simulation Step* (garis bawah):

```
Time Axis (ms) 
0ms        16.6ms      33.3ms      50.0ms      66.6ms      83.3ms     100.0ms
|-----------|-----------|-----------|-----------|-----------|-----------|
[Physics 0] [Physics 1] [Physics 2] [Physics 3] [Physics 4] [Physics 5]   <- Fixed Tick (16.66ms)
     |           |           |           |           |           |
     |           |           |           |           |           |
+----------+-------+---------------+-------------------+-------------+
| Frame A  |Frame B| Frame C       | Frame D           | Frame E     |   <- Variable Render Frames
| (14ms)   |(10ms) | (22ms)        | (28ms)            | (15ms)      |
+----------+-------+---------------+-------------------+-------------+
     ^             ^               ^                   ^
     |             |               |                   |
Alpha=0.84    Alpha=0.44      Alpha=0.76          Alpha=0.44
(Render       (Render         (Render             (Render
 Posisi A)     Posisi B)       Posisi C)           Posisi D)

* Note: Alpha adalah representasi sisa waktu di Accumulator dibagi Fixed Step.
  Posisi visual dirender DI ANTARA Physics Step terakhir dan Physics Step sebelumnya.
```

---

### 7. Core Mechanism
Mekanisme akumulator beroperasi sebagai berikut:

1.  **High-Precision Time Stamping:** Loop membaca *hardware counter* (misalnya via `std::chrono::steady_clock` di C++ atau `QueryPerformanceCounter` di Windows). Penggunaan `wall-clock time` sistem dilarang keras karena dapat terdistorsi sinkronisasi NTP atau penyesuaian jam OS manual.
2.  **Clamping Frame Time (Anti-Spiral of Death):** Jika proses terhenti sejenak (misal: memuat aset besar, breakpoint debugger, atau OS lag spike), `frameTime` bisa bernilai sangat masif (misal $1000\text{ ms}$). Jika ini dibiarkan masuk ke akumulator, loop simulasi akan mencoba mengeksekusi $1000 / 16.66 = 60$ kali update dalam satu frame. Update komputasi ini menyebabkan frame berikutnya makin lambat, memicu siklus macet permanen yang disebut **Spiral of Death**. Solusi: Batasi nilai maksimal waktu frame (umumnya $0.25\text{ s}$).
3.  **Consumption Loop:** Selama nilai waktu pada `accumulator >= FIXED_DELTA_TIME`:
    *   Simpan kondisi spasial saat ini ke buffer `previousState`.
    *   Integrasikan simulasi fisika untuk menghasilkan `currentState`.
    *   Kurangkan `FIXED_DELTA_TIME` dari `accumulator`.
4.  **Blending/Interpolasi Alpha Calculation:** Sisa waktu di akumulator mencerminkan fraksi waktu simulasi yang tersisa:
    $$\alpha = \frac{\text{accumulator}}{\Delta t_{\text{fixed}}}$$
5.  **Render Submission:** Menggunakan nilai $\alpha$ untuk menginterpolasikan translasi objek sebelum data geometri dipasok ke render pipeline.

---

### 8. Code Walkthrough: Simple/Minimal Implementation
Implementasi C++20 dasar ini mengimplementasikan konsep fixed timestep dengan delta accumulator.

```cpp
#include <iostream>
#include <chrono>
#include <thread>

// Aliasing clock presisi tinggi
using Clock = std::chrono::steady_clock;
using Duration = std::chrono::duration<double>;

struct Transform {
    double position{0.0};
    double velocity{10.0}; // 10 unit per detik
};

void UpdatePhysics(Transform& state, double dt) {
    // Integrasi eksplisit deterministic
    state.position += state.velocity * dt;
}

void Render(const Transform& current, const Transform& previous, double alpha) {
    // Interpolasi linier state visual
    double visualPosition = current.position * alpha + previous.position * (1.0 - alpha);
    std::cout << "[Render] Visual Pos: " << visualPosition << " (Alpha: " << alpha << ")\n";
}

int main() {
    constexpr double FIXED_DT = 1.0 / 60.0; // 60 ticks per detik (~0.016667 detik)
    
    Transform currentState;
    Transform previousState;

    auto previousTime = Clock::now();
    double accumulator = 0.0;
    
    int simulatedFrames = 0;

    // Game loop sederhana (dibatasi 5 iterasi untuk demonstrasi)
    while (simulatedFrames < 5) {
        auto currentTime = Clock::now();
        Duration elapsed = currentTime - previousTime;
        previousTime = currentTime;

        double frameTime = elapsed.count();
        
        // Anti-Spiral of Death: Clamp frame time maksimal 250ms
        if (frameTime > 0.25) {
            frameTime = 0.25;
        }

        accumulator += frameTime;

        // Consumer loop: Eksekusi update fisika selama sisa akumulator mencukupi
        while (accumulator >= FIXED_DT) {
            previousState = currentState;
            UpdatePhysics(currentState, FIXED_DT);
            accumulator -= FIXED_DT;
        }

        // Hitung faktor interpolasi
        double alpha = accumulator / FIXED_DT;

        // Render hasil interpolasi
        Render(currentState, previousState, alpha);

        // Simulasi latensi rendering bervariasi (jitter)
        std::this_thread::sleep_for(std::chrono::milliseconds(10 + (simulatedFrames % 3) * 8));
        simulatedFrames++;
    }

    return 0;
}
```

---

### 9. Code Walkthrough: Practical/Production-Grade
Implementasi production-grade memisahkan subsystem engine, thread safety, integrasi input polling, serta instrumentasi metrik.

```cpp
#pragma once
#include <chrono>
#include <cstdint>
#include <algorithm>
#include <functional>
#include <iostream>

class EngineCore {
public:
    struct Configuration {
        double targetSimulationRateHz{60.0};
        double maxAccumulatedLagSeconds{0.2};
    };

    struct PerformanceMetrics {
        uint64_t totalSimulationTicks{0};
        uint64_t totalFramesRendered{0};
        double rawDeltaTime{0.0};
        double currentAlpha{0.0};
    };

    using InputCallback = std::function<void()>;
    using PhysicsCallback = std::function<void(double fixedDt)>;
    using RenderCallback = std::function<void(double alpha)>;

    explicit EngineCore(const Configuration& config)
        : m_config(config),
          m_fixedDeltaTime(1.0 / config.targetSimulationRateHz),
          m_isRunning(false) {}

    void SetInputCallback(InputCallback cb) { m_onInput = std::move(cb); }
    void SetPhysicsCallback(PhysicsCallback cb) { m_onPhysics = std::move(cb); }
    void SetRenderCallback(RenderCallback cb) { m_onRender = std::move(cb); }

    void Stop() noexcept {
        m_isRunning = false;
    }

    void Run() {
        using Clock = std::chrono::steady_clock;
        using DurationSeconds = std::chrono::duration<double>;

        m_isRunning = true;
        auto lastTimePoint = Clock::now();
        double lagAccumulator = 0.0;

        while (m_isRunning) {
            const auto currentTimePoint = Clock::now();
            DurationSeconds elapsedTime = currentTimePoint - lastTimePoint;
            lastTimePoint = currentTimePoint;

            double frameDuration = elapsedTime.count();
            m_metrics.rawDeltaTime = frameDuration;

            // Panic mode: Hindari "Spiral of Death" jika terjadi hitch besar
            if (frameDuration > m_config.maxAccumulatedLagSeconds) {
                // Catat anomali pada trace engine (misal: dropped frame logging)
                frameDuration = m_config.maxAccumulatedLagSeconds;
            }

            lagAccumulator += frameDuration;

            // 1. Polling Hardware & OS Input Events
            if (m_onInput) {
                m_onInput();
            }

            // 2. Fixed Ticked Updates (Deterministic Domain)
            while (lagAccumulator >= m_fixedDeltaTime) {
                if (m_onPhysics) {
                    m_onPhysics(m_fixedDeltaTime);
                }
                
                lagAccumulator -= m_fixedDeltaTime;
                m_metrics.totalSimulationTicks++;
            }

            // 3. Normalized Alpha Calculation untuk Visual Blending
            const double alpha = lagAccumulator / m_fixedDeltaTime;
            m_metrics.currentAlpha = std::clamp(alpha, 0.0, 1.0);

            // 4. Render State Update & Command Buffer Submission
            if (m_onRender) {
                m_onRender(m_metrics.currentAlpha);
            }
            m_metrics.totalFramesRendered++;
        }
    }

    [[nodiscard]] const PerformanceMetrics& GetMetrics() const noexcept {
        return m_metrics;
    }

private:
    Configuration m_config;
    double m_fixedDeltaTime;
    bool m_isRunning;
    PerformanceMetrics m_metrics;

    InputCallback m_onInput;
    PhysicsCallback m_onPhysics;
    RenderCallback m_onRender;
};

// ==========================================
// Contoh Penggunaan Subsystem
// ==========================================
struct RigidBody {
    float x_curr{0.0f};
    float x_prev{0.0f};
    float v{25.0f}; // 25 m/s
};

int main() {
    EngineCore::Configuration cfg{
        .targetSimulationRateHz = 60.0,
        .maxAccumulatedLagSeconds = 0.25
    };

    EngineCore engine(cfg);
    RigidBody playerBody;

    engine.SetInputCallback([]() {
        // Polling events: glfwPollEvents() / SDL_PollEvent()
    });

    engine.SetPhysicsCallback([&playerBody](double dt) {
        playerBody.x_prev = playerBody.x_curr;
        // Eksplisit Integrasi:
        playerBody.x_curr += playerBody.v * static_cast<float>(dt);
    });

    int renderPasses = 0;
    engine.SetRenderCallback([&playerBody, &engine, &renderPasses](double alpha) {
        // Linear interpolation visual state:
        float visualX = playerBody.x_curr * static_cast<float>(alpha) + 
                        playerBody.x_prev * (1.0f - static_cast<float>(alpha));
        
        // Komunikasi visual transform ke GPU (Uniform/Push Constants)
        (void)visualX; 

        renderPasses++;
        if (renderPasses >= 1000) { // Berhenti untuk kebutuhan demonstrasi
            engine.Stop();
        }
    });

    std::cout << "Starting Industrial-grade Deterministic Engine Loop...\n";
    engine.Run();
    std::cout << "Engine stopped cleanly. Simulation Ticks: " 
              << engine.GetMetrics().totalSimulationTicks 
              << ", Render Passes: " << engine.GetMetrics().totalFramesRendered << "\n";

    return 0;
}
```

---

### 10. Edge Cases & Failure Modes

1.  **The Spiral of Death:**
    *   *Kondisi:* Beban komputasi satu langkah fisika melebihi durasi alokasi waktu aslinya ($T_{\text{compute}} > \Delta t_{\text{fixed}}$).
    *   *Manifestasi:* Setiap siklus akumulator mencoba mengejar ketertinggalan, menghasilkan pekerjaan komputasi baru yang lebih lama, menyebabkan FPS turun ke 0 secara permanen.
    *   *Mitigasi:* Melakukan *hard clamp* pada akumulator (`lagAccumulator = std::min(lagAccumulator, maxLag)`). Korbankan waktu riil (*slow-motion*) daripada membuat aplikasi macet total (*freeze*).
2.  **Floating Point Time Evaporation (Precision Breakdown):**
    *   *Kondisi:* Menggunakan tipe `float` (32-bit IEEE 754) tunggal untuk melacak total waktu permainan (`float totalTime += dt`).
    *   *Manifestasi:* Presisi mantissa 24-bit mulai habis setelah beberapa jam. Pada jam ke-9, $dt = 0.01666$ tidak dapat ditambahkan lagi ke `totalTime` karena nilai $dt$ berada di bawah batas resolusi bit terkecil (*ulp - unit in the last place*). Gerakan objek mendadak terhenti atau patah-patah.
    *   *Mitigasi:* Selalu gunakan `double` (64-bit IEEE 754) atau bilangan bulat presisi tinggi (nanodetik dalam `int64_t`) untuk tracking waktu absolut.
3.  **Temporal Aliasing via Extrapolation Divergence:**
    *   *Kondisi:* Menggunakan *ekstrapolasi* alih-alih *interpolasi* untuk menghindari latensi 1 frame.
    *   *Manifestasi:* Ekstrapolasi memprediksi posisi masa depan berdasarkan vektor kecepatan saat ini ($\mathbf{x}_{\text{predict}} = \mathbf{x} + \mathbf{v} \cdot \Delta t$). Jika objek tiba-tiba memantul dari dinding di dalam fixed tick berikutnya, ekstrapolasi akan sempat merender objek menembus dinding sebelum melompat balik (*snapping artifact*).
    *   *Mitigasi:* Prioritaskan interpolasi hermite/linier antara state `n-1` dan `n`. Interpolasi memiliki latensi visual bawaan sebesar $\Delta t$ langkah sim, namun secara visual selalu stabil.

---

### 11. Trade-offs & Engineering Decisions

Dalam merancang loop simulasi, tidak ada satu solusi yang sempurna untuk seluruh skenario. Berikut perbandingannya:

| Parameter | Variable Time Step | Pure Fixed Step (No Interp) | Fixed Step with Accumulator & Interpolation |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Kode** | Sangat Rendah | Rendah | Sedang-Tinggi |
| **Determinisme Simulasi** | Nol (Beda spek PC beda hasil) | Penuh | Penuh |
| **Visual Smoothness** | Rentan stutter jika FPS turun | Stutter/Micro-jitter pada refresh rate tinggi (misal 144Hz) | Halus sempurna (*framerate-independent visual*) |
| **Latensi Input** | Terendah (Render instan) | Sedang | Memiliki trade-off rendering latensi 1 tick simulasi |
| **Beban Memori** | Rendah (Hanya 1 state) | Rendah (Hanya 1 state) | Butuh buffer untuk *Previous* dan *Current* transform |
| **Penggunaan Ideal** | Aplikasi UI, prototipe kasar | Server-side headless simulation | AAA Game Engine, High-speed Physics, Platformer |

---

### 12. Anti-patterns & Code Smells

#### Anti-pattern: The Naive Variable $\Delta t$ Update
Pengembang pemula kerap menyuntikkan delta waktu langsung ke translasi objek di sembarang tempat update logika game.

```cpp
// BURUK: Anti-pattern Variable Delta Time dalam Game Logic
void Actor::Tick(float dt) {
    // Bahaya 1: Jika dt besar (lag spike), collider menembus dinding
    // Bahaya 2: Algoritma integrasi tak tentu memicu desync
    m_position += m_velocity * dt;
    
    // Logika gameplay terdistorsi: Timer berbasis tick acak
    m_abilityCooldown -= dt; 
}
```

```cpp
// BAIK: Pemisahan state diskrit deterministik
void Actor::SimulateFixed(double fixedDt) {
    // Nilai fixedDt dijamin konstan (misal: tepat 0.01666666666)
    m_position += m_velocity * fixedDt;
    m_abilityCooldown -= fixedDt;
}

void Actor::ComputeInterpolatedRenderState(double alpha) {
    // Menghitung transformasi visual khusus untuk GPU presentation
    m_renderTransform = Interpolate(m_previousTransform, m_currentTransform, alpha);
}
```

---

### 13. Performance & Memory Implications
1.  **Dukungan Cache Hierarchy (L1/L2 Data Locality):**
    Menyimpan data `previousState` dan `currentState` di dalam arsitektur berbasis *Array-of-Structures* (AoS) yang terfragmentasi di heap memory (seperti `std::vector<Actor*>`) akan memicu banyak *cache miss* saat fase interpolasi rendering.
    *Optimasi Engine:* Susun transformasi spasial menggunakan format *Structure-of-Arrays* (SoA) atau flat continuous buffers.
    ```cpp
    struct TransformBuffer {
        std::vector<glm::vec3> prevPositions;
        std::vector<glm::vec3> currPositions;
        std::vector<glm::quat> prevRotations;
        std::vector<glm::quat> currRotations;
    };
    ```
2.  **Overhead Thread Synchronization:**
    Bila arsitektur loop didorong ke pola *Multithreaded Game Loop* (Thread Input, Thread Worker Fisika, Thread Rendering), pengiriman snapshot interpolasi membutuhkan struktur data *Double Buffering* atau *Triple Buffering* yang bebas *lock-contention* (menggunakan *Atomic Ring Buffers*).

---

### 14. Security & Robustness Concerns
1.  **Speed Hacking via Virtual Clock Manipulation:**
    *   *Vektor Serangan:* Aplikasi eksternal (seperti *Cheat Engine*) menginjeksi proses sistem untuk mengubah rasio clock hook kernel OS (misal: mempercepat return value dari API `QueryPerformanceCounter` atau `GetTickCount`).
    *   *Dampak:* Karakter bergerak lebih cepat dari pemain lain dalam game client-authoritative.
    *   *Mitigasi:* Server engine **tidak boleh mempercayai** $\Delta t$ atau koordinat posisi yang dikirim oleh client. Server harus menjalankan game loop secara independen (*Server-Authoritative*) dan hanya menerima paket input deterministik dari pemain (keystroke/command), lalu memvalidasi apakah urutan gerakan logis secara fisik.
2.  **Denial-of-Service (DoS) via Frame Spikes:**
    *   *Vektor Serangan:* Pemain sengaja memicu ribuan collider secara simultan (misal melempar ribuan proyektil) untuk membuat game loop masuk ke kondisi *Spiral of Death*, menyebabkan server hang dan mengorbankan integritas pertandingan multiplayer.

---

### 15. Testing & Verification Strategies
Karena game loop bersifat continuous dan real-time, pengujian unit reguler tidak cukup. Diperlukan simulasi *Virtual Time Harness*:

```cpp
#include <cassert>
#include <cmath>

void TestDeterministicPhysicsSimulation() {
    constexpr double FIXED_DT = 1.0 / 60.0;
    double currentPos = 0.0;
    double velocity = 100.0; // 100 m/s

    // Jalankan 600 ticks diskrit (persis 10 detik virtual)
    for(int tick = 0; tick < 600; ++tick) {
        currentPos += velocity * FIXED_DT;
    }

    // Prediksi analitis tepat: 1000.0 meter
    double expected = 1000.0;
    double error = std::abs(currentPos - expected);
    
    // Verifikasi batas toleransi numerik floating point
    assert(error < 1e-4 && "Kegagalan determinisme: Integrasi drift melampaui toleransi!");
}
```

*Strategi Pengujian Engine:*
*   **Time Step Invariance Test:** Menjalankan skenario game yang sama pada framerate tiruan 30 FPS, 60 FPS, dan 144 FPS. Pastikan status biner hash dari world state pada detik virtual ke-60 menghasilkan nilai byte yang identik (Determinism Verification).

---

### 16. Debugging & Observability
Metrik kritis yang wajib diekspos oleh game loop ke overlay debug (HUD/Telemetry):

```
+------------------ ENGINE TELEMETRY -------------------+
| Engine FPS: 142.4 (Presentation Time: 7.02 ms)        |
| Raw DeltaTime: 6.98 ms | Accumulator Residual: 2.1 ms |
| Fixed Tick Target: 60 Hz (16.66 ms)                   |
| Physics Steps Executed Last Frame: 0 (Visual Lerp)    |
| Worst Frame Spike (Last 5s): 34.2 ms -> Clamp Trigger |
| State Buffer Allocations: 12.4 MB (Contiguous Flat)   |
+-------------------------------------------------------+
```

*   **Deteksi Micro-stuttering:** Hitung varians dari waktu penyelesaian frame ($\sigma^2_{\Delta t}$). Varians yang tinggi meski FPS rata-rata tercatat 60 menunjukkan engine sering melewatkan interval *VSync presentation*, mengakibatkan drop-frame tersembunyi yang mengganggu kenyamanan bermain.

---

### 17. Real-world Case Study
**Insiden Masalah Refresh Rate pada Peluncuran Skyrim (Creation Engine):**
Ketika *The Elder Scrolls V: Skyrim* dirilis di platform PC, loop internal Havok Physics terikat erat dengan laju frame monitor yang diasumsikan selalu berada pada standar 60Hz.

*   *Insiden:* Ketika para pemain menggunakan monitor modern 120Hz dan 144Hz, waktu integrasi internal memproses nilai $\Delta t$ dengan kecepatan dua kali lipat lebih cepat.
*   *Dampak:* Objek dekorasi di dalam ruangan (seperti piring, cangkir, keranjang) terlontar ke segala arah dengan kecepatan supersonik akibat gaya penolakan tumpang tindih collision yang berlipat ganda. Kuda dan kereta gerobak melayang ke langit saat adegan pembuka (*intro sequence*), merusak gameplay secara permanen (*soft-lock*).
*   *Penyelesaian Masalah:* Komunitas modder terpaksa membuat wrapper DLL eksternal untuk membatasi eksekusi engine secara paksa ke 60 FPS sebelum Bethesda akhirnya merevisi struktur loop internal engine pada rilis engine generasi berikutnya (*Special Edition*).

---

### 18. Hands-on Challenge
**Judul Tantangan:** Implementasi "Rewindable Time Engine" Berbasis Accumulator Loop.

**Deskripsi Masalah:**
Rancang program konsol/window C++ sederhana yang mensimulasikan partikel dengan gravitasi dan sistem pantulan elastis dari tanah.

**Spesifikasi Kebutuhan:**
1.  Gunakan Fixed Timestep loop ($60\text{ Hz}$).
2.  Implementasikan struktur data *Ring Buffer* (kapasitas 300 frame = 5 detik terakhir) yang merekam seluruh snapshot posisi dan kecepatan partikel dari setiap tick simulasi fisika.
3.  Ketika tombol 'R' ditekan pada keyboard, engine beralih ke mode **Rewind**: alih-alih menambahkan waktu ke akumulator, loop membaca mundur snapshot dari ring buffer untuk merender kembali visual partikel mundur secara mulus menggunakan interpolasi.
4.  Cegah terjadinya *Spiral of Death* jika terminal OS dibekukan selama 2 detik (misal: saat teks konsol diseleksi dengan kursor mouse).

---

### 19. Self-Reflection & Conceptual Check
Jawab pertanyaan berikut untuk mengukur penguasaan materi arsitektur ini:

1.  Mengapa perhitungan interpolasi render `(Current * Alpha + Previous * (1 - Alpha))` menyebabkan latensi visual sebesar 1 tick simulasi, dan mengapa latensi ini dapat diterima oleh mata manusia?
2.  Jelaskan skenario matematis di mana integrasi numerik *Semi-Implicit Euler* (Verlet) lebih unggul daripada *Explicit Euler* di dalam eksekusi `FixedUpdate`!
3.  Jika Anda merancang game VR (*Virtual Reality*) yang menuntut latensi visual kurang dari $20\text{ ms}$ pada 90Hz, di mana posisi eksekusi thread input polling harus diletakkan dalam kaitannya dengan game loop?
4.  Apa bahayanya memanggil fungsi rendering GPU secara langsung di dalam perulangan `while (accumulator >= FIXED_DT)`?
5.  Bagaimana arsitektur *Headless Game Server* memanfaatkan loop deterministik untuk menghemat utilisasi komputasi CPU cloud?

---

### 20. Further Reading & References
*   **Buku:** Gregory, Jason. *Game Engine Architecture, 3rd Edition*. CRC Press, 2018. (Bab 7: The Game Loop and Real-Time Simulation).
*   **Artikel Klasik:** Fix Your Timestep! by Glenn Fiedler (Gaffer on Games): `https://gafferongames.com/post/fix_your_timestep/`
*   **Makalah Akademik:** Nystrom, Robert. *Game Programming Patterns*. Genever Benning, 2014. (Chapter: Game Loop).
*   **Dokumentasi Engine:** Unreal Engine Documentation: *Tick Functions and Actor Lifecycle Execution Order*.
*   **Standar Industri:** IEEE 754-2019: *Standard for Floating-Point Arithmetic* (Pahami implikasi presisi temporal).