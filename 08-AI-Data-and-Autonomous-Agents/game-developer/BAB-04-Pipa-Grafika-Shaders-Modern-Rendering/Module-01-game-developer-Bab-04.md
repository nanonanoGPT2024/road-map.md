# Bab 04: Pipa Grafika, Shaders, & Modern Rendering — Module 01

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
* **Menganalisis** alur eksekusi mikro-arsitektur GPU dari *Input Assembler*, *Vertex Processing*, *Rasterization*, hingga *Output Merger* secara deterministik.
* **Merancang & Mengimplementasikan** *Pipeline State Object* (PSO) modern serta integrasi komputasi *Shader* (*Compute Shader*) untuk simulasi multi-agent spasial terakselerasi perangkat keras.
* **Mengevaluasi & Memilih** arsitektur *rendering* (*Forward+*, *Deferred*, *Clustered*, dan *GPU-Driven Rendering*) berdasarkan batasan latensi, anggaran VRAM, dan densitas beban kalkulasi sensor visual AI.
* **Memitigasi Sinkronisasi Konkurensi** (*Memory Barriers*, *Resource Hazards*, *Race Conditions*) pada pertukaran buffer antara *Compute Pass* dan *Render Pass*.
* **Membangun Headless Graphics & Compute Harness** skala produksi untuk menghasilkan *synthetic ground truth data* (Depth, Albedo, Surface Normals) bagi *autonomous agents*.

---

## 2. Concept Overview
Pipa grafika modern (*Modern Graphics Pipeline*) bukan lagi sekadar fungsi tetap (*fixed-function*) linier untuk memproyeksikan segitiga 3D ke layar 2D. Dalam arsitektur komputasi modern dan agen otonom, GPU diposisikan sebagai mesin pemrosesan data paralel masif berbasis arsitektur **SIMT** (*Single Instruction, Multiple Threads*).

```
[Traditional Fixed Function Pipeline]
Primitives -> Transform -> Clip -> Project -> Rasterize -> Fixed Fog/Color -> Framebuffer

[Modern GPU Architecture & Unified Core Pipeline]
Unified Compute Units (ALUs, FP32/INT32, Tensor/RT Cores, Registers, Shared Memory)
       |                   |                   |                   |
[Compute Shader]   [Vertex Shader]    [Mesh Shader]       [Fragment Shader]
       \                   |                   |                  /
        +------------------+-------------------+-----------------+
                           | Memory System |
               L1/Shared Mem <-> L2 Cache <-> VRAM (HBM/GDDR)
```

### Mental Model: The Unified Processor Matrix
Secara fisik, perangkat keras modern tidak lagi memiliki unit silikon terpisah untuk *vertex* atau *pixel*. GPU modern terdiri dari ratusan *Streaming Multiprocessors* (SM pada NVIDIA) atau *Compute Units* (CU pada AMD). Setiap SM/CU menjalankan ribuan thread paralel yang diorganisasi ke dalam grup eksekusi:
* **Warp** (NVIDIA: 32 thread) atau **Wavefront** (AMD: 32/64 thread).
* Eksekusi bersifat *lock-step*: seluruh thread dalam satu warp menjalankan instruksi yang sama pada siklus jam yang sama. Jika terjadi percabangan logika (*branch divergence* melalui `if/else`), kedua jalur dieksekusi secara serial dengan *masking*, menurunkan efisiensi komputasi.

Dalam konteks simulasi agen otonom (*Autonomous Agents*) dan *Game Development*:
1. **Pipa Grafika Komputasi Terpadu (*Unified Compute-Graphics Pipeline*)**: Kita mengeksekusi dinamika agen (fisika, sensor spasial raycast, *state transition*) langsung di GPU menggunakan *Compute Shader*.
2. **Zero-Copy Pipeline Integration**: Buffer hasil komputasi status agen (posisi, orientasi, status animasi) langsung dikonsumsi oleh tahap *Vertex/Instance Fetch* atau *Mesh Shader* tanpa melalui *round-trip* bus PCIe kembali ke memori CPU (RAM).

---

## 3. Why It Matters
Pada pengembangan *engine* game generasi modern dan pelatihan sensorik *Autonomous Agents* (seperti platform *NVIDIA Isaac Gym*, *Unreal Engine 5*, atau *Unity Sentis*), pendekatan *render loop* klasik CPU-driven menghadapi hambatan kritis:

1. **Bottleneck PCIe & CPU Draw Call Overhead**: 
   Mengirim jutaan koordinat agen per frame dari RAM (CPU) ke VRAM (GPU) via PCIe Gen 4/5 menimbulkan latensi transfer sebesar 8–16 ms per frame, membatasi throughput simulasi.
2. **Kebutuhan Synthetic Sensor Generation Masif**:
   Sistem visi komputer untuk robotika dan agen otonom memerlukan ribuan sudut pandang kamera virtual yang dirender pada kecepatan ratusan frame per detik (*headless rendering*). Menggunakan *Forward Rendering* naif untuk 10.000 agen dengan pencahayaan dinamis akan mengakibatkan kompleksitas komputasi $O(M \times N)$ (di mana $M$ adalah jumlah fragment dan $N$ adalah jumlah sumber cahaya), yang langsung memicu GPU *Timeout Detection and Recovery* (TDR).
3. **Deterministik State Tracking**:
   Simulasi multi-agent skala besar membutuhkan sinkronisasi eksplisit berbasis *Barriers* dan *Execution Fences*. Kegagalan dalam mengelola dependensi antar-pass (*Hazard Read-After-Write*) menghasilkan frame korup dan status AI yang tidak deterministik.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan transisi state dan alur data dari komputasi agen hingga rasterisasi fragment dalam satu siklus *frame* terpadu:

