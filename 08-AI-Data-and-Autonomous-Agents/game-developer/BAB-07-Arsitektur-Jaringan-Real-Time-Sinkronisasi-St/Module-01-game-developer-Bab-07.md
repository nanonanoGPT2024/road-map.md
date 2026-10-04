# Bab 07: Arsitektur Jaringan Real-Time & Sinkronisasi State

## 1. Learning Objectives
Setelah menyelesaikan bab ini, Anda diharapkan mampu:
- **Menganalisis dan Memilih Paradigma Jaringan**: Mengevaluasi trade-off antara *Authoritative Client-Server*, *Deterministic Lockstep*, dan *Distributed State Synchronization* untuk skenario game multiplayer kompetitif dan simulasi AI multi-agent skala besar.
- **Mengimplementasikan Client-Side Prediction & Server Reconciliation**: Merancang arsitektur loop simulasi di sisi klien yang memprediksi state lokal, menyimpan riwayat input/state, dan merekonsiliasi deviasi saat server menolak atau mengoreksi simulasi.
- **Membangun Sistem Snapshot Interpolation & Dead Reckoning**: Mengembangkan algoritma interpolasi snapshot dengan buffering dinamis berbasis jitter, serta algoritma ekstrapolasi berbasis fisika untuk entitas non-lokal dan autonomous agent.
- **Mengoptimalkan Throughput dengan Delta Compression & Quantization**: Mengurangi beban bandwidth menggunakan teknik bit-packing, quantizing floating-point vectors, dan spatial interest management (AOI - Area of Interest).
- **Mengintegrasikan Agen Otonom (Autonomous Agents)**: Menangani sinkronisasi status AI perilaku tinggi (seperti behavior trees atau policy-based agents) secara terdistribusi tanpa membebani throughput jaringan secara eksponensial.

---

## 2. Concept Overview
Komunikasi real-time dalam arsitektur game terdistribusi berakar pada fakta tak terelakkan: **kecepatan cahaya adalah batasan fundamental**. Informasi membutuhkan waktu untuk berpindah antara node ($RTT > 0$), paket data dapat hilang (*packet loss*), dan variasi latensi (*jitter*) akan merusak kontinuitas simulasi jika tidak dimitigasi.

### Mental Model: Paradigma Sinkronisasi
State game pada waktu fisik $t$ di node $A$ tidak akan pernah identik secara instan dengan state di node $B$. Oleh karena itu, arsitektur sinkronisasi game bergeser dari model "menyamakan state setiap saat" menjadi **"merekayasa ilusi konsistensi waktu nyata"**.

```
[INPUT DRIVEN] -----------------------------------------------------> [STATE DRIVEN]
Deterministic Lockstep                               Snapshot Interpolation
- Bandwidth: Sangat Rendah ($O(\text{Inputs})$)      - Bandwidth: Tinggi ($O(\text{Entities})$)
- Latensi: Bergantung pada klien terlambat            - Latensi: Terisolasi antar-klien
- Determinisme: Mutlak (Float IEEE-754 sama)          - Determinisme: Relatif toleran
```

Tiga pilar utama arsitektur sinkronisasi real-time modern:
1. **Authoritative Server**: Server adalah sumber kebenaran tunggal (*single source of truth*). Klien hanya mengirimkan *input* (atau intent), bukan state posisi/kesehatan. Server menjalankan simulasi, memvalidasi aturan fisika dan gameplay, lalu memancarkan state kembali ke klien.
2. **Client-Side Prediction (CSP)**: Untuk menghilangkan persepsi input lag lokal, klien langsung menerapkan input pemain lokal ke state lokalnya tanpa menunggu otorisasi dari server.
3. **Server Reconciliation**: Ketika update state resmi dari server tiba, klien memeriksa apakah state yang diprediksi sebelumnya pada tick tersebut cocok dengan snapshot server. Jika terjadi deviasi (akibat tabrakan, intervensi AI, atau *packet drop*), klien melakukan *rewind* ke tick server dan memutar ulang (*replay*) seluruh input yang belum diakui (*unacknowledged inputs*).

