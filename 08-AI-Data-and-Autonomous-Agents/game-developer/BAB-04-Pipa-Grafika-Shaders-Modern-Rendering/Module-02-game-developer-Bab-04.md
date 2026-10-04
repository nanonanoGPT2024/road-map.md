# BAB 04: Pipa Grafika, Shaders & Modern Rendering
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur rendering modern berbasis **GPU-Driven Pipeline** menggunakan Compute Shader untuk *Frustum* dan *Occlusion Culling* (Hi-Z).
- Menganalisis perbedaan performa, *memory bandwidth*, dan trade-off antara arsitektur **Clustered Forward Rendering** dan **Modern Deferred Shading with Tile-Based Compute**.
- Mengeliminasi overhead CPU bottleneck dengan memanfaatkan **Bindless Resource Management** dan **Indirect Draw Execution** (`vkCmdDrawIndexedIndirect` / `ExecuteIndirect`).
- Menulis dan mengoptimalkan compute shader tingkat lanjut untuk komputasi paralel masif dengan meminimalisasi *thread divergence* dan memaksimalkan penggunaan *Shared Memory/LDS (Local Data Share)*.
- Menerapkan pipeline mitigasi *pipeline stalls* dan *GPU bubble* melalui *Asynchronous Compute* dan sinkronisasi *explicit barriers*.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta harus telah menguasai:
- **Foundational Graphics Concepts**: Pipeline rasterisasi dasar (Vertex, Fragment/Pixel, Rasterizer), linear algebra (vektor, matriks 4x4, transformasi affine, quaternion), dan ruang koordinat (Object, World, View, Clip, NDC, Screen Space).
- **Modern Low-Level Graphics APIs**: Pemahaman kerja Vulkan (Descriptor Sets, Command Buffers, Pipelines) atau DirectX 12 (Root Signatures, Command Lists, PSO).
- **Bahasa Pemrograman**: C++17/20 tingkat lanjut (manajemen memori manual, pointer, alignment, multi-threading) dan HLSL/GLSL/Slang untuk shader writing.
- **Hardware Architecture Awareness**: Pengetahuan mendasar mengenai arsitektur GPU kontemporer (SIMD/SIMT model, Warps/Wavefronts, GPC, SM/Compute Unit, VRAM bus latency, L1/L2 Cache hierarchy).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Evolusi dari CPU-Driven ke GPU-Driven Rendering Pipeline
Dalam rendering konvensional (CPU-Driven), CPU bertanggung jawab untuk:
1. Memeriksa visibilitas objek (*Frustum Culling* via CPU BVH traversal).
2. Melakukan sorting berdasarkan material atau kedalaman (*State Sorting*).
3. Melakukan iterasi jutaan objek dan membungkusnya dalam satu per satu *API Draw Calls* (`glDrawElements`, `vkCmdDrawIndexed`).
4. Mengunggah data per-objek (Matrix transforms) ke Dynamic Uniform Buffers.

Masalah utama dari arsitektur ini adalah **CPU Bottleneck**: CPU kehabisan siklus instruksi untuk memetakan objek ke GPU, menyebabkan GPU sering berada dalam kondisi *starvation* (idle cycles).

```
[ Traditional CPU-Driven Pipeline ]
CPU: [ Frustum Cull ] -> [ State Sort ] -> [ Set Descriptor ] -> [ vkCmdDrawIndexed ] x 10,000 -> Stalls!
GPU:                                                               [ Vertex ] -> [ Pixel ]

[ Modern GPU-Driven Pipeline ]
CPU: [ Push Frame Data ] -----------------------------------------------------> [ Wait/Frame sync ]
GPU: [ Compute: Cull & Hi-Z ] -> [ Build Indirect Args ] -> [ Execute Indirect ] -> [ Rasterize ]
```

Dalam **GPU-Driven Pipeline**:
- Seluruh scene representation (*Bounding Volumes*, *Mesh Instance Data*, *Transform Matrices*) disimpan secara persisten di VRAM dalam bentuk Storage Buffers (`VkBuffer` dengan *Device Local Memory*).
- CPU hanya menerbitkan **satu** perintah draw call global: `vkCmdDrawIndexedIndirect`.
- Compute shader mengevaluasi visibilitas ribuan instans objek secara paralel menggunakan *Frustum Culling* dan *Hi-Z (Hierarchical Z-Buffer) Occlusion Culling*.
- Compute shader menuliskan parameter draw call (*Index count, Instance count, First index, Base vertex, Base instance*) secara langsung ke dalam indirect argument buffer yang akan dikonsumsi oleh Fixed-Function Command Processor GPU.