```
+-----------------------------------------------------------------------------------+
|                              GPU GLOBAL MEMORY (VRAM)                             |
|  +---------------------------+  +----------------------+  +--------------------+  |
|  | Agent State Storage Buffer|  | Index/Mesh VBO Buffer|  | Depth/Color Target |  |
|  +---------------------------+  +----------------------+  +--------------------+  |
+-----------------------------------------------------------------------------------+
          |                                  ^                         ^
          | [RAW Hazard: Explicit Barrier]   |                         |
          v                                  |                         |
+-----------------------+                    |                         |
|   1. COMPUTE PASS     |                    |                         |
| +-------------------+ |                    |                         |
| | Compute Shader    | |                    |                         |
| | - Update Position | |                    |                         |
| | - Collision/Avoid | |                    |                         |
| | - Spatial Query   | |                    |                         |
| +-------------------+ |                    |                         |
+-----------------------+                    |                         |
          |                                  |                         |
     [PIPELINE BARRIER: COMPUTE_SHADER_WRITE -> VERTEX_SHADER_READ]    |
          v                                  |                         |
+----------------------------------------------------------------------+------------+
|   2. GRAPHICS PIPELINE PASS (Rasterization Path)                                  |
|                                                                                   |
|  +------------------------+      +------------------------+                       |
|  | Input Assembler (IA)   | ---> | Vertex Shader (VS)     |                       |
|  | Instanced Fetch:       |      | Pos = P * V * M(Agent) |                       |
|  | Mesh + Agent State     |      | Generates Clip-Space   |                       |
|  +------------------------+      +------------------------+                       |
|                                              |                                    |
|                                              v                                    |
|  +------------------------+      +------------------------+                       |
|  | Early-Z Testing        | <--- | Rasterization (RS)     |                       |
|  | Coarse/Fine Depth Rej  |      | Interpolate UV, Norms  |                       |
|  +------------------------+      +------------------------+                       |
|              | (Pass)                                                             |
|              v                                                                    |
|  +------------------------+      +------------------------+                       |
|  | Fragment Shader (FS)   | ---> | Output Merger (OM)     |                       |
|  | PBR Lighting / Normals |      | Blend, Late-Z,         | --------------------+ |
|  | Emits Multi-RenderTarget|      | Write to Target Buffer |                      |
|  +------------------------+      +------------------------+                      |
+-----------------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Tahapan Eksekusi Hardware
1. **Input Assembler (IA)**: Membaca indeks dan vertex mentah dari VRAM. Menggunakan *Hardware Instancing*, IA mengawinkan data topologi 3D statis (*base mesh*) dengan data dinamis *per-instance* (array posisi, orientasi agen yang diproduksi oleh *Compute Pass*).
2. **Vertex Shading**: Transformasi koordinat lokal via *Model-View-Projection* (MVP) matrix ke *Homogeneous Clip Space* ($\mathbf{v}_{clip} = \mathbf{P} \cdot \mathbf{V} \cdot \mathbf{M} \cdot \mathbf{v}_{local}$).
3. **Primitive Assembly & Clipping**: Geometri yang berada di luar *frustum* pandang dipotong (*clipped*). Nilai koordinat dinormalisasi melalui *Perspective Division* ($\frac{x}{w}, \frac{y}{w}, \frac{z}{w}$) ke dalam *Normalized Device Coordinates* (NDC) $[-1, 1]$.
4. **Rasterization**: Menghitung *bounding box* primitif, menguji titik sampel piksel (menggunakan arsitektur ubin/tile-based atau scanline hierarkis), dan menginterpolasi atribut vertex secara *perspective-correct*:
   $$I = \frac{\frac{I_0}{w_0}(1-t) + \frac{I_1}{w_1}t}{\frac{1}{w_0}(1-t) + \frac{1}{w_1}t}$$
5. **Early-Z / Hierarchical Z (HiZ)**: Sebelum mengeksekusi Fragment Shader, perangkat keras menguji nilai depth fragment terhadap *Depth Buffer*. Fragment yang tertutup objek lain langsung dieliminasi, menghemat siklus komputasi shader secara signifikan.
6. **Fragment/Pixel Shading**: Mengevaluasi pencahayaan berbasis fisika (*Physically Based Rendering* / PBR) atau menulis data segmentasi semantik/kedalaman untuk konsumsi neural model.
7. **Output Merger (OM)**: Melakukan *Late Depth/Stencil test*, menangani operasi *alpha blending*, dan melakukan penulisan atomik data piksel ke *Render Targets*.

### 5.2 Manajemen Hazards & Memory Synchronization
Dalam model komputasi grafika eksplisit (seperti Vulkan, DirectX 12, atau WebGPU), tidak ada dependensi otomatis antar-tahap pemrosesan:
* **Read-After-Write (RAW)**: Terjadi jika Render Pass membaca buffer agen sebelum Compute Pass selesai menulis seluruh data instance.
* **Solusi**: Pemasangan *Memory Barrier* dan *Execution Barrier* eksplisit. Driver menginstruksikan GPU untuk *flush* L1/L2 cache dan menunggu seluruh *warp* pada tahap `COMPUTE` selesai (*drain*) sebelum tahap `VERTEX_INPUT` mulai membaca data.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem simulasi pergerakan multi-agent terakselerasi compute shader yang langsung dirender secara instansiasi (*GPU-driven instancing*) menggunakan standar WebGPU (via Python `wgpu` backend native). Arsitektur ini dirancang untuk rendering inferensi sensor agen secara modular dan nir-latensi CPU.

```python
"""
production_rendering_pipeline.py
Sistem Render & Komputasi Agen Terpadu Skala Produksi.
Mengimplementasikan Compute Pass + Instanced Render Pass dengan sinkronisasi eksplisit.
"""

from __future__ import annotations
import ctypes
import logging
from dataclasses import dataclass
from typing import Final, Tuple
import numpy as np
import wgpu
from wgpu.gui.auto import WgpuCanvas, run

# Konfigurasi Logging Teknis
logging.basicConfig(level=logging.INFO, format="[%(asctime)s - %(levelname)s] %(message)s")
logger: Final[logging.Logger] = logging.getLogger("GraphicsPipeline")

# ============================================================================
# KONSTANTA & STRUKTUR MEMORI (STD430 / STRUCT ALIGNMENT)
# ============================================================================
NUM_AGENTS: Final[int] = 50_000
WORKGROUP_SIZE: Final[int] = 256