---

## 3. Why It Matters
Dalam konteks game modern berskala enterprise—terutama yang mengintegrasikan agen AI otonom (NPC berbasis ML atau Finite State Machines kompleks)—arsitektur jaringan yang naif akan menghasilkan kegagalan kritis:
- **Eksploitasi dan Cheating**: Arsitektur peer-to-peer atau klien non-otoritatif memungkinkan injeksi memori (misalnya *speedhack*, *teleportation*, dan *god mode*).
- **Desinkronisasi Simulasi AI**: Jika server dan klien menjalankan AI non-deterministik, agen dapat membelok ke arah yang berbeda pada tiap mesin, menghancurkan integritas taktis.
- **Bandwidth Saturation**: Memancarkan state seluruh entitas ($N$) ke semua klien ($N$) menyebabkan kompleksitas data $O(N^2)$. Tanpa *Area of Interest* (AOI) dan *Delta Compression*, server akan mengalami *buffer bloat* dan *packet drop* masif di tingkat kernel socket.
- **Pengalaman Pengguna yang Buruk**: *Rubber-banding* ekstrem atau *hit registration failure* menurunkan retensi pemain secara drastis dalam game kompetitif.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur Authoritative Tick Server dengan Client-Side Prediction, Server Reconciliation, dan Interest Management.