#### 3.2 Hardware Execution Model: Wavefronts, Warps, dan Register Allocation
GPU modern mengeksekusi instruksi dalam unit eksekusi paralel yang disebut **Warp** (NVIDIA, 32 thread) atau **Wavefront** (AMD, 32 atau 64 thread).
- **Lock-step Execution**: Seluruh thread dalam satu Warp mengeksekusi Program Counter (PC) yang sama.
- **Branch Divergence**: Ketika terjadi branching dinamis (`if (condition)`):
  - Jika 16 thread mengambil branch `true` dan 16 thread mengambil branch `false`, Warp akan mengeksekusi *kedua jalur secara sekuensial* menggunakan execution mask. Ini memotong throughput komputasi hingga 50%.
- **Register Pressure vs. Occupancy**:
  - Setiap SM (*Streaming Multiprocessor*) / CU (*Compute Unit*) memiliki alokasi register file berukuran tetap (misal: 64 KB atau 256 KB).
  - Jumlah register yang digunakan per shader thread berbanding terbalik dengan jumlah Warp aktif yang dapat dijadwalkan secara simultan (*Occupancy*).
  - Jika shader menggunakan terlalu banyak *Virtual Registers* ($>64$ per thread), GPU terpaksa mengurangi occupancy, sehingga kehilangan kemampuannya untuk menyembunyikan *memory latency* (VRAM stall hiding).

#### 3.3 Memory Latency Hiding & Cache Coherency
Latency akses memori ke VRAM (HBM2e / GDDR6) adalah sekitar 200 hingga 400 siklus GPU. Untuk menyembunyikan latensi ini, scheduler GPU melakukan *latency hiding* dengan cara menukar Warp yang sedang menunggu data (misal: menunggu hasil *Texture Fetch*) dengan Warp lain yang instruksinya siap dieksekusi (*Arithmetic Logic Execution*).

```
Cycle 0      : Warp 0 -> Memory Fetch (Stall) -> Scheduler parkir Warp 0
Cycle 1      : Warp 1 -> Math Instruction (ALU)
Cycle 2      : Warp 2 -> Math Instruction (ALU)
...
Cycle 200    : Data Warp 0 selesai di-fetch -> Scheduler mengaktifkan kembali Warp 0
```

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Itu Sebenarnya (What) |
| :--- | :--- | :--- |
| **GPU-Driven Culling** | CPU bound pada scene masif (>100.000 draw calls) menghancurkan target frametime 16.6ms (60 FPS) atau 8.3ms (120 FPS). | Compute shader yang menguji bounding box scene terhadap view frustum dan hierarki kedalaman (Hi-Z), menghasilkan indirect draw command. |
| **Bindless Textures** | State swapping (berganti texture bind per objek) memaksa CPU melakukan context switch dan membatasi batching. | Teknik mendeskripsikan seluruh tekstur ke dalam satu global descriptor array array-of-textures, diakses melalui dynamic integer index pada shader. |
| **Clustered Shading** | Deferred shading biasa boros bandwidth memori pada resolusi 4K dan tidak mendukung multi-layer transparency secara native. | Algoritma pencahayaan yang membagi View Frustum secara spatial menjadi grid 3D ($X \times Y \times Z$), mengalokasikan index lampu per-cluster via Compute Pass. |
| **Hi-Z Occlusion** | Objek-objek yang berada di belakang objek besar (seperti gedung/gunung) tetap diproses jika hanya mengandalkan frustum culling. | Pengujian bounding box instans terhadap downsampled mip chain dari Depth Buffer frame sebelumnya secara hierarkis pada Compute Shader. |

---

### 5. How (Workflow Detail)

Arsitektur produksi modern umumnya mengimplementasikan tahapan eksekusi frame sebagai berikut:

```
+---------------------------------------------------------------------------------------+
|                               GPU FRAME TIMELINE PIPELINE                             |
+---------------------------------------------------------------------------------------+
 [ Phase 1: Depth Pre-pass & Hi-Z Generation ]
   CPU  : Menerbitkan static mesh depth draws
   GPU  : Render static depth -> Compute: Generate Hi-Z Downsampled Mip Chain

 [ Phase 2: Compute Culling Pass (Async Compute Queue) ]
   GPU  : Traversal Bounding Box vs View Frustum & Hi-Z Buffer
   GPU  : Tulis hasil lolos ke Indirect Draw Buffer & Compact Buffers via Atomic Counter

 [ Phase 3: Clustered Light Assignment ]
   GPU  : Compute: AABB Frustum Slicing -> Intersect point/spot lights per 3D Cluster Grid
   GPU  : Simpan Light Index List & Cluster Lookup Table

 [ Phase 4: Base Pass (G-Buffer atau Clustered Forward) ]
   GPU  : Eksekusi vkCmdDrawIndexedIndirect -> Bindless Resource Lookups -> Output Render Targets

 [ Phase 5: Compute Post-Processing & Async Compute Passes ]
   GPU  : TAA, SSR / Ray Traced Reflections, Bloom, Tonemapping
+---------------------------------------------------------------------------------------+
```

