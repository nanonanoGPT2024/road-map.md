# BAB 08: Keamanan Server, Validasi Otoritatif & Anti-Cheat
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *authoritative game server* berbasis deterministik deterministik bertingkat (*client-side prediction*, *server reconciliation*, dan *lag compensation*) yang kebal terhadap manipulasi memori lokal (*speedhack*, *teleportation*, *noclip*, dan *aimbot*).
- Membangun *continuous validation pipeline* untuk fisika pergerakan dan kalkulasi tembakan (*hitscan/projectile*) pada server tick rate tinggi (64Hz–128Hz) dengan alokasi memori nol (*zero dynamic allocation during tick*).
- Mengintegrasikan sistem deteksi bot dan agen otonom berbasis analisis heuristik telemetri (*jerk, entropy, reaction-time distributions*) dan inferensi *real-time machine learning* (ONNX Runtime C++ engine) langsung pada *pipeline* pemrosesan paket jaringan.
- Mengamankan komunikasi UDP kustom dengan skema *sliding-window replay protection*, *session token rolling*, dan enkripsi simetris terakselerasi perangkat keras (AES-128-GCM via CPU AES-NI).

---

### 2. Prerequisite
- **Pemrograman Sistem:** Mahir dalam C++20 atau Go (tingkat mahir: memory layout, pointer arithmetic, zero-allocation buffers, SIMD intrinsic basics).
- **Protokol Jaringan:** Pemahaman mendalam terkait OSI Layer 4 (UDP socket programming, packet serialization, MTU fragmentation, RTT estimation via Jacobson/Karels algorithm).
- **Matematika Terapan:** Aljabar linear (vektor 3D, quaternion, transformasi matriks, ray-box/ray-capsule intersection).
- **Sistem Operasi:** Linux low-latency tuning (`epoll`/`io_uring`, CPU pinning via `taskset`, thread priority scheduling `SCHED_FIFO`, core isolation).

---

### 3. Concept & Internal Architecture
Arsitektur keamanan *server-side* pada game berkecepatan tinggi (*fast-paced multiplayer*) bersandar pada prinsip mutlak: **Server adalah Sumber Kebenaran Tunggal (*Server Authoritative*)**. Klien hanyalah terminal perender (*dumb display*) yang menjalankan simulasi prediktif lokal demi kenyamanan visual pemain.

```
+----------------------------------------------------------------------------------------------------+
|                                      AUTHORITATIVE SERVER ARCHITECTURE                             |
|                                                                                                    |
|  [ Inbound UDP ]                                                                                   |
|        │                                                                                           |
|        ▼                                                                                           |
|  +───────────────────────────────────────────────────────────+                                     |
|  | Network Layer (io_uring / eBPF XDP)                       |                                     |
|  | - Packet Decryption (AES-GCM-NI)                          |                                     |
|  | - Replay Attack Filter (Sliding Bitmask 64-frame)         |                                     |
|  +───────────────────────────────────────────────────────────+                                     |
|        │                                                                                           |
|        ▼                                                                                           |
|  +───────────────────────────────────────────────────────────+                                     |
|  | Tick Alignment & Jitter Buffer                            |                                     |
|  | - Deserialization into Flat Structs (Zero-Copy)           |                                     |
|  | - Command Queue Insertion (Target Server Tick N)          |                                     |
|  +───────────────────────────────────────────────────────────+                                     |
|        │                                                                                           |
|        ▼                                                                                           |
|  +───────────────────────────────────────────────────────────+                                     |
|  | Game Simulation Core (64Hz / 128Hz Tick Loop)             |                                     |
|  |  ┌─────────────────────────────────────────────────────┐  |                                     |
|  |  | Authoritative Movement Validation                   |  |                                     |
|  |  | - Kinematic Verification (Max Vel, Accel, Gravity)  |  |                                     |
|  |  | - Spatial Octree / BVH Collision Query              |  |                                     |
|  |  └─────────────────────────────────────────────────────┘  |                                     |
|  |  ┌─────────────────────────────────────────────────────┐  |                                     |
|  |  | Combat & Hit Registration (Lag Compensator)         |  |                                     |
|  |  | - Ring Buffer History Rewind (RTT + Interpolation)  |  |                                     |
|  |  | - Swept Capsule / Raycast Occlusion Check           |  |                                     |
|  |  └─────────────────────────────────────────────────────┘  |                                     |
|  +───────────────────────────────────────────────────────────+                                     |
|        │                                                                                           |
|        ├── Telemetry Event (Lock-free RingBuffer) ──────────────┐                                  |
|        ▼                                                        ▼                                  |
|  +────────────────────────────────────+   +─────────────────────────────────────────────────────+  |
|  | Replication Pipeline               |   | Real-Time Anti-Cheat In-Process Pipeline            |  |
|  | - Delta Compression                |   | - Input Entropy Analysis (Shannon Entropy)          |  |
|  | - Potentially Visible Set (PVS)    |   | - Kinematic Outlier Filter (Chi-Square Test)        |  |
|  | - UDP Outbound Packaging           |   | - ONNX Runtime In-Memory Inference (Bot/Aim Model) |  |
|  +────────────────────────────────────+   +─────────────────────────────────────────────────────+  |
+----------------------------------------------------------------------------------------------------+
```