```
       CLIENT ARCHITECTURE                             SERVER ARCHITECTURE
+-------------------------------+              +--------------------------------+
| Local Input (Tick T)          |              | Network Layer (UDP/WebTrans)   |
+---------------+---------------+              +---------------+----------------+
                |                                              |
                v                                              v
+-------------------------------+              +--------------------------------+
| Input Buffer & History        |              | Inbound Ring Buffer            |
| (Tick -> Input Record)        |              | (Per-Client Input Queues)      |
+---------------+---------------+              +---------------+----------------+
                |                                              |
                v                                              v
+-------------------------------+              +--------------------------------+
| Client-Side Prediction Engine |              | Authoritative Simulation Tick  |
| - Apply local movement physics|              | - Drain inputs up to Tick S    |
| - Store predicted State(T)    |              | - Tick AI Autonomous Agents    |
+---------------+---------------+              | - Run Physics & Gameplay Logic |
                |                              +---------------+----------------+
                | UDP (Input Packet)                           |
                +----------------------------->                v
                                               +--------------------------------+
                                               | Spatial Partitioning / AOI     |
                                               | (BVH / Grid-based filtering)   |
                                               +---------------+----------------+
                                                               |
                                                               v
                                               +--------------------------------+
                <----------------------------- | Snapshot Generation &          |
                | UDP (Snapshot/Delta Packet)  | Delta Compression (Pack/Quant) |
                v                              +--------------------------------+
+-------------------------------+
| Server Reconciliation &       |
| Snapshot Interpolation        |
| - Verify State(S) vs Server   |
| - If Error > Threshold:       |
|     * Rewind to State(S)      |
|     * Replay unacked inputs   |
| - Remote Entities:            |
|     * Lerp between past ticks |
+-------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1. Clock Synchronization & The Tick Loop
Simulasi real-time bekerja berdasarkan diskritisasi waktu (*tick*), biasanya 60 Hz (16.66ms per tick) pada klien dan 30-128 Hz pada server.
Hubungan antara waktu server ($T_s$) dan waktu klien ($T_c$) dikalibrasi menggunakan modifikasi algoritma Cristian / NTP untuk menghitung Round-Trip Time ($RTT$) dan Clock Offset ($\theta$):

$$\text{RTT} = (t_4 - t_1) - (t_3 - t_2)$$

$$\theta = \frac{(t_2 - t_1) + (t_3 - t_4)}{2}$$

Estimasi moving average yang stabil menggunakan Exponential Moving Average (EMA):

$$\overline{\text{RTT}}_{n} = \alpha \cdot \text{RTT}_{\text{sample}} + (1 - \alpha) \cdot \overline{\text{RTT}}_{n-1}$$

### 5.2. Client-Side Prediction & Server Reconciliation (CSP/SR)
1. **Prediction**: Klien pada tick lokal $k$ membaca input $I_k$, menerapkan formula state transition $S_k = f(S_{k-1}, I_k)$, dan menyimpannya di ring buffer riwayat:
   $$\mathcal{H} = \{ (i, I_i, S_i) \mid k - M \le i \le k \}$$
2. **Transmission**: Klien mengirimkan $I_k$ disertai nomor urut tick $k$ ke server.
3. **Server Processing**: Server memproses $I_k$ saat tiba, menghasilkan state resmi $S^*_k$. Server mengirim balik $(k, S^*_k)$.
4. **Reconciliation**: Klien menerima $(m, S^*_m)$ di mana $m \le k$.
   - Klien mengambil state prediksinya $S_m$ dari $\mathcal{H}$.
   - Dihitung galat deviasi: $\epsilon = \|S_m - S^*_m\|$.
   - Jika $\epsilon > \text{threshold}$, terjadi koreksi:
     $$S_m \leftarrow S^*_m$$
     Untuk setiap tick $j$ dari $m+1$ hingga $k$:
     $$S_j \leftarrow f(S_{j-1}, I_j)$$
   - Riwayat di bawah $m$ dihapus (*purged*).

### 5.3. Entity Interpolation untuk Remote Agents
Entitas yang dikendalikan oleh remote player atau server AI tidak diprediksi menggunakan input lokal klien. Klien merendernya di masa lalu (*interpolation delay*, biasanya setara $RTT/2 + \text{jitter buffer}$):

$$t_{\text{render}} = t_{\text{current}} - \Delta t_{\text{interp}}$$

Mencari dua snapshot $S_a$ dan $S_b$ sedemikian rupa sehingga $t_a \le t_{\text{render}} \le t_b$:

$$\alpha = \frac{t_{\text{render}} - t_a}{t_b - t_a}$$

$$\vec{P}_{\text{render}} = \text{Lerp}(\vec{P}_a, \vec{P}_b, \alpha) = \vec{P}_a + \alpha(\vec{P}_b - \vec{P}_a)$$

$$\mathbf{Q}_{\text{render}} = \text{Slerp}(\mathbf{Q}_a, \mathbf{Q}_b, \alpha)$$

### 5.4. Delta Compression & Quantization
Float 32-bit memiliki presisi berlebih untuk posisi game dunia virtual standar.
- **Quantization**: Jika koordinat $X \in [-1024, 1024]$ meter dan resolusi yang diinginkan adalah $1\text{ mm}$ ($0.001\text{ m}$):
  $$\text{Total steps} = \frac{2048}{0.001} = 2{,}048{,}000 < 2^{21}$$
  Kita dapat mengompresi float 32-bit menjadi integer unsigned 21-bit, menghemat ~34% bandwidth.
- **Delta Encoding**: Server hanya mengirim field yang berubah (*dirty bitmask*) dibandingkan dengan tick terakhir yang telah diakui (*acknowledged tick*) oleh klien penerima.

---

## 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python 3.11+ yang memanfaatkan `asyncio`, type annotations ketat, serialisasi biner via `struct`, serta pemisahan murni antara simulasi, prediksi, rekonsiliasi, dan kompresi data.

```python
"""
Real-time Network State Synchronization Engine
Implements Authoritative Tick, Prediction, Reconciliation, and Quantization.
"""

from __future__ import annotations

import asyncio
import copy
import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Core Math & Quantization Utilities
# ============================================================================

@dataclass(slots=True, frozen=True)
class Vector2:
    x: float
    y: float

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2:
        return Vector2(self.x * scalar, self.y * scalar)

    def length_squared(self) -> float:
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.sqrt(self.length_squared())

    def distance_to(self, other: Vector2) -> float:
        return (self - other).length()