1. **Hi-Z Pyramid Creation**: Depth frame sebelumnya (atau depth pre-pass frame aktif) di-downsample menggunakan compute shader dengan operasi `min()` atau `max()` depth (tergantung *reverse-Z*) hingga level $1 \times 1$.
2. **GPU Culling Execution**:
   - Instance data dimasukkan via buffer berukuran $N$.
   - Compute Shader (Workgroup size: 64 thread) mengambil instance ID via `SV_DispatchThreadID`.
   - Menguji 8 sudut Bounding Box (AABB) terhadap 6 plane frustum kamera.
   - Jika lolos, proyeksikan AABB ke screen space, ambil level mip Hi-Z yang sesuai dengan ukuran proyeksi AABB, lalu bandingkan depth instance terhadap depth Hi-Z.
   - Jika lolos Hi-Z, lakukan `InterlockedAdd` pada argument indirect draw buffer, lalu tulis index instance ke index buffer aktif.
3. **Execute Indirect**: Pipeline utama membaca buffer argument tersebut langsung pada GPU Command Processor tanpa intervensi CPU.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional dan Sistem Pemeriksaan Bagasi
- **CPU-Driven Rendering** ibarat petugas tiket (CPU) yang memegang koper setiap penumpang satu per satu, mengukurnya secara manual, mengantarkannya langsung ke lambung pesawat (GPU), lalu kembali lagi untuk mengambil koper berikutnya. Sistem akan macet jika ada 5.000 penumpang.
- **GPU-Driven Rendering** ibarat sistem logistik bandara modern: Semua koper dimasukkan ke conveyor belt otomatis berkecepatan tinggi. Scanner otomatis (Compute Shader) memilah koper mana yang lolos ukuran dan berat (Frustum & Occlusion Culling) secara paralel dalam hitungan detik. Koper yang lolos langsung dialirkan masuk ke pesawat secara otomatis tanpa petugas menyentuh koper tersebut kembali.

#### Diagram Hierarki Clustered Shading (3D Cluster Grid):
```
Near Plane (Z = 0.1m)
+---+---+---+---+   Slice Z = 0
|   |   |   |   |   Setiap kubus kecil adalah "Cluster" (Tile X, Tile Y, Depth Slice Z).
+---+---+---+---+   
|   |   |   |   |   Compute shader memetakan lampu ke dalam
+---+---+---+---+   cluster yang bersinggungan saja.
 \   \   \   \
  \   \   \   \     Frustum meluas secara eksponensial secara logaritmik
   \   \   \   \    sepanjang sumbu Z kamera hingga Far Plane.
    +----+----+----+----+
    |    |    |    |    |  Slice Z = N (Far Plane, misal: Z = 1000m)
    +----+----+----+----+
    |    |    |    |    |
    +----+----+----+----+
```

---

### 7. Simple Example & Practical Example (Standar Industri)

#### 7.1 Simple Example: Basic Compute Shader Frustum Culling (HLSL / Slang)
Shader ini menguji satu bounding sphere terhadap 6 plane frustum.

```hlsl
// culling_simple.hlsl
struct InstanceData {
    float3 Position;
    float  Radius;
    uint   MeshIndex;
};

struct DrawIndexedIndirectCommand {
    uint IndexCountPerInstance;
    uint InstanceCount;
    uint StartIndexLocation;
    int  BaseVertexLocation;
    uint StartInstanceLocation;
};

ConstantBuffer<float4> FrustumPlanes[6] : register(b0);
StructuredBuffer<InstanceData> AllInstances : register(t0);
RWStructuredBuffer<DrawIndexedIndirectCommand> OutCommand : register(u0);
RWStructuredBuffer<uint> OutVisibleInstanceIDs : register(u1);

[numthreads(64, 1, 1)]
void CSMain(uint3 dispatchThreadId : SV_DispatchThreadID)
{
    uint instanceID = dispatchThreadId.x;
    // Early exit jika melebihi total instans
    if (instanceID >= 100000) return;

    InstanceData instance = AllInstances[instanceID];
    
    // Frustum sphere test
    bool visible = true;
    [unroll]
    for (int i = 0; i < 6; ++i) {
        float distance = dot(FrustumPlanes[i].xyz, instance.Position) + FrustumPlanes[i].w;
        if (distance < -instance.Radius) {
            visible = false;
            break;
        }
    }

    if (visible) {
        uint slotIndex;
        // Atomically increment visible instance count
        InterlockedAdd(OutCommand[0].InstanceCount, 1, slotIndex);
        OutVisibleInstanceIDs[slotIndex] = instanceID;
    }
}
```

#### 7.2 Practical Example: Production-Ready GPU Hi-Z Culling & Indirect Argument Generation
Contoh kode C++ (skema Vulkan) dan Shader HLSL modern lengkap dengan Hierarchical-Z Occlusion Culling.

