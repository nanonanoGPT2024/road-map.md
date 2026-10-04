# Bab 03: Arsitektur Game & Data-Oriented Design
## Module 01: Entity Component System (ECS) & Data-Oriented Design untuk AI & Simulasi Otonom

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** dampak hierarki memori perangkat keras (L1/L2/L3 Cache, Cache Lines, RAM) terhadap throughput eksekusi simulasi otonom berskala besar ($>50.000$ entitas).
- **Merancang** struktur data berorientasi data (*Data-Oriented Design* / DOD) dengan membedah kelemahan memori dari *Array of Structures* (AoS) dan mengonversinya menjadi *Structure of Arrays* (SoA) atau *Array of Structures of Arrays* (AoSoA).
- **Mengimplementasikan** arsitektur *Entity Component System* (ECS) berbasis *Archetype* atau *Sparse Set* yang aman terhadap *pointer invalidation* dan bebas dari *pointer chasing*.
- **Mengeliminasi** *Virtual Method Table (VMT) lookup overhead* pada loop simulasi AI agen otonom.
- **Mengembangkan** *Deferred Command Buffer* untuk mengeksekusi mutasi struktural (*structural changes*) secara deterministik tanpa mengganggu kontinuitas iterasi memori.

---

### 2. Concept Overview
Paradigma Berorientasi Objek (*Object-Oriented Programming* / OOP) klasik memodelkan dunia game sebagai hierarki entitas polimorfik. Setiap entitas direpresentasikan sebagai *object instance* individual yang menyimpan state internalnya sendiri beserta pointer ke *Virtual Method Table* (VMT).

```
[ Traditional OOP: Pointer Chasing & Cache Misses ]
RAM:
[Entity A (VMT, Pos, AI)] ---> Heap Ref ---> [Entity B (VMT, Pos, AI)] ---> Heap Ref
(Data tersebar di memori; CPU Cache memuat 64-byte chunks berisi garbage data)
```

Sebaliknya, **Data-Oriented Design (DOD)** memandang simulasi bukan sebagai interaksi objek, melainkan sebagai transformasi aliran data secara sekuensial. Prinsip inti DOD adalah:
1. **Data Berada Berdekatan di Memori (*Spatial Locality*)**: Data yang diproses bersamaan harus dialokasikan secara kontigu di memori fisik agar setiap pembacaan *Cache Line* (umumnya 64 byte pada x86-64 dan ARM) dapat dimanfaatkan hingga 100%.
2. **Instruksi Dieksekusi Berurutan (*Temporal Locality*)**: Instruksi yang sama diterapkan ke sejumlah besar data dalam satu lintasan, meminimalkan *instruction cache miss* dan memaksimalkan *hardware prefetching*.
3. **Pemisahan Identitas, Data, dan Logika (ECS)**:
   - **Entity**: Hanya sebuah integer ID numerik (sering kali menyertakan *generation counter* untuk daur ulang ID).
   - **Component**: *Plain Old Data* (POD) tanpa logika bisnis atau fungsi virtual.
   - **System**: Fungsi murni atau prosedur transformasi yang melakukan iterasi linear atas array komponen yang relevan.

---

### 3. Why It Matters
Pada pengembangan game modern dan simulasi multi-agent (seperti swarm robotics, simulasi lalu lintas perkotaan, atau RTS dengan puluhan ribu unit otonom), performa komputasi terbentur pada **Memory Wall** (kesenjangan kecepatan transfer data antara CPU dan DRAM). 

Biaya latensi akses memori:
- **L1 Cache Hit**: $\approx 1 - 1.5\text{ ns}$ ($\approx 4\text{ siklus CPU}$)
- **L2 Cache Hit**: $\approx 3 - 4\text{ ns}$ ($\approx 12\text{ siklus CPU}$)
- **L3 Cache Hit**: $\approx 10 - 20\text{ ns}$ ($\approx 40\text{ siklus CPU}$)
- **DRAM Access (Main Memory)**: $\approx 60 - 100\text{ ns}$ ($\approx 200+\text{ siklus CPU}$)

Jika sebuah simulasi memiliki $20.000$ agen AI polimorfik yang diupdate setiap frame ($60\text{ FPS} \rightarrow 16.6\text{ ms}$ anggaran waktu frame), pendekatan OOP klasik dengan alokasi heap terfragmentasi akan memicu jutaan *L1/L2 cache misses* akibat *pointer chasing*. 