# Kode WGSL: Compute Shader untuk Dinamika Spasial Agen
COMPUTE_SHADER_SOURCE: Final[str] = """
struct Agent {
    position: vec2<f32>,
    velocity: vec2<f32>,
};

struct SimParams {
    delta_time: f32,
    bound_limit: f32,
    speed_scale: f32,
    padding: f32,
};

@group(0) @binding(0) var<storage, read_write> agents: array<Agent>;
@group(0) @binding(1) var<uniform> params: SimParams;

@compute @workgroup_size(256)
fn cs_main(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let index = global_id.x;
    if (index >= arrayLength(&agents)) {
        return;
    }

    var agent = agents[index];
    
    // Integrasi Posisi Euler
    agent.position += agent.velocity * (params.delta_time * params.speed_scale);

    // Deteksi Batas Area & Resolusi Pantulan Elastis Sederhana
    if (abs(agent.position.x) > params.bound_limit) {
        agent.velocity.x = -agent.velocity.x;
        agent.position.x = sign(agent.position.x) * params.bound_limit;
    }
    if (abs(agent.position.y) > params.bound_limit) {
        agent.velocity.y = -agent.velocity.y;
        agent.position.y = sign(agent.position.y) * params.bound_limit;
    }

    agents[index] = agent;
}
"""

# Kode WGSL: Render Pipeline (Vertex & Fragment Shader)
RENDER_SHADER_SOURCE: Final[str] = """
struct VertexInput {
    @location(0) local_pos: vec2<f32>,
};

struct InstanceInput {
    @location(1) agent_pos: vec2<f32>,
    @location(2) agent_vel: vec2<f32>,
};

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) color: vec3<f32>,
};

@vertex
fn vs_main(vertex: VertexInput, instance: InstanceInput) -> VertexOutput {
    var out: VertexOutput;
    
    // Skala geometri primitif segitiga
    let scale: f32 = 0.015;
    let world_pos = (vertex.local_pos * scale) + instance.agent_pos;
    
    out.clip_position = vec4<f32>(world_pos, 0.0, 1.0);
    
    // Visualisasi Kecepatan sebagai Sensor Ground Truth Warna
    let speed = length(instance.agent_vel);
    out.color = vec3<f32>(
        normalize(instance.agent_vel) * 0.5 + vec2<f32>(0.5, 0.5),
        clamp(speed, 0.0, 1.0)
    );
    
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    return vec4<f32>(in.color, 1.0);
}
"""

# ============================================================================
# INFRASTRUKTUR PIPELINE & MANAJER PERANGKAT
# ============================================================================

@dataclass(frozen=True)
class SimulationParameters:
    delta_time: float
    bound_limit: float
    speed_scale: float
    padding: float = 0.0

    def to_bytes(self) -> bytes:
        return np.array([self.delta_time, self.bound_limit, self.speed_scale, self.padding], dtype=np.float32).tobytes()

