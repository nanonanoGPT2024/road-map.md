# Kurikulum Rekayasa Perangkat Lunak Game Engine Enterprise
## Bab 05: Audio Teknis, Animasi Skeletal, dan Spatial Systems
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada level Principal Game Engine Architect / Lead Systems Engineer diharapkan mampu:
- **Merancang dan mengimplementasikan** subsistem evaluasi animasi skeletal berbasis SIMD (*Single Instruction, Multiple Data*) dan *Structure of Arrays* (SoA) yang mampu memproses minimal 500 skeletal rig aktif secara konkuren pada target *frame budget* $\le 1.5\text{ ms}$ (skenario $120\text{ FPS}$).
- **Menguasai algoritma kinematika lanjutan**: Mengimplementasikan *Forward Kinematics* (FK), *Inverse Kinematics* (IK) berbasis *FABRIK (Forwards And Backwards Reaching Inverse Kinematics)* dan *Two-Bone IK*, serta transisi pose menggunakan teknik *Inertialization* (menggantikan *cross-fading* linier tradisional).
- **Membangun sistem audio spasial deterministik**: Mengintegrasikan algoritma konvolusi HRTF (*Head-Related Transfer Function*), propagasi gelombang suara berbasis *ray-traced acoustic occlusion/diffraction*, serta *lock-free SPSC (Single Producer Single Consumer) audio ring-buffer pipeline*.
- **Mengeliminasi *bottleneck* sinkronisasi konkurensi**: Menghilangkan fenomena *priority inversion* dan *mutex lock contention* antara *Main Game Loop*, *Animation Worker Threads*, dan *Real-time Audio Thread* berlatensi ultra-rendah ($\le 10\text{ ms}$).

---

### 2. Prerequisite
Sebelum mempelajari modul tingkat lanjut ini, engineer wajib memiliki pemahaman mendalam pada:
- **Bahasa & Standar**: C++20 tingkat lanjut (*move semantics*, *concepts*, *memory model*, *atomics*, memory alignment `alignas`).
- **Matematika Terapan**: Aljabar Linier (Rotasi Quaternion, Dual Quaternion, Matriks Transformasi Homogen $4\times 4$, Dekomposisi Polar, Vektor R3).
- **Arsitektur Komputer Modern**: Hierarki cache (L1/L2/L3), *Cache line invalidation*, *False sharing*, SIMD Intrinsics (x86 AVX2/AVX-512 atau ARM Neon).
- **Sinyal & Audio Dasar**: PCM dasar, *Sample rate*, *Audio buffer framing*, operasi domain frekuensi (Fast Fourier Transform/FFT).

---

### 3. Concept & Internal Architecture

Arsitektur runtime game modern menuntut subsistem audio teknis dan animasi skeletal bekerja dalam sinkronisasi deterministik tanpa memblokir thread render maupun logic.

```
                           +---------------------------+
                           |     Main Game Loop        |
                           |  (State & Logic Update)   |
                           +-------------+-------------+
                                         |
               Dispatch Animation Job    |    Dispatch Audio Events (Lock-free SPSC)
               +-------------------------+-------------------------+
               |                                                   |
               v                                                   v
+-------------------------------+               +----------------------------------+
|   Worker Thread Pool (SIMD)   |               |     Real-Time Audio Thread       |
| - Evaluate Blend Trees        |               |  (Priority: Realtime / SCHED_FIFO)|
| - FABRIK / Two-Bone IK        |               +-----------------+----------------+
| - Dual Quaternion Skinning    |                                 |
| - Bone Matrix Array (SoA)     |                                 |
+--------------+----------------+                                 |
               |                                                  |
       Cache to Shared Memory                                     |
               |                                                  |
               v                                                  v
+-------------------------------+               +----------------------------------+
| GPU Skinning Constant Buffers |               | Spatial DSP Processing           |
| (Render Thread Submission)    |               | - Acoustic Occlusion Raycasts    |
+-------------------------------+               | - HRTF Direct Convolution / FFT  |
                                                | - Ambisonics B-Format Mixdown    |
                                                +-----------------+----------------+
                                                                  |
                                                                  v
                                                +----------------------------------+
                                                | Hardware DMA Buffer (Audio DAC)  |
                                                +----------------------------------+
```

#### A. Data-Oriented Skeletal Animation Pipeline
Pendekatan tradisional berbasis OOP (*Object-Oriented Programming*) menyimpan hierarki tulang sebagai *tree* objek pointer (`Bone* m_parent`, `std::vector<Bone*> m_children`). Pendekatan ini menghasilkan *pointer chasing* masif yang merusak L1 Instruction/Data Cache (*cache thrashing*).

Arsitektur enterprise modern menggunakan representasi **Flat Array of Bones** yang diurutkan secara topologis (*Topological Sorting* / *Parent-First Indexing*). Jika index tulang $i$ memiliki parent $P(i)$, maka secara invarian dijamin:
$$P(i) < i$$

Dengan aturan ini, transformasi tulang dunia (*Global Transform*) dapat dihitung secara serial tanpa rekursi melalui pemindaian linier tunggal menggunakan vektor SIMD:
$$M_{\text{global}}[i] = M_{\text{global}}[P(i)] \times M_{\text{local}}[i]$$

Struktur data internal mengadopsi prinsip SoA (*Structure of Arrays*):
```
struct BoneTransformsSoA {
    // Dipisahkan untuk vectorization 8-wide AVX2 (atau 16-wide AVX-512)
    float* alignas(64) posX;
    float* alignas(64) posY;
    float* alignas(64) posZ;
    float* alignas(64) rotX;
    float* alignas(64) rotY;
    float* alignas(64) rotZ;
    float* alignas(64) rotW;
    float* alignas(64) scaleX;
    float* alignas(64) scaleY;
    float* alignas(64) scaleZ;
    int32_t* parentIndices;
};
```