**Compute Shader: `hiz_culling.hlsl`**
```hlsl
// hiz_culling.hlsl - Production Standard Hi-Z & Frustum Culling
struct BoundingBox {
    float3 Center;
    float3 Extents;
};

struct InstanceDrawData {
    BoundingBox Bounds;
    float4x4    WorldMatrix;
    uint        IndexCount;
    uint        StartIndex;
    uint        BaseVertex;
};

struct IndirectDrawIndexedArgs {
    uint IndexCount;
    uint InstanceCount;
    uint FirstIndex;
    int  VertexOffset;
    uint FirstInstance;
};

cbuffer FrameData : register(b0) {
    float4x4 ViewProjection;
    float4x4 ViewMatrix;
    float4   FrustumPlanes[6];
    float2   HiZScreenSize;
    float    ZNear;
    float    ZFar;
};

Texture2D<float> HiZMap : register(t0);
SamplerState     PointClampSampler : register(s0);

StructuredBuffer<InstanceDrawData> Instances : register(t1);
RWStructuredBuffer<IndirectDrawIndexedArgs> DrawArgs : register(u0);
RWStructuredBuffer<uint> VisibleInstanceBuffer : register(u1);

bool IsAABBOutsidePlane(float3 center, float3 extents, float4 plane) {
    float3 p = center + extents * sign(plane.xyz);
    return (dot(plane.xyz, p) + plane.w) < 0.0f;
}

[numthreads(64, 1, 1)]
void MainCS(uint3 dispatchThreadId : SV_DispatchThreadID) {
    uint id = dispatchThreadId.x;
    if (id >= 250000) return; // Asumsi 250K total objects

    InstanceDrawData inst = Instances[id];

    // 1. Frustum Culling
    [unroll]
    for (int i = 0; i < 6; ++i) {
        if (IsAABBOutsidePlane(inst.Bounds.Center, inst.Bounds.Extents, FrustumPlanes[i])) {
            return; // Dieliminasi oleh Frustum
        }
    }

    // 2. Project AABB ke Screen Space untuk Hi-Z Culling
    float3 minPoint = inst.Bounds.Center - inst.Bounds.Extents;
    float3 maxPoint = inst.Bounds.Center + inst.Bounds.Extents;

    float3 boxCorners[8] = {
        float3(minPoint.x, minPoint.y, minPoint.z),
        float3(minPoint.x, minPoint.y, maxPoint.z),
        float3(minPoint.x, maxPoint.y, minPoint.z),
        float3(minPoint.x, maxPoint.y, maxPoint.z),
        float3(maxPoint.x, minPoint.y, minPoint.z),
        float3(maxPoint.x, minPoint.y, maxPoint.z),
        float3(maxPoint.x, maxPoint.y, minPoint.z),
        float3(maxPoint.x, maxPoint.y, maxPoint.z)
    };

    float minZ = 1.0f;
    float4 screenBounds = float4(1.0f, 1.0f, -1.0f, -1.0f); // minXY, maxXY

    [unroll]
    for (int c = 0; c < 8; ++c) {
        float4 clip = mul(ViewProjection, float4(boxCorners[c], 1.0f));
        if (clip.w <= 0.0f) continue; // Di belakang kamera
        
        float3 ndc = clip.xyz / clip.w;
        float2 uv = ndc.xy * float2(0.5f, -0.5f) + 0.5f;

        screenBounds.xy = min(screenBounds.xy, uv);
        screenBounds.zw = max(screenBounds.zw, uv);
        minZ = min(minZ, ndc.z); // Asumsi Standard 0..1 atau Reverse-Z
    }

    // Clamp UV ke boundary layar
    screenBounds = saturate(screenBounds);

    // 3. Hi-Z Occlusion Test
    float2 size = (screenBounds.zw - screenBounds.xy) * HiZScreenSize;
    float maxDimension = max(size.x, size.y);
    float mipLevel = ceil(log2(max(maxDimension, 1.0f)));

    // Ambil sampel 4 tap pada mip level terpilih
    float4 depthTaps;
    depthTaps.x = HiZMap.SampleLevel(PointClampSampler, screenBounds.xy, mipLevel).r;
    depthTaps.y = HiZMap.SampleLevel(PointClampSampler, screenBounds.zy, mipLevel).r;
    depthTaps.z = HiZMap.SampleLevel(PointClampSampler, screenBounds.xw, mipLevel).r;
    depthTaps.w = HiZMap.SampleLevel(PointClampSampler, screenBounds.zw, mipLevel).r;

    // Untuk Reverse-Z (1 = Near, 0 = Far):
    float maxOccluderDepth = max(max(depthTaps.x, depthTaps.y), max(depthTaps.z, depthTaps.w));
    
    // Jika bounding box berada lebih jauh dari occluder terdalam, cull objek
    if (minZ < maxOccluderDepth) {
        return; // Terhalang oleh geometri lain
    }

    // Objek Lolos! Tulis ke dynamic command buffer
    uint writeIndex;
    InterlockedAdd(DrawArgs[0].InstanceCount, 1, writeIndex);
    VisibleInstanceBuffer[writeIndex] = id;
}
```

