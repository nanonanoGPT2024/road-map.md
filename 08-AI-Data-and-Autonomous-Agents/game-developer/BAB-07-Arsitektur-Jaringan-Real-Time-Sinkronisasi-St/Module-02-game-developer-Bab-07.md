# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Topik:** Game Developer (Kategori: 08-AI-Data-and-Autonomous-Agents)  
**Bab 07:** Arsitektur Jaringan Real-Time & Sinkronisasi State

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Merancang & Mengimplementasikan Arsitektur Server-Authoritative**: Membangun pipeline jaringan deterministik atau semi-deterministik menggunakan UDP murni dengan reliabilitas selektif (*Hybrid Reliability Layer*).
2. **Mengeksekusi Client-Side Prediction & Server Reconciliation**: Mengeliminasi persepsi latensi lokal (*perceived latency*) pada input pergerakan pemain dan memitigasi anomali *rubberbanding* saat koreksi desinkronisasi terjadi.
3. **Membangun Sistem Lag Compensation (Rewind Hitbox System)**: Mengimplementasikan riwayat state berbasis *circular ring buffer* di sisi server untuk verifikasi penembakan (*hitscan/projectile*) yang adil (*fair latency arbitration*).
4. **Optimasi Bandwidth Skala Produksi**: Merancang serialisasi data biner tingkat lanjut (*bit-packing*, *delta compression*, dan *quantization*) untuk menekan alokasi memori hingga zero-allocation dan konsumsi bandwidth di bawah 20 KB/s per client pada tick rate 60–128 Hz.
5. **Mengisolasi & Memitigasi Vektor Cheat**: Menangkal manipulasi *speedhack*, *teleportation*, dan *sub-tick manipulation* langsung pada tingkat validasi state machine server.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **Pemrograman Sistem Tingkat Rendah**: Memahami manajemen memori manual/unsafe, manipulasi bitwise (`>>`, `<<`, `|`, `&`), alokasi stack vs. heap, dan struktur data *circular ring buffer*.
* **Dasar Jaringan Komputer**: Pemahaman mendalam tentang model OSI Layer 4 (UDP vs. TCP), MTU (*Maximum Transmission Unit*), fragmentasi IP, RTT (*Round Trip Time*), dan jitter.
* **Matematika Vektor & Fisika Simulasi**: Aljabar linear (vektor 3D, kuaternion), kalkulus gerak Euler/Verlet, dan konsep *fixed-timestep loop* vs. *variable-render loop*.
* **Tooling Minimal**: .NET 8.0 SDK (C#) atau C++20 compiler (Clang/GCC/MSVC), Wireshark untuk inspeksi paket raw UDP, dan Git CLI.

---

## 3. Concept & Internal Architecture

Jaringan permainan kompetitif real-time modern (FPS, MOBA, Fighting Games) beroperasi pada filosofi: **Never Trust the Client, Mask Latency at All Costs, dan Economize Every Bit**.

```
                   CLIENT TIMELINE (Tick 104)
[Local Input T104] -> [Predict State T104] -> [Render Scene]
        |
   Send Input (Tick 104, Inputs)
        |
        v [Transit Delay: RTT/2 + Jitter]
+-----------------------------------------------------------+
|                  SERVER TIMELINE (Tick 100)               |
|                                                           |
| 1. Collect inputs from all clients (T100)                 |
| 2. Fetch authoritative state T99                          |
| 3. Step Physics Simulation -> Authoritative State T100    |
| 4. Write to Ring Buffer [State T100, History Snapshot]    |
| 5. Delta Compress (T100 relative to Client's Acked Tick)  |
| 6. Broadcast Compressed Snapshot                          |
+-----------------------------------------------------------+
        |
        v [Transit Delay: RTT/2 + Jitter]
        |
[Receive Snapshot T100]
        |
        v
[Reconciliation Phase]:
if (ServerState[T100] != PredictedState[T100]) {
    LocalState = ServerState[T100]; // Hard Reset
    Re-simulate Local Inputs from Tick 101 to 104; // Replay Buffer
}
```

### 3.1 Network Loop & Fixed Timestep Synchronization
Game loop lokal berjalan independen terhadap render framerate. Jika render berjalan pada 144 FPS atau fluktuatif, network loop *harus* terkunci pada tick tetap (misal: 64 Hz = 15.625 ms per tick, atau 128 Hz = 7.8125 ms per tick). Setiap tick diberi nomor urut monotonik yang disebut **Tick ID**.

### 3.2 Delta Snapshots & Bit-Packing
Server tidak mengirimkan representasi objek secara utuh (Full State) setiap frame karena dapat memicu fragmentasi paket MTU (> 1400 bytes). Sebaliknya, server menggunakan algoritma **Delta Compression**:
1. Server melacak acknowledgment paket terakhir dari client (misal: Client telah mengonfirmasi Tick 95).
2. Ketika memproses Tick 100, server menghitung XOR atau perbedaan nilai (*diff*) antara State Tick 100 dan State Tick 95.
3. Nilai floating-point (misal koordinat posisi 32-bit float) diubah menjadi integer dengan presisi tetap (**Quantization**).
4. Data di-*pack* ke level bit tanpa padding byte (`BitStreamWriter`).

### 3.3 Temporal Rewind (Lag Compensation)
Ketika Client A (ping 100 ms, berada di temporal render Tick 95) menembak Client B pada Tick 100 (server time):
1. Client A mengirim RPC: `FireShot(targetTick: 95, aimRay)`.
2. Server menerima RPC tersebut pada Tick 103.
3. Server memvalidasi batas deviasi: `|CurrentTick - targetTick| <= MaxRewindTicks`.
4. Server memutar kembali (rewind) *bounding box* seluruh entitas di dunia virtual ke kondisi **Tick 95**.
5. Server mengeksekusi *raycast intersection* pada snapshot masa lalu tersebut.
6. Server mengembalikan hitbox seluruh entitas ke posisi real-time **Tick 103** dan menyiarkan hasil tembakan (*hit/miss*).

---

## 4. Why & What

| Pendekatan Tradisional (Naive Client-Server) | Pendekatan Enterprise (Deterministic/Authoritative) |
|---|---|
| Menggunakan TCP untuk semua data karena menjamin urutan dan keutuhan paket. | Menggunakan UDP dengan protokol *Selective Reliability*. TCP memicu *Head-of-Line (HoL) Blocking* yang menghancurkan integritas real-time. |
| Client menunggu konfirmasi server sebelum memindahkan karakter (Terasa *laggy* dan lambat merespons). | **Client-Side Prediction**: Client langsung bergerak seketika menggunakan prediksi fisika lokal, lalu mencocokkan dengan snapshot server. |
| Posisi dikirim mentah sebagai `float X, Y, Z` (12 byte per entitas). | Nilai posisi dikuantisasi, di-offsetkan terhadap *world grid bounds*, dan di-*delta compress* (rata-rata 1–3 byte per entitas dinamis). |
| Validasi tembakan dieksekusi di sisi client (Sangat rentan terhadap injeksi memori dan manipulasi *cheat engine*). | **Server Rewind Lag Compensation**: Validasi tembakan sepenuhnya di sisi server dengan rekonstruksi temporal deterministik. |

---

## 5. How (Workflow Detail)

Alur kerja sinkronisasi input-to-render terbagi dalam empat tahapan diskrit:

```
[Phase 1: Input Sampling]
       │
       ▼
[Phase 2: Local Simulation & Prediction]
       │
       ▼
[Phase 3: Network Serialization & Wire Transmission]
       │
       ▼
[Phase 4: Server Processing, Rewind Verification & Reconciliation]
```

### Tahap 1: Pengambilan Input (*Input Sampling*)
1. Pada setiap awal siklus fixed update, client membaca *raw input device* (keyboard, mouse, gamepad).
2. Input dienkapsulasi ke dalam struktur data kompak (`PlayerInputPayload`) yang mencakup `TickId`, `Vector2 Movement`, `Quaternion ViewRotation`, dan bitflag `ActionButtons`.

### Tahap 2: Simulasi Lokal & Penyimpanan History (*Prediction*)
1. Client memasukkan input tersebut ke fungsi transfer gerak deterministik: $State_{T} = f(State_{T-1}, Input_{T})$.
2. State hasil simulasi disimpan ke dalam **Client Ring Buffer** berkapasitas tetap (misal: 1024 elemen).
3. Karakter lokal dirender seketika berdasarkan hasil estimasi internal ini.

### Tahap 3: Serialisasi & Transmisi Jaringan
1. Input dikemas bersama beberapa frame input historis sebelumnya (misal: Tick $T, T-1, T-2$) sebagai strategi *Redundant Input Transmission* untuk mengatasi packet loss tanpa perlu transmisi ulang (retransmission).
2. Paket dikompresi menggunakan bit-packing dan dikirimkan melalui soket UDP mentah.

### Tahap 4: Pemrosesan Server, Verifikasi & Rekonsiliasi
1. Server menerima payload, mengekstrak input untuk Tick $T$, memvalidasi batas wajar (*anti-speedhack sanity check*).
2. Server mengeksekusi simulasi autoritatif pada tick yang bersangkutan.
3. Server mengirimkan authoritative snapshot ke client.
4. Client menerima state server untuk Tick $T$:
   - Jika jarak geometris $|\text{ServerState}_T - \text{ClientState}_T| < \epsilon$ (ambang toleransi desinkronisasi), konfirmasi diterima tanpa koreksi.
   - Jika deviasi melebihi $\epsilon$, terjadi **Rollback Reconciliation**: Posisi client ditarik kembali ke $\text{ServerState}_T$, kemudian seluruh riwayat input dari $T+1$ hingga tick terkini disimulasikan ulang dalam satu siklus CPU (*replay frames*).

---

## 6. Analogy & Diagram ASCII

### Analogi Kantor Pos & Catatan Buku Akuntansi
Bayangkan dua orang akuntan: **Akuntan Pusat (Server)** dan **Asisten Lapangan (Client)**. 
- Asisten Lapangan mencatat pengeluaran di bukunya dan langsung mengasumsikan pengeluaran itu sah (*Prediction*).
- Setiap minggu, Asisten mengirim salinan ringkas ke Kantor Pusat. 
- Kantor Pusat memverifikasi aturan kepatuhan fiskal (*Authoritative Validation*). 
- Jika Kantor Pusat menemukan selisih pada minggu ke-2, ia mengirimkan catatan perbaikan ke Asisten. 
- Begitu Asisten menerima surat tersebut pada minggu ke-4, ia tidak membuang buku barunya; ia menghapus catatan mulai minggu ke-2, menimpa dengan angka Kantor Pusat, lalu menghitung ulang transaksi minggu ke-3 dan ke-4 secara instan (*Reconciliation & Rollback*).

### Arsitektur Aliran Buffer Jaringan

```
                CLIENT STATE RING BUFFER (Capacity: 1024)
+---------+---------+---------+---------+---------+---------+---------+
| Tick 98 | Tick 99 | Tick 100| Tick 101| Tick 102| Tick 103| Tick 104|
| Pos: 10m| Pos: 11m| Pos: 12m| Pos: 13m| Pos: 14m| Pos: 15m| Pos: 16m|
+---------+---------+---------+---------+---------+---------+---------+
                         ▲                                       ▲
                         │                                       │
                [Server Ack Received]                     [Current Prediction]
                  Tick: 100, Pos: 11.2m                      (Head of Timeline)
                  
                  * DEVIATION DETECTED! *
                  Expected: 12.0m, Server: 11.2m
                  
                  Step 1: Hard overwrite Tick 100 pos = 11.2m
                  Step 2: Resimulate Physics using stored inputs:
                          Tick 101 (Input 101) -> New Pos: 12.2m
                          Tick 102 (Input 102) -> New Pos: 13.2m
                          Tick 103 (Input 103) -> New Pos: 14.2m
                          Tick 104 (Input 104) -> New Pos: 15.2m
                  Step 3: Interpolate rendering to smoothly mask 0.8m jump.
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Bit-Packing Serialization
Implementasi zero-allocation writer yang mengompresi koordinat kontinu 3D dan bitmask tombol menjadi stream bit diskrit.

```csharp
using System;
using System.Runtime.CompilerServices;

public ref struct BitStreamWriter
{
    private Span<byte> _buffer;
    private int _bitPosition;

    public BitStreamWriter(Span<byte> buffer)
    {
        _buffer = buffer;
        _bitPosition = 0;
        _buffer.Clear();
    }

    public int BitsWritten => _bitPosition;
    public int BytesWritten => (_bitPosition + 7) >> 3;

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public void WriteBits(uint value, int bitCount)
    {
        for (int i = 0; i < bitCount; i++)
        {
            int byteIndex = _bitPosition >> 3;
            int bitOffset = _bitPosition & 7;

            if ((value & (1u << i)) != 0)
            {
                _buffer[byteIndex] |= (byte)(1 << bitOffset);
            }

            _bitPosition++;
        }
    }

    // Mengompresi float ke rentang nilai integer diskrit
    public void WriteQuantizedFloat(float value, float min, float max, float precision)
    {
        float clamped = Math.Clamp(value, min, max);
        uint quantized = (uint)Math.Round((clamped - min) / precision);
        
        // Menghitung bit yang dibutuhkan untuk menampung resolusi nilai
        int requiredBits = 32 - System.Numerics.BitOperations.LeadingZeroCount((uint)((max - min) / precision));
        WriteBits(quantized, requiredBits);
    }
}

public ref struct BitStreamReader
{
    private ReadOnlySpan<byte> _buffer;
    private int _bitPosition;

    public BitStreamReader(ReadOnlySpan<byte> buffer)
    {
        _buffer = buffer;
        _bitPosition = 0;
    }

    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public uint ReadBits(int bitCount)
    {
        uint result = 0;
        for (int i = 0; i < bitCount; i++)
        {
            int byteIndex = _bitPosition >> 3;
            int bitOffset = _bitPosition & 7;

            if ((_buffer[byteIndex] & (1 << bitOffset)) != 0)
            {
                result |= (1u << i);
            }

            _bitPosition++;
        }
        return result;
    }

    public float ReadQuantizedFloat(float min, float max, float precision)
    {
        int requiredBits = 32 - System.Numerics.BitOperations.LeadingZeroCount((uint)((max - min) / precision));
        uint quantized = ReadBits(requiredBits);
        return min + (quantized * precision);
    }
}
```

### 7.2 Practical Example: Production-Grade Client-Side Prediction with Circular History Buffer
Implementasi inti state history ring-buffer, deterministik player kinematic prediction, dan reconciliation engine.

```csharp
using System;
using System.Numerics;

public struct PlayerInput
{
    public uint Tick;
    public Vector3 Direction;
    public byte Buttons; // Bit 0: Jump, Bit 1: Sprint, Bit 2: Fire
}

public struct PlayerState
{
    public uint Tick;
    public Vector3 Position;
    public Vector3 Velocity;
    public bool IsGrounded;
}

public sealed class KinematicPredictionEngine
{
    private const int BUFFER_SIZE = 512;
    private const int BUFFER_MASK = BUFFER_SIZE - 1;
    private const float FIXED_DELTA_TIME = 1.0f / 60.0f;
    private const float MOVE_SPEED = 8.0f;
    private const float GRAVITY = -9.81f;
    private const float TOLERANCE_EPSILON_SQR = 0.0001f;

    // Zero-allocation circular arrays
    private readonly PlayerInput[] _inputBuffer = new PlayerInput[BUFFER_SIZE];
    private readonly PlayerState[] _stateBuffer = new PlayerState[BUFFER_SIZE];

    public uint CurrentTick { get; private set; }

    public KinematicPredictionEngine(uint initialTick, Vector3 initialPosition)
    {
        CurrentTick = initialTick;
        int idx = (int)(initialTick & BUFFER_MASK);
        _stateBuffer[idx] = new PlayerState
        {
            Tick = initialTick,
            Position = initialPosition,
            Velocity = Vector3.Zero,
            IsGrounded = true
        };
    }

    // Dipanggil pada FixedUpdate di Client
    public PlayerState StepClientPhysics(PlayerInput input)
    {
        CurrentTick++;
        input.Tick = CurrentTick;

        int prevIndex = (int)((CurrentTick - 1) & BUFFER_MASK);
        int currIndex = (int)(CurrentTick & BUFFER_MASK);

        _inputBuffer[currIndex] = input;
        
        // Eksekusi prediksi berdasarkan state sebelumnya
        _stateBuffer[currIndex] = IntegrateState(_stateBuffer[prevIndex], input, FIXED_DELTA_TIME);
        
        return _stateBuffer[currIndex];
    }

    // Dipanggil saat menerima Authoritative State dari Server
    public bool ReconcileServerState(PlayerState serverState)
    {
        uint sTick = serverState.Tick;
        if (sTick > CurrentTick || sTick < (CurrentTick - BUFFER_SIZE))
        {
            // Snapshot terlalu tua untuk di-reconcile atau berada di masa depan (drop)
            return false;
        }

        int bufferIndex = (int)(sTick & BUFFER_MASK);
        PlayerState localState = _stateBuffer[bufferIndex];

        float deltaSqr = Vector3.DistanceSquared(localState.Position, serverState.Position);
        if (deltaSqr <= TOLERANCE_EPSILON_SQR)
        {
            // Prediksi akurat, tidak membutuhkan rollback
            return true;
        }

        // DESINKRONISASI TERJADI: Overwrite dan Rollback
        _stateBuffer[bufferIndex] = serverState;

        // Simulasi ulang (Resimulation / Replay) seluruh history input hingga CurrentTick
        uint rewindTick = sTick;
        while (rewindTick < CurrentTick)
        {
            uint nextTick = rewindTick + 1;
            int currentIdx = (int)(rewindTick & BUFFER_MASK);
            int nextIdx = (int)(nextTick & BUFFER_MASK);

            PlayerInput storedInput = _inputBuffer[nextIdx];
            _stateBuffer[nextIdx] = IntegrateState(_stateBuffer[currentIdx], storedInput, FIXED_DELTA_TIME);

            rewindTick = nextTick;
        }

        return false; // Mengindikasikan terjadi koreksi state
    }

    // Fungsi transisi state deterministik murni (Stateless & Identik di Server maupun Client)
    public static PlayerState IntegrateState(PlayerState current, PlayerInput input, float dt)
    {
        Vector3 moveDir = input.Direction;
        if (moveDir.LengthSquared() > 1.0f)
        {
            moveDir = Vector3.Normalize(moveDir);
        }

        Vector3 newVelocity = moveDir * MOVE_SPEED;
        
        // Kalkulasi gravitasi sederhana
        if (!current.IsGrounded)
        {
            newVelocity.Y = current.Velocity.Y + (GRAVITY * dt);
        }
        else if ((input.Buttons & 0x01) != 0) // Jump
        {
            newVelocity.Y = 5.0f;
            current.IsGrounded = false;
        }

        Vector3 newPosition = current.Position + (newVelocity * dt);

        // Simulasi batasan lantai absolut Y = 0
        if (newPosition.Y <= 0.0f)
        {
            newPosition.Y = 0.0f;
            newVelocity.Y = 0.0f;
            current.IsGrounded = true;
        }

        return new PlayerState
        {
            Tick = current.Tick + 1,
            Position = newPosition,
            Velocity = newVelocity,
            IsGrounded = current.IsGrounded
        };
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Unreal Engine 128-Tick Architecture & Apex Legends Desync Glitch
* **Konteks**: Game shooter kompetitif skala masif (60–100 pemain per match) dengan target tick rate server tinggi.
* **Insiden/Tantangan**: Ketika *Apex Legends* dan beberapa game berlatar belakang source-engine mengimplementasikan *lag compensation*, pemain dengan latensi tinggi (150–200 ms) menembak musuh yang telah berlari melewati dinding pelindung (*getting shot behind cover*). Di sisi lain, game seperti *Valorant* (Riot Games) mempertahankan integritas server 128-tick dengan batas toleransi rewind yang sangat ketat.
* **Analisis Akar Masalah**:
  1. *Unbounded Temporal Rewind*: Server mengizinkan rollback hingga 400 ms ke belakang untuk memfasilitasi koneksi buruk. Akibatnya, pemain dengan koneksi stabil dihukum oleh tindakan pemain dengan ping tinggi.
  2. *Tick Aliasing*: Fluktuasi rate pemrosesan menyebabkan perhitungan *inter-frame interpolation* tidak linier, merusak validitas hitbox.
* **Solusi Skala Enterprise**:
  1. **Hard Clamping Rewind Window**: Nilai rollback window dibatasi maksimal **120 ms** (ekuivalen dengan 8 tick pada 64 Hz, atau 16 tick pada 128 Hz). Jika latensi one-way pemain melebihi batas ini, server menolak melakukan kompensasi mundur penuh dan memotong extrapolasi secara sepihak.
  2. **Sub-Tick Input Timestamps**: Riot Games dan Valve (CS2) mengadopsi pencatatan timestamp sub-tick (presisi microsecond di dalam rentang tick paket) untuk menghitung secara deterministik momen peluru keluar di antara dua tick server.

```
       Timeline Event: Cover vs. Lag Compensation
Player A (Ping 150ms)                        Server (Tick Rate 128Hz)            Player B (Ping 20ms)
       │                                                │                                   │
Time 0ms: Sights B                                      │                           Time 0ms: In Open
       │                                                │                                   │
       │                                                │                          Time 20ms: Runs Behind Wall
Time 50ms: Press Fire (B was open at T=0)               │                                   │
       │                                                │                          Time 40ms: FULLY SAFE
       │ [Packet Travels 150ms]                         │                                   │
       │                                       Time 200ms: Receive Packet A                 │
       │                                                │                                   │
       │                                [EVALUATE CLAMP]                                    │
       │                                Rewind target = 0ms                                 │
       │                                Max allowable = 80ms (200 - 120ms)                  │
       │                                Server rewinds only to 80ms!                        │
       │                                Pos B at 80ms was BEHIND WALL                       │
       │                                Result: REJECT (SHOT MISSED)                        │
       │                                                │                                   │
```

---

## 9. Trade-offs

| Parameter | State Synchronization Penuh (Full Snapshots) | Lockstep Deterministic | Client-Side Prediction + Reconciliation |
|---|---|---|---|
| **Latensi Respons Pemain** | Buruk (Dibatasi oleh 1x RTT penuh). | Sangat Buruk (Harus sinkron dengan pemain terlambat). | **Nol / Instan** (Tindakan langsung dieksekusi lokal). |
| **Konsumsi Bandwidth** | Sangat Tinggi ($O(N \times M)$ data transfer per tick). | **Sangat Rendah** (Hanya mengirim input mentah). | Sedang-Tinggi (Tergantung teknik *delta-compression*). |
| **Beban Komputasi Server** | Rendah (Server hanya me-relay dan memproses sedikit integrasi). | Minimal (Hanya relay paket input). | **Sangat Tinggi** (Server memproses physics autoritatif + rewind buffer). |
| **Sensitivitas Packet Loss** | Rendah (Snapshot baru menimpa packet loss lama). | Ekstrem (Game terhenti/pause jika satu input hilang). | Moderat (Dapat ditutupi dengan transmisi input redundan). |
| **Keamanan (Anti-Cheat)** | Tinggi (Server authoritatif). | Lemah (Memory injection dapat memodifikasi state lokal). | **Sangat Tinggi** (Semua input divalidasi dan diuji terhadap aturan gerak). |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan 1: Non-Deterministic Floating Point Resimulation
* **Gejala**: Terjadi desinkronisasi minor terus-menerus (*jittery jitter* atau *micro-rubberbanding*) meskipun tidak ada gangguan rintangan fisik.
* **Akar Masalah**: Perbedaan set instruksi CPU (x87 vs. SSE/AVX) atau compiler flag optimizations (misal: `/fp:fast` di C++) menghasilkan pembulatan float yang berbeda antara host server Linux dan client Windows.
* **Solusi**: Gunakan library fixed-point math (misal: *Q48.16*) untuk mekanika deterministik murni, atau hindari dependensi floating-point order pada rantai akumulasi numerik. Pastikan menggunakan instruksi IEEE-754 konsisten.

### Kesalahan 2: Unclamped History Buffer Overflow
* **Gejala**: Server mengalami memory leak atau CPU spike ekstrem saat menerima paket manipulatif dengan Tick ID purba.
* **Akar Masalah**: Array rewind dialokasikan secara dinamis atau pointer rollback tidak divalidasi terhadap range kapasitas minimum buffer.
* **Solusi**: Gunakan struct array statically allocated *Ring Buffer* dengan validasi tegas:
  ```csharp
  if (requestedTick < currentServerTick - MAX_REWIND_TICKS || requestedTick > currentServerTick) {
      // Tolak permintaan lag compensation secara instan
      return HitResult.InvalidTimeBounds;
  }
  ```

### Kesalahan 3: Missing Redundant Inputs on Packet Loss
* **Gejala**: Ketika packet loss UDP mencapai 5%, pergerakan karakter client sering tersendat (*stutter*) karena input frame hilang di tengah transmisi.
* **Akar Masalah**: Client hanya mengirim satu paket input untuk satu tick yang sedang aktif.
* **Solusi**: Terapkan skema *Input Redundancy Array*. Setiap paket mengirimkan input tick aktif saat ini ($T$) beserta $N$ input sebelumnya ($T-1, T-2, T-3$).

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokasi Heap Nol (Zero-GC Loop)**: Pastikan pada method `Update()`, `Simulate()`, dan `Serialize()` tidak ada keyword `new` atau operasi boxing/unboxing untuk mencegah Garbage Collector pause.
- [ ] **Bit-Packing & Quantization**: Konversi posisi `Vector3` menjadi format integer terkustomisasi (misal: 16-bit untuk horizontal, 18-bit untuk vertikal).
- [ ] **MTU Compliance**: Batasi ukuran payload single packet maksimum **1200 byte** guna menghindari fragmentasi layer IP di router publik.
- [ ] **Batas Rollback Wajar (Lag Clamping)**: Batasi temporal rewinding maksimum di angka **100 ms – 150 ms** untuk mempertahankan integritas keadilan bermain.
- [ ] **Input Sanitization**: Pastikan server memvalidasi nilai panjang vektor `Direction` ($\le 1.0$) untuk mencegah exploit modifikasi memori yang mengubah nilai translasi.
- [ ] **Heartbeat & Disconnection Watchdog**: Pantau interval RTT menggunakan ping berkala; tandai status timeout jika tidak ada paket masuk dalam kurun waktu 5000 ms.

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun simulator jaringan standalone dengan pipeline: Bit-Packing, Client-Side Prediction, Packet Loss Simulator, dan Reconciliation.

### Struktur Proyek
```
hands-on/m02/
├── Program.cs
├── Core/
│   ├── BitStream.cs
│   ├── NetworkTypes.cs
│   └── NetworkSimulator.cs
└── Engine/
    ├── KinematicEngine.cs
    └── ServerSimulation.cs
```

### Langkah 1: Siapkan Konfigurasi Proyek
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/Core hands-on/m02/Engine
cd hands-on/m02
dotnet new console
```

### Langkah 2: Buat Modul Data Jaringan (`Core/NetworkTypes.cs`)
```csharp
using System.Numerics;

namespace ProductionNetcode.Core;

public struct UserCommand
{
    public uint Tick;
    public Vector3 Direction;
    public byte Buttons;
}

public struct WorldSnapshot
{
    public uint Tick;
    public Vector3 Position;
    public Vector3 Velocity;
}
```

### Langkah 3: Buat Simulator Jaringan Lossy (`Core/NetworkSimulator.cs`)
```csharp
using System;
using System.Collections.Generic;

namespace ProductionNetcode.Core;

public class NetworkSimulator<T>
{
    private struct PacketHolder
    {
        public double DeliveryTime;
        public T Data;
    }

    private readonly List<PacketHolder> _inFlight = new();
    private readonly Random _rand = new(42);
    private readonly double _latencySeconds;
    private readonly float _lossRate;

    public NetworkSimulator(double latencySeconds, float lossRate)
    {
        _latencySeconds = latencySeconds;
        _lossRate = lossRate;
    }

    public void Send(T packet, double currentTime)
    {
        if (_rand.NextSingle() < _lossRate)
        {
            // Drop packet (Simulasi Packet Loss)
            return;
        }

        _inFlight.Add(new PacketHolder
        {
            DeliveryTime = currentTime + _latencySeconds + ((_rand.NextDouble() - 0.5) * 0.01), // Jitter
            Data = packet
        });
    }

    public List<T> ReceiveAvailable(double currentTime)
    {
        List<T> available = new();
        for (int i = _inFlight.Count - 1; i >= 0; i--)
        {
            if (currentTime >= _inFlight[i].DeliveryTime)
            {
                available.Add(_inFlight[i].Data);
                _inFlight.RemoveAt(i);
            }
        }
        return available;
    }
}
```

### Langkah 4: Buat Entry Point Uji Integrasi (`Program.cs`)
```csharp
using System;
using System.Numerics;
using ProductionNetcode.Core;

Console.WriteLine("=== SIMULASI CLIENT-SIDE PREDICTION & RECONCILIATION ===");

KinematicPredictionEngine client = new KinematicPredictionEngine(0, Vector3.Zero);
Vector3 serverPosition = Vector3.Zero;
Vector3 serverVelocity = Vector3.Zero;
uint serverTick = 0;

NetworkSimulator<UserCommand> clientToServer = new(latencySeconds: 0.05, lossRate: 0.02f);
NetworkSimulator<WorldSnapshot> serverToClient = new(latencySeconds: 0.05, lossRate: 0.02f);

double simulationTime = 0.0;
double fixedDeltaTime = 1.0 / 60.0;

for (int step = 0; step < 300; step++)
{
    simulationTime += fixedDeltaTime;

    // 1. Client menghasilkan input & prediksi lokal
    UserCommand cmd = new UserCommand
    {
        Tick = client.CurrentTick + 1,
        Direction = new Vector3(1, 0, 0), // Pemain bergerak ke sumbu X konstan
        Buttons = 0
    };

    PlayerState predicted = client.StepClientPhysics(new PlayerInput
    {
        Tick = cmd.Tick,
        Direction = cmd.Direction,
        Buttons = cmd.Buttons
    });

    clientToServer.Send(cmd, simulationTime);

    // 2. Server menerima input
    var incomingCmds = clientToServer.ReceiveAvailable(simulationTime);
    foreach (var serverCmd in incomingCmds)
    {
        serverTick = serverCmd.Tick;
        // Server eksekusi autoritatif
        PlayerState sOut = KinematicPredictionEngine.IntegrateState(
            new PlayerState { Tick = serverTick - 1, Position = serverPosition, Velocity = serverVelocity, IsGrounded = true },
            new PlayerInput { Tick = serverCmd.Tick, Direction = serverCmd.Direction, Buttons = serverCmd.Buttons },
            (float)fixedDeltaTime
        );

        serverPosition = sOut.Position;
        serverVelocity = sOut.Velocity;

        // Injeksi anomali server-side (misal: tertabrak collider server pada tick 120)
        if (serverTick == 120)
        {
            serverPosition -= new Vector3(2.5f, 0, 0); // Desinkronisasi paksa
            Console.WriteLine($"[SERVER EVENT] Tick {serverTick}: Anomali benturan terdeteksi. Posisi dipaksa mundur!");
        }

        serverToClient.Send(new WorldSnapshot
        {
            Tick = serverTick,
            Position = serverPosition,
            Velocity = serverVelocity
        }, simulationTime);
    }

    // 3. Client memproses validasi Snapshot dari Server
    var incomingSnapshots = serverToClient.ReceiveAvailable(simulationTime);
    foreach (var snap in incomingSnapshots)
    {
        bool inSync = client.ReconcileServerState(new PlayerState
        {
            Tick = snap.Tick,
            Position = snap.Position,
            Velocity = snap.Velocity,
            IsGrounded = true
        });

        if (!inSync)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"[CLIENT RECONCILIATION] Tick {snap.Tick} Desync! Rollback dan Re-simulasi berhasil dieksekusi.");
            Console.ResetColor();
        }
    }
}

Console.WriteLine("Simulasi selesai tanpa alokasi memori berlebih.");
```

---

## 13. Exercise

### Level Easy
Modifikasi struct `PlayerInputPayload` dan tambahkan fungsi serialisasi bit-packing untuk tombol `Crouch` dan `Prone`. Hitung total bit yang berhasil dihemat dibandingkan jika menggunakan byte array biasa.

### Level Medium
Perluas fungsi `KinematicPredictionEngine` dengan menambahkan variabel orientasi (`Yaw` sudut rotasi). Lakukan kuantisasi kompresi sudut 360 derajat ke dalam unsigned 8-bit integer ($[0, 255]$), lalu hitung tingkat galat presisi numeriknya (*precision error margin*).

### Level Hard
Implementasikan sistem **Interpolation Buffer** untuk entitas *Remote Proxy* (pemain lain). Karakter lawan tidak boleh menggunakan Client-Side Prediction, melainkan dirender terlambat secara halus (*render delay*) menggunakan algoritma *Hermite cubic spline* atau *Spherical Linear Interpolation (SLERP)* di antara dua snapshot autoritatif server.

---

## 14. Challenge

**Skenario**: Anda memimpin tim rekayasa netcode untuk game competitive tactical shooter. Desain dan bangun sebuah arsitektur anti-lag switch protection dan dynamic tick-rate degradation mitigation dengan ketentuan teknis berikut:
1. **Pendeteksian Latency Tampering**: Client yang sengaja menahan paket keluar (*outgoing traffic throttling*) hingga 400 ms untuk menyergap musuh (*peeker's advantage abuse*) harus terdeteksi secara otonom oleh server dalam rentang 3 RTT berturut-turut.
2. **Dynamic Clamping Action**: Buat state-machine server yang secara halus mendegradasi otorisasi rollback bagi client tersebut dari 100 ms turun ke 0 ms (memaksa client bermain murni *server-side without compensation*).
3. **Sub-Tick Determinism**: Terapkan skema perhitungan peluru sub-tick dengan float offset $[0.0, 1.0)$ yang merepresentasikan fraksi tick saat tombol tembak ditekan.

*Ketentuan Evaluasi: Solusi harus diserahkan dalam bentuk technical architecture document beserta pseudo-code/kode fungsional tanpa memicu Garbage Collection spikes.*

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Mengapa transmisi state real-time pada game kompetitif hampir selalu menggunakan UDP, bukan TCP?
2. Apa tujuan utama dari arsitektur *Client-Side Prediction*?
3. Apa perbedaan fundamental antara *Server Reconciliation* dan *Client Extrapolation*?
4. Apa yang dimaksud dengan teknik *Quantization* pada serialisasi payload jaringan?
5. Mengapa floating-point operations non-deterministik menjadi ancaman besar bagi netcode berbasis rollback?

### 15.2 Pertanyaan Intermediate
6. Bagaimana strategi *Redundant Input Array* memitigasi dampak dari hilangnya paket (*packet loss*) pada koneksi UDP tanpa memerlukan proses transmisi ulang (*ACK/NACK resend*)?
7. Jelaskan bagaimana server mengompensasi penembakan (*Lag Compensation / Rewind*) untuk client yang memiliki RTT 100 ms tanpa memindahkan posisi karakter pemain lain di masa kini!
8. Pada skenario apa *Client-Side Prediction* dapat menimbulkan fenomena visual yang disebut *rubberbanding*?
9. Apa perbedaan esensial antara arsitektur jaringan *Deterministic Lockstep* (seperti pada game RTS klasik) dan *Snapshot Interpolation* (seperti pada game FPS)?
10. Mengapa data snapshot server dikirim dalam bentuk *Delta Compression* relatif terhadap tick terakhir yang di-acknowledge client, bukan dikirim absolut secara periodik?

### 15.3 Skenario Kasus Produksi
11. **Skenario A**: Dalam pengujian beban, bandwidth server game melonjak drastis saat 64 pemain berkumpul di satu area kecil (*cluster*). Inspeksi paket menunjukkan ukuran paket per tick melebihi MTU (1500 bytes) dan memicu fragmentasi IP level router. Langkah serialisasi dan spatial interest management apa yang wajib Anda ambil?
12. **Skenario B**: Seorang programmer mengimplementasikan reconciliasi fisika menggunakan Unity Rigidbody / PhysX langsung di dalam pipeline jaringan. Hasilnya, setiap kali server melakukan koreksi, client mengalami micro-stutter parah. Mengapa PhysX tradisional tidak cocok untuk *Rollback Reconciliation* dan bagaimana solusinya?
13. **Skenario C**: Seorang penyerang (cheater) memodifikasi client memory sehingga nilai `Tick` input yang dikirim melonjak 500 tick lebih maju dari server clock (*Tick Inflation Attack*). Jika server menerima paket ini tanpa validasi, apa bahaya sistemik yang terjadi dan bagaimana mitigasi autoritatifnya?

---

## Kunci Jawaban & Rubrik Evaluasi Quiz

### 15.1 Jawaban Basic
1. **UDP vs TCP**: TCP memiliki mekanisme *Head-of-Line Blocking* di mana kehilangan satu paket menahan semua aliran paket berikutnya sampai transmisi ulang berhasil. Dalam game real-time, data posisi yang usang lebih baik dibuang daripada ditunggu. UDP memungkinkan pengiriman data instan tanpa mekanisme penahanan tersebut.
2. **Tujuan Client-Side Prediction**: Menghilangkan persepsi latensi (*zero perceived input latency*) bagi pemain lokal, sehingga respons kontrol terasa instan seperti game single-player.
3. **Reconciliation vs Extrapolation**: *Reconciliation* adalah tindakan mengoreksi posisi lokal berdasarkan data autoritatif masa lalu dari server lalu mensimulasikan ulang masa kini. *Extrapolation* adalah teknik menebak posisi masa depan suatu entitas ketika paket data berikutnya belum tiba di penerima.
4. **Quantization**: Proses konversi nilai kontinu (seperti `float` 32-bit) ke representasi diskrit berukuran bit lebih kecil (seperti `int` 12-bit) dengan rentang presisi tetap untuk menghemat bandwidth transmisi.
5. **Bahaya Float Non-deterministik**: Perbedaan pembulatan bit terkecil antara server dan client akan terus terakumulasi (*divergence drift*), menyebabkan desinkronisasi permanen yang memicu koreksi rubberbanding tanpa henti.

### 15.2 Jawaban Intermediate
6. **Redundant Input Array**: Dengan menyertakan riwayat input beberapa frame lalu (misal: Tick $T, T-1, T-2$) di setiap paket data, jika paket $T-1$ hilang di jaringan, server tetap dapat membaca input $T-1$ di dalam payload paket $T$. Hal ini mengeliminasi kebutuhan retransmisi TCP.
7. **Prinsip Lag Compensation**: Server menyimpan *circular history buffer* posisi seluruh pemain. Ketika client menembak pada timeline masa lalunya ($T - \text{ping}$), server memundurkan (*rewind*) hitbox lawan secara internal ke posisi pada tick masa lalu tersebut, melakukan evaluasi *raycast*, lalu mengembalikan posisi hitbox ke tick aktif saat itu dalam frame yang sama. Pemain lain tidak melihat ada pergeseran spasial.
8. **Penyebab Rubberbanding**: Terjadi ketika hasil kalkulasi lokal client berbeda signifikan dengan simulasi autoritatif server (misal: client memprediksi dapat berjalan maju, namun server mendeteksi ada halangan/tembok). Ketika server mengirim state resmi, client dipaksa melakukan *hard rollback* yang tampak seperti karakter terlempar kembali ke posisi lama.
9. **Lockstep vs Snapshot Interpolation**: *Lockstep* hanya mengirimkan input controller dari setiap client dan setiap mesin mengeksekusi simulasi identik (membutuhkan 100% determinisme mutlak). *Snapshot Interpolation* mengirimkan state hasil simulasi dari server autoritatif ke client, dan client merender entitas lain dengan cara interpolasi mundur di antara snapshot-snapshot tersebut.
10. **Alasan Delta Compression**: Mengirimkan seluruh entitas dan propertinya secara utuh setiap tick memakan bandwidth sangat besar. Delta compression hanya mentransmisikan bit-bit properti yang mengalami perubahan nilai (*dirty bitflags*) sejak paket konfirmasi acknowledgment terakhir client, menghemat ukuran data hingga 80–90%.

### 15.3 Panduan Solusi Skenario Produksi
11. **Solusi Skenario A**: 
    - Implementasikan **Area of Interest (AoI) / Spatial Grid Partitioning**: Server hanya mengirim data entitas yang berada dalam radius pandang dan pengaruh pemain (*network relevancy culling*).
    - Terapkan **Bit-Packing & Quantization** ketat untuk memangkas ukuran header dan payload per entitas.
    - Turunkan update rate entitas yang jauh dari pemain (*frequency scaling/LOD networking*).
12. **Solusi Skenario B**:
    - Engine fisika umum seperti standard PhysX tidak stateless dan memiliki biaya internal step time yang berat, sehingga tidak dapat dimundurkan (*rewind*) dan disimulasikan ulang puluhan kali dalam satu frame tanpa performa anjlok (*frame drop*).
    - **Solusi**: Pisahkan logika gerak pemain menggunakan kinematic custom controller berbasis matematika analitik deterministik murni, atau manfaatkan sub-sistem low-level physics khusus rollback (seperti Unity Physics DOTS / custom software broadphase) yang mendukung snapshotting dan instan fast-forward.
13. **Solusi Skenario C**:
    - **Bahaya**: Buffer overflow pada ring buffer server, alokasi tak terbatas, atau server mengeksekusi integrasi simulasi fisika kosong sebanyak 500 step yang menyebabkan CPU *denial of service (DoS)*.
    - **Mitigasi**: Server menerapkan aturan validasi *Clock Synchronization & Tick Bounds*. Jika paket input masuk dengan selisih `Tick > CurrentServerTick + MaxAllowedDrift` (misal drift maksimum 2-4 tick), paket harus dibuang seketika, dan client diberikan flag peringatan/desync reset ke timeline server saat itu.

---

## 16. Summary

1. Arsitektur jaringan real-time modern mengandalkan model **Server-Authoritative**, di mana server memegang kebenaran mutlak simulasi dunia virtual untuk mencegah manipulasi client.
2. **Client-Side Prediction** meniadakan latensi input dengan cara memprediksi masa depan karakter lokal secara seketika, sementara **Server Reconciliation** memperbaiki deviasi prediksi melalui mekanisme rollback dan resimulasi deterministik.
3. Keadilan dalam penembakan diakomodasi oleh **Lag Compensation (Temporal Rewind)** yang merekonstruksi layout spasial hitbox lawan di server sesuai dengan waktu ketika pemain melepaskan tembakan di layarnya.
4. Skalabilitas enterprise menuntut optimasi level rendah: penggunaan **UDP**, **Bit-Packing**, **Quantization**, **Delta Compression**, serta penghapusan alokasi memori dinamis (*zero-allocation principle*) pada critical tick loop.
5. Pemisahan rendering terinterpolasi dan fixed update networking loop merupakan prasyarat mutlak untuk menghasilkan visual pergerakan yang halus tanpa mengorbankan integritas determinisme logika permainan.