#### B. Inertialization vs. Cross-fading
*Cross-fading* standar mengevaluasi dua graf animasi berbeda ($A$ dan $B$) secara simultan lalu melakukan *Spherical Linear Interpolation* (Slerp) antar transformasinya selama masa transisi:
$$\text{Cost} = O(\text{Nodes}_A) + O(\text{Nodes}_B) + O(\text{Blend})$$

Teknik **Inertialization** memutus evaluasi Sumber $A$ seketika pada saat transisi dimulai ($t_0$). Ia mengkalkulasi offset diskontinuitas posisi, kecepatan (*velocity*), dan akselerasi (*acceleration*) pada waktu transisi, lalu menerapkan fungsi peluruhan diferensial analitik (*decay polynomial*) ke dalam evaluasi Sumber $B$:
$$\text{Cost} = O(\text{Nodes}_B) + O(\text{Inertial Decay})$$

Persamaan peluruhan polinomial derajat 5 (Quintic Decay Function) memastikan kontinuitas $C^2$ (posisi, kecepatan, dan akselerasi mulus tanpa patahan gerak):
$$x(t) = x_1(t) + \left( A_0 + A_1 t + A_2 t^2 \right) e^{-t / \tau}$$

#### C. Spatial Audio: HRTF & Acoustic Propagation
Suara 3D realistis tidak dapat diperoleh hanya dengan penyesuaian gain amplitudo kiri-kanan (*Stereo Panning*). Gelombang suara mengalami pemfilteran anatomis oleh bentuk pinna telinga luar, kepala, dan bahu. Efek ini dimodelkan melalui filter respons impuls *HRIR* (*Head-Related Impulse Response*).

Pada domain waktu diskrit, sinyal mono sumber suara $s[n]$ diubah menjadi sinyal binaural kiri/kanan ($y_L[n], y_R[n]$) melalui operasi konvolusi:
$$y_L[n] = s[n] * h_L[n, \theta, \phi] = \sum_{m=0}^{M-1} s[n - m] \cdot h_L[m, \theta, \phi]$$
Di mana:
- $h_L, h_R$: Filter HRIR untuk sudut azimuth $\theta$ dan elevasi $\phi$.
- $M$: Panjang respon impuls (lazimnya 128 hingga 512 sampel).

Untuk propagasi fisik, engine meluncurkan *asynchronous raycasts* dari koordinat listener menuju sumber audio untuk mendeteksi:
1. **Direct Path Obstruction (Occlusion)**: Menurunkan frekuensi *cutoff* filter Low-Pass IIR orde ke-2 (Biquad Filter) secara logaritmik.
2. **Indirect Reflections (Early Reflections & Late Reverb)**: Ray tracing memantul pada material dinding (memperhitungkan koefisien absorpsi akustik material $\alpha$) untuk menghasilkan parameter *Spatial Impulse Response Matrix*.

---

### 4. Why & What

| Paradigma Lama (Legacy) | Pendekatan Enterprise Modern | Alasan Teknis & Dampak Arsitektural |
| :--- | :--- | :--- |
| **Penyimpanan Tulang Hirarkis (OOP)**: `std::vector<Bone*>` | **Flat SoA Contiguous Buffers** | Menghilangkan *cache misses* (L1/L2), memungkinkan eksekusi instruksi SIMD FMA (*Fused Multiply-Add*). |
| **Traditional Cross-Fade** | **Inertialization** | Memangkas biaya komputasi hingga 50% selama transisi animasi; mengeliminasi anomali *foot sliding* akibat desinkronisasi fase gerak. |
| **Linear Blend Skinning (LBS)** | **Dual Quaternion Skinning (DQS)** | Mengeliminasi artefak *candy-wrapper volume loss* saat tulang mengalami rotasi torsi ekstrem ($180^\circ$). |
| **Volume-distance Panning** | **Binaural HRTF + Ray-Acoustics** | Memberikan diferensiasi elevasi ($Z$) dan lokalisasi spasial depan/belakang (*front-back ambiguity*) berbasis neuroakustik. |
| **Mutex Lock pada Audio Buffers** | **Lock-Free Atomic SPSC Ring Buffers** | Menjamin Audio Thread tidak pernah mengalami *blocking* (*priority inversion*), meniadakan risiko *audio glitch/crackle/dropout*. |

---

### 5. How (Workflow Detail)

Alur komputasi per-frame terdistribusi dalam pipeline decoupling non-blocking:

```
[Main Thread]
   │
   ├── 1. Kumpulkan Input Pemain & State AI
   ├── 2. Tentukan Anim State Machine Target
   ├── 3. Kirim snapshot transform & event audio ke Ring Buffer
   └── 4. Jalankan Worker Pool Animation Jobs
             │
             ├── [Animation Workers]
             │      ├── Parsing Track Keyframes (Interpolasi Hermite / Catmull-Rom)
             │      ├── Local Space Evaluation -> Global Space Flattening (SIMD SSE/AVX2)
             │      ├── FABRIK Pass untuk Constraint Kaki/Tangan terhadap Collision World
             │      ├── Write Final Palettes to Unified GPU Skinning Buffer
             │      └── Selesai
             │
[Render Thread] <── Mengambil Matrix Buffer dari Shared Memory
             │
             └── Menjalankan Draw Call Skinned Mesh (GPU Vertex Pulling)

[Audio Engine Thread (Asinkron, Latensi 10ms)]
   │
   ├── 1. Poll Lock-Free Ring Buffer (Ambil Audio Commands & Transform Listener/Emitter)
   ├── 2. Ray-march Geometry Akustik (Occlusion, Diffraction Factor)
   ├── 3. Dynamic Filter Parameter Update (Cutoff, Feedback Reverb)
   ├── 4. HRTF Convolution (SIMD Time-Domain FIR atau Frequency-Domain Overlap-Add FFT)
   └── 5. Kirim data PCM ke Hardware Audio Output Buffer
```

---

### 6. Analogy & Diagram ASCII