#### Komponen Kunci Internal:
1. **Network Demux & Cryptographic Replay Guard:** Menolak paket usang atau duplikasi berbasis nomor urut (*packet sequence number*) sebelum parsing payload game logic.
2. **Deterministic Kinematic Evaluator:** Server tidak memproses posisi mutlak $(X, Y, Z)$ yang dikirim klien, melainkan mengevaluasi aksi input klien $(W, A, S, D, \vec{v}_{yaw}, \vec{v}_{pitch}, \Delta t)$ dan menghitung posisi baru server-side. Jika posisi klien melenceng di luar toleransi epsilon ($\epsilon$), server mengeluarkan koreksi (*hard/soft snap reconciliation*).
3. **Lag Compensator Engine:** Menyimpan *world snapshots* dalam *ring buffer* (misal: 1000ms terakhir). Ketika klien menyatakan menembak pada tick $T - k$, server memutar kembali (*rewind*) *hitbox* target ke tick $T - k$, melakukan raycasting, dan mengembalikan kondisi dunia ke tick $T$ tanpa menghentikan simulasi global.
4. **Behavioral Ingestion Pipeline:** Menangkap koordinat pandangan (*Euler angles / Quaternion*), interval waktu penekanan tombol (*keystroke duration*), dan *mouse acceleration* untuk mendeteksi bantuan bidikan instan (*Aimbot*) atau simulasi input berbasis agen otomatis.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Manfaatnya (What) |
| :--- | :--- | :--- |
| **Authoritative Movement Validation** | Klien dapat memanipulasi memori lokal (misal: Cheat Engine) untuk mengubah nilai koordinat $X, Y, Z$, kecepatan, atau gravitasi. | Server memproses input mentah dan menghitung posisi berdasarkan hukum kinematika dan collision map statis server. |
| **Lag-Compensated Rewind** | Latensi jaringan (10ms - 200ms) menyebabkan klien melihat posisi target di masa lalu. Tanpa lag compensation, pemain harus menembak mendahului target secara manual (*leading shot*). | Server merekonstruksi posisi target persis seperti yang dilihat klien pada saat tembakan dieksekusi, memastikan keadilan kompetitif (*favor the shooter*) tanpa kehilangan otoritas. |
| **Cryptographic Replay Buffer** | Penyerang dapat menyadap paket *action* (misal: menembakkan senjata atau aktivasi skill) dan mengirimkannya berulang-ulang (*replay attack*). | Menolak paket yang berada di luar jendela *sliding window* atau yang hash kriptografisnya telah terekam. |
| **Real-Time Statistical Inference** | Bot pintar (berbasis deep learning atau pixel-bot) dapat meniru input perangkat manusia tanpa menyuntikkan kode ke memori game. | Menganalisis kurva pergerakan, micro-adjustment, dan distribusi varians waktu input secara independen dari deteksi signature klien. |

---

### 5. How (Workflow Detail)

#### Siklus Validasi Pergerakan (Movement Tick Validation Loop):
1. **Penerimaan Paket:** Driver jaringan mengekstrak paket UDP, memverifikasi HMAC, memeriksa nomor urut terhadap sliding bitmask.
2. **Ekstraksi Input:** Input diekstrak ke dalam `PlayerCmd` yang memuat `TickNumber`, `MovementVector`, `ViewAngles`, `ActionMask`.
3. **Validasi Delta-Time ($\Delta t$):** Server memastikan bahwa akumulasi waktu input tidak melebihi waktu fisik riil server (mencegah *tick-injection* / *speedhack*).
4. **Prediksi Kinematika Server:**
   $$\vec{v}_{target} = \text{CalculateTargetVelocity}(\text{CurrentVelocity}, \text{Cmd.Direction}, \text{Friction})$$
   $$\vec{p}_{new} = \vec{p}_{current} + \vec{v}_{target} \cdot \Delta t$$
5. **Collision Detection via Spatial Octree/BVH:** Server melempar *swept capsule* dari $\vec{p}_{current}$ ke $\vec{p}_{new}$ terhadap geometri level statis.
6. **Error Verification:** 
   $$\text{Error} = \|\vec{p}_{client\_reported} - \vec{p}_{new}\|$$
   Jika $\text{Error} > \epsilon$ (ambang batas toleransi jitter/desinkronisasi), tandai status *Desync Detected*, timpa posisi klien dengan $\vec{p}_{new}$, dan kirim paket rekonsiliasi (*reconciliation packet*).

#### Siklus Lag Compensation (Combat Raycasting):
1. Server menerima paket tembakan: `ShootCmd { Timestamp: T_client, Ray: Origin, Direction }`.
2. Hitung latency: 
   $$\text{RewindTick} = \text{CurrentTick} - \text{Clamp}\left(\frac{\text{RTT}}{2} + \text{InterpDelay}, 0, \text{MaxHistory}\right)$$
3. **World Rollback:** Pindahkan semua *hitbox* pemain lawan ke status spasial mereka pada `RewindTick` menggunakan interpolasi linier/hermite antar-snapshot di ring buffer.
4. **Raycast Intersect:** Evaluasi tembakan terhadap *oriented bounding box (OBB)* kepala, dada, dan kaki target.
5. **Occlusion Check:** Pastikan tidak ada dinding level statis yang memblokir antara penembak dan target pada tick tersebut.
6. **World Restore:** Kembalikan seluruh *hitbox* ke status spasial `CurrentTick`.
7. **Damage Application:** Terapkan pengurangan HP pada target dalam data otoritatif server jika valid.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Wasit Catur Buta vs. Wasit Catur Otoritatif
- **Klien Non-Otoritatif:** Pemain memberi tahu wasit, *"Saya memindahkan kuda saya langsung melompati 5 petak dan memakan raja lawan."* Wasit menerimanya begitu saja karena mempercayai mata pemain.
- **Klien Otoritatif:** Pemain memberi tahu wasit, *"Saya ingin menggerakkan bidak dari koordinat B1 ke C3."* Wasit memiliki papan catur resmi di mejanya, memeriksa aturan validitas langkah kuda, mengonfirmasi tidak ada rintangan terlarang, lalu menggerakkan bidak di papan resmi dan memberitahu kedua belah pihak posisi baru bidak tersebut.