class Quantizer:
    """Mengompresi floating-point float32 menjadi uint16 integer bertingkat."""
    def __init__(self, min_val: float, max_val: float, bits: int = 16):
        self.min_val = min_val
        self.max_val = max_val
        self.max_int = (1 << bits) - 1

    def quantize(self, val: float) -> int:
        clamped = max(self.min_val, min(self.max_val, val))
        normalized = (clamped - self.min_val) / (self.max_val - self.min_val)
        return int(normalized * self.max_int)

    def dequantize(self, quantized: int) -> float:
        normalized = quantized / float(self.max_int)
        return self.min_val + normalized * (self.max_val - self.min_val)


# ============================================================================
# Protocol Definitions
# ============================================================================

@dataclass(slots=True)
class InputCommand:
    tick: int
    move_dir: Vector2  # Normalized direction (-1.0 to 1.0)

    def pack(self) -> bytes:
        # Formatter: H (tick: uint16), h (move_dir.x * 10000: int16), h (move_dir.y * 10000: int16)
        x_q = int(self.move_dir.x * 10000)
        y_q = int(self.move_dir.y * 10000)
        return struct.pack("!Hhh", self.tick % 65536, x_q, y_q)

    @classmethod
    def unpack(cls, data: bytes) -> InputCommand:
        tick, x_q, y_q = struct.unpack("!Hhh", data)
        return cls(tick=tick, move_dir=Vector2(x_q / 10000.0, y_q / 10000.0))


@dataclass(slots=True)
class EntityState:
    entity_id: int
    position: Vector2
    velocity: Vector2


quantizer_x = Quantizer(-1000.0, 1000.0, 16)
quantizer_y = Quantizer(-1000.0, 1000.0, 16)


@dataclass(slots=True)
class WorldSnapshot:
    server_tick: int
    last_processed_client_tick: int
    entities: Dict[int, EntityState] = field(default_factory=dict)

    def pack(self) -> bytes:
        """
        Binary Structure:
        [ServerTick: uint16][AckTick: uint16][EntityCount: uint8]
        Loop Entities:
           [EntityID: uint8][PosX: uint16][PosY: uint16][VelX: int16][VelY: int16]
        """
        header = struct.pack(
            "!HHB",
            self.server_tick % 65536,
            self.last_processed_client_tick % 65536,
            len(self.entities)
        )
        entity_payload = bytearray()
        for ent in self.entities.values():
            pos_x_q = quantizer_x.quantize(ent.position.x)
            pos_y_q = quantizer_y.quantize(ent.position.y)
            vel_x_q = int(ent.velocity.x * 100)
            vel_y_q = int(ent.velocity.y * 100)
            entity_payload.extend(
                struct.pack("!BHHhh", ent.entity_id, pos_x_q, pos_y_q, vel_x_q, vel_y_q)
            )
        return header + bytes(entity_payload)

    @classmethod
    def unpack(cls, data: bytes) -> WorldSnapshot:
        server_tick, ack_tick, count = struct.unpack("!HHB", data[:5])
        entities: Dict[int, EntityState] = {}
        offset = 5
        entity_size = struct.calcsize("!BHHhh")

        for _ in range(count):
            e_id, px_q, py_q, vx_q, vy_q = struct.unpack(
                "!BHHhh", data[offset : offset + entity_size]
            )
            entities[e_id] = EntityState(
                entity_id=e_id,
                position=Vector2(quantizer_x.dequantize(px_q), quantizer_y.dequantize(py_q)),
                velocity=Vector2(vx_q / 100.0, vy_q / 100.0)
            )
            offset += entity_size

        return cls(server_tick=server_tick, last_processed_client_tick=ack_tick, entities=entities)


# ============================================================================
# Simulation Logic
# ============================================================================

SPEED: float = 10.0  # units per second
FIXED_DELTA_TIME: float = 1.0 / 30.0  # 30 Hz tick rate


def step_kinematics(position: Vector2, move_dir: Vector2, dt: float) -> Tuple[Vector2, Vector2]:
    """Fungsi simulasi fisika deterministik tunggal."""
    if move_dir.length_squared() > 1.0:
        inv_len = 1.0 / move_dir.length()
        move_dir = Vector2(move_dir.x * inv_len, move_dir.y * inv_len)

    velocity = move_dir * SPEED
    new_position = position + (velocity * dt)
    return new_position, velocity