#### A. Topological Bone Flattening
Bayangkan struktur organisasi perusahaan. Jika CEO ingin menandatangani dokumen yang harus disetujui bertingkat dari Manajer ke Staf, menyimpan staf di kantor-kantor acak di seluruh kota memaksa kurir bolak-balik (Pointer chasing). 

Topological flattening menata seluruh pekerja dalam satu lorong lurus panjang: Meja 0 (CEO), Meja 1 (Direktur), Meja 2 (Manajer), Meja 3 (Staf). Transformasi mengalir searah tanpa pernah melangkah mundur:

```
Index:        [0]        [1]         [2]         [3]          [4]
Hierarchy:   Pelvis ──> Spine ───> Chest ───> L_Shoulder ──> L_Arm
Memory:     | Chunk 0  | Chunk 1   | Chunk 2   | Chunk 3    | Chunk 4    | (Cache Line Continuous)
SIMD Lane:  |--- FMA Vectorized Execution Direction ----------------------->|
```

#### B. HRTF Spatial Acoustic Delay
Bila suara datang dari arah $45^\circ$ kanan, telinga kanan mendengar suara lebih dulu dibanding telinga kiri (*Interaural Time Difference* / ITD). Selain itu, kepala memblokir frekuensi tinggi ke telinga kiri (*Interaural Level Difference* / ILD):

```
                   Emitter (Sound Source)
                          *
                         / \
                        /   \
                       /     \
                      /       \
                     /         \  (Direct Path)
    (Acoustic Shadow) \         \
            x          v         v
         [ Left ]     Head    [ Right ]
         Ear (ILD+ITD)         Ear (Earliest arrival)
```

---

### 7. Implementasi Teknis

#### A. FABRIK (Forwards And Backwards Reaching Inverse Kinematics) SIMD-Aligned Implementation

Berikut implementasi production-grade C++20 solver untuk multi-joint chain constraint FABRIK.

```cpp
#pragma once
#include <immintrin.h>
#include <vector>
#include <cmath>
#include <cstdint>
#include <algorithm>

struct alignas(16) Vec4 {
    float x, y, z, w; // w diabaikan untuk point/vector 3D, mempermudah SIMD SSE
};

inline Vec4 Sub(const Vec4& a, const Vec4& b) {
    return Vec4{ a.x - b.x, a.y - b.y, a.z - b.z, 0.0f };
}

inline Vec4 Add(const Vec4& a, const Vec4& b) {
    return Vec4{ a.x + b.x, a.y + b.y, a.z + b.z, 0.0f };
}

inline Vec4 MulScalar(const Vec4& a, float scalar) {
    return Vec4{ a.x * scalar, a.y * scalar, a.z * scalar, 0.0f };
}

inline float DistanceSq(const Vec4& a, const Vec4& b) {
    float dx = a.x - b.x;
    float dy = a.y - b.y;
    float dz = a.z - b.z;
    return dx * dx + dy * dy + dz * dz;
}

inline float FastInverseSqrt(float number) {
    // Menghitung 1/sqrt(x) menggunakan SIMD SSE
    __m128 nr = _mm_set_ss(number);
    __m128 rsqrt = _mm_rsqrt_ss(nr);
    float res;
    _mm_store_ss(&res, rsqrt);
    // 1 Iterasi Newton-Raphson untuk akurasi presisi
    return res * (1.5f - (0.5f * number * res * res));
}

class FabrikSolver {
public:
    static bool Solve(
        Vec4* const positions,       // Array pointer tulang (In/Out)
        const float* const distances,// Jarak default antar sendi (In)
        const size_t jointCount,     // Jumlah tulang dalam chain
        const Vec4& target,          // Target IK
        const float tolerance = 0.001f,
        const uint32_t maxIterations = 15
    ) {
        if (jointCount < 2) return false;

        const float toleranceSq = tolerance * tolerance;
        const Vec4 root = positions[0];

        // 1. Validasi jangkauan maksimum (Reachability test)
        float totalLength = 0.0f;
        for (size_t i = 0; i < jointCount - 1; ++i) {
            totalLength += distances[i];
        }

        const float distToTargetSq = DistanceSq(positions[0], target);
        if (distToTargetSq > (totalLength * totalLength)) {
            // Target tidak terjangkau, bentangkan seluruh sendi lurus ke target
            const float invDist = FastInverseSqrt(distToTargetSq);
            const Vec4 dir = MulScalar(Sub(target, positions[0]), invDist);
            
            for (size_t i = 0; i < jointCount - 1; ++i) {
                positions[i + 1] = Add(positions[i], MulScalar(dir, distances[i]));
            }
            return false;
        }

        // 2. Iterasi FABRIK
        for (uint32_t iteration = 0; iteration < maxIterations; ++iteration) {
            // Evaluasi kondisi berhenti
            if (DistanceSq(positions[jointCount - 1], target) <= toleranceSq) {
                return true;
            }

            // --- STAGE 1: FORWARD REACHING (End-effector ke Root) ---
            positions[jointCount - 1] = target;
            for (size_t i = jointCount - 1; i > 0; --i) {
                const size_t prev = i - 1;
                const Vec4 delta = Sub(positions[prev], positions[i]);
                const float currentDistSq = delta.x * delta.x + delta.y * delta.y + delta.z * delta.z;
                const float invDist = FastInverseSqrt(currentDistSq);
                
                // Set posisi baru sendi prev
                positions[prev] = Add(positions[i], MulScalar(delta, distances[prev] * invDist));
            }

            // --- STAGE 2: BACKWARD REACHING (Root ke End-effector) ---
            positions[0] = root;
            for (size_t i = 0; i < jointCount - 1; ++i) {
                const size_t next = i + 1;
                const Vec4 delta = Sub(positions[next], positions[i]);
                const float currentDistSq = delta.x * delta.x + delta.y * delta.y + delta.z * delta.z;
                const float invDist = FastInverseSqrt(currentDistSq);
                
                // Koreksi sendi next
                positions[next] = Add(positions[i], MulScalar(delta, distances[i] * invDist));
            }
        }

        return DistanceSq(positions[jointCount - 1], target) <= toleranceSq;
    }
};
```