#### Diagram Ring Buffer Lag Compensation:

```
Snapshot Ring Buffer (Capacity: 128 Ticks @ 64Hz = 2.0s History)
Index:    [0]   [1]   ...   [60]  [61]  [62]  ...  [126] [127]
Tick:     100   101         160   161   162        226   227 (Current Server Tick)
                            ▲           ▲
                            │           │
                     Target Rewind  Interpolate
                     (RTT = 100ms)  (Tick 160 -> 161)

Step 1: Save current poses of all entities at Tick 227 (Zero-Allocation Heap Scratchpad)
Step 2: Linear interpolate entity positions at Tick 160.4:
        Pos(160.4) = Pos(160) + 0.4 * (Pos(161) - Pos(160))
Step 3: Update spatial partition (BVH) with interpolated poses
Step 4: Execute Raycast(Origin, Direction)
Step 5: Restore all entities back to Tick 227 poses
```

---

### 7. Simple Example & Practical Example

#### Simple Example (C++20): Sliding Window Anti-Replay Protection
Mencegah penyerang menyuntikkan kembali (*replaying*) paket jaringan yang sah.

```cpp
#include <cstdint>
#include <iostream>

class ReplayProtectionWindow {
public:
    static constexpr uint64_t WINDOW_SIZE = 64;

    bool ValidateAndAdvance(uint64_t sequence) {
        if (sequence == 0) return false;

        // Paket baru lebih maju dari head
        if (sequence > max_seq_) {
            uint64_t diff = sequence - max_seq_;
            if (diff >= WINDOW_SIZE) {
                bitmap_ = 1; // Seluruh window lama gugur
            } else {
                bitmap_ <<= diff;
                bitmap_ |= 1;
            }
            max_seq_ = sequence;
            return true;
        }

        // Paket berada di masa lampau (out-of-order)
        uint64_t diff = max_seq_ - sequence;
        if (diff >= WINDOW_SIZE) {
            return false; // Terlalu usang, drop
        }

        // Periksa apakah paket sudah pernah diterima
        uint64_t bit = (1ULL << diff);
        if (bitmap_ & bit) {
            return false; // Replay attack terdeteksi!
        }

        // Tandai sequence telah diterima
        bitmap_ |= bit;
        return true;
    }

private:
    uint64_t max_seq_ = 0;
    uint64_t bitmap_ = 0; // Bit 0 adalah max_seq_, Bit 1 adalah max_seq_-1, dst.
};

int main() {
    ReplayProtectionWindow filter;
    std::cout << std::boolalpha;
    std::cout << filter.ValidateAndAdvance(1) << "\n";  // True
    std::cout << filter.ValidateAndAdvance(2) << "\n";  // True
    std::cout << filter.ValidateAndAdvance(1) << "\n";  // False (Replay detected!)
    std::cout << filter.ValidateAndAdvance(65) << "\n"; // True
    std::cout << filter.ValidateAndAdvance(2) << "\n";  // False (Dropped, out of 64-bit window)
    return 0;
}
```

#### Practical Example (C++20): Zero-Allocation Authoritative Movement & Kinematic Validator
Komponen inti *production-grade* yang memverifikasi input gerakan, memeriksa akselerasi maksimum, kecepatan terminal, dan interpenetrasi level statis.