# ============================================================================
# Network Simulation Harness (Simulated UDP Pipe with Lag & Jitter)
# ============================================================================

class NetworkChannel:
    def __init__(self, one_way_latency_ms: float = 50.0):
        self.latency: float = one_way_latency_ms / 1000.0
        self.queue: List[Tuple[float, bytes]] = []

    def send(self, data: bytes, current_time: float) -> None:
        arrival_time = current_time + self.latency
        self.queue.append((arrival_time, data))

    def receive(self, current_time: float) -> List[bytes]:
        ready: List[bytes] = []
        remaining: List[Tuple[float, bytes]] = []
        for arrival_time, payload in self.queue:
            if current_time >= arrival_time:
                ready.append(payload)
            else:
                remaining.append((arrival_time, payload))
        self.queue = remaining
        return ready


# ============================================================================
# Authoritative Server
# ============================================================================

class AuthoritativeServer:
    def __init__(self):
        self.current_tick: int = 0
        self.entities: Dict[int, EntityState] = {
            1: EntityState(entity_id=1, position=Vector2(0.0, 0.0), velocity=Vector2(0.0, 0.0)),  # Player
            2: EntityState(entity_id=2, position=Vector2(50.0, 50.0), velocity=Vector2(0.0, 0.0)) # Autonomous AI
        }
        self.client_input_queue: List[InputCommand] = []
        self.last_processed_client_tick: int = 0

    def enqueue_client_input(self, payload: bytes) -> None:
        cmd = InputCommand.unpack(payload)
        self.client_input_queue.append(cmd)

    def tick(self) -> bytes:
        self.current_tick += 1

        # 1. Proses Input Klien untuk Entitas 1
        if self.client_input_queue:
            # Mengurutkan input berdasarkan nomor tick untuk mitigasi packet out-of-order
            self.client_input_queue.sort(key=lambda c: c.tick)
            for cmd in self.client_input_queue:
                pos, vel = step_kinematics(
                    self.entities[1].position, cmd.move_dir, FIXED_DELTA_TIME
                )
                self.entities[1] = EntityState(entity_id=1, position=pos, velocity=vel)
                self.last_processed_client_tick = cmd.tick
            self.client_input_queue.clear()
        else:
            # Zero-friction drag jika tidak ada input
            self.entities[1] = EntityState(
                entity_id=1, position=self.entities[1].position, velocity=Vector2(0.0, 0.0)
            )

        # 2. Simulasi State AI Otonom (Entitas 2) - Patroli Sederhana
        ai = self.entities[2]
        ai_dir = Vector2(math.cos(self.current_tick * 0.1), math.sin(self.current_tick * 0.1))
        ai_pos, ai_vel = step_kinematics(ai.position, ai_dir, FIXED_DELTA_TIME)
        self.entities[2] = EntityState(entity_id=2, position=ai_pos, velocity=ai_vel)

        # 3. Snapshot Generation
        snapshot = WorldSnapshot(
            server_tick=self.current_tick,
            last_processed_client_tick=self.last_processed_client_tick,
            entities=self.entities
        )
        return snapshot.pack()


# ============================================================================
# Client Architecture with Prediction & Reconciliation
# ============================================================================