#### B. High-Performance Lock-Free SPSC Audio Ring Buffer

Sistem ini digunakan untuk mengirim pesan audio, parameter DSP, dan spatial pose secara asinkron dari Main Game Loop ke Audio Thread secara aman tanpa memicu deadlock atau konteks switching.

```cpp
#pragma once
#include <atomic>
#include <cstdint>
#include <new>
#include <utility>
#include <type_traits>

template <typename T, size_t Capacity>
class LockFreeSPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity harus bernilai eksponensial 2 (power of two).");
    static_assert(std::is_trivially_copyable_v<T>, "T harus bersifat trivially copyable untuk determinisme memori.");

private:
    alignas(64) std::atomic<size_t> m_head{0}; // Dikelola oleh Producer (Game Thread)
    alignas(64) size_t m_headCached{0};        // Local cache Producer untuk meminimalkan lintas cache-line
    
    alignas(64) std::atomic<size_t> m_tail{0}; // Dikelola oleh Consumer (Audio Thread)
    alignas(64) size_t m_tailCached{0};        // Local cache Consumer

    alignas(64) T m_buffer[Capacity];

    static constexpr size_t IndexMask = Capacity - 1;

public:
    LockFreeSPSCQueue() = default;
    ~LockFreeSPSCQueue() = default;

    // Dilarang copy/assign demi integritas konkurensi memori
    LockFreeSPSCQueue(const LockFreeSPSCQueue&) = delete;
    LockFreeSPSCQueue& operator=(const LockFreeSPSCQueue&) = delete;

    // Dipanggil eksklusif oleh Producer (Main Engine Loop)
    bool TryEnqueue(const T& item) noexcept {
        const size_t currentHead = m_head.load(std::memory_order_relaxed);

        // Validasi buffer penuh terhadap cached tail
        if ((currentHead - m_tailCached) == Capacity) {
            // Refresh local cache tail dengan sinkronisasi acquire
            m_tailCached = m_tail.load(std::memory_order_acquire);
            if ((currentHead - m_tailCached) == Capacity) {
                return false; // Queue Penuh: buang sinyal / drop event secara aman
            }
        }

        m_buffer[currentHead & IndexMask] = item;
        
        // Mempublikasikan entry ke Consumer melalui memory order release
        m_head.store(currentHead + 1, std::memory_order_release);
        return true;
    }

    // Dipanggil eksklusif oleh Consumer (Audio Thread)
    bool TryDequeue(T& item) noexcept {
        const size_t currentTail = m_tail.load(std::memory_order_relaxed);

        // Validasi buffer kosong terhadap cached head
        if (currentTail == m_headCached) {
            // Refresh local cache head
            m_headCached = m_head.load(std::memory_order_acquire);
            if (currentTail == m_headCached) {
                return false; // Queue Kosong: tidak ada event baru
            }
        }

        item = m_buffer[currentTail & IndexMask];

        // Membebaskan slot ke Producer
        m_tail.store(currentTail + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] size_t GetApproximateOccupancy() const noexcept {
        const size_t head = m_head.load(std::memory_order_relaxed);
        const size_t tail = m_tail.load(std::memory_order_relaxed);
        return (head >= tail) ? (head - tail) : (Capacity - (tail - head));
    }
};
```

#### C. Spatial HRTF Convolution Filter Kernel (AVX2-Accelerated)

Kernel pemrosesan sinyal audio digital berikut mengeksekusi Time-Domain Finite Impulse Response (FIR) Convolution untuk lokalisasi 3D real-time.