**Host C++ Pipeline Integration (Sketsa Arsitektur Vulkan API):**
```cpp
// GpuDrivenRenderer.cpp
#include <vulkan/vulkan.h>
#include <cstdint>

struct DrawIndexedIndirectCommand {
    uint32_t indexCount;
    uint32_t instanceCount;
    uint32_t firstIndex;
    int32_t  vertexOffset;
    uint32_t firstInstance;
};

class GpuDrivenRenderer {
public:
    void ExecuteFrame(VkCommandBuffer cmd, VkBuffer indirectBuffer, VkBuffer countBuffer) {
        // Step 1: Reset Instance Count ke 0 pada Indirect Buffer via vkCmdFillBuffer
        vkCmdFillBuffer(cmd, indirectBuffer, offsetof(DrawIndexedIndirectCommand, instanceCount), sizeof(uint32_t), 0);

        // Pasang Barrier: Pastikan FillBuffer selesai sebelum Compute Culling menulis
        VkMemoryBarrier2 clearToComputeBarrier{
            .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER_2,
            .srcStageMask = VK_PIPELINE_STAGE_2_TRANSFER_BIT,
            .srcAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT,
            .dstStageMask = VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT,
            .dstAccessMask = VK_ACCESS_2_SHADER_STORAGE_READ_BIT | VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT
        };
        VkDependencyInfo dep1{ .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO, .memoryBarrierCount = 1, .pMemoryBarriers = &clearToComputeBarrier };
        vkCmdPipelineBarrier2(cmd, &dep1);

        // Step 2: Jalankan Compute Shader Culling (250,000 instance / 64 threads per group)
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_cullingPipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_cullingPipelineLayout, 0, 1, &m_cullingDescriptorSet, 0, nullptr);
        vkCmdDispatch(cmd, (250000 + 63) / 64, 1, 1);

        // Step 3: Barrier Compute Write -> Indirect Read & Vertex Shader Input
        VkMemoryBarrier2 computeToDrawBarrier{
            .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER_2,
            .srcStageMask = VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT,
            .srcAccessMask = VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT,
            .dstStageMask = VK_PIPELINE_STAGE_2_DRAW_INDIRECT_BIT | VK_PIPELINE_STAGE_2_VERTEX_SHADER_BIT,
            .dstAccessMask = VK_ACCESS_2_INDIRECT_COMMAND_READ_BIT | VK_ACCESS_2_SHADER_STORAGE_READ_BIT
        };
        VkDependencyInfo dep2{ .sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO, .memoryBarrierCount = 1, .pMemoryBarriers = &computeToDrawBarrier };
        vkCmdPipelineBarrier2(cmd, &dep2);

        // Step 4: Render Scene Menggunakan Eksekusi Indirect
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, m_basePassPipeline);
        vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, m_basePassPipelineLayout, 0, 1, &m_bindlessMeshSet, 0, nullptr);
        
        // Membaca argumen yang dihasilkan 100% oleh compute shader
        vkCmdDrawIndexedIndirect(cmd, indirectBuffer, 0, 1, sizeof(DrawIndexedIndirectCommand));
    }

private:
    VkPipeline       m_cullingPipeline;
    VkPipelineLayout m_cullingPipelineLayout;
    VkDescriptorSet  m_cullingDescriptorSet;

    VkPipeline       m_basePassPipeline;
    VkPipelineLayout m_basePassPipelineLayout;
    VkDescriptorSet  m_bindlessMeshSet;
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Studi Kasus: Unreal Engine 5 Nanite Virtualized Geometry
*Nanite* mengubah paradigma rendering modern dengan memaksimalkan instruksi GPU-driven secara penuh.
- **Problem Formulation**: Pada game open-world dengan resolusi poligon film-grade (ratusan juta segitiga per frame), CPU-culling mustahil memproses data tepat waktu. Selain itu, rasterizer konvensional mengalami degradasi performa luar biasa ketika ukuran poligon lebih kecil dari satu piksel hardware (*Quad-overdraw penalty*).
- **Architectural Solution**:
  1. **Hierarchical Cluster Trees (BVH on GPU)**: Mesh di-precompute menjadi cluster-cluster berisi rata-rata 128 segitiga.
  2. **Streaming & GPU Culling**: Nanite mengevaluasi level-of-detail (LOD) dinamis dan visibilitas per cluster pada Compute Shader.
  3. **Custom Software Rasterizer**: Jika poligon cluster lebih kecil dari ukuran quad standar hardware ($2 \times 2$ pixel), Nanite memotong pipa rasterisasi GPU standar dan menjalankan **Compute Shader Software Rasterizer** yang menuliskan instance ID dan depth langsung ke 64-bit VisBuffer (`R32G32_UINT`).
- **Impact & Measurements**:
  - Mengurangi draw call CPU dari puluhan ribu menjadi kurang dari 10 indirect draw per frame.
  - Memori rendering tetap stabil meskipun densitas geometri meningkat dari puluhan ribu menjadi jutaan instans dalam jarak pandang puluhan kilometer.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
       [ TRADEOFF COMPARISON: RENDERING ARCHITECTURES ]
                
                   Forward+ (Clustered)
                         /\
                        /  \
                       /    \
                      /      \
      Bandwidth      /________\   Complex Multi-Material
      Efficient     /          \  Support
                   /____________\
      Traditional               Modern VisBuffer /
      Deferred                  GPU-Driven Deferred
      (High VRAM Bandwidth,     (High ALU Cost,
       Terrible MSAA)            Complex Tooling)
```