class GameClient:
    def __init__(self, local_entity_id: int):
        self.local_entity_id: int = local_entity_id
        self.client_tick: int = 0
        self.predicted_position: Vector2 = Vector2(0.0, 0.0)
        self.predicted_velocity: Vector2 = Vector2(0.0, 0.0)

        # Buffers
        self.input_history: Dict[int, InputCommand] = {}
        self.state_history: Dict[int, Vector2] = {}
        self.remote_entities: Dict[int, EntityState] = {}

        self.reconciliation_count: int = 0

    def generate_input(self, direction: Vector2) -> bytes:
        self.client_tick += 1
        cmd = InputCommand(tick=self.client_tick, move_dir=direction)
        self.input_history[self.client_tick] = cmd

        # Client-Side Prediction
        self.predicted_position, self.predicted_velocity = step_kinematics(
            self.predicted_position, cmd.move_dir, FIXED_DELTA_TIME
        )
        self.state_history[self.client_tick] = self.predicted_position

        return cmd.pack()

    def process_snapshot(self, snapshot_data: bytes) -> None:
        snapshot = WorldSnapshot.unpack(snapshot_data)
        
        # Tangani Entitas Remote
        for e_id, ent in snapshot.entities.items():
            if e_id != self.local_entity_id:
                self.remote_entities[e_id] = ent

        # Server Reconciliation untuk Local Entity
        if self.local_entity_id in snapshot.entities:
            server_ent = snapshot.entities[self.local_entity_id]
            acked_tick = snapshot.last_processed_client_tick

            if acked_tick in self.state_history:
                client_pos_at_tick = self.state_history[acked_tick]
                # Hitung positional drift/error
                error = client_pos_at_tick.distance_to(server_ent.position)

                RECONCILIATION_THRESHOLD = 0.05  # 5 sentimeter
                if error > RECONCILIATION_THRESHOLD:
                    self.reconciliation_count += 1
                    # REWIND
                    corrected_position = server_ent.position
                    corrected_velocity = server_ent.velocity

                    # REPLAY
                    replay_tick = acked_tick + 1
                    while replay_tick <= self.client_tick:
                        if replay_tick in self.input_history:
                            cmd = self.input_history[replay_tick]
                            corrected_position, corrected_velocity = step_kinematics(
                                corrected_position, cmd.move_dir, FIXED_DELTA_TIME
                            )
                            self.state_history[replay_tick] = corrected_position
                        replay_tick += 1

                    self.predicted_position = corrected_position
                    self.predicted_velocity = corrected_velocity

                # Prune history yang lebih tua dari acked_tick
                old_ticks = [t for t in self.input_history if t <= acked_tick]
                for t in old_ticks:
                    del self.input_history[t]
                    del self.state_history[t]


# ============================================================================
# Execution Entry Point & Integration Test
# ============================================================================

async def run_simulation():
    server = AuthoritativeServer()
    client = GameClient(local_entity_id=1)

    c2s_network = NetworkChannel(one_way_latency_ms=60.0)
    s2c_network = NetworkChannel(one_way_latency_ms=60.0)

    sim_time = 0.0
    total_duration = 2.0  # seconds

    # Simulasikan gerakan ke arah kanan (1.0, 0.0)
    move_intent = Vector2(1.0, 0.0)

    print(f"--- Memulai Simulasi Real-Time ({FIXED_DELTA_TIME*1000:.1f}ms per Tick) ---")

    while sim_time < total_duration:
        sim_time += FIXED_DELTA_TIME

        # 1. Klien mengirim input
        input_packet = client.generate_input(move_intent)
        c2s_network.send(input_packet, sim_time)

        # 2. Server menerima input
        for packet in c2s_network.receive(sim_time):
            server.enqueue_client_input(packet)

        # 3. Server melakukan ticking & memancarkan state
        snapshot_packet = server.tick()
        s2c_network.send(snapshot_packet, sim_time)

        # 4. Klien memproses snapshot & rekonsiliasi
        for snap_bytes in s2c_network.receive(sim_time):
            client.process_snapshot(snap_bytes)

    print(f"Simulasi Selesai pada T={sim_time:.2f}s")
    print(f"Client Tick Terakhir: {client.client_tick}")
    print(f"Server Tick Terakhir: {server.current_tick}")
    print(f"Client Position: ({client.predicted_position.x:.3f}, {client.predicted_position.y:.3f})")
    server_pos = server.entities[1].position
    print(f"Server Position: ({server_pos.x:.3f}, {server_pos.y:.3f})")
    print(f"Deviasi Final: {client.predicted_position.distance_to(server_pos):.5f} unit")
    print(f"Total Intervensi Rekonsiliasi: {client.reconciliation_count}")


if __name__ == "__main__":
    asyncio.run(run_simulation())