```cpp
#include <cmath>
#include <array>
#include <vector>
#include <iostream>
#include <algorithm>

struct Vector3 {
    float x{0.0f}, y{0.0f}, z{0.0f};

    constexpr Vector3 operator+(const Vector3& o) const noexcept { return {x + o.x, y + o.y, z + o.z}; }
    constexpr Vector3 operator-(const Vector3& o) const noexcept { return {x - o.x, y - o.y, z - o.z}; }
    constexpr Vector3 operator*(float s) const noexcept { return {x * s, y * s, z * s}; }
    [[nodiscard]] constexpr float SqrMagnitude() const noexcept { return x * x + y * y + z * z; }
    [[nodiscard]] float Magnitude() const noexcept { return std::sqrt(SqrMagnitude()); }
    
    [[nodiscard]] Vector3 Normalized() const noexcept {
        float m = Magnitude();
        return m > 0.00001f ? Vector3{x / m, y / m, z / m} : Vector3{0, 0, 0};
    }
};

struct UserCommand {
    uint32_t tick_number;
    Vector3 wish_dir;     // Normalisasi input horizontal (-1 to 1)
    float delta_time;     // Waktu frame klien (dikontrol oleh tick server)
    Vector3 claimed_pos;  // Posisi yang dilaporkan klien untuk verifikasi
};

struct PlayerPhysicsState {
    Vector3 position;
    Vector3 velocity;
    bool is_grounded;
};

class AuthoritativeMovementSystem {
public:
    static constexpr float MAX_ACCEL = 50.0f;           // m/s^2
    static constexpr float MAX_SPEED = 12.0f;           // m/s
    static constexpr float GRAVITY = -9.81f;            // m/s^2
    static constexpr float EPSILON_TOLERANCE_SQ = 0.25f;// 0.5 meter toleransi deviasi kuadrat (0.5^2)

    struct ValidationResult {
        bool violation_detected;
        Vector3 authoritative_position;
        std::string reason;
    };

    // Eksekusi tick simulasi dan validasi klaim pergerakan klien
    ValidationResult ProcessAndValidateCommand(
        PlayerPhysicsState& current_state, 
        const UserCommand& cmd
    ) noexcept {
        // 1. Validasi Keabsahan Delta Time untuk mencegah manipulasi clock
        if (cmd.delta_time <= 0.0f || cmd.delta_time > 0.05f) {
            return {true, current_state.position, "EXCESSIVE_OR_INVALID_DELTATIME"};
        }

        // 2. Simulasi Kinematika Internal Server
        Vector3 wish_dir_clamped = cmd.wish_dir;
        if (wish_dir_clamped.SqrMagnitude() > 1.0f) {
            wish_dir_clamped = wish_dir_clamped.Normalized();
        }

        // Terapkan akselerasi horizontal
        Vector3 accel_vector = wish_dir_clamped * MAX_ACCEL;
        current_state.velocity.x += accel_vector.x * cmd.delta_time;
        current_state.velocity.z += accel_vector.z * cmd.delta_time;

        // Clamp kecepatan horizontal ke batas fisik dunia game
        float horiz_speed_sq = current_state.velocity.x * current_state.velocity.x + 
                              current_state.velocity.z * current_state.velocity.z;
        if (horiz_speed_sq > (MAX_SPEED * MAX_SPEED)) {
            float scale = MAX_SPEED / std::sqrt(horiz_speed_sq);
            current_state.velocity.x *= scale;
            current_state.velocity.z *= scale;
        }

        // Gravitasi server-side
        if (!current_state.is_grounded) {
            current_state.velocity.y += GRAVITY * cmd.delta_time;
        } else {
            current_state.velocity.y = 0.0f; // Reset vertikal jika di tanah
        }

        // Hitung posisi otoritatif baru
        Vector3 simulated_pos = current_state.position + (current_state.velocity * cmd.delta_time);

        // Simulasi dasar kontak lantai (Ground plane @ y = 0.0f)
        if (simulated_pos.y <= 0.0f) {
            simulated_pos.y = 0.0f;
            current_state.is_grounded = true;
            current_state.velocity.y = 0.0f;
        }

        // 3. Verifikasi Posisi Klien vs Otoritatif Server
        float deviation_sq = (cmd.claimed_pos - simulated_pos).SqrMagnitude();
        bool violation = false;
        std::string violation_reason = "NONE";

        if (deviation_sq > EPSILON_TOLERANCE_SQ) {
            violation = true;
            violation_reason = "POSITION_DESYNC_OR_TELEPORT";
            // Koreksi state langsung ke otoritatif tanpa toleransi lebih lanjut
            current_state.position = simulated_pos;
        } else {
            // Posisi dalam batas aman desinkronisasi rendering, gunakan kalkulasi server
            current_state.position = simulated_pos;
        }

        return {violation, current_state.position, violation_reason};
    }
};

int main() {
    AuthoritativeMovementSystem engine;
    PlayerPhysicsState player_state{.position = {0, 0, 0}, .velocity = {0, 0, 0}, .is_grounded = true};

    // Skenario 1: Input pergerakan normal
    UserCommand normal_cmd{
        .tick_number = 101,
        .wish_dir = {1.0f, 0.0f, 0.0f},
        .delta_time = 0.015625f, // 64 Hz tick
        .claimed_pos = {0.0122f, 0.0f, 0.0f}
    };
    auto res1 = engine.ProcessAndValidateCommand(player_state, normal_cmd);
    std::cout << "[Tick 101] Validated: " << !res1.violation_detected 
              << " | Server Pos: (" << res1.authoritative_position.x << ", " 
              << res1.authoritative_position.y << ", " << res1.authoritative_position.z << ")\n";

    // Skenario 2: Manipulasi memori lokal (Teleport Hack)
    UserCommand malicious_cmd{
        .tick_number = 102,
        .wish_dir = {1.0f, 0.0f, 0.0f},
        .delta_time = 0.015625f,
        .claimed_pos = {50.0f, 0.0f, 0.0f} // Klien memaksa loncat 50 meter
    };
    auto res2 = engine.ProcessAndValidateCommand(player_state, malicious_cmd);
    std::cout << "[Tick 102] Validated: " << !res2.violation_detected 
              << " | Violation: " << res2.reason 
              << " | Rollback Pos: (" << res2.authoritative_position.x << ")\n";

    return 0;
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: AAA First-Person Tactical Shooter (64-Player Match, 128Hz Tick Rate)
- **Problem Statement:** Game mengalami gelombang eksploitasi:
  1. *Silent Aim / Aimbot*: Paket tembakan selalu mengklaim rotasi sudut Euler yang tepat mengarah ke kepala musuh dalam selisih 1 frame (0 latency micro-adjustment).
  2. *Lag-Switching Exploits*: Klien memutus koneksi masuk secara artifisial, bergerak di lokal, lalu menyemburkan ratusan paket sekaligus untuk mengeksekusi *kills* tanpa memberi kesempatan server merespons.
  3. *CPU Spikes*: Algoritma lag compensation memakan 45% CPU budget pada tick loop server 128Hz saat 30+ pemain menembak serentak dalam pertempuran titik objektif.

#### Solusi Arsitektural Skala Produksi:
1. **Pipelined Spatial Rewind Buffering:**
   - Menyimpan *Bounding Volume Hierarchy (BVH)* terkompresi dari seluruh karakter game dalam representasi *Structure of Arrays (SoA)* pada shared arena memory pool.
   - Interpolasi posisi tidak menggunakan alokasi dinamis. Server menggunakan SIMD AVX2 intrinsic untuk melakukan kalkulasi Ray-AABB intersection pada 8 hit-box target secara paralel dalam satu instruksi siklus CPU.
2. **Mitigasi Lag-Switching (Command Rate Limiting & Tick Budgeting):**
   - Server menerapkan *Strict Fixed-Rate Consumption*. Server hanya memproses maksimal 1 unit pergerakan ($\Delta t = 7.8125\text{ms}$) per *server tick*.
   - Jika paket klien datang terlambat dalam jumlah besar, sisa perintah dimasukkan ke *Jitter Queue* dan dibatasi maksimal 3 tick eksekusi per frame hingga tersinkronisasi kembali. Input selebihnya di-drop (*Client hard-snap reconciliation*).
3. **Telemetry-Based Bot Detection In-Process Engine:**
   - Ditambahkan *ring-buffer* mini berukuran 30 entri yang mencatat *angular jerk* ($\frac{d^3\theta}{dt^3}$) pergerakan crosshair.
   - Pustaka inferensi ONNX Runtime yang di-embed langsung pada proses game server mengevaluasi *tensor window* 30 frame tersebut setiap kali tembakan dilepaskan. Jika skor non-human aim $> 0.985$ dengan entropy deviasi $< 0.001$, paket tembakan dinetralkan (*damage multiplier* diatur ke $0.0$) dan sinyal telemetri dikirim ke antrian isolasi untuk penalti *shadowban*.

---

### 9. Trade-offs

| Parameter Desain | Pilihan A: Permissive Server Validation | Pilihan B: Strict Authoritative Lockstep | Konsekuensi & Engineering Trade-off |
| :--- | :--- | :--- | :--- |
| **Beban CPU Server** | Rendah: Menyetujui posisi klien dan hanya validasi periodik. | Sangat Tinggi: Server mensimulasikan kinematika lengkap, raycasting, dan continuous collision. | Pilihan B membutuhkan alokasi *dedicated CPU cores* per instance match dan kompilasi agresif dengan optimasi `-O3 -march=native`. |
| **Kompensasi Latensi** | Ekstensif: Hingga 500ms lag window (*Favor the shooter*). | Ketat: Dibatasi maksimal 150ms. | Jendela mundur yang besar membuat pemain di balik perlindungan (*behind the wall*) tetap terkena tembakan (*peeker's advantage desync*). Membatasi ke 150ms menjaga integritas kompetitif meski pemain dengan ping tinggi dirugikan. |
| **Input Bandwidth** | Rendah: Mengirimkan hasil akhir posisi dan state per tick. | Tinggi: Mengirimkan input mentah, target angles, delta ticks, dan status penekanan tombol. | Pilihan B menuntut kompresi bit-packing kustom (misal: Huffman coding atau bit-level quantization untuk float) agar paket UDP tetap di bawah batas MTU 1200 bytes. |
| **False-Positive Risk** | Nol (tidak ada pemblokiran heuristik). | Moderat (Heuristik anti-cheat ML dapat menandai atlet esports ber-refleks tinggi). | Pilihan B harus menggunakan skema mitigasi bertingkat: dari *silent rollback*, pengabaian tembakan, hingga verifikasi manual tim audit daripada *auto-ban* langsung. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi:
1. **Menggunakan Waktu Klien (`Cmd.DeltaTime`) Secara Mentah:**
   - *Bug:* Server mengeksekusi `pos += vel * cmd.delta_time` langsung dari payload jaringan klien.
   - *Exploit:* Peretas mengirim `delta_time = 1.0` pada setiap frame 64Hz, menghasilkan pergerakan 64x lebih cepat tanpa terdeteksi oleh cek kecepatan dasar.
   - *Fix:* Abaikan `cmd.delta_time`. Gunakan interval tick server konstan $\Delta t_{server} = \frac{1}{\text{TickRate}}$.
2. **Dynamic Allocations (`malloc` / `new`) di dalam Lag Rewind Loop:**
   - *Bug:* Instansiasi objek `std::vector<Hitbox>` atau pembuatan tree nodes saat melakukan *world rewind*.
   - *Dampak:* Fragmentasi heap memori dan *tail latency spike* (p99 latency melonjak > 50ms), menyebabkan server drop tick.
   - *Fix:* Gunakan *pre-allocated contiguous flat ring-buffer* dan alokasikan scratchpad memory statis per-thread game tick.
3. **Floating Point Non-Determinism Lintas Arsitektur:**
   - *Bug:* Mengharapkan kalkulasi trigonometri float pada klien ARM (mobile) identik presisi per-bit dengan server x86-64.
   - *Dampak:* *Desync loop* permanen; klien terus-menerus terkena koreksi rekonsiliasi (*rubberbanding*).
   - *Fix:* Terapkan toleransi batas $\epsilon$ (misal: $\pm 0.05$ unit) atau gunakan representasi integer berbasis *Fixed-Point Math* (Q24.8 atau Q16.16) untuk komputasi status kritis.

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Zero-Trust:** Tidak pernah menganggap valid koordinat $(X, Y, Z)$ yang dikirim dari antarmuka jaringan.
- [ ] **Rate Limiting Socket Layer:** Membatasi jumlah paket UDP inbound maksimal $1.5 \times \text{TickRate}$ per detik per koneksi.
- [ ] **Fixed-Size Packet Buffers:** Hindari buffer tak terbatas; gunakan ring-buffer berukuran tetap untuk antrian input klien.
- [ ] **Zero Dynamic Allocations:** Pastikan alokator memori heap tidak disentuh selama tick aktif (gunakan custom arena atau stack allocators).
- [ ] **Thread Pinning:** Pin thread utama server game ke core CPU fisik terisolasi (`isolcpus` pada Linux Kernel).
- [ ] **Quantized Float Transmission:** Kompresi floating-point sudut dan posisi menggunakan integer quantization (misal: 16-bit unsigned short untuk merepresentasikan sudut $[0, 360)$ derajat).
- [ ] **Cryptographic Entropy Source:** Pastikan nomor session token atau UDP challenge dibuat menggunakan CSPRNG (`/dev/urandom` atau OS-native crypto provider).

---

### 12. Hands-on Practice

Buat dan simpan struktur file berikut pada direktori kerja Anda di `hands-on/m02/`:

#### Direktori Struktur:
```
hands-on/m02/
├── CMakeLists.txt
├── include/
│   ├── LagCompensator.hpp
│   └── MathTypes.hpp
└── src/
    ├── LagCompensator.cpp
    └── Main.cpp