| Dimensi Arsitektur | Traditional Deferred | Clustered Forward | GPU-Driven VisBuffer |
| :--- | :--- | :--- | :--- |
| **VRAM Bandwidth Consumption** | **Sangat Tinggi** (Membutuhkan 4-5 G-Buffer formats: Albedo, Normal, Material, Depth). | **Rendah** (Hanya 1 Depth Pass + Forward Framebuffer). | **Ultra Rendah** (Hanya render Material ID + Primitive ID ke single 64-bit target). |
| **Material Flexibility** | **Terbatas** (Semua material harus muat dalam model shading G-Buffer yang sama). | **Tinggi** (Setiap material dapat mengompilasi shader unik, mendukung transparan). | **Sangat Tinggi** (Material dievaluasi terpisah pada pass kedua menggunakan bindless resource). |
| **CPU Overhead** | **Tinggi** (Perlu memilah state draw calls). | **Sedang** (Perlu memetakan light frustum di CPU jika tidak di-port ke compute). | **Minimal** (CPU hanya mendispatch 1-5 indirect calls). |
| **GPU ALU Cost** | Rendah-Sedang. | Sedang (Tergantung jumlah cluster light limits). | Tinggi (Membutuhkan decode visibility buffer dan per-pixel barycentric derivation). |
| **Hardware Compatibility** | GPU Lama (DX11, OpenGL 4.x). | GPU Modern (DX11 feature level 11_0+, Vulkan). | GPU Modern Tingkat Lanjut (DX12 SM 6.6+, Vulkan 1.2+ dengan dynamic indexing / bindless). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. GPU Race Condition pada Atomic Increment Argument Buffer
- **Gejala**: Geometri berkedip-kedip (*flickering*), atau rendering *crash* dengan kode `VK_ERROR_DEVICE_LOST` / `DXGI_ERROR_DEVICE_REMOVED`.
- **Akar Masalah**: Kegagalan menginisialisasi atau me-reset counter `InstanceCount` kembali ke nol di setiap frame sebelum compute shader dijalankan, atau mengeksekusi multi-workgroup atomic tanpa boundary barrier eksplisit.
- **Solusi**: Gunakan `vkCmdFillBuffer` untuk me-reset counter tepat sebelum culling pass, pasang pipeline barrier `VK_PIPELINE_STAGE_2_TRANSFER_BIT` $\to$ `VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT`.

#### 2. False Occlusion Culling (Objek Lenyap di Tepi Layar)
- **Gejala**: Objek menghilang saat kamera berputar, terutama saat objek berada di pinggir viewport.
- **Akar Masalah**: Perhitungan Mip Level Hi-Z salah mengasumsikan resolusi nonsquare, atau pengujian AABB menghasilkan proyeksi di belakang *Camera Near Plane* ($W \le 0$) tanpa penanganan *homogeneous clipping*.
- **Solusi**: Terapkan *Near-plane clipping* pada AABB polygon sebelum proyeksi perspektif. Pastikan formula kalkulasi Mip menggunakan nilai konservatif:
  $$\text{mip} = \text{floor}(\log_2(\max(\text{width}, \text{height})))$$