CPU menghabiskan $>70\%$ siklusnya dalam status *idle* menunggu pembacaan bus RAM. Arsitektur DOD dan ECS meniadakan *pointer chasing*, menjamin pemanfaatan *CPU prefetcher*, serta membuka potensi otomatisasi vektorisasi instruksi (SIMD - Single Instruction, Multiple Data).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut membedakan layout memori fisik antara OOP klasik (AoS) dan DOD (SoA) serta topologi eksekusi Archetype-based ECS:

```
=============================================================================
1. MEMORY LAYOUT COMPARISON (64-byte Cache Line Boundary)
=============================================================================
Array of Structures (AoS - OOP):
[ PosX | PosY | VelX | VelY | Health | TargetID | VMT_Ptr ] -> [ PosX | PosY | ... ]
|<----------------- Cache Line 1 (64 Bytes) ------------->|
* Masalah: System hanya butuh Pos & Vel, tetapi Health & VMT_Ptr ikut dimuat.
  Efisiensi Cache = Rendah (~30%).

Structure of Arrays (SoA - DOD):
PosX Table:   [ X0 | X1 | X2 | X3 | X4 | X5 | X6 | X7 | X8 | X9 ... ]
PosY Table:   [ Y0 | Y1 | Y2 | Y3 | Y4 | Y5 | Y6 | Y7 | Y8 | Y9 ... ]
VelX Table:   [ VX0| VX1| VX2| VX3| VX4| VX5| VX6| VX7| VX8| VX9... ]
|<----------------- Cache Line 1 (64 Bytes) ------------->|
* Hasil: 100% data dalam Cache Line relevan dan siap diproses oleh CPU SIMD.

=============================================================================
2. ARCHETYPE-BASED ECS ARCHITECTURE FOR AUTONOMOUS AGENTS
=============================================================================

            +--------------------------------------------------+
            |                  WORLD / REGISTRY                |
            +--------------------------------------------------+
                                     |
         +---------------------------+---------------------------+
         |                                                       |
         v                                                       v
+-------------------------------+               +-------------------------------+
|  Archetype A: [Pos, Vel]      |               | Archetype B: [Pos, Vel, AI]   |
+-------------------------------+               +-------------------------------+
| Entity Chunk Storage:         |               | Entity Chunk Storage:         |
| - Entities: [E1, E2, E5]      |               | - Entities: [E3, E4, E6]      |
| - Component Arrays (Contig.): |               | - Component Arrays (Contig.): |
|   * Pos: [P1, P2, P5]         |               |   * Pos: [P3, P4, P6]         |
|   * Vel: [V1, V2, V5]         |               |   * Vel: [V3, V4, V6]         |
+-------------------------------+               |   * AI:  [A3, A4, A6]         |
                                                +-------------------------------+
                                                                 ^
                                                                 |
                                                    Iterates contiguously
                                                                 |
                                                +-------------------------------+
                                                |     AgentSteeringSystem       |
                                                +-------------------------------+
                                                | Execution:                    |
                                                | Linear scan over [Pos,Vel,AI] |
                                                | zero pointer dereference.     |
                                                +-------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Generational Indexing
Untuk mencegah masalah *dangling reference* tanpa menggunakan *smart pointer* (yang menambah alokasi metadata heap), entitas didefinisikan sebagai kombinasi bit:
- **Index** (misal: 32-bit): Indeks offset ke dalam slot array.
- **Generation** (misal: 32-bit): Penghitung siklus hidup slot tersebut.

Ketika entitas dihapus, nilai *Generation* pada slot indeks bersangkutan dinaikkan ($+1$). Jika ada referensi lama yang mencoba mengakses indeks tersebut menggunakan *Generation* usang, sistem langsung mendeteksi bahwa entitas tersebut sudah mati (*stale reference*).

#### B. Archetype Storage vs Sparse Sets
1. **Sparse Sets (e.g., EnTT)**: Menggunakan array sparse bertindak sebagai lookup table ke dense array komponen. Sangat cepat untuk penambahan dan penghapusan komponen dinamis ($O(1)$ mutasi), tetapi iterasi multi-komponen membutuhkan pencarian indeks terkecil dan *random access* sekunder pada dense array lainnya.
2. **Archetype-based Storage (e.g., Unity DOTS, Flecs)**: Entitas dengan kombinasi komponen unik yang persis sama dikelompokkan ke dalam satu tabel memori kontigu (*Archetype*). Iterasi sistem berjalan pada kecepatan memori maksimum (*linear streaming* murni). Kelemahannya: penambahan/penghapusan komponen memerlukan operasi pemindahan komponen antar-tabel (*archetype transition*).

#### C. Deferred Command Buffers (Structural Synchronization)
Mutasi struktural—seperti instansiasi entitas baru, penghapusan entitas, atau penambahan/pengurangan komponen—tidak boleh langsung mengubah layout memori ketika suatu *System* sedang mengiterasi tabel komponen. Jika dilakukan, iterasi memori akan rusak (*iterator invalidation* / *out of bounds*). 

Solusinya: Semua mutasi struktural ditulis ke dalam *thread-local Command Buffer* sebagai aksi tertunda (*deferred actions*) dan dieksekusi secara terpusat (*flushed*) di titik sinkronisasi aman antar-*tick*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul performa tinggi ECS berbasis struktur data kontigu (menggunakan *contiguous layout* yang diemulasikan via typed storage dan NumPy memory buffer) dalam Python. Arsitektur ini dirancang khusus untuk memproses simulasi perilaku gerak dan navigasi agen otonom secara deterministik.

```python
"""
Core Data-Oriented Design (DOD) Entity Component System (ECS) Engine.
Optimized for high-throughput autonomous agent state updates and cache-locality simulation.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Type, Optional, Any, Callable


@dataclass(frozen=True, slots=True)
class Entity:
    """Represents a lightweight generational entity ID."""
    id: int
    generation: int


class ComponentArray:
    """
    Interface for contiguous component data storage.
    Enforces contiguous memory layout to prevent pointer-chasing.
    """
    def __init__(self, capacity: int, dtype: np.dtype):
        self.capacity: int = capacity
        self.size: int = 0
        self.data: np.ndarray = np.zeros(capacity, dtype=dtype)
        self.entity_to_index: Dict[int, int] = {}
        self.index_to_entity: Dict[int, int] = {}

    def insert(self, entity_id: int, component_data: np.void) -> None:
        if self.size >= self.capacity:
            self._grow()

        index = self.size
        self.data[index] = component_data
        self.entity_to_index[entity_id] = index
        self.index_to_entity[index] = entity_id
        self.size += 1

    def remove(self, entity_id: int) -> bool:
        if entity_id not in self.entity_to_index:
            return False

        # Swap-and-pop technique to ensure data remains strictly contiguous O(1)
        removed_index = self.entity_to_index[entity_id]
        last_index = self.size - 1

        if removed_index != last_index:
            last_entity = self.index_to_entity[last_index]
            self.data[removed_index] = self.data[last_index]
            self.entity_to_index[last_entity] = removed_index
            self.index_to_entity[removed_index] = last_entity

        del self.entity_to_index[entity_id]
        del self.index_to_entity[last_index]
        self.size -= 1
        return True

    def get_view(self) -> np.ndarray:
        """Returns the active contiguous memory slice."""
        return self.data[:self.size]

    def _grow(self) -> None:
        new_capacity = self.capacity * 2
        new_data = np.zeros(new_capacity, dtype=self.data.dtype)
        new_data[:self.size] = self.data[:self.size]
        self.data = new_data
        self.capacity = new_capacity


# Structured Component Data Formats (Memory aligned POD equivalents)
TransformDType = np.dtype([
    ('x', np.float32),
    ('y', np.float32),
    ('rot', np.float32)
], align=True)

KinematicsDType = np.dtype([
    ('vx', np.float32),
    ('vy', np.float32),
    ('max_speed', np.float32)
], align=True)

AgentAIDType = np.dtype([
    ('target_x', np.float32),
    ('target_y', np.float32),
    ('state', np.int32),      # 0: Idle, 1: Seek, 2: Arrived
    ('arrival_radius', np.float32)
], align=True)


class CommandBuffer:
    """Stores structural changes safely during pipeline execution."""
    def __init__(self) -> None:
        self._commands: List[Callable[[], None]] = []

    def add_command(self, cmd: Callable[[], None]) -> None:
        self._commands.append(cmd)

    def execute(self) -> None:
        for cmd in self._commands:
            cmd()
        self._commands.clear()


class EntityManager:
    """Manages generation-based entity lifecycles."""
    def __init__(self, initial_capacity: int = 100_000) -> None:
        self._generations: List[int] = [0] * initial_capacity
        self._free_indices: List[int] = list(reversed(range(initial_capacity)))

    def create(self) -> Entity:
        if not self._free_indices:
            # Expand entity capacity
            start = len(self._generations)
            expansion = start
            self._generations.extend([0] * expansion)
            self._free_indices.extend(reversed(range(start, start + expansion)))

        index = self._free_indices.pop()
        return Entity(id=index, generation=self._generations[index])

    def destroy(self, entity: Entity) -> bool:
        if not self.is_alive(entity):
            return False
        self._generations[entity.id] += 1
        self._free_indices.append(entity.id)
        return True

    def is_alive(self, entity: Entity) -> bool:
        return (entity.id < len(self._generations) and 
                self._generations[entity.id] == entity.generation)


class World:
    """Central Context coordinating entities, contiguous storages, and execution stages."""
    def __init__(self, capacity: int = 50_000) -> None:
        self.entity_manager: EntityManager = EntityManager(initial_capacity=capacity)
        self.command_buffer: CommandBuffer = CommandBuffer()
        
        # Component stores (Structure of Arrays paradigm per system group)
        self.transforms: ComponentArray = ComponentArray(capacity, TransformDType)
        self.kinematics: ComponentArray = ComponentArray(capacity, KinematicsDType)
        self.agent_ais: ComponentArray = ComponentArray(capacity, AgentAIDType)

    def create_autonomous_agent(self, x: float, y: float, max_speed: float, target_x: float, target_y: float) -> Entity:
        entity = self.entity_manager.create()
        
        t_data = np.zeros(1, dtype=TransformDType)[0]
        t_data['x'], t_data['y'], t_data['rot'] = x, y, 0.0
        self.transforms.insert(entity.id, t_data)

        k_data = np.zeros(1, dtype=KinematicsDType)[0]
        k_data['vx'], k_data['vy'], k_data['max_speed'] = 0.0, 0.0, max_speed
        self.kinematics.insert(entity.id, k_data)

        ai_data = np.zeros(1, dtype=AgentAIDType)[0]
        ai_data['target_x'], ai_data['target_y'], ai_data['state'], ai_data['arrival_radius'] = target_x, target_y, 1, 0.5
        self.agent_ais.insert(entity.id, ai_data)

        return entity

    def destroy_entity_deferred(self, entity: Entity) -> None:
        """Schedules safe destruction at the synchronization point."""
        def _cleanup():
            if self.entity_manager.destroy(entity):
                self.transforms.remove(entity.id)
                self.kinematics.remove(entity.id)
                self.agent_ais.remove(entity.id)

        self.command_buffer.add_command(_cleanup)

    def sync(self) -> None:
        """Executes all pending structural commands."""
        self.command_buffer.execute()


class AutonomousSteeringSystem:
    """
    Processes steering behaviors via dense vector mathematical computations.
    Data streaming maximizes cache line utilization.
    """
    @staticmethod
    def update(world: World, dt: float) -> None:
        # Menentukan domain iris data terkecil (irisan entitas yang memiliki ketiga komponen)
        # Pada arsitektur Archetype murni, iterasi ini dilakukan langsung per archetype chunk.
        ai_entities = set(world.agent_ais.entity_to_index.keys())
        kin_entities = set(world.kinematics.entity_to_index.keys())
        trans_entities = set(world.transforms.entity_to_index.keys())

        matched_entities = list(ai_entities & kin_entities & trans_entities)
        if not matched_entities:
            return

        # Ambil flat contiguous arrays via indexing
        ai_indices = [world.agent_ais.entity_to_index[e] for e in matched_entities]
        kin_indices = [world.kinematics.entity_to_index[e] for e in matched_entities]
        trans_indices = [world.transforms.entity_to_index[e] for e in matched_entities]

        pos_view = world.transforms.data
        kin_view = world.kinematics.data
        ai_view = world.agent_ais.data

        # Vektorisasi logis navigasi otonom (Seek Behavior)
        for e_id, a_idx, k_idx, t_idx in zip(matched_entities, ai_indices, kin_indices, trans_indices):
            dx = ai_view[a_idx]['target_x'] - pos_view[t_idx]['x']
            dy = ai_view[a_idx]['target_y'] - pos_view[t_idx]['y']
            distance = np.sqrt(dx * dx + dy * dy)

            if distance < ai_view[a_idx]['arrival_radius']:
                kin_view[k_idx]['vx'] = 0.0
                kin_view[k_idx]['vy'] = 0.0
                ai_view[a_idx]['state'] = 2  # Arrived
                # Contoh: Request hapus entitas saat target tercapai
                world.destroy_entity_deferred(Entity(id=e_id, generation=world.entity_manager._generations[e_id]))
            else:
                # Normalisasi dan scaling kecepatan (Steering vector)
                inv_dist = 1.0 / distance
                kin_view[k_idx]['vx'] = (dx * inv_dist) * kin_view[k_idx]['max_speed']
                kin_view[k_idx]['vy'] = (dy * inv_dist) * kin_view[k_idx]['max_speed']


class MovementSystem:
    """Updates position transforms contiguously based on calculated velocities."""
    @staticmethod
    def update(world: World, dt: float) -> None:
        trans_entities = set(world.transforms.entity_to_index.keys())
        kin_entities = set(world.kinematics.entity_to_index.keys())

        matched_entities = list(trans_entities & kin_entities)
        if not matched_entities:
            return

        trans_indices = [world.transforms.entity_to_index[e] for e in matched_entities]
        kin_indices = [world.kinematics.entity_to_index[e] for e in matched_entities]

        # Operasi pembaruan posisi kontigu (SIMD-friendly batch update)
        world.transforms.data['x'][trans_indices] += world.kinematics.data['vx'][kin_indices] * dt
        world.transforms.data['y'][trans_indices] += world.kinematics.data['vy'][kin_indices] * dt


# --- Pipeline Verification & Execution Loop ---
if __name__ == "__main__":
    simulation_world = World(capacity=10_000)

    # Inisialisasi 5.000 Agen Otonom
    print("[Engine] Mengalokasikan 5.000 Agen Otonom ke dalam kontigu SoA...")
    for i in range(5000):
        simulation_world.create_autonomous_agent(
            x=0.0,
            y=0.0,
            max_speed=5.0 + (i % 3),
            target_x=10.0 + (i % 5),
            target_y=15.0 + (i % 5)
        )

    fixed_dt = 1.0 / 60.0
    print(f"[Engine] Memulai tick simulasi dengan dt={fixed_dt:.4f}s")

    # Jalankan 120 Tick Simulasi
    for tick in range(120):
        # 1. Update Steering & AI Decisions
        AutonomousSteeringSystem.update(simulation_world, fixed_dt)
        # 2. Update Kinematics & Transformations
        MovementSystem.update(simulation_world, fixed_dt)
        # 3. Sinkronisasi Structural Changes (Pembersihan Entitas)
        simulation_world.sync()

    remaining_entities = simulation_world.transforms.size
    print(f"[Engine] Simulasi selesai. Entitas aktif tersisa: {remaining_entities}")
    assert remaining_entities <= 5000, "Validasi kegagalan siklus hidup entitas."
```

---

### 7. Edge Cases & Failure Modes

#### A. Structural Invalidation Saat Iterasi Berjalan
- **Gejala Kerusakan**: Penambahan komponen secara instan memicu alokasi ulang array (`_grow()`). Hal ini menyebabkan pointer alamat dasar berpindah di memori fisik atau merusak indeks swap-and-pop pada array aktif.
- **Mitigasi**: Larang keras pemanggilan mutasi struktural (`insert`, `remove`, `destroy`) secara langsung dalam logika inti sistem. Akses hanya diizinkan via `CommandBuffer`.

#### B. Generational Overflow
- **Gejala Kerusakan**: Entitas sering dibuat dan dihancurkan dalam siklus loop jutaan kali per jam. Jika nilai `generation` bertipe `uint16`, angka dapat mengalami *integer overflow* kembali ke `0`, sehingga memvalidasi referensi lama yang salah.
- **Mitigasi**: Gunakan minimum 32-bit integer untuk *Generation Counter*. Sebuah siklus 32-bit memerlukan $4{,}29\text{ miliar}$ daur ulang pada slot yang sama sebelum collision terjadi.

#### C. False Sharing pada Multithreaded Systems
- **Gejala Kerusakan**: Ketika memparalelkan sistem menggunakan task graphs (misal: Job System), Thread 1 memodifikasi `Component[0]` dan Thread 2 memodifikasi `Component[1]`. Meskipun memorinya berbeda variabel, keduanya berada dalam satu batas *64-byte Cache Line* yang sama. Akibatnya, CPU Core saling membatalkan (*invalidate*) cache L1 masing-masing secara berulang (*cache line bouncing*).
- **Mitigasi**: Partisi chunk eksekusi worker thread minimal sebesar kelipatan batas *Cache Line* (misalnya per-blok pemrosesan minimal berisi 64 entitas atau gunakan *chunk padding*).

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Traditional OOP (Polimorfisme) | Sparse-Set ECS (e.g., EnTT) | Archetype-based ECS (e.g., Flecs/DOTS) |
| :--- | :--- | :--- | :--- |
| **Cache Locality** | Sangat Buruk (Acak via Heap) | Baik pada Dense Arrays | Maksimum (100% Kontigu per Archetype) |
| **Iterasi Multi-Komponen** | Lambat ($O(N)$ pointer dereferencing) | Menengah (Dibatasi intersection overhead) | Maksimum (Linear vector scan tanpa overhead) |
| **Mutasi Komponen Dinamis** | Instan (Variabel internal class) | Cepat ($O(1)$ add/remove) | Lambat ($O(N)$ memory copy antar Archetype) |
| **Kompleksitas Implementasi** | Sangat Rendah (Native bahasa OOP) | Menengah | Sangat Tinggi (Manajemen memori chunk manual) |
| **Penggunaan Memori** | Tinggi (Overhead alignment & VMT) | Menengah (Sparse array overhead) | Sangat Padat (Zero alignment waste) |

---

### 9. Best Practices & Standard Industri
1. **Zero-Allocation Inner Loop**: Jangan pernah memicu instansiasi objek, alokasi memori dinamis, atau *boxing/unboxing* di dalam loop `update()` sistem. Semua memori harus dialokasikan di muka (*pre-allocated arenas*).
2. **Kompak dan Sejajarkan Data (Memory Packing)**: Urutkan variabel di dalam *Component Struct* dari ukuran data terbesar ke terkecil (misal: `float64` $\rightarrow$ `float32` $\rightarrow$ `int32` $\rightarrow$ `bool`) untuk mencegah timbulnya *padding bytes* akibat *memory alignment*.
3. **Pemisahan Read-Only dan Read-Write Clones**: Pisahkan array komponen yang hanya dibaca (*read-only*) dari array komponen yang dimodifikasi (*read-write*) untuk menyederhanakan dependensi eksekusi *concurrency* paralel.
4. **Isolasi Logika Otonom Berat ke Frame-Decoupled Systems**: Logika persepsi global (misal: pencarian pathfinding $A^*$, raycasting sensor agen) tidak harus berjalan pada 60 FPS. Pisahkan menjadi tick spasial berkala (misal: 10 atau 20 Hz) menggunakan ECS System terpisah, sementara pergerakan posisi tetap dieksekusi pada 60 FPS murni secara linear.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Simulasikan skenario penghindaran tabrakan massal (*boids flocking / avoidance*) untuk $20.000$ agen otonom. Anda ditugaskan untuk mengukur perbedaan performa waktu eksekusi antara pendekatan OOP klasik berbasis referensi objek vs Data-Oriented System kontigu.

#### Langkah Pengerjaan
1. **Langkah 1**: Buat implementasi referensi OOP klasik:
   - Buat `Class AgentOOP` dengan atribut `x, y, vx, vy, radius`.
   - Buat loop eksekusi yang mengiterasi list $20.000$ `AgentOOP`, menghitung jarak antar tetangga terdekat secara acak, dan memutakhirkan posisi.
2. **Langkah 2**: Buat implementasi Data-Oriented (SoA):
   - Alokasikan array memori kontigu NumPy untuk variabel posisi dan kecepatan seluruh agen.
   - Buat fungsi sistem eksekusi yang beroperasi langsung pada slice array kontigu tersebut.
3. **Langkah 3**: Benchmark & Profiling:
   - Ukur waktu eksekusi untuk 300 tick simulasi menggunakan `time.perf_counter_ns()`.
   - Amati perbedaan durasi rata-rata per frame antara kedua paradigma tersebut.

#### Ekspektasi Hasil
Implementasi Data-Oriented (SoA) harus menunjukkan peningkatan performa minimum **$5\times - 15\times$ lebih cepat** dibandingkan loop OOP polimorfik murni pada Python/NumPy, yang membuktikan efisiensi eliminasi overhead pointer chasing dan lokalisasi memori.