```

#### File: `hands-on/m02/include/MathTypes.hpp`
```cpp
#pragma once
#include <cmath>

struct Vec3 {
    float x{0.0f}, y{0.0f}, z{0.0f};

    constexpr Vec3 operator+(const Vec3& o) const noexcept { return {x + o.x, y + o.y, z + o.z}; }
    constexpr Vec3 operator-(const Vec3& o) const noexcept { return {x - o.x, y - o.y, z - o.z}; }
    constexpr Vec3 operator*(float s) const noexcept { return {x * s, y * s, z * s}; }
    [[nodiscard]] constexpr float Dot(const Vec3& o) const noexcept { return x * o.x + y * o.y + z * o.z; }
};

struct Ray {
    Vec3 origin;
    Vec3 direction; // Harus dinormalisasi
};

struct CapsuleCollider {
    Vec3 bottom;
    Vec3 top;
    float radius;

    // Evaluasi Ray vs Capsule Intersection
    [[nodiscard]] bool Intersects(const Ray& ray, float max_dist) const noexcept {
        // Implementasi aproksimasi cepat ray-segment distance check
        Vec3 d = top - bottom;
        Vec3 m = ray.origin - bottom;
        float md = m.Dot(d);
        float nd = ray.direction.Dot(d);
        float dd = d.Dot(d);

        if (dd <= 0.0001f) return false;

        float t = (nd * md - m.Dot(ray.direction) * dd) / (dd - nd * nd);
        t = std::clamp(t, 0.0f, max_dist);
        Vec3 point_on_segment = bottom + d * std::clamp(t / std::sqrt(dd), 0.0f, 1.0f);
        
        Vec3 diff = (ray.origin + ray.direction * t) - point_on_segment;
        return diff.Dot(diff) <= (radius * radius);
    }
};
```

#### File: `hands-on/m02/include/LagCompensator.hpp`
```cpp
#pragma once
#include "MathTypes.hpp"
#include <vector>
#include <cstdint>