#### 3. Memory Coherency & Missing Barricades
- **Gejala**: Compute shader menghasilkan data yang benar di frame debugger (RenderDoc/PIX), tetapi drawing command menggambar geometri frame sebelumnya atau artefak statis.
- **Akar Masalah**: Barrier antara Compute execution (`VK_ACCESS_SHADER_WRITE_BIT`) dan Indirect Command Consumption (`VK_ACCESS_INDIRECT_COMMAND_READ_BIT`) hilang atau salah set stage flags.
- **Solusi**: Pastikan `dstStageMask` menyertakan `VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT` dengan akses `VK_ACCESS_INDIRECT_COMMAND_READ_BIT`.

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Checklist untuk Render Architecture
- [ ] **Reverse-Z Implementation**: Gunakan Floating Point Depth (`VK_FORMAT_D32_SFLOAT`) dipadukan dengan Near Clip di $1.0$ dan Far Clip di $0.0$. Ini menyelesaikan masalah presisi kedalaman pada jarak jauh secara matematis.
- [ ] **Bindless Descriptor Sets**: Gunakan `VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT` dan `VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT` untuk memastikan jutaan tekstur dapat diakses langsung tanpa re-binding pipelines.
- [ ] **Shared Memory Padding**: Jika menggunakan *LDS / Thread Group Shared Memory* di Compute Shader, tambahkan padding untuk mencegah *bank conflicts* (akses ke memory bank 32-bit yang sama oleh thread berbeda pada Warp yang sama).
- [ ] **Workgroup Size Tuning**: Standardisasi Compute Workgroup Size ke $64$ thread. Ini kompatibel optimal dengan kelipatan Wavefront AMD (32/64) dan Warp NVIDIA (32), serta meminimalkan sisa thread yang tidak terpakai (*idle threads*).
- [ ] **Conservative Rasterization for Small Geometry**: Aktifkan Conservative Rasterization pada depth pre-pass untuk geometri tipis (antena, dedaunan) agar selalu menghasilkan sample di Hi-Z buffer.

---

### 12. Hands-on Practice

Simpan seluruh hasil pekerjaan Anda pada direktori: `hands-on/m02/`

#### Langkah Praktikum:
1. **Inisialisasi Data**:
   Buat file `hands-on/m02/scene_generator.py` untuk membangkitkan buffer binary `instances.bin` yang memuat 100.000 data AABB acak tersebar di area $1000 \times 1000 \times 1000$ unit.
2. **Kompilasi Shaders**:
   Tulis shader `hands-on/m02/shaders/cull.slang` (atau HLSL) yang mengimplementasikan Frustum Culling dan Occlusion Culling. Kompilasi shader ke format SPIR-V menggunakan `slangc` atau `dxc`:
   ```bash
   dxc -T cs_6_0 -E MainCS hiz_culling.hlsl -Fo hands-on/m02/shaders/cull.spv
   ```
3. **Eksekusi Host App**:
   Tulis program C++ sederhana `hands-on/m02/main.cpp` yang:
   - Membuat Vulkan/D3D12 device.
   - Mengalokasikan Host Visible Buffer untuk mentransfer `instances.bin` ke Device Local Memory.
   - Mengalokasikan indirect command buffer.
   - Melakukan dispatch compute shader berukuran $\lceil 100000 / 64 \rceil$.
   - Membaca hasil `InstanceCount` yang lolos kembali ke CPU menggunakan memory mapping untuk verifikasi kebenaran filter.
4. **Analisis Output**:
   Pastikan jumlah instans yang lolos berkurang secara proporsional ketika *Field of View (FOV)* kamera dipersempit.

---

### 13. Exercise

#### Level Easy
Ubah implementasi frustum culling dasar agar mengabaikan pengujian pada far-plane jika jarak render diset ke nilai tak terhingga (*Infinite Far Plane projection matrix*). Hitung efisiensi ALU yang dihemat (dalam satuan cycle shader instructions).

#### Level Medium
Tambahkan pengujian **LOD (Level of Detail)** selection langsung di dalam Compute Culling Shader.
- Input: Jarak kamera ke instance center.
- Aturan:
  - Jarak $< 50\text{m} \to \text{LOD 0 (Full detail)}$
  - Jarak $50\text{m} - 150\text{m} \to \text{LOD 1 (Medium detail)}$
  - Jarak $> 150\text{m} \to \text{LOD 2 (Low detail)}$
- Output: Tulis ke Indirect Argument Buffer yang berbeda untuk masing-masing LOD pass.

#### Level Hard
Rancang dan implementasikan **Two-Phase Occlusion Culling** menggunakan Hi-Z:
- **Phase 1**: Cull instans frame aktif hanya terhadap Hi-Z yang dibangun dari frame *sebelumnya*. Gambar instans yang lolos.
- **Update**: Buat Hi-Z baru dari geometri yang baru saja digambar.
- **Phase 2**: Evaluasi ulang instans yang **gagal** di Phase 1 terhadap Hi-Z baru. Jika ada objek yang ternyata terlihat (misalnya karena occluder bergerak), render sisa objek tersebut (*Second Small Draw Pass*). Ini menjamin tidak ada artefak visual (*popping*) tanpa perlu rendering ulang seluruh scene.

---

### 14. Challenge

**Skenario Kasus Produksi Skala Besar: Disaster Scene Simulation Engine**
Sebuah studio game AAA menuntut Anda mendesain rendering backend yang mampu menampilkan kota metropolitan yang hancur, berisi 500.000 komponen puing-puing dinamis (*dynamic debris*), di mana setiap puing memiliki material PBR unik dan bayangan real-time (*Cascaded Shadow Maps* 4 split). Target sistem: PlayStation 5 dan PC (RTX 3070 tier), resolusi 4K dinamis @ 60 FPS terkunci.