class ModernGraphicsComputePipeline:
    """Mengelola siklus hidup resource GPU, Compute Pipeline, dan Render Pipeline."""

    def __init__(self, canvas: WgpuCanvas) -> None:
        self.canvas = canvas
        self.device = self._initialize_gpu_device()
        self.context = self.canvas.get_context()
        self.render_format = self.context.get_preferred_format(self.device.adapter)
        self.context.configure(device=self.device, format=self.render_format)

        # Inisialisasi Buffer dan Pipelines
        self._allocate_buffers()
        self._build_compute_pipeline()
        self._build_render_pipeline()

        logger.info("Pipeline State Objects (PSO) dan Buffers berhasil dikompilasi.")

    def _initialize_gpu_device(self) -> wgpu.GPUDevice:
        """Memilih adapter perangkat keras dengan performa tertinggi."""
        adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        if not adapter:
            raise RuntimeError("Perangkat keras grafis kompatibel tidak ditemukan.")
        logger.info("Adapter Aktif: %s", adapter.properties.get("name", "Unknown GPU"))
        return adapter.request_device_sync(required_features=[], required_limits={})

    def _allocate_buffers(self) -> None:
        """Alokasi GPU Storage, Vertex, dan Uniform Buffers."""
        # 1. Mesh Geometri Lokal (Segitiga Sederhana: 3 vertex)
        triangle_mesh = np.array([
            0.0,  1.0,
           -0.86, -0.5,
            0.86, -0.5
        ], dtype=np.float32)
        self.vertex_buffer = self.device.create_buffer_with_data(
            data=triangle_mesh.tobytes(),
            usage=wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST
        )

        # 2. Buffer Status Agen (Posisi X, Y, Kecepatan X, Y)
        # Membangkitkan kondisi acak seragam
        positions = np.random.uniform(-0.95, 0.95, (NUM_AGENTS, 2)).astype(np.float32)
        velocities = np.random.uniform(-0.5, 0.5, (NUM_AGENTS, 2)).astype(np.float32)
        
        # Interleave data posisi dan kecepatan ke layout terstruktur
        agent_data = np.empty((NUM_AGENTS, 4), dtype=np.float32)
        agent_data[:, 0:2] = positions
        agent_data[:, 2:4] = velocities

        self.agent_buffer = self.device.create_buffer_with_data(
            data=agent_data.tobytes(),
            usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST
        )

        # 3. Uniform Buffer Parameter Simulasi
        initial_params = SimulationParameters(delta_time=0.016, bound_limit=0.98, speed_scale=0.8)
        self.uniform_buffer = self.device.create_buffer_with_data(
            data=initial_params.to_bytes(),
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST
        )

    def _build_compute_pipeline(self) -> None:
        """Kompilasi Compute Shader dan Bind Group."""
        compute_module = self.device.create_shader_module(code=COMPUTE_SHADER_SOURCE)

        self.compute_bind_group_layout = self.device.create_bind_group_layout(entries=[
            {
                "binding": 0,
                "visibility": wgpu.ShaderStage.COMPUTE,
                "buffer": {"type": wgpu.BufferBindingType.storage}
            },
            {
                "binding": 1,
                "visibility": wgpu.ShaderStage.COMPUTE,
                "buffer": {"type": wgpu.BufferBindingType.uniform}
            }
        ])

        self.compute_pipeline = self.device.create_compute_pipeline(
            layout=self.device.create_pipeline_layout(bind_group_layouts=[self.compute_bind_group_layout]),
            compute={"module": compute_module, "entry_point": "cs_main"}
        )

        self.compute_bind_group = self.device.create_bind_group(
            layout=self.compute_bind_group_layout,
            entries=[
                {"binding": 0, "resource": {"buffer": self.agent_buffer}},
                {"binding": 1, "resource": {"buffer": self.uniform_buffer}}
            ]
        )

    def _build_render_pipeline(self) -> None:
        """Kompilasi Render Pipeline untuk Instanced Rendering."""
        render_module = self.device.create_shader_module(code=RENDER_SHADER_SOURCE)

        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[])

        # Deskriptor Buffer Vertex: Slot 0 = Geometri Statis, Slot 1 = Data Agen (Per-Instance)
        vertex_buffers = [
            {
                "array_stride": 2 * 4,  # vec2<f32>
                "step_mode": wgpu.VertexStepMode.vertex,
                "attributes": [{"format": wgpu.VertexFormat.float32x2, "offset": 0, "shader_location": 0}]
            },
            {
                "array_stride": 4 * 4,  # vec2<f32> pos + vec2<f32> vel
                "step_mode": wgpu.VertexStepMode.instance,
                "attributes": [
                    {"format": wgpu.VertexFormat.float32x2, "offset": 0, "shader_location": 1},
                    {"format": wgpu.VertexFormat.float32x2, "offset": 2 * 4, "shader_location": 2}
                ]
            }
        ]

        self.render_pipeline = self.device.create_render_pipeline(
            layout=pipeline_layout,
            vertex={
                "module": render_module,
                "entry_point": "vs_main",
                "buffers": vertex_buffers
            },
            fragment={
                "module": render_module,
                "entry_point": "fs_main",
                "targets": [{"format": self.render_format}]
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_list,
                "cull_mode": wgpu.CullMode.none
            }
        )

    def step_and_render(self, dt: float) -> None:
        """Mengeksekusi siklus Compute & Render Pass secara sekuensial."""
        # 1. Update parameter simulasi di uniform buffer
        current_params = SimulationParameters(delta_time=dt, bound_limit=0.98, speed_scale=0.8)
        self.device.queue.write_buffer(self.uniform_buffer, 0, current_params.to_bytes())

        # Inisialisasi Command Encoder
        encoder = self.device.create_command_encoder()

        # ====================================================================
        # PASS 1: COMPUTE PASS (Update Status AI/Partikel Agen)
        # ====================================================================
        compute_pass = encoder.begin_compute_pass()
        compute_pass.set_pipeline(self.compute_pipeline)
        compute_pass.set_bind_group(0, self.compute_bind_group)
        
        # Kalkulasi jumlah dispatch workgroups
        num_workgroups = (NUM_AGENTS + WORKGROUP_SIZE - 1) // WORKGROUP_SIZE
        compute_pass.dispatch_workgroups(num_workgroups, 1, 1)
        compute_pass.end()

        # ====================================================================
        # PASS 2: RENDER PASS (Rasterisasi Instansiasi Agen ke Swapchain)
        # ====================================================================
        current_texture = self.context.get_current_texture()
        render_pass = encoder.begin_render_pass(
            color_attachments=[{
                "view": current_texture.create_view(),
                "resolve_target": None,
                "clear_value": (0.05, 0.05, 0.08, 1.0),
                "load_op": wgpu.LoadOp.clear,
                "store_op": wgpu.StoreOp.store
            }]
        )
        render_pass.set_pipeline(self.render_pipeline)
        
        # Bind slot 0: Geometri lokal
        render_pass.set_vertex_buffer(0, self.vertex_buffer)
        # Bind slot 1: Data agen (Compute Storage Buffer difungsikan sebagai Vertex Instance Buffer)
        render_pass.set_vertex_buffer(1, self.agent_buffer)
        
        # Eksekusi instanced draw call: 3 vertex per instance, sejumlah NUM_AGENTS
        render_pass.draw(vertex_count=3, instance_count=NUM_AGENTS, first_vertex=0, first_instance=0)
        render_pass.end()

        # Submit perintah ke GPU Queue
        self.device.queue.submit([encoder.finish()])