struct PlayerSnapshot {
    uint32_t tick;
    CapsuleCollider hitbox;
};

class LagCompensator {
public:
    static constexpr size_t BUFFER_SIZE = 128; // Menyimpan 128 snapshot

    LagCompensator() : history_(BUFFER_SIZE) {}

    void RecordSnapshot(uint32_t tick, const CapsuleCollider& hitbox) noexcept;
    [[nodiscard]] bool ValidateHit(uint32_t rewind_tick, const Ray& shot_ray, float max_distance) const noexcept;

private:
    std::vector<PlayerSnapshot> history_;
    size_t head_index_{0};
};
```

#### File: `hands-on/m02/src/LagCompensator.cpp`
```cpp
#include "../include/LagCompensator.hpp"
#include <iostream>

void LagCompensator::RecordSnapshot(uint32_t tick, const CapsuleCollider& hitbox) noexcept {
    history_[head_index_] = PlayerSnapshot{tick, hitbox};
    head_index_ = (head_index_ + 1) % BUFFER_SIZE;
}

bool LagCompensator::ValidateHit(uint32_t rewind_tick, const Ray& shot_ray, float max_distance) const noexcept {
    // Cari snapshot yang cocok atau dua titik terdekat untuk interpolasi
    const PlayerSnapshot* best_match = nullptr;
    for (size_t i = 0; i < BUFFER_SIZE; ++i) {
        if (history_[i].tick == rewind_tick) {
            best_match = &history_[i];
            break;
        }
    }

    if (!best_match) {
        std::cerr << "[Security Audit] Rewind tick " << rewind_tick << " out of history buffer!\n";
        return false; // Upaya manipulasi tick atau packet terlalu tua
    }

    // Eksekusi intersection check
    return best_match->hitbox.Intersects(shot_ray, max_distance);
}
```

#### File: `hands-on/m02/src/Main.cpp`
```cpp
#include "../include/LagCompensator.hpp"
#include <iostream>

