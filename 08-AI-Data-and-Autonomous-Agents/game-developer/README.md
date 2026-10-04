# Kurikulum Rekayasa Sistem Game (Game Engineering) Terapan

Kurikulum ini dirancang berdasarkan standar industri game AAA dan ekosistem resmi [roadmap.sh: Game Developer](https://roadmap.sh/game-developer). Pendekatan yang digunakan berfokus pada rekayasa sistem berkinerja tinggi (*high-performance systems engineering*), manipulasi memori tingkat rendah (*low-level memory manipulation*), matematika grafika komputer, serta arsitektur terdistribusi untuk game multipemain skala besar (*large-scale networked multiplayer*).

---

## 1. Pandangan Umum Kursus & Pola Pikir (Course Overview & Mindset)

Pengembangan game pada tingkat industri bukan sekadar perakitan aset di dalam *game engine*, melainkan cabang ilmu rekayasa perangkat lunak dengan konstrain performa terketat di dunia komputasi. Setiap instruksi CPU dan siklus alokasi memori beroperasi di bawah batasan waktu yang tidak dapat ditawar: **16,6 milidetik per frame (60 FPS)** atau **8,3 milidetik per frame (120 FPS)**.

### Prinsip Inti Rekayasa Game
1. **Cache-Friendly & Data-Oriented Design (DOD):** Model Pemrograman Berorientasi Objek (OOP) klasik sering kali memicu *cache misses* massal akibat pointer chasing dan data fragmentation. Arsitek game modern mendesain struktur data berbasis susunan contiguous memory (struktur SoA vs AoS) dan arsitektur Entity Component System (ECS).
2. **Determinisme dan Presisi Numerik:** Memahami batasan *floating-point arithmetic*, divergensi arsitektur CPU, representasi orientasi menggunakan Kuaternion, dan mitigasi *gimbal lock*.
3. **Simulasi Frame Berbasis Tick yang Deterministik:** Memisahkan *render loop* yang variabel dari *physics/simulation loop* yang fixed-step demi kestabilan kalkulasi dan integrasi jaringan.
4. **Alokasi Memori Tanpa Runtime Garbage Collection:** Mengeliminasi latensi tak terduga (*stuttering*) dengan membangun *custom memory allocators* (Linear, Stack, Pool, dan Free-List Allocators) sejak hari pertama.

---

## 2. Peta Jalan Pembelajaran (Learning Roadmap)

```text
Game Developer Engineering Roadmap
├── BAB 01: Fondasi Matematika, Fisika, & Arsitektur Engine
├── BAB 02: Pemrograman Sistem Rendah & Manajemen Memori
├── BAB 03: Arsitektur Game & Data-Oriented Design (ECS)
├── BAB 04: Pipa Grafika, Shaders, & Modern Rendering
├── BAB 05: Audio Teknis, Animasi Skeletal, & Spatial Systems
├── BAB 06: Gameplay AI Terapan & Sistem Status Reaktif
├── BAB 07: Arsitektur Jaringan Real-Time & Sinkronisasi State
├── BAB 08: Engine Tooling, Pipeline Aset, & Serialisasi Data
├── BAB 09: Profiling Komputasi, SIMD, & Optimasi Hardware
└── BAB 10: Pipeline Produksi Enterprise, Anti-Cheat, & LiveOps
```

---

## 3. Navigasi Detail Modul (Bab 01 s/d Bab 10)

### [BAB 01: Fondasi Matematika, Fisika, & Arsitektur Engine](./BAB-01-fondasi-matematika-fisika-engine/)
Memahami fondasi kalkulasi pergerakan, orientasi spasial, serta struktur dasar engine loop independen platform.
* [Modul 01: Aljabar Linear, Transformasi Matriks, & Kuaternion](./BAB-01-fondasi-matematika-fisika-engine/01-aljabar-linear-kuaternion.md) - Operasi Vektor, Dot/Cross Product, Basis Spasial, Rotasi 3D, Kuaternion Slerp.
* [Modul 02: Kinematika & Kalkulus Vektor untuk Simulasi](./BAB-01-fondasi-matematika-fisika-engine/02-kinematika-kalkulus-vektor.md) - Integrasi Euler, Verlet, dan Runge-Kutta (RK4) untuk kalkulasi pergerakan presisi.
* [Modul 03: Anatomi Game Loop & Sub-Sistem Lifecycle](./BAB-01-fondasi-matematika-fisika-engine/03-game-loop-subsystem-lifecycle.md) - Fixed timestep, variable rendering, accumulator pattern, OS message dispatching.

### [BAB 02: Pemrograman Sistem Rendah & Manajemen Memori](./BAB-02-pemrograman-sistem-manajemen-memori/)
Membangun kontrol mutlak atas memori, layout data CPU, dan interaksi hardware menggunakan C++ modern.
* [Modul 01: Arsitektur Memori CPU, Cache Locality, & Pointer](./BAB-02-pemrograman-sistem-manajemen-memori/01-cpu-cache-pointer-internals.md) - L1/L2/L3 cache misses, prefetcher, page faults, dan memory alignment/padding.
* [Modul 02: Custom Memory Allocators](./BAB-02-pemrograman-sistem-manajemen-memori/02-custom-memory-allocators.md) - Implementasi Stack, Linear, Pool, dan Free-List Allocator tanpa runtime `malloc`/`free`.
* [Modul 03: Smart Pointers, Resource Ownership, & RAII](./BAB-02-pemrograman-sistem-manajemen-memori/03-raii-move-semantics.md) - Manajemen siklus hidup memori tanpa garbage collector, move semantics, dan rvalue references.

### [BAB 03: Arsitektur Game & Data-Oriented Design (ECS)](./BAB-03-arsitektur-game-ecs/)
Meninggalkan hierarki pewarisan OOP yang kaku dan beralih ke arsitektur data-oriented berkecepatan tinggi.
* [Modul 01: Kegagalan OOP Klasik & Transisi ke DOD](./BAB-03-arsitektur-game-ecs/01-oop-failure-dod-transition.md) - Analisis cache invalidation pada virtual inheritance, relasi Struct-of-Arrays (SoA) vs Array-of-Structures (AoS).
* [Modul 02: Implementasi Entity Component System (ECS)](./BAB-03-arsitektur-game-ecs/02-implementasi-ecs-sparse-sets.md) - Sparse Sets, Archetype-based storage, dan memory chunk iteration berkecepatan tinggi.
* [Modul 03: Event-Driven Systems & Decoupled Messaging](./BAB-03-arsitektur-game-ecs/03-event-bus-decoupled-messaging.md) - Lock-free ring buffer event queues, thread-safe command buffers, dan pub/sub terisolasi.

### [BAB 04: Pipa Grafika, Shaders, & Modern Rendering](./BAB-04-grafika-shaders-rendering/)
Menguasai komunikasi GPU, penulisan shader yang efisien, dan rendering pipeline modern.
* [Modul 01: Graphic APIs Core Concepts & Rendering Pipeline](./BAB-04-grafika-shaders-rendering/01-graphics-pipeline-fundamentals.md) - Vertex pulling, primitive assembly, rasterization, framebuffers, dan state management.
* [Modul 02: Shading Languages (HLSL/GLSL) & PBR](./BAB-04-grafika-shaders-rendering/02-hlsl-glsl-pbr-pipeline.md) - Teori Physically Based Rendering: BRDF Cook-Torrance, Roughness, Metallic, dan Fresnel equations.
* [Modul 03: Forward vs Deferred vs Clustered Rendering](./BAB-04-grafika-shaders-rendering/03-deferred-clustered-rendering.md) - G-Buffer management, light culling, compute shader passes, dan dynamic resolution scaling.

### [BAB 05: Audio Teknis, Animasi Skeletal, & Spatial Systems](./BAB-05-audio-animasi-spatial/)
Mengelola pemrosesan audio berlatensi rendah, skeletal skinning, dan algoritma partisi spasial untuk fisika.
* [Modul 01: Spatial Partitioning (BVH, Octrees, Spatial Hashes)](./BAB-05-audio-animasi-spatial/01-spatial-partitioning-bvh.md) - Optimasi deteksi tabrakan (broadphase collision detection) dan frustum culling.
* [Modul 02: Skeletal Mesh Animation & Inverse Kinematics](./BAB-05-audio-animasi-spatial/02-skeletal-animation-ik.md) - Matrix palette skinning, dual quaternion skinning, Two-Bone IK, dan FABRIK.
* [Modul 03: Technical Audio Pipelines & Digital Signal Processing](./BAB-05-audio-animasi-spatial/03-audio-dsp-spatialization.md) - Audio buffers, convolution reverb, HRTF 3D spatialization, dan dynamic ducking.

### [BAB 06: Gameplay AI Terapan & Sistem Status Reaktif](./BAB-06-gameplay-ai-state-systems/)
Membangun kecerdasan buatan musuh dan karakter otonom yang efisien dan responsif terhadap perubahan lingkungan.
* [Modul 01: State Machines & Hierarchical State Machines (HFSM)](./BAB-06-gameplay-ai-state-systems/01-hfsm-state-pattern.md) - Struktur status karakter non-alokatif, deterministik, dan bebas memori leak.
* [Modul 02: Behavior Trees & Goal-Oriented Action Planning (GOAP)](./BAB-06-gameplay-ai-state-systems/02-behavior-trees-goap.md) - Blackboard systems, composable conditional nodes, dan dynamic A* action-graph planning.
* [Modul 03: Spatial Pathfinding & Dynamic NavMesh Navigation](./BAB-06-gameplay-ai-state-systems/03-navmesh-pathfinding.md) - Recast/Detour architecture, funneled path smoothing, dan local steering behaviors (RVO).

### [BAB 07: Arsitektur Jaringan Real-Time & Sinkronisasi State](./BAB-07-arsitektur-jaringan-multiplayer/)
Membangun game multiplayer kompetitif yang tangguh menghadapi kondisi jaringan publik yang fluktuatif.
* [Modul 01: UDP Layer, Reliable-UDP, & Packet Serialization](./BAB-07-arsitektur-jaringan-multiplayer/01-udp-custom-packet-serialization.md) - Bit-packing, delta compression, packet loss mitigation, dan bandwidth throttling.
* [Modul 02: Client-Side Prediction & Server Reconciliation](./BAB-07-arsitektur-jaringan-multiplayer/02-client-prediction-reconciliation.md) - Deterministic input buffering, server authoritative physics, dan error reconciliation snapping.
* [Modul 03: Entity Interpolation, Extrapolation, & Lag Compensation](./BAB-07-arsitektur-jaringan-multiplayer/03-interpolation-lag-compensation.md) - Snapshot buffering, time-travel collision rewind, dan jitter buffers.

### [BAB 08: Engine Tooling, Pipeline Aset, & Serialisasi Data](./BAB-08-engine-tooling-pipeline-aset/)
Membangun toolset produksi, format file kustom, dan pipeline kompilasi aset untuk pengembang konten.
* [Modul 01: Asset Baking, Cooker, & Custom Binary Formats](./BAB-08-engine-tooling-pipeline-aset/01-asset-baking-binary-formats.md) - Mengubah JSON/FBX menjadi flattened memory-mapped binary payloads siap konsumsi CPU/GPU.
* [Modul 02: In-Game Tooling, Dear ImGui, & Reflection Systems](./BAB-08-engine-tooling-pipeline-aset/02-imgui-engine-reflection.md) - Compile-time/Runtime type reflection, live property editing, dan editor viewport orchestration.
* [Modul 03: Hot-Reloading Systems & Live Compilation](./BAB-08-engine-tooling-pipeline-aset/03-hot-reload-dynamic-libraries.md) - Dynamic link library (DLL) swapping saat game berjalan tanpa memutus memori state game.

### [BAB 09: Profiling Komputasi, SIMD, & Optimasi Hardware](./BAB-09-profiling-simd-optimasi-hardware/)
Mengidentifikasi bottleneck hardware dan memaksimalkan pemanfaatan arsitektur prosesor modern.
* [Modul 01: Frame Budgeting, CPU Profiling, & GPU Tracing](./BAB-09-profiling-simd-optimasi-hardware/01-frame-budget-tracy-profiler.md) - Integrasi Tracy Profiler, RenderDoc, identifying pipeline stalls, dan sync points.
* [Modul 02: Vektorisasi SIMD (Single Instruction Multiple Data)](./BAB-09-profiling-simd-optimasi-hardware/02-simd-vectorization-intrinsics.md) - Instruksi SSE/AVX/NEON untuk operasi transformasi matriks dan partikel massal.
* [Modul 03: Multithreading & Work Stealing Job Systems](./BAB-09-profiling-simd-optimasi-hardware/03-job-system-work-stealing.md) - Fiber-based architecture, lock-free queues, eliminasi deadlocks, dan load balancing core CPU.

### [BAB 10: Pipeline Produksi Enterprise, Anti-Cheat, & LiveOps](./BAB-10-enterprise-ci-cd-anti-cheat/)
Menghubungkan rekayasa internal game dengan kebutuhan operasional skala enterprise dan peluncuran produk.
* [Modul 01: Automated CI/CD, Headless Testing, & Build Pipelines](./BAB-10-enterprise-ci-cd-anti-cheat/01-ci-cd-headless-builds.md) - Headless server builds, automated unit/integration testing pada dedicated GPU runners.
* [Modul 02: Client-Server Anti-Cheat & Memory Integrity Checks](./BAB-10-enterprise-ci-cd-anti-cheat/02-anti-cheat-memory-integrity.md) - Memverifikasi integritas memori, server-side simulation sanity checking, dan proteksi replay attack.
* [Modul 03: Crash Telemetry, Performance Metrics, & Hotfix Deployments](./BAB-10-enterprise-ci-cd-anti-cheat/03-telemetry-liveops-hotfixes.md) - Minidump analysis via symbol servers, live error aggregation, dynamic asset patching.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title: *Aethelgard: Networked 3D Action-RPG Simulation Engine*

Siswa diwajibkan membangun *vertical slice* dari sebuah simulasi 3D Action RPG multipemain terdistribusi secara *from scratch* (atau menggunakan Custom Engine Architecture berbasis C++ / Modern C# / Rust) yang mendemonstrasikan implementasi seluruh bab dalam silabus ini.

#### Persyaratan Arsitektural & Teknis:
1. **Low-Level Simulation & Memory:**
   * Tidak boleh menggunakan alokasi memori dinamis runtime (`malloc`, `new`, dsb.) di dalam loop gameplay utama.
   * Harus mengimplementasikan custom Arena/Stack Allocator khusus gameplay loop dengan penegakan zero per-frame garbage.
2. **Rendering Pipeline:**
   * Pipeline Deferred/Clustered kustom yang mampu menangani minimal **500 sumber cahaya dinamis serentak** pada stabil 60 FPS pada kartu grafis kelas menengah (mis. RTX 3060).
   * PBR Shading Model dengan cascaded shadow maps (CSM).
3. **Multiplayer Networking Engine:**
   * Arsitektur Server-Authoritative beroperasi melalui protocol UDP kustom.
   * Implementasi Client-Side Prediction dengan Server Reconciliation deterministik.
   * Lag Compensation berbasis Historical Snapshot Rewind untuk deteksi tabrakan proyektil/serangan jarak dekat.
4. **Gameplay & AI:**
   * Minimum 50 agen musuh otonom simultan yang digerakkan oleh Goal-Oriented Action Planning (GOAP) dan NavMesh A* Pathfinding dengan Dynamic Local Avoidance (RVO).
   * Hierarchical State Machine (HFSM) untuk pengendalian karakter utama dengan transisi animasi berbasis Root Motion & Inverse Kinematics (IK).

#### Batasan Layanan & Service-Level Agreement (SLA):
* **CPU Target:** < 10.0 ms per simulation frame pada 4-core base host.
* **Network Throughput:** < 64 KB/sec per client snapshot bandwidth budget.
* **Server Tickrate:** Fixed 60 Hz deterministik dengan drift clock < 1ms.

#### Definition of Done (DoD) Pengujian Proyek:
1. Menyerahkan laporan profiling menggunakan **Tracy / RenderDoc** yang membuktikan frame time di bawah 16,6 ms dan tidak adanya heap allocation di dalam runtime loop.
2. Melakukan simulasi pengujian jaringan (*network condition simulation*) dengan **150ms latency dan 5% packet loss**: karakter harus tetap dapat bermanuver mulus tanpa desinkronisasi (*teleport/rubberbanding*) ekstrem berkat client reconciliation.
3. Seluruh unit testing, static analysis, dan binary packaging terintegrasi secara otomatis via skrip CI/CD headless runner.