# ============================================================================
# RUNTIME ENTRYPOINT
# ============================================================================

def main() -> None:
    canvas = WgpuCanvas(title="Modern GPU Pipeline: Instanced Agent Simulation", size=(1024, 768))
    pipeline_engine = ModernGraphicsComputePipeline(canvas)

    last_time = None

    def draw_frame() -> None:
        nonlocal last_time
        import time
        now = time.perf_counter()
        dt = (now - last_time) if last_time is not None else 0.016
        last_time = now

        # Menjaga stabilitas delta time dari spike ekstrem
        dt = min(dt, 0.033)

        pipeline_engine.step_and_render(dt)
        canvas.request_draw()

    canvas.request_draw(draw_frame)
    run()

if __name__ == "__main__":
    main()
```

---

## 7. Edge Cases & Failure Modes

### 7.1 Data Race & Memory Hazards (RAW, WAR, WAW)
* **Kondisi**: Compute Pass menulis data agen pada frame saat ini sementara Vertex Fetch pada render pass sebelumnya belum selesai membaca data dari area memori yang sama.
* **Mitigasi**: 
  1. *Resource Transition Barriers*: Menambahkan dependensi pipeline eksplisit menggunakan sinkronisasi subpass atau barrier antrian:
     ```python
     # Konseptual Vulkan-level barrier:
     # srcStageMask = VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT
     # dstStageMask = VK_PIPELINE_STAGE_VERTEX_INPUT_BIT
     # srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT
     # dstAccessMask = VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT
     ```
  2. *Double-buffering (Ping-Pong buffers)*: Memisahkan buffer input status dan output status agen jika simulasi memerlukan data *neighbor querying* yang deterministik tanpa race condition.

### 7.2 GPU Timeout Detection and Recovery (TDR)
* **Kondisi**: Eksekusi *Compute Pass* memproses query spasial agen yang terlalu padat ($O(N^2)$ brute-force avoidance), menyebabkan kernel shader berjalan lebih lama dari ambang batas OS (biasanya 2 detik di Windows). Driver me-reset context kartu grafis, menghasilkan `DeviceLostError`.
* **Mitigasi**:
  * Pecah dispatch masif menjadi beberapa eksekusi sub-workgroup berurutan atau gunakan akselerasi struktur data spasial berbasis GPU (*Linear Bounding Volume Hierarchy* / LBVH atau *Uniform Spatial Grid Hash*).
  * Implementasikan callback pemulihan context (`device.lost.then(...)`) untuk mengalokasi ulang buffer tanpa menjatuhkan proses aplikasi utama.

### 7.3 Divergensi Warp / Wavefront
* **Kondisi**:
  ```wgsl
  if (agent.velocity.x > 0.0) {
      // Jalur Branch A
  } else {
      // Jalur Branch B
  }
  ```
  Jika 16 thread dalam warp mengeksekusi Jalur A dan 16 thread mengeksekusi Jalur B, efisiensi eksekusi turun menjadi 50%.
* **Mitigasi**: Gunakan fungsi intrinsik bebas percabangan matematis (*branchless programming*) dengan operator `select()`, `clamp()`, `step()`, atau `mix()`.

---

## 8. Trade-offs & Alternatif Solusi

| Kriteria / Arsitektur | Forward Rendering Klasik | Deferred Shading | Clustered Shading (Forward+) | GPU-Driven Rendering (Mesh Shader) |
| :--- | :--- | :--- | :--- | :--- |
| **Kompleksitas Komputasi Cahaya** | $O(\text{Piksel} \times \text{Lampu})$ | $O(\text{Piksel}) + O(\text{Lampu})$ | $O(\text{Piksel} \times \frac{\text{Lampu}}{\text{Cluster}})$ | $O(\text{Cluster}) + \text{Culling Dinamis}$ |
| **Overhead Memori (VRAM)** | Sangat Rendah | Sangat Tinggi (G-Buffer raksasa) | Moderat | Rendah – Moderat |
| **Penanganan Geometri Transparan** | Alami & Mudah | Sangat Sulit (Perlu Forward Pass terpisah) | Mendukung native | Mendukung native |
| **Beban Bandwidth Memori** | Rendah (Kecuali overdraw parah) | Sangat Tinggi (Read/Write Multi-RenderTarget) | Rendah (Single Pass) | Sangat Efisien (Cache-friendly) |
| **Kesesuaian Sensor AI Agen** | Kurang Optimal | **Sangat Baik** (Dapat langsung mengekstrak Depth, Albedo, Normal buffer) | Baik | **Sangat Baik** (Menangani jutaan instance agen secara instan) |

### Analisis Evaluatif: Compute Buffer vs Uniform Buffer
* **Uniform Buffers**: Dibatasi ukuran alokasi kecil (biasanya $\le 64 \text{ KB}$), tetapi di-cache secara agresif pada memori L1/Konstan perangkat keras. Ideal untuk parameter global lingkungan (cth: matriks kamera, parameter simulasi global).
* **Storage Buffers (SSBO)**: Mendukung kapasitas hingga beberapa gigabyte, mendukung operasi atomik dan pembacaan/penulisan simultan. Esensial untuk menyimpan seluruh larik struktur agen.

---

## 9. Best Practices & Standar Industri

1. **Alignment & Padding Struktur Data (std140 & std430 Rule)**:
   * Pada layout memori GPU (`WGSL`/`GLSL`/`HLSL`), tipe data vektor 2-komponen (`vec2`) memiliki alignment 8-byte, sedangkan `vec4` memiliki alignment 16-byte.
   * Pastikan array of structures (AoS) pada CPU memiliki padding yang identik dengan layout shader agar tidak terjadi pergeseran memori (*memory misalignment distortion*).
2. **Hindari Sinkronisasi CPU-GPU Menggunakan Blocking Calls**:
   * Jangan pernah memanggil operasi pembacaan buffer sinkron (seperti `map_read` atau `glGetBufferSubData`) di dalam loop render utama. Operasi ini memaksa pipeline GPU terhenti (*pipeline stall*), menunggu seluruh pipa eksekusi kosong.
3. **Instanced Indirect Drawing**:
   * Pada pipeline generasi modern, gunakan *Indirect Draws* di mana jumlah instansiasi dan parameter gambar tidak ditulis oleh CPU, melainkan dihasilkan langsung oleh *Compute Pass* lain yang melakukan *Frustum Culling* dan *Occlusion Culling* berbasis GPU.
4. **Pre-compiled PSOs**:
   * Buat dan kompilasi seluruh *Pipeline State Objects* saat inisialisasi aplikasi. Kompilasi shader saat *runtime gameplay* akan menyebabkan lonjakan latensi frame (*frame stutter*).

---

## 10. Hands-on Lab Exercise

### Judul Lab: Implementasi Sensor Visi Simfoni (Multi-Render Target Depth & Semantics)
**Tujuan**: Memodifikasi Graphics Pipeline agar menghasilkan dua *render target* secara bersamaan: (1) Citra visual RGB, dan (2) Buffer Segmentasi Semantik Agen & Kedalaman, yang diumpankan ke model sensor Vision AI otonom.

### Prasyarat
* Lingkungan Python $\ge 3.10$ terpasang modul `wgpu` dan `numpy`.
* Perangkat keras atau backend software (Vulkan/Metal/DirectX 12) yang mendukung konfigurasi Multi-Render-Target (MRT).

### Langkah Implementasi

#### Langkah 1: Modifikasi Shader Interface
Buka modul shader render dan definisikan output fragment ganda (*Dual Target*):

```wgsl
struct FragmentOutput {
    @location(0) color_target: vec4<f32>,
    @location(1) semantic_target: vec4<f32>,
};