```cpp
#pragma once
#include <immintrin.h>
#include <cstddef>
#include <cstdint>

// Melakukan direct time-domain convolution untuk buffer mono source dengan HRTF Impulse Response
// Menghasilkan channel output individual (Left atau Right)
void ProcessHRTFChannel_AVX2(
    const float* const __restrict inputAudio,  // Audio source buffer mono (N samples)
    const float* const __restrict hrtfKernel,  // Koefisien FIR HRTF (harus kelipatan 8, e.g. 128 taps)
    float* const __restrict outputAudio,       // Output binaural buffer
    const size_t frameCount,                  // Jumlah frame per audio tick (e.g. 256 / 512)
    const size_t kernelTaps                   // Jumlah filter taps (e.g. 128)
) {
    // Pastikan kernelTaps merupakan kelipatan 8 untuk SIMD 256-bit AVX
    for (size_t n = 0; n < frameCount; ++n) {
        __m256 accum = _mm256_setzero_ps();

        // Operasi perkalian akumulasi vektor (FMA) 8 float paralel
        for (size_t k = 0; k < kernelTaps; k += 8) {
            // Ambil 8 koefisien HRTF
            __m256 h = _mm256_loadu_ps(&hrtfKernel[k]);

            // Ambil 8 sampel audio historis mundur (s[n - k])
            // Catatan: Memerlukan validasi buffer input memiliki padding masa lalu sebesar kernelTaps
            __m256 s = _mm256_loadu_ps(&inputAudio[n - k - 7]);

            // Reverse urutan sampel input agar berkorespondensi dengan urutan filter convolution
            // s[n-k-7], s[n-k-6], ... s[n-k] -> di-reverse secara horizontal
            const __m256 s_reversed = _mm256_permute2f128_ps(s, s, 0x01);
            // Untuk penyederhanaan loop performa tinggi, input audio idealnya di-pre-reverse pada ring buffer
            // Di sini kita asumsikan komputasi FMA terpadu:
            accum = _mm256_fmadd_ps(h, s, accum);
        }

        // Reduksi Horizontal: Menggabungkan 8 float dalam register accum menjadi 1 nilai float skalar
        __m128 low = _mm256_castps256_ps128(accum);
        __m128 high = _mm256_extractf128_ps(accum, 1);
        __m128 sum128 = _mm_add_ps(low, high);
        
        sum128 = _mm_hadd_ps(sum128, sum128);
        sum128 = _mm_hadd_ps(sum128, sum128);

        float finalSample;
        _mm_store_ss(&finalSample, sum128);

        outputAudio[n] = finalSample;
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: Studio AAA — Open-World Tactical Action Title
- **Beban Kerja**: 350 karakter skeletal aktif di area medan perang perkotaan padat.
- **Masalah Kritis**:
  1. *Frame-time hitching* setiap kali animasi berganti masif antar ledakan ledakan (evaluasi animasi menyentuh $8.7\text{ ms}$).
  2. Suara desingan peluru dan langkah musuh di balik dinding beton terdengar datar dan arah sumber audio vertikal (musuh di lantai 2 gedung vs ground) tidak dapat dibedakan oleh pemain.
  3. Audio crackling/glitch sering terjadi saat pertempuran intensif karena audio thread kehabisan waktu buffer (*buffer starvation*).

#### Root Cause Analysis (RCA)
- Evaluasi cross-fade standar mengevaluasi $2 \times \text{blend-tree}$ untuk 350 karakter ($700\text{ graph evaluations}$/frame).
- Audio thread menggunakan `std::mutex` untuk membaca koordinat karakter dari engine, memicu *Priority Inversion* saat Main Thread memegang lock terlalu lama selama Garbage Collection atau Physics Update.
- Sistem audio hanya mengandalkan perhitungan sudut horizontal pan tanpa filtering HRIR dan penelusuran oklusi geometry real-time.

#### Solusi Arsitektural Terapan
1. **Migrasi Animasi ke Pure Inertialization & SIMD SoA**:
   - Struktur animasi dipangkas dari Dual-Graph Evaluation menjadi Single Graph Target + Inertial Decay State. Beban kerja komputasi langsung turun dari $8.7\text{ ms}$ menjadi $1.15\text{ ms}$.
2. **Implementasi Lock-Free Ring Buffer untuk Data Transform Spasial Audio**:
   - Koordinat spasial di-push dari Animation Job completion langsung ke `LockFreeSPSCQueue<AudioEntityState, 4096>` tanpa alokasi dinamis. *Priority inversion* tereliminasi total; buffer underrun mencapai $0\%$.
3. **Hybrid Geometry Acoustics**:
   - Sistem audio meluncurkan 8 sinar *Asynchronous Physics Traces* per sumber audio penting.
   - Jika sinar terhalang oleh material `Concrete`, filter IIR Biquad Low-Pass disetel ke $f_c = 450\text{ Hz}$ dan gain diturunkan sebesar $-18\text{ dB}$. Konvolusi HRTF AVX2 diaktifkan khusus untuk peluru, dialog, dan langkah kaki.

---

### 9. Trade-offs

```
                       PERFORMANCE (Throughput / FPS)
                                    /\
                                   /  \
                                  /    \
                                 /      \
                                /   * A  \  (SIMD SoA + Inertialization)
                               /          \
                              /      * B   \ (Raytraced HRTF + Full DQS)
                             /              \
       (AoS + Crossfade) * C/________________\
           LOW LATENCY                        ACCURACY / HIGH FIDELITY
```

| Keputusan Arsitektur | Keuntungan | Kompensasi / Konsekuensi (Downside) | Batas Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **Inertialization (vs Crossfade)** | Penghematan CPU hingga $50\%$; transisi bebas *foot sliding*. | Memerlukan *authoring* transisi yang presisi; dapat menghasilkan twitching jika transisi dipicu saat kecepatan ekstrem. | Semua gameplay animasi gerak karakter (Locomotion/Combat). |
| **Dual Quaternion Skinning (vs Linear Blend)** | Tidak ada volume loss (*candy wrapper*) pada sendi putar (bahu, pergelangan). | Membutuhkan instruksi aritmatika GPU tambahan ($+25\%$ ALU cycles) dibanding LBS standar. | Karakter detail tinggi; model dengan baju zirah/pakaian tebal. |
| **Time-Domain FIR HRTF (vs FFT Frequency-Domain)** | Latensi zero-frame; buffer deterministik; sangat efisien untuk ukuran tap pendek ($\le 128$). | Tidak skalabel untuk panjang impuls akustik besar ($> 512$ taps) di mana komputasi $O(N^2)$ mengalahkan algoritma FFT $O(N \log N)$. | Lokalisasi audio spasial directional (ear/pinna cue filtering). |
| **SoA Memory Transformation** | Eksekusi SIMD instan tanpa translasi; ramah cache. | Struktur data lebih sulit dibaca secara human-readable; rekonstruksi data ke AoS memerlukan overhead *gather*. | Core Engine Animation Runtime & Physics pipelines. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Alignment Trap pada Instruksi SIMD AVX/SSE
- **Gejala**: Program mengalami *Crash* mendadak dengan sinyal `SIGSEGV` / `STATUS_ACCESS_VIOLATION` pada baris eksekusi instruksi `_mm256_load_ps` atau `_mm_load_ps`.
- **Akar Masalah**: Pemuatan data SIMD yang ditujukan untuk alamat biner ter-align (16-byte untuk SSE, 32-byte untuk AVX) menerima pointer dari alokasi memori standar (`malloc` / `new`) yang hanya menjamin 8-byte alignment.
- **Solusi**: Gunakan instruksi unaligned `_mm256_loadu_ps` atau alokasikan memori menggunakan operator `alignas(32)` / API native aligned:
  ```cpp
  float* buffer = static_cast<float*>(_aligned_malloc(sizeof(float) * count, 32));
  // Platform Unix: posix_memalign(...)
  ```

#### B. Priority Inversion pada Audio Thread
- **Gejala**: Audio terputus-putus (*stuttering/glitching*) terutama saat render frame time melonjak atau saat level streaming dimuat di latar belakang.
- **Akar Masalah**: Audio Thread (yang dialokasikan OS dengan prioritas tinggi/Real-Time) mencoba mengakuisisi `std::mutex` yang sedang dipegang oleh Main Thread (prioritas normal). Ketika thread prioritas menengah mengambil CPU, Main Thread terhambat, secara tidak langsung menghentikan Audio Thread.
- **Solusi**: Jangan pernah menggunakan OS synchronization primitives (`std::mutex`, `std::condition_variable`, semaphores) di dalam loop pemrosesan audio berlatensi rendah. Terapkan arsitektur **Lock-Free Atomic Ring Buffers**.

#### C. Quaternion Sign Discontinuity pada Rotasi Animasi
- **Gejala**: Interpolasi gerak sambungan tulang berputar secara liar sebesar $360^\circ$ alih-alih mengambil rotasi terpendek saat dievaluasi.
- **Akar Masalah**: Representasi rotasi quaternion bersifat *double-cover* ($q$ dan $-q$ merepresentasikan orientasi fisik yang identik di ruang 3D). Jika operasi dot product antara dua quaternion bertanda negatif ($q_1 \cdot q_2 < 0$), interpolasi akan memutar rute terjauh.
- **Solusi**: Normalisasi dan deteksi tanda *dot product* sebelum melakukan Slerp / Lerp:
  ```cpp
  float dot = q1.w*q2.w + q1.x*q2.x + q1.y*q2.y + q1.z*q2.z;
  if (dot < 0.0f) {
      q2 = Quaternion(-q2.w, -q2.x, -q2.y, -q2.z);
  }
  ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Memory Alignment**: Pastikan seluruh buffer data transformasi lokal dan global memiliki penataan `alignas(64)` guna menghindari pemecahan jalur data cache line (*cache-line splits*).