**Tugas Anda:**
1. Rancang arsitektur memory buffer persisten untuk menyimpan 500.000 instans tersebut tanpa memicu *out-of-memory* VRAM.
2. Tuliskan spesifikasi teknis dan diagram alir sinkronisasi queue (*Graphics Queue* vs *Async Compute Queue*) untuk pipeline culling puing-puing tersebut bersamaan dengan pembuatan Cascaded Shadow Maps.
3. Definisikan strategi mitigasi ketika terjadi *worst-case camera angle* (misal: kamera melihat seluruh puing kota dari atas langit tanpa occluder, yang menyebabkan 500.000 draw calls lolos culling). Tunjukkan skema alokasi dynamic dynamic command buffer memory dan mekanisme fall-back degradation-nya.

*Kirimkan rancangan arsitektur teknis Anda dalam format dokumen rekayasa perangkat lunak sistemik.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa fungsi utama instruksi `InterlockedAdd` (atau atomic add) pada compute shader culling?
2. Mengapa *branch divergence* di dalam satu Warp/Wavefront menurunkan performa komputasi GPU?
3. Sebutkan kelemahan utama dari format depth konvensional 24-bit integer dibanding Floating-Point Reverse-Z ($[1..0]$)!
4. Apa yang dimaksud dengan *Indirect Draw* dalam konteks modern graphics API?
5. Mengapa pipeline *state sorting* pada CPU menjadi tidak relevan dalam arsitektur GPU-Driven Bindless Rendering?

#### Intermediate (5 Soal)
1. Bagaimana cara menentukan Mip Level yang tepat pada Hi-Z Buffer saat mengevaluasi AABB (Axis-Aligned Bounding Box) suatu objek?
2. Jelaskan bahaya *Bank Conflict* pada *Shared Memory / LDS* dan bagaimana cara mendeteksinya menggunakan profiling tool seperti NVIDIA Nsight Graphics!
3. Apa perbedaan fundamental antara alokasi *Descriptor Indexing* (Bindless) dan alokasi tradisional *Descriptor Table / Sets*?
4. Mengapa pada Reverse-Z, operasi komparasi kedalaman diubah dari `LESS_OR_EQUAL` menjadi `GREATER_OR_EQUAL`?
5. Dalam Clustered Forward Shading, bagaimana pembagian cluster pada sumbu Z didistribusikan (linear vs. eksponensial/logaritmik) dan mengapa?

#### Scenario-Based Questions (3 Kasus)
1. **Kasus 1**: Profiler menunjukkan GPU mengalami *Pipeline Bubble* (terdapat jeda panjang di mana tidak ada compute maupun graphics unit yang bekerja) di antara *Depth Pre-pass* dan *Main Forward Pass*. Apa penyebab paling logis dari fenomena ini dan bagaimana memperbaikinya menggunakan pipeline barriers?
2. **Kasus 2**: Implementasi Hi-Z Culling Anda menyebabkan beberapa objek kecil (seperti tiang lampu jalan) tiba-tiba menghilang dan muncul kembali (*popping*) tergantung pergerakan sudut kamera yang sangat kecil. Analisis kemungkinan bug pada mip generation atau depth comparison logic!
3. **Kasus 3**: Game engine Anda mengalami penurunan performa drastis (frame drop dari 60 FPS ke 18 FPS) seketika saat karakter masuk ke area kabut lebat (*dense fog*) yang menggunakan ratusan partikel transparan overlap. Jelaskan mengapa deferred rendering standar gagal mengatasi kasus ini dan bagaimana Clustered Shading memitigasinya!

---

### 16. Summary

- **GPU-Driven Pipeline** merevolusi rendering modern dengan mengalihkan beban evaluasi visibilitas (culling) dan pembuatan command draw calls dari CPU sepenuhnya ke GPU Compute Shaders.
- Penggunaan **Hi-Z Occlusion Culling** dipadukan dengan **Frustum Culling** memangkas ratusan ribu objek di luar pandangan atau di balik dinding sebelum menyentuh tahap rasterisasi base pass.
- **Reverse-Z** adalah standar industri rendering enterprise mutlak yang menyelesaikan masalah *Z-fighting* secara geometris dengan mendistribusikan presisi floating-point secara merata ke seluruh kedalaman frustum.
- Arsitektur **Bindless Resources** membebaskan shader dari limitasi slot register tradisional, memungkinkan shader mengakses seluruh mesh, material, dan tekstur scene melalui satu descriptor array global menggunakan index integer.
- Menguasai model eksekusi hardware GPU (Warp/Wavefronts, Register Pressure, Memory Latency Hiding, dan Synchronization Barriers) adalah pembeda fundamental antara programmer engine amatir dan Senior Engine/Graphics Architect.