```

---

## 7. Edge Cases & Failure Modes

1. **Catastrophic Desync (Reconciliation Thrashing)**:
   - *Penyebab*: Inkonsistensi floating-point non-deterministik antar-kompiler/arsitektur (misal: SSE vs AVX, ARM vs x86-64), atau ketergantungan fisika pada *variable delta time*.
   - *Dampak*: Rekonsiliasi terpicu pada setiap frame, menghasilkan stutter rendering visual yang konstan.
   - *Mitigasi*: Gunakan *fixed-point arithmetic* integer math untuk simulasi logika atau batasi penegakan rekonsiliasi hanya saat error melebihi radius batas toleransi (epsilon band).

2. **Packet Bursts and Late Packets (Jitter)**:
   - *Penyebab*: Fluktuasi routing penyedia ISP klien atau bufferbloat di router lokal.
   - *Dampak*: Inbound queue server kosong di beberapa frame, kemudian dibanjiri 5-10 input packet sekaligus.
   - *Mitigasi*: Terapkan *Input Buffer Clamp*. Batasi server untuk memproses maksimal $\Delta k_{\max}$ input per tick. Jika klien mengirim input terlalu cepat secara kronis, percepat laju konsumsi tick server secara dinamis (*clock skewing*).

3. **Packet Loss pada Delta Baseline**:
   - *Penyebab*: Hilangnya snapshot UDP yang menjadi basis referensi delta compression.
   - *Dampak*: Klien tidak dapat mendekode state berikutnya karena state dasar (*delta base*) tidak pernah eksis di klien.
   - *Mitigasi*: Mekanisme Acknowledgement (ACK) per-packet. Server hanya menghitung delta dari snapshot terakhir yang secara eksplisit telah di-ACK oleh klien penerima.

4. **Floating Origin Shifts pada Peta Berskala Besar**:
   - *Penyebab*: Hilangnya presisi floating point 32-bit di atas koordinat absolut besar ($> 10{,}000$ unit).
   - *Dampak*: Getaran fisik (*mesh jittering*) dan kegagalan komparasi epsilon rekonsiliasi.
   - *Mitigasi*: Gunakan koordinat int32 berbasis sektor/tile untuk dunia global, dan floating point lokal yang relatif terhadap pusat sektor tersebut.

---

## 8. Trade-offs & Alternatif Solusi

| Parameter | Deterministic Lockstep | Authoritative State Sync | Distributed State / P2P |
| :--- | :--- | :--- | :--- |
| **Bandwidth Usage** | Sangat Rendah ($O(\text{Inputs})$) | Sedang hingga Tinggi ($O(\text{Visible Entities})$) | Tinggi antar-peer |
| **Resistansi Cheat** | Rendah (Maphacks mutlak mungkin) | Sangat Tinggi (Server otoritatif penuh) | Sangat Rendah |
| **Sensitivitas Latensi** | Tinggi (Klien terikat ke node terlambat) | Rendah (CSP menyembunyikan latensi) | Bervariasi |
| **Kebutuhan Determinisme** | Mutlak (Koreksi bit-level) | Rendah/Moderat | Tidak ada jaminan |
| **Kesesuaian AI** | Ratusan ribu unit AI murah | AI dihitung di server (mahal di CPU) | Kompleksitas tinggi |
| **Skenario Ideal** | RTS, Game Pertarungan Berbasis Frame | FPS, Battle Royale, MMORPG, MOBA | Co-op kasual 2-4 pemain |

### Alternatif Transport Layer:
- **Raw UDP**: Fleksibilitas maksimal, namun membutuhkan implementasi manual untuk multiplexing, retransmisi selektif, dan MTU discovery.
- **Reliable UDP (misal: ENet, KCP, Photon NAT)**: Memberikan channel *sequenced*, *unreliable*, dan *reliable* secara out-of-the-box. Pilihan standar industri indie-AAA.
- **WebTransport / WebSockets**: Wajib digunakan untuk game berbasis web/browser. WebTransport (berbasis HTTP/3 over QUIC) mengeliminasi problem *Head-of-Line Blocking* yang dialami TCP/WebSocket konvensional.

---

## 9. Best Practices & Standar Industri

1. **Decouple Render Loop dari Simulation Tick**:
   - Render engine harus berjalan menggunakan $dt$ variabel berbasis performa GPU ($144\text{ Hz}+$), sedangkan sim engine berjalan pada fixed cadence (misal: $30\text{ Hz}$ atau $60\text{ Hz}$).
   - Lakukan interpolasi antara state frame simulasi saat ini dan sebelumnya untuk visual rendering:
     $$S_{\text{render}} = \text{Lerp}(S_{\text{prev}}, S_{\text{curr}}, \alpha_{\text{accum}})$$

2. **Quantize Everything**:
   - Jangan pernah mengirim IEEE-754 32-bit mentah secara serial jika integer range diskrit sudah mencukupi.
   - Rotasi kuaternion diserialisasikan menggunakan metode **Smallest Three**: cari komponen terbesar dari $(x, y, z, w)$, kirim indeks 2-bit untuk menandai komponen terbesar, lalu kirim 3 komponen sisanya yang di-quantize. Komponen terbesar dapat direkonstruksi via $\sum q_i^2 = 1$.

3. **Spatial Interest Management (Grid / KD-Tree / BVH)**:
   - Partisisi dunia virtual ke dalam sel heksagonal atau kubus spasial.
   - Batasi pemancaran snapshot hanya untuk entitas di dalam radius visibilitas pemain ($AOI$). Autonomous agent yang berada di luar jangkauan sensor klien cukup dipancarkan sebagai low-frequency heartbeat atau tidak sama sekali.

4. **Lag Compensation (Lag Rewind) untuk Hitscan**:
   - Ketika pemain menembak pada frame lokal mereka di tick $T$, sertakan tick $T$ dalam paket tembakan.
   - Server mengembalikan posisi *hitbox* target ke masa lampau sesuai tick $T$ (dengan batas toleransi maksimal, misal: $\le 200\text{ms}$), melakukan evaluasi *raycast*, lalu mengembalikan state ke masa kini.

---

## 10. Hands-on Lab Exercise: Implementasi Jitter Buffer & State Interpolation

### Objektif
Membangun pipeline klien yang mengonsumsi stream snapshot entitas jarak jauh (*remote AI agent*) yang terkena delay dan jitter acak, serta merendernya secara mulus menggunakan algoritma **Jitter-Adaptive Snapshot Interpolation**.

### Langkah-langkah:
1. **Setup Lab File**:
   Buat berkas bernama `snapshot_interpolator_lab.py`.
2. **Implementasikan Data Source**:
   Bangun generator snapshot yang memancarkan posisi sinusoidal dari remote agent pada rate $20\text{ Hz}$ (tiap $50\text{ms}$).
3. **Simulasikan Latensi Acak**:
   Lalukan paket ke fungsi yang menahan data dengan latensi normal-distributed:
   $$\text{Delay} \sim \mathcal{N}(\mu=80\text{ms}, \sigma=25\text{ms})$$
4. **Implementasikan Interpolation Ring Buffer**:
   - Di sisi penerima, tempatkan snapshot ke dalam ordered array berdasarkan timestamp snapshot.
   - Tentukan delay rendering target ($D = \text{Mean Latency} + 3 \times \sigma$).
   - Cari interval snapshot yang melingkupi $t_{\text{target}} = t_{\text{local}} - D$.
   - Eksekusi LERP di antara kedua snapshot.
5. **Evaluasi Metrik**:
   - Cetak jumlah kejadian *starvation* (ketika buffer tidak memiliki snapshot masa lalu dan terpaksa melakukan ekstrapolasi/freezing).
   - Verifikasi apakah kurva posisi yang diinterpolasi tetap kontinu secara visual tanpa patahan diskrit.

### Verifikasi Keberhasilan:
Eksekusi pengujian selama 10 detik simulasi. Buffer dikatakan lulus kualifikasi produksi jika tingkat starvation $\le 1\%$ dari total frame simulasi yang dirender pada rate $60\text{ Hz}$.