2. [ ] **Zero Dynamic Allocation**: Dilarang memanggil `malloc`, `free`, `new`, `delete`, atau metode STL yang mengubah kapasitas memori dinamis (`std::vector::push_back`, `std::string`) di dalam Hot Paths loop animasi dan audio thread.
3. [ ] **Pre-allocated Linear Ring Buffers**: Seluruh event pemutaran audio, update spasial, dan matrix stream harus menggunakan arena memori yang telah dialokasikan statis pada saat engine diinisialisasi.
4. [ ] **Thread Pinning (Affinity)**: Ikat (pin) Audio Processing Thread pada dedicated CPU core yang terpisah dari thread pekerjaan render dan gameplay logic (`SetThreadAffinityMask` pada Windows, `pthread_setaffinity_np` pada Linux).
5. [ ] **Float Denormals Flush**: Aktifkan flag penghentian angka float terdenormalisasi (*denormals*) pada unit register floating-point engine untuk mencegah penurunan siklus instruksi CPU hingga 100x lipat saat audio mendekati hening:
   ```cpp
   _MM_SET_FLUSH_ZERO_MODE(_MM_FLUSH_ZERO_ON);
   _MM_SET_DENORMALS_ZERO_MODE(_MM_DENORMALS_ZERO_ON);
   ```
6. [ ] **Inertialization Continuity**: Simpan state transisi sekunder (vektor kecepatan transisi tulang) secara persisten untuk menjamin tidak terjadinya lonjakan percepatan saat ada pembatalan transisi (*interrupting blends*).

---

### 12. Hands-on Practice
Langkah instruksional implementasi praktikum pada direktori `hands-on/m02/`:

#### Langkah 1: Membangun Struktur Proyek
Buat struktur file berikut:
```text
hands-on/m02/
├── CMakeLists.txt
├── include/
│   ├── AlignedMath.hpp
│   ├── LockFreeQueue.hpp
│   ├── SpatialAudioDSP.hpp
│   └── SkeletalRigSoA.hpp
└── src/
    ├── main.cpp
    └── SpatialAudioDSP.cpp
```

#### Langkah 2: Setup Konfigurasi Build (CMakeLists.txt)
Konfigurasi compiler C++20 dengan optimasi SIMD AVX2 dan thread realtime:
```cmake
cmake_minimum_required(VERSION 3.20)
project(EngineSpatialSystems LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if (MSVC)
    add_compile_options(/arch:AVX2 /W4 /O2)
else()
    add_compile_options(-mavx2 -mfma -O3 -Wall -Wextra)
endif()

include_directories(include)

add_executable(EngineModule02 
    src/main.cpp 
    src/SpatialAudioDSP.cpp
)

find_package(Threads REQUIRED)
target_link_libraries(EngineModule02 PRIVATE Threads::Threads)
```

#### Langkah 3: Implementasi Test Engine Harness (src/main.cpp)
Tuliskan test rig yang menjalankan:
1. Thread produser: Menghasilkan 500 skeletal hierarchies dan melakukan FABRIK pass per frame.
2. Memasukkan spatial audio coordinate emitter hasil komputasi FABRIK end-effector ke dalam `LockFreeSPSCQueue`.
3. Thread konsumer (Audio Thread): Mengambil koordinat secara independen setiap 10ms dan melakukan filter HRTF processing loop menggunakan instruksi AVX2.

---

### 13. Exercise

#### Level Easy
Implementasikan fungsi verifikasi Topological Ordering pada data hierarki tulang. 
- **Input**: Array integer yang merepresentasikan ID parent dari setiap tulang (`int32_t* parents`, `size_t count`).
- **Output**: Mengembalikan boolean `true` jika untuk setiap indeks $i$, nilai $P(i) < i$ (dengan pengecualian root di mana $P(0) = -1$), dan `false` jika hierarki melanggar urutan tersebut.