int main() {
    LagCompensator compensator;

    // Simulasikan pergerakan target dari tick 100 ke tick 105
    for (uint32_t t = 100; t <= 105; ++t) {
        float x_pos = static_cast<float>(t - 100) * 1.5f;
        CapsuleCollider collider{
            .bottom = {x_pos, 0.0f, 10.0f},
            .top = {x_pos, 2.0f, 10.0f},
            .radius = 0.5f
        };
        compensator.RecordSnapshot(t, collider);
    }

    // Skenario A: Klien dengan RTT 60ms menembak posisi pada tick 102
    Ray legitimate_shot{
        .origin = {3.0f, 1.0f, 0.0f},
        .direction = {0.0f, 0.0f, 1.0f} // Mengarah ke z=10, x=3 (Posisi pada tick 102 adalah x=3.0)
    };

    bool hit_valid = compensator.ValidateHit(102, legitimate_shot, 50.0f);
    std::cout << "Legitimate Shot (Tick 102) Validation Result: " 
              << (hit_valid ? "HIT CONFIRMED" : "MISS") << "\n";

    // Skenario B: Exploiter mencoba menembak posisi tick 102 padahal mengklaim tick 100
    bool exploit_valid = compensator.ValidateHit(100, legitimate_shot, 50.0f);
    std::cout << "Forged Hit Shot (Claimed Tick 100 for Tick 102 Position): " 
              << (exploit_valid ? "HIT CONFIRMED" : "REJECTED (EXPLOIT BLOCKED)") << "\n";

    return 0;
}
```

#### File: `hands-on/m02/CMakeLists.txt`
```cmake
cmake_minimum_required(VERSION 3.20)
project(AuthoritativeAntiCheatEngine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -Wall -Wextra -Wpedantic")

include_directories(include)

add_executable(anti_cheat_demo
    src/Main.cpp
    src/LagCompensator.cpp
)
```

#### Langkah Eksekusi Praktikum:
```bash
cd hands-on/m02/
mkdir build && cd build
cmake ..
cmake --build .
./anti_cheat_demo
```

---

### 13. Exercise

#### Level Easy
- **Tugas:** Tambahkan pemeriksaan sudut rotasi (*Euler yaw/pitch*) pada `UserCommand` di `AuthoritativeMovementSystem`. Jika pitch melebihi rentang $[-89.0^\circ, 89.0^\circ]$ (indikasi eksploitasi manipulasi kamera inversion), tolak paket dan setel violation status ke `INVALID_VIEW_ANGLE`.

#### Level Medium
- **Tugas:** Modifikasi `LagCompensator` untuk mendukung interpolasi linier (*lerp*). Jika klien meminta rewind pada pecahan tick (misal: Tick $102.4$ karena RTT fractional), hitung posisi capsule collider baru hasil *lerp* antara tick $102$ dan $103$, lalu jalankan evaluasi raycast.

#### Level Hard
- **Tugas:** Implementasikan detektor *Silent Aimbot* berbasis *Angular Acceleration Variance*. Buat struktur data yang mencatat 16 rotasi arah tembakan terakhir dari seorang pemain. Hitung rata-rata deviasi standar sudut. Jika deviasi pergeseran sudut mendekati nol mutlak sebelum tembakan dan melonjak $> 90^\circ$ tepat saat penembakan lalu kembali ke orientasi awal dalam 1 frame (*snap-back behavior*), sistem harus mengembalikan flag `TELEMETRY_AIMBOT_POSITIVE`.

---

### 14. Challenge

#### Skenario Masalah: High-Velocity Projectile Ballistics & Desync Mitigation
Rancang modul verifikasi server-side untuk proyektil non-hitscan (misal: peluru senapan penembak runduk dengan kecepatan $900\text{ m/s}$, hambatan udara kuadratik, dan kelengkungan gravitasi) pada pertandingan skala 100 pemain.
- **Batasan Masalah:**
  1. Klien mensimulasikan lintasan peluru secara lokal dan mengklaim *hit* 850 milidetik setelah tembakan ditarik.
  2. Server tidak boleh menyimpan status historis seluruh entitas dunia game selama 850 milidetik penuh dalam bentuk uncompressed snapshot karena kendala batas RAM server (maksimal 500MB untuk 100 pemain).
  3. Peluru dapat berinteraksi dengan proyektil atau kendaraan yang sedang melaju cepat.
- **Tantangan Arsitektur:** 
  Tuliskan dokumen teknis komprehensif atau implementasi mock (C++20) yang mendemonstrasikan algoritma *Event-Based Segmented Validation* untuk memverifikasi keabsahan lintasan proyektil tanpa menyimpan history snapshot penuh per tick, menjaga latensi verifikasi di bawah $1.5\text{ms}$ per peluru, serta kebal terhadap pemalsuan vektor elevasi klien.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa server game kompetitif modern tidak boleh mempercayai koordinat posisi yang dikirimkan oleh klien?**
   - *Jawaban:* Karena memori pada perangkat klien berada di luar perimeter keamanan server. Pengguna dapat memodifikasi variabel posisi secara lokal menggunakan memory debugger/injector, memungkinkan eksploitasi teleportasi dan noclip jika server tidak menghitung posisi secara otoritatif.
2. **Apa yang dimaksud dengan konsep *Server Reconciliation*?**
   - *Jawaban:* Mekanisme di mana server mengirimkan posisi dan tick otoritatif kepada klien setelah mendeteksi desinkronisasi. Klien wajib menimpa simulasi lokalnya dengan status server dan memutar ulang (*replay*) sisa input yang belum diproses dari titik tersebut.
3. **Mengapa UDP lebih dipilih daripada TCP untuk transmisi paket pergerakan otoritatif pada game realtime?**
   - *Jawaban:* TCP memiliki mekanisme *Head-of-Line Blocking* dan retransmisi otomatis yang menimbulkan lonjakan latensi (*jitter*) tak terkendali saat terjadi packet loss. UDP memungkinkan pemrosesan paket terbaru secara langsung tanpa menunggu paket lama yang hilang.
4. **Apa bahaya dari mengeksekusi lag compensation tanpa batas waktu maksimum (*unbounded rewind*)?**
   - *Jawaban:* Membuka celah *Lag-Switching exploit*. Pemain dapat menahan koneksi mereka secara sengaja, membunuh pemain lain yang telah berpindah posisi detik sebelumnya, dan memaksa server memvalidasi kejadian yang terjadi jauh di masa lampau.
5. **Apa fungsi dari algoritma *Sliding Window Bitmask* pada transport layer UDP kustom?**
   - *Jawaban:* Menolak serangan pengulangan paket (*replay attacks*) dan mengeliminasi paket duplikat yang datang di luar urutan (*out-of-order*) tanpa memerlukan alokasi memori dinamis.

#### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara server membedakan antara pemain yang mengalami lonjakan latensi alami (*lag spike*) dengan pelaku kecurangan *speedhack*?**
   - *Jawaban:* Memeriksa total *Command Count Accumulation* terhadap *Real-World Elapsed Server Time*. Lonjakan latensi alami menghasilkan akumulasi sementara yang rata-ratanya setara dengan laju tick server seiring waktu, sedangkan *speedhack* menyuntikkan total paket melebihi batas waktu absolut fisik server.
2. **Mengapa interpolasi posisi pada snapshot ring-buffer harus dilakukan antar-dua tick historis, bukan mengekstrapolasinya ke masa depan?**
   - *Jawaban:* Ekstrapolasi bersifat spekulatif dan rentan terhadap kesalahan gerak yang tajam, sedangkan interpolasi memanfaatkan dua data yang sudah pasti terjadi di masa lampau sehingga menghasilkan kalkulasi batas volumetrik (*hitbox*) yang sepenuhnya deterministik.
3. **Apa trade-off utama dari penggunaan SIMD (Single Instruction Multiple Data) dalam algoritma spatial hitscan server?**
   - *Jawaban:* Peningkatan drastis throughput komputasi ray-capsule dan penurunan latency per-tick, namun menuntut data terstruktur rapi secara berkelanjutan di memori (*Structure of Arrays*, alinyemen byte 32/64-bit) dan meningkatkan kompleksitas basis kode backend.
4. **Mengapa teknik *PVS (Potentially Visible Set)* atau *Spatial Area Interest Management* penting untuk keamanan selain optimasi bandwidth?**
   - *Jawaban:* PVS mencegah kecurangan *Wallhack / ESP*. Server sama sekali tidak mengirimkan data posisi atau status entitas musuh yang berada di luar jangkauan pandang logis atau pendengaran pemain.
5. **Bagaimana model deteksi bot berbasis inferensi ONNX di server dapat menjaga p99 tick loop tidak terganggu?**
   - *Jawaban:* Melalui eksekusi model secara asinkron (*off-thread worker pool*) via *lock-free ring buffer* atau mengoptimalkan model menjadi *quantized INT8 model* yang waktu inferensinya terjamin sub-milidetik sehingga aman dieksekusi sekuensial.

#### Bagian 3: Skenario Kasus Produksi (3 Kasus)
1. **Skenario Kasus A:**
   - *Gejala:* Tim operasi menemukan pemain dengan koneksi fiber 5ms secara konsisten gagal meregistrasikan tembakan (*no-reg*) saat menembak target yang memiliki ping 180ms.
   - *Akar Masalah:* Sistem lag compensation server secara keliru menghitung nilai interpolasi target menggunakan RTT penembak ditambah jitter target secara ganda, mengakibatkan hitbox target diputar balik (*rewound*) terlalu jauh ke masa lalu melebihi apa yang terlihat di layar penembak.
   - *Solusi Engineering:* Standarisasi formula rewind: $\text{RewindTime} = T_{server} - (\text{RTT}_{shooter} / 2) - \text{InterpDelay}_{shooter}$. Parameter jitter target tidak boleh dimasukkan ke dalam kalkulasi rewind sudut pandang penembak.

2. **Skenario Kasus B:**
   - *Gejala:* Saat pertempuran 30 vs 30 di satu area sempit, server mengalami freeze selama 100-200ms setiap kali granat fragmentasi meledak dan memicu pengecekan collision ke banyak pemain.
   - *Akar Masalah:* Pengecekan ledakan melakukan broadphase scan secara $O(N^2)$ terhadap seluruh collider tanpa spatial partitioning, dan kode instansiasi event mengalokasikan memori dinamis di stack tick loop.
   - *Solusi Engineering:* Gunakan Dynamic AABB Tree / Octree statis untuk mempersempit kandidat ke $O(\log N)$ dan gunakan array *pre-allocated buffer* untuk menampung hasil query raycast tanpa dynamic heap invocation.

3. **Skenario Kasus C:**
   - *Gejala:* Peretas merancang bypass *Speedhack Validation* dengan cara mengirimkan nilai rotasi Euler pitch/yaw yang tidak normal ($NaN$ atau float overflow `1e38`), menyebabkan pembagian nol pada kalkulasi normalisasi vektor dan meloloskan posisi baru dari pengecekan bounds.
   - *Akar Masalah:* Kurangnya sanitasi tipe data floating-point primitif sebelum komputasi aljabar linear.
   - *Solusi Engineering:* Terapkan fungsi validasi numerik `std::isfinite()` pada seluruh komponen vektor input langsung setelah deserialisasi bitstream; jika ditemukan nilai bukan hingga (*infinite* atau *NaN*), segera putuskan koneksi socket secara sepihak (*instant drop*).

---

### 16. Summary
Keamanan server game multipemain bertumpu pada **validasi otoritatif yang tidak berkompromi** dipadukan dengan **rekayasa sistem berkinerja tinggi**. Integritas dunia game hanya dapat dijamin apabila server:
1. Menghitung status dunia secara deterministik dari input mentah, bukan dari klaim posisi klien.
2. Memperlakukan jaringan UDP sebagai media yang tidak aman melalui sanitasi batas floating-point, sliding window anti-replay, dan batasan rate konsumsi perintah per-tick yang kaku.
3. Mengadopsi arsitektur memory *zero-allocation* dan representasi data kontinu (SoA/AoS teroptimasi cache) untuk mengeksekusi lag compensation dan query spasial dalam batas tick budget mikrodetik.
4. Memanfaatkan analitik perilaku telemetri dan inferensi machine learning in-process untuk mendeteksi kecurangan generasi modern yang beroperasi di luar ranah deteksi integritas memori lokal.