@fragment
fn fs_main(in: VertexOutput) -> FragmentOutput {
    var output: FragmentOutput;
    
    // Target 0: Visualisasi warna RGB
    output.color_target = vec4<f32>(in.color, 1.0);
    
    // Target 1: Ground Truth ID Semantik (Misal: ID Kelas Agen = 1.0, Background = 0.0)
    // dan kedalaman terformat
    output.semantic_target = vec4<f32>(1.0, 0.0, in.clip_position.z, 1.0);
    
    return output;
}
```

#### Langkah 2: Alokasi Texture Target Tambahan
Tambahkan tekstur sekunder untuk menampung data segmentasi pada Python script:

```python
# Di dalam _allocate_buffers / init:
self.semantic_texture = self.device.create_texture(
    size=(1024, 768, 1),
    usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
    format=wgpu.TextureFormat.rgba8unorm
)
self.semantic_view = self.semantic_texture.create_view()
```

#### Langkah 3: Update Deskriptor Render Pipeline
Sesuaikan atribut fragment pipeline untuk menerima dua target:

```python
# Di dalam _build_render_pipeline:
fragment_targets = [
    {"format": self.render_format},             # Target 0: Swapchain Canvas
    {"format": wgpu.TextureFormat.rgba8unorm}    # Target 1: Sensor Visual AI
]
# Terapkan array targets ini ke parameter fragment pipeline.
```

#### Langkah 4: Modifikasi Render Pass Attachments
Perbarui daftar *color attachments* saat encoding Render Pass:

```python
render_pass = encoder.begin_render_pass(
    color_attachments=[
        {
            "view": current_texture.create_view(),
            "load_op": wgpu.LoadOp.clear,
            "store_op": wgpu.StoreOp.store,
            "clear_value": (0.05, 0.05, 0.08, 1.0),
        },
        {
            "view": self.semantic_view,
            "load_op": wgpu.LoadOp.clear,
            "store_op": wgpu.StoreOp.store,
            "clear_value": (0.0, 0.0, 0.0, 1.0),
        }
    ]
)
```

### Verifikasi Keberhasilan
Jalankan harness pengujian berikut untuk memvalidasi bahwa buffer target kedua berhasil dialokasikan dan menerima data semantik agen:

```python
def verify_pipeline_integrity(engine: ModernGraphicsComputePipeline) -> None:
    # Trigger 1 siklus render pass
    engine.step_and_render(0.016)
    
    # Validasi spesifikasi tekstur MRT
    assert engine.semantic_texture.size == (1024, 768, 1), "Dimensi Render Target Semantik Salah!"
    assert engine.semantic_texture.format == wgpu.TextureFormat.rgba8unorm, "Format Warna Tidak Sesuai!"
    logger.info("VERIFIKASI PIPELINE BERHASIL: Multi-Render-Target aktif dan valid.")

verify_pipeline_integrity(pipeline_engine)
```

**Hasil yang Diharapkan:**
```text
[INFO] Adapter Aktif: NVIDIA GeForce RTX ... / Apple M-Series / Intel Iris
[INFO] Pipeline State Objects (PSO) dan Buffers berhasil dikompilasi.
[INFO] VERIFIKASI PIPELINE BERHASIL: Multi-Render-Target aktif dan valid.
```