#### Level Medium
Modifikasi kelas `FabrikSolver` yang disediakan pada Bagian 7 untuk mendukung **Angular Constraint**:
- Tambahkan batasan sudut kerucut (*cone constraint*) maksimum sebesar $45^\circ$ deviasi dari orientasi vektor segmen tulang sebelumnya.
- Jika tulang melebihi sudut maksimum setelah langkah backward reaching, proyeksi paksa vektor tulang tersebut agar tepat berada pada batas batas kerucut lingkaran.

#### Level Hard
Rancang dan implementasikan struktur data **Inertializer** translasi satu dimensi:
- Buat kelas yang menerima parameter perubahan target posisi ($x_0$), offset awal saat interupsi ($v_0$), durasi transisi ($T$).
- Implementasikan evaluasi polinomial quintic deterministik:
  $$x(t) = x_{\text{target}} + (A_0 + A_1 t + A_2 t^2 + A_3 t^3 + A_4 t^4 + A_5 t^5)$$
  di mana turunan ke-0, ke-1, dan ke-2 bernilai kontinu mulus menuju target saat $t \ge T$, tanpa pernah mengalami *overshoot* yang melebihi $5\%$ dari amplitudo awal.

---

### 14. Challenge

#### Skenario Kasus Kompleks:
Sebuah engine ditugaskan untuk menjalankan pertarungan massal beranggotakan **1.000 karakter skeletal** yang berada di dalam arena tertutup berstruktur gua (*caved acoustic environment*).

**Spesifikasi Masalah**:
1. **Target**: Frametime keseluruhan evaluasi animasi dan pembaruan audio transforms tidak boleh melebihi $2.0\text{ ms}$ pada CPU 8-Core (16-Threads) modern.
2. **Kendala Fisik & Spatial**:
   - Setiap karakter memiliki 64 tulang.
   - Sebanyak 200 karakter berada dalam radius pendengaran langsung listener dan membutuhkan kalkulasi dynamic early reflection akustik (pantulan pantulan dinding).
   - Karakter-karakter yang saling bertubrukan memicu perubahan arah transisi animasi secara tiba-tiba (*high frequency interrupt transitions*).

**Tugas Arsitektur Anda**:
- Rancang cetak biru arsitektur pipeline data (*Data Flow Architecture*) yang mencakup alokasi memori, skema pembagian Job ke Worker Threads, skema LOD (*Level of Detail*) animasi dan audio processing, serta protokol transfer data antar memori CPU-GPU.
- Jabarkan secara analitis: Kapan HRTF kalkulasi penuh dimatikan dan dialihkan ke pendekatan ambisonics berbiaya konstan, serta bagaimana menghindari starvation pada audio ring buffer saat 1.000 karakter memicu audio footsteps secara serentak dalam rentang 1 frame logic.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic (5 Soal)
1. **Mengapa pemrosesan hierarki tulang berbasis pointer node (`Bone*`) sangat dihindari dalam modern low-level game engine?**
   - *Jawaban*: Menyebabkan pengaksesan memori acak (*pointer chasing*) yang memicu L1/L2 cache misses berulang, serta mencegah compiler memvektorisasi kalkulasi matriks menggunakan instruksi SIMD.
2. **Apa yang mendasari aturan indeksasi $P(i) < i$ pada hierarki skeletal SoA?**
   - *Jawaban*: Menjamin bahwa transformasi ruang dunia (*world space transform*) dari parent tulang $i$ telah selesai dihitung sebelum tulang $i$ dievaluasi, sehingga seluruh skeleton dapat diselesaikan dalam pemindaian linier satu arah tanpa rekursi.
3. **Mengapa cross-fading tradisional membutuhkan komputasi dua kali lipat lebih banyak dibanding Inertialization selama masa blending?**
   - *Jawaban*: Karena cross-fade wajib mengevaluasi kedua Animation Graph (Sumber dan Target) secara utuh sebelum melakukan interpolasi antar pose, sedangkan inertialization langsung menghentikan evaluasi Sumber dan hanya mengevaluasi Target ditambah peluruhan polinomial tunggal.
4. **Apa bahaya terbesar memanggil fungsi `std::mutex::lock()` di dalam real-time Audio Thread?**
   - *Jawaban*: Bahaya *Priority Inversion*, di mana thread prioritas rendah yang memegang lock dapat terhenti oleh scheduler, menyebabkan Audio Thread berprioritas tinggi terblokir hingga terjadi *buffer underrun* (audio pop/crack).
5. **Fenomena visual apakah yang dieliminasi oleh Dual Quaternion Skinning (DQS) jika dibandingkan dengan Linear Blend Skinning (LBS)?**
   - *Jawaban*: Artefak penyusutan volume sendi secara drastis saat terjadi rotasi puntir (torsi), yang dikenal sebagai efek bungkus permen (*candy-wrapper artifact*).

#### Pertanyaan Intermediate (5 Soal)
6. **Bagaimana cara kerja Fast Inverse Square Root (`_mm_rsqrt_ss`) dan mengapa masih membutuhkan 1 iterasi Newton-Raphson dalam kalkulasi IK?**
   - *Jawaban*: Instruksi perangkat keras mengestimasi $1/\sqrt{x}$ secara instan melalui look-up table internal berbasis representasi eksponen float IEEE-754. Iterasi Newton-Raphson ditambahkan untuk memperbaiki galat presisi (*relative error*) dari ~0.1% menjadi presisi float 24-bit penuh yang dibutuhkan matematika joint.
7. **Dalam lock-free SPSC queue, mengapa variabel index `m_head` dan `m_tail` diletakkan pada cache-line terpisah dengan atribut `alignas(64)`?**
   - *Jawaban*: Untuk mencegah fenomena *False Sharing*, di mana penulisan thread Producer pada `m_head` membatalkan seluruh cache line CPU yang sedang dibaca oleh thread Consumer pada `m_tail`, yang berakibat pada degradasi drastis performa memori bus.
8. **Jelaskan perbedaan mendasar antara ITD (Interaural Time Difference) dan ILD (Interaural Level Difference) pada fungsi transfer HRTF!**
   - *Jawaban*: ITD adalah selisih waktu tiba gelombang suara antar kedua telinga yang dipicu oleh jarak tempuh spasial (relevan pada frekuensi rendah $< 1.5\text{ kHz}$), sedangkan ILD adalah perbedaan intensitas redaman amplitudo akibat bayangan akustik kepala (relevan pada frekuensi tinggi $> 1.5\text{ kHz}$).
9. **Kapan konvolusi audio domain waktu (Time-Domain Convolution) lebih unggul secara performa dibanding konvolusi domain frekuensi berbasis FFT (Overlap-Add/Save)?**
   - *Jawaban*: Konvolusi domain waktu lebih efisien saat ukuran kernel impulse response (FIR taps) relatif kecil ($\le 128$ sampel) karena tidak memerlukan overhead komputasi forward-backward FFT, serta tidak memperkenalkan latensi pemrosesan buffer awal (*zero latency*).
10. **Mengapa aktivasi register mode `Flush-to-Zero` (FTZ) dan `Denormals-are-Zero` (DAZ) sangat kritikal pada DSP Audio Engine?**
    - *Jawaban*: Filter audio IIR yang meluruh mendekati hening dapat menghasilkan angka denormal (sangat mendekati nol). Pemrosesan angka denormal oleh unit FPU standar dialihkan ke penanganan microcode software yang dapat memperlambat komputasi hingga ratusan siklus CPU per instruksi.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Setelah mengintegrasikan sistem physics ragdoll dengan animasi skeletal, model karakter sesekali hancur menjadi serpihan mesh yang melesat ke nilai floating point tak terhingga (`NaN` / `INF`). Tim gameplay mencurigai data animasi yang rusak. Bagaimana Anda mengisolasi dan mengatasi akar masalahnya secara matematis?
    - *Solusi & Analisis*: Masalah biasanya berakar dari normalisasi vektor berpanjang nol ($0,0,0$) pada solver IK saat posisi sendi bertubrukan persis di titik yang sama, menyebabkan pembagian dengan nol ($1/0 \rightarrow \text{NaN}$). Lakukan penambahan epsilon perlindungan ($\epsilon = 10^{-7}$) pada operasi normalisasi magnitudo, dan tambahkan SIMD assert check yang secara otomatis menolak (clamp) transformasi yang menghasilkan determinan matriks non-positif atau NaN sebelum diunggah ke buffer GPU.
12. **Skenario 2**: Profiling audio menunjukkan bahwa pada konsol game dengan CPU multi-core, Audio Thread sering mengalami *starvation* acak setiap 15-30 detik meskipun utilisasi rata-rata CPU audio berada di bawah $20\%$. SPSC Queue terbukti tidak pernah penuh. Di mana letak potensi masalah level OS?
    - *Solusi & Analisis*: Penyebab umum adalah *OS Core Migration* dan ketiadaan *Thread Affinity*. Scheduler sistem operasi secara berkala memindahkan Audio Thread dari satu Core fisik ke Core lain demi pendinginan termal. Proses migrasi ini mengosongkan L1/L2 cache secara instan dan menimbulkan jeda penjadwalan (*scheduling latency*) melebihi batas window audio hardware (misal $5.33\text{ ms}$ pada buffer 256 sample / 48kHz). Solusinya adalah mengunci thread menggunakan OS processor affinity mask dan menyetel prioritas thread ke `THREAD_PRIORITY_TIME_CRITICAL` atau `SCHED_FIFO`.
13. **Skenario 3**: Saat melakukan transisi cepat dari status "Sprint" ke "Cover Crouch", sistem animasi Inertialization menghasilkan lonjakan posisi pelvis ke bawah tanah selama 2 frame sebelum naik kembali ke posisi cover. Apa yang salah pada kalkulasi derivatif transisi tersebut?
    - *Solusi & Analisis*: Anomali ini terjadi akibat turunan pertama kecepatan (*velocity vector*) dari pose sumber saat transisi memiliki magnitudo ke bawah yang terlalu tinggi, dan durasi peluruhan ($T$) disetel terlalu panjang, sehingga polinomial menghasilkan *overshoot* negatif ekstrem. Solusinya adalah menerapkan *clamping* pada vektor kecepatan awal transisi berdasarkan limit kecepatan gerak fisik maksimal karakter, atau menurunkan durasi blend $T$ secara dinamis proporsional terhadap besaran deviasi percepatan awal.

---

### 16. Summary

1. Arsitektur skeletal animation enterprise modern meninggalkan paradigma OOP hierarkis dan beralih ke **Topologically Sorted Flat Structure of Arrays (SoA)**, memungkinkan kalkulasi matrix flattening tereksekusi linier berkecepatan tinggi melalui instruksi SIMD tanpa *pointer indirection*.
2. **Inertialization** merevolusi komputasi blending pose dengan mengevaluasi satu node animasi aktif secara konsisten dan meluruhkan diskontinuitas menggunakan polinomial quintic ($C^2$ continuity), memangkas siklus CPU hingga setengah dari teknik cross-fading konvensional.
3. Subsistem audio berlatensi rendah harus sepenuhnya terisolasi dari latensi main game loop melalui **Lock-Free Atomic SPSC Queues**, menjamin audio DAC beroperasi pada latensi real-time bebas dari risiko *priority inversion*.
4. Akustik spasial 3D modern memadukan **Binaural HRTF Convolution** untuk penyaringan spektral pinna dengan **Asynchronous Raymarched Acoustic Tracing** untuk menghasilkan difraksi, refleksi dini, dan oklusi fisik yang realistis secara deterministik.
5. Efisiensi eksekusi subsistem ini ditentukan oleh kedisiplinan alokasi memori runtime: memory aligned (`alignas(64)`), zero dynamic allocations pada hot loops, penanganan denormal numbers via hardware flags (FTZ/DAZ), serta pemanfaatan komputasi paralel SIMD (AVX2/AVX-512).