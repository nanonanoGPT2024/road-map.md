# BAB 10: PIPELINE PRODUKSI ENTERPRISE, ANTI-CHEAT, & LIVEOPS
## Modul 01: Arsitektur Telemetri & Deteksi Anomali Perilaku (Behavioral Anti-Cheat) Real-Time

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Merancang** arsitektur *event-driven telemetry ingestion pipeline* berkapasitas tinggi dengan *latency budget* end-to-end $\le 100\text{ ms}$ menggunakan pola *asynchronous decoupling* dari *dedicated game server* (DGS).
*   **Mengimplementasikan** modul ekstraksi fitur kinematika spasio-temporal (*angular jerk*, *entropy of trajectory*, dan *velocity dispersion*) pada *data stream* untuk memisahkan input motorik manusia dari injeksi sinyal sintetis (*aimbot*, *DMA hardware cheats*, *recoil scripting*).
*   **Membangun** pipeline inferensi *unsupervised anomaly detection* berbasis *ensemble modeling* (Autoencoder Reconstruction Error + Streaming Isolation Forest) dengan target *False Positive Rate* (FPR) $< 0.001\%$ ($1$ false positive per $100.000$ evaluasi).
*   **Mengintegrasikan** sistem mitigasi *LiveOps automated enforcement* (*shadow-quarantine*, *dynamic latency injection*, *re-routing to untrusted lobbies*) tanpa mendegradasi *tick rate* simulasi game (60 Hz / 128 Hz).

---

### 2. Concept Overview
Proteksi integritas kompetitif pada game enterprise tidak lagi dapat mengandalkan *client-side anti-cheat* (seperti kernel drivers Ring 0) semata. Perkembangan perangkat keras penyerang—seperti kartu *Direct Memory Access* (DMA), *PCIe leechers*, dan bot bertenaga *computer vision* yang beroperasi pada mesin terpisah via kartu penangkap video (*capture card*)—membuat *memory space* klien tidak lagi dapat dipercaya (*zero-trust client*).

```
[Zero-Trust Client Space]                  [Authoritative Server Space]
+-------------------------+               +--------------------------------------+
|  Client Hardware & OS   |               | Game Simulation (60/128 Tick)        |
|  +-------------------+  |               |  +--------------------------------+  |
|  | Untrusted Engine  |  | UDP Game Loop |  | Authoritative State Validation |  |
|  | - DMA Bypass      |====================>| - Server Hitreg                |  |
|  | - Virtual Input   |  |               |  | - Kinematic Verification       |  |
|  +-------------------+  |               |  +--------------------------------+  |
+-------------------------+               +-------------------|------------------+
                                                              | Async Telemetry
                                                              v
                                          +--------------------------------------+
                                          | ML Pipeline & Anti-Cheat LiveOps     |
                                          | - Stream Ingestion & Feature Store   |
                                          | - Behavioral Anomaly Detection       |
                                          | - Automated Quarantine Enforcement   |
                                          +--------------------------------------+
```

Mental model pertahanan modern bertumpu pada **Behavioral Telemetry Analysis di sisi Server**:
1.  **Kinematic Envelope Verification**: Memvalidasi apakah dinamika gerak pemain (kecepatan, akselerasi, *jerk*) melanggar batasan biomekanik manusia normal. Manusia tunduk pada hukum *Fitts's Law* dan *neuromuscular noise*; bot algoritmik menghasilkan transisi state diskrit, penyesuaian sudut tanpa kurva akselerasi (*instantaneous delta yaw/pitch*), atau penekanan *recoil* yang terlalu matematis.
2.  **Telemetry Offloading Non-Blocking**: Game loop server berjalan pada frekuensi tinggi (misal: 128 Hz di mana tiap frame berdurasi $\approx 7.81\text{ ms}$). Ekstraksi dan pengiriman telemetri tidak boleh mengorbankan siklus CPU simulasi dunia. Telemetri diekspor melalui *ring buffer* bebas kunci (*lock-free circular buffer*) ke proses *sidecar* secara asinkron.
3.  **Tiered Enforcement Strategy**: Tindakan terhadap anomali tidak dieksekusi secara instan dengan *perma-ban* (yang memberi umpan balik cepat bagi pengembang cheat untuk melakukan rekayasa balik). Model menerapkan penegakan sanksi bertingkat (*silent flag* $\rightarrow$ *quarantine matchmaking* $\rightarrow$ *phantom damage reduction* $\rightarrow$ *delayed permanent ban* secara berkala).

---

### 3. Why It Matters
Pada ekosistem game skala AAA (*Free-to-Play* dan kompetitif multi-pemain), integritas gameplay berbanding lurus dengan stabilitas finansial studio:
*   **Retensi Pemain & Nilai Seumur Hidup (LTV)**: Survei industri menunjukkan lebih dari 60% pemain kompetitif meninggalkan game jika mereka mendapati kecurangan pada lebih dari 1 dari 5 sesi pertandingan. Penurunan *Monthly Active Users* (MAU) secara langsung memicu penurunan konversi *battle pass* dan transaksi mikro.
*   **Ekonomi In-Game Terdistribusi**: Pada game MMORPG atau ekstraksi (*extraction shooters*), botting otomatis merusak pasar lelang (*auction house*) melalui hiperinflasi mata uang virtual, menghancurkan insentif pemain sah yang bermain secara manual.
*   **Kelemahan Client-Side Enforcement**: Perangkat anti-cheat di sisi klien beroperasi di lingkungan musuh (*hostile environment*). Penyerang menggunakan *hypervisor-based rootkits*, *custom firmware* pada *NIC PCIe*, dan *AI aim assistance* yang membaca buffer HDMI dan menyuntikkan input HID (*Human Interface Device*) palsu melalui mikrokontroler Arduino/Raspberry Pi Pico. Sinyal input fisik ini tidak meninggalkan jejak proses pada memori OS, sehingga **hanya analisis telemetri data berbasis server yang mampu mendeteksi manipulasi tersebut.**

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan aliran data dari Dedicated Game Server (DGS) ke sistem inferensi machine learning terdistribusi hingga eksekusi mitigasi LiveOps:

```
+---------------------------------------------------------------------------------------+
| DEDICATED GAME SERVER CLUSTER (AGONES / K8S)                                          |
|                                                                                       |
|  [Sim Loop: 128Hz] ---> [Lock-Free SPSC RingBuffer] ---> [Async Sidecar Agent]        |
|                                                                  |                    |
+------------------------------------------------------------------|--------------------+
                                                                   | ZeroMQ / gRPC Stream
                                                                   v
+---------------------------------------------------------------------------------------+
| DISTRIBUTED INGESTION & FEATURE PIPELINE                                              |
|                                                                                       |
|        +-------------------------------------------------------------+                |
|        | Message Broker: Apache Kafka / Redpanda Cluster             |                |
|        | Topic: `gameplay.telemetry.v1` (Partitioned by SessionId)   |                |
|        +------------------------------+------------------------------+                |
|                                       |                                               |
|                                       v                                               |
|        +-------------------------------------------------------------+                |
|        | Stream Processor: Apache Flink / Custom Python Vectorizer   |                |
|        | - Sliding Window: 2.0s (Step: 250ms)                        |                |
|        | - Compute Jerk, Shannon Entropy, Fréchet Distance           |                |
|        +------------------------------+------------------------------+                |
+---------------------------------------|-----------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------------+
| ONLINE INFERENCE & DECISION ENGINE                                                    |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Inference Worker Pool (TorchScript / ONNX Runtime C++ Service)                   |  |
|  |                                                                                 |  |
|  |  +-----------------------------+      +--------------------------------------+  |  |
|  |  | Autoencoder Anomaly Model   |      | Streaming Isolation Forest Ensemble  |  |  |
|  |  | (Reconstruction Loss > Th)  |      | (Kinematic Outlier Threshold)        |  |  |
|  |  +--------------+--------------+      +-------------------+------------------+  |  |
|  |                 \                                        /                       |  |
|  |                  \                                      /                        |  |
|  |                   v                                    v                         |  |
|  |                +------------------------------------------+                      |  |
|  |                |     Calibrated Ensemble Risk Scoring     |                      |  |
|  |                +---------------------+--------------------+                      |  |
|  +--------------------------------------|-------------------------------------------+  |
+-----------------------------------------|---------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------+
| LIVEOPS ORCHESTRATION & STATE SYNCHRONIZATION                                         |
|                                                                                       |
|  +--------------------------------+       +----------------------------------------+  |
|  | Redis Cluster State Store      |       | LiveOps Action Dispatcher              |  |
|  | Key: `player:risk:{account_id}`| ----> | - Target: Quarantine Matchmaking       |  |
|  | TTL: Sliding 7-Days Window     |       | - Target: Dynamic Recoil Multiplier    |  |
|  +--------------------------------+       | - Target: Audit Vault (Deterministic)  |  |
|                                           +----------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Kinematika Gerak & Analisis Input
Gerak bidikan (*aiming dynamics*) manusia diatur oleh transmisi impuls saraf neuromuskular. Karakteristik dasarnya mencakup fase *ballistic saccade* (akselerasi cepat mendekati target) yang diikuti oleh fase *deceleration* dan koreksi mikro (*micro-corrections*). Sebaliknya, *aimbot* deterministik atau skrip interpolasi linier umumnya memiliki karakteristik berikut:

1.  **Angular Jerk ($\vec{J}$)**:
    Turunan ketiga dari posisi sudut ($\theta$) terhadap waktu ($t$):
    $$\vec{\omega}(t) = \frac{d\vec{\theta}(t)}{dt}, \quad \vec{\alpha}(t) = \frac{d\vec{\omega}(t)}{dt}, \quad \vec{J}(t) = \frac{d\vec{\alpha}(t)}{dt}$$
    Di mana $\theta$ merepresentasikan vektor $(\text{pitch}, \text{yaw})$. Bot snapping langsung memodifikasi vektor rotasi dalam durasi 1 tick ($\Delta t = 1/128\text{ s}$), menghasilkan nilai jerk teoretis yang mendekati tak hingga ($\vec{J} \to \infty$) atau dibatasi hanya oleh *clamp* buatan yang memunculkan distribusi diskrit kaku.

2.  **Entropi Sudut Pandang (Shannon Entropy)**:
    Menghitung keacakan distribusi pergerakan sudut bidikan dalam jendela waktu $W$:
    $$H(\Delta\vec{\theta}) = -\sum_{i=1}^{K} P(b_i) \log_2 P(b_i)$$
    Di mana $P(b_i)$ adalah probabilitas diskretisasi kecepatan sudut jatuh ke dalam bin $b_i$. Skrip *anti-recoil* statis menghasilkan $H \approx 0$ pada sumbu vertikal (*pitch*), menandakan ketiadaan variasi biologis.

#### B. Asynchronous Decoupling pada Dedicated Server
Untuk menjamin eksekusi simulasi game tetap deterministik dan tidak terpengaruh oleh operasi I/O jaringan, *tick loop* server menerapkan arsitektur *Single-Producer Single-Consumer* (SPSC) *Lock-Free Ring Buffer*.
*   Produser: Thread simulasi server menulis state snapshot paket input per pemain. Jika buffer penuh (*full condition*), telemetri ditandai dengan bit *overflow drop*, mencegah terjadinya *blocking* pada *game loop*.
*   Konsumen: Thread *worker I/O* terpisah membaca buffer dan memaketkannya ke dalam format biner terkompresi (Google Protocol Buffers atau FlatBuffers) untuk dialirkan via TCP/gRPC/Kafka.

#### C. Ensemble Anomaly Scoring
Tidak ada model tunggal yang mencukupi untuk mendeteksi seluruh jenis kecurangan tanpa menghasilkan *false positive*. Sistem produksi mengombinasikan dua paradigma:
1.  **Deep Autoencoder Reconstruction Error**: Dilatih khusus hanya menggunakan jutaan data telemetri dari pemain sah berkategori tinggi (*verified pro players*). Ketika data gerak cheat dimasukkan, model gagal merekonstruksi pola input yang tidak wajar:
    $$\mathcal{L}_{\text{recon}} = \|\mathbf{x} - \hat{\mathbf{x}}\|^2_2$$
2.  **Streaming Isolation Forest**: Mengisolasi anomali struktural pada ruang metrik berdimensi tinggi (*outlier spatial distribution*) tanpa membutuhkan pelatihan berbasis label.
3.  **Bayesian Risk Accumulator**:
    Skor risiko tidak langsung mengeksekusi sanksi dari 1 snapshot abnormal. Kepercayaan dinaikkan menggunakan algoritma akumulasi berbasis bukti (*evidence accumulation window*):
    $$R_t = \gamma R_{t-1} + (1 - \gamma) \cdot \text{EnsembleScore}(\mathbf{x}_t)$$
    Di mana $\gamma \in (0.95, 0.99)$ adalah faktor pembobot (*decay factor*) yang mencegah lonjakan fluktuatif sesaat akibat gangguan jaringan klien (*lag spike*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem pemrosesan telemetri, ekstraksi fitur kinematika, deteksi anomali ensemble, dan pembaruan profil risiko pemain menggunakan Python modern (asinkron, type-hinted, dan arsitektur modular).

```python
# telemetry_pipeline.py
"""
Sistem Pipeline Analisis Telemetri Anti-Cheat Enterprise.
Menyediakan modul ekstraksi data gerak, deteksi anomali streaming, dan integrasi LiveOps.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import math
import time
from typing import Final, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# DOMAIN MODELS & SCHEMAS
# ============================================================================

class ViewAngle(BaseModel):
    """Representasi vektor sudut bidikan pemain (Euler Angles dalam derajat)."""
    pitch: float = Field(..., ge=-90.0, le=90.0, description="Rotasi vertikal")
    yaw: float = Field(..., ge=-180.0, le=180.0, description="Rotasi horizontal")

    @field_validator("pitch", "yaw")
    @classmethod
    def check_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Sudut rotasi harus berupa angka riil yang terhingga.")
        return v


class TelemetryFrame(BaseModel):
    """Payload paket telemetri game dari Dedicated Server per-tick."""
    player_id: str = Field(..., min_length=8, max_length=64)
    tick: int = Field(..., ge=0)
    timestamp_ms: float = Field(..., gt=0.0)
    view_angles: ViewAngle
    world_position: Tuple[float, float, float]
    is_firing: bool

    class Config:
        frozen = True


class KinematicFeatures(BaseModel):
    """Fitur ekstraksi kinematik turunan untuk model evaluasi inferensi."""
    player_id: str
    window_end_tick: int
    mean_angular_velocity: float
    max_angular_jerk: float
    pitch_entropy: float
    recoil_autocorrelation: float


# ============================================================================
# FEATURE EXTRACTION ENGINE
# ============================================================================

class KinematicFeatureExtractor:
    """Mengekstrak metrik spasio-temporal dari rangkaian frame telemetri mentah."""

    def __init__(self, entropy_bins: int = 10) -> None:
        self.entropy_bins: Final[int] = entropy_bins

    def extract(self, frames: List[TelemetryFrame]) -> Optional[KinematicFeatures]:
        """
        Mengekstraksi fitur turunan kinematik dari sliding window frame.
        Membutuhkan minimal 4 frame untuk menghitung turunan ketiga (Jerk).
        """
        if len(frames) < 4:
            return None

        # Urutkan berdasarkan tick untuk menjaga integritas data waktu
        sorted_frames = sorted(frames, key=lambda f: f.tick)
        n = len(sorted_frames)

        timestamps = np.array([f.timestamp_ms / 1000.0 for f in sorted_frames], dtype=np.float64)
        dt = np.diff(timestamps)
        
        # Validasi deviasi interval waktu untuk mencegah division by zero
        dt = np.where(dt <= 0.0, 1e-4, dt)

        pitches = np.array([f.view_angles.pitch for f in sorted_frames], dtype=np.float64)
        yaws = np.array([f.view_angles.yaw for f in sorted_frames], dtype=np.float64)

        # Unwrapping yaw angle untuk mengatasi diskontinuitas boundary (-180/180)
        yaws_unwrapped = np.unwrap(np.radians(yaws))
        pitches_rad = np.radians(pitches)

        # 1. Angular Velocity (rad/s)
        pitch_vel = np.diff(pitches_rad) / dt
        yaw_vel = np.diff(yaws_unwrapped) / dt
        total_ang_vel = np.sqrt(pitch_vel**2 + yaw_vel**2)

        # 2. Angular Acceleration (rad/s^2)
        dt_acc = dt[1:]
        pitch_acc = np.diff(pitch_vel) / dt_acc
        yaw_acc = np.diff(yaw_vel) / dt_acc

        # 3. Angular Jerk (rad/s^3)
        dt_jerk = dt_acc[1:]
        pitch_jerk = np.diff(pitch_acc) / dt_jerk
        yaw_jerk = np.diff(yaw_acc) / dt_jerk
        total_jerk = np.sqrt(pitch_jerk**2 + yaw_jerk**2)

        # 4. Shannon Entropy of Pitch Corrections
        hist, _ = np.histogram(pitch_vel, bins=self.entropy_bins, density=True)
        hist = hist[hist > 0.0]  # Filter zero probability
        pitch_entropy = -float(np.sum(hist * np.log2(hist + 1e-12))) if len(hist) > 0 else 0.0

        # 5. Autocorrelation of Pitch on Firing (Recoil script detection)
        firing_frames = [f.is_firing for f in sorted_frames[1:]]
        recoil_corr = 0.0
        if any(firing_frames) and len(pitch_vel) > 2:
            firing_pitch_vel = pitch_vel[firing_frames[:len(pitch_vel)]]
            if len(firing_pitch_vel) > 3 and np.std(firing_pitch_vel) > 1e-4:
                norm_series = firing_pitch_vel - np.mean(firing_pitch_vel)
                autocorr = np.correlate(norm_series, norm_series, mode="full")
                autocorr_val = autocorr[len(autocorr) // 2 + 1] / autocorr[len(autocorr) // 2]
                recoil_corr = float(np.nan_to_num(autocorr_val))

        return KinematicFeatures(
            player_id=sorted_frames[-1].player_id,
            window_end_tick=sorted_frames[-1].tick,
            mean_angular_velocity=float(np.mean(total_ang_vel)),
            max_angular_jerk=float(np.max(total_jerk)) if len(total_jerk) > 0 else 0.0,
            pitch_entropy=pitch_entropy,
            recoil_autocorrelation=recoil_corr,
        )


# ============================================================================
# ML ANOMALY INFERENCE WORKER
# ============================================================================

class AnomalyInferenceModel:
    """
    Model inferensi simulasi berbasis rekonstruksi Autoencoder heuristik 
    dan spatial isolation bounds.
    """

    def __init__(self, jerk_threshold: float = 1800.0, entropy_min_bound: float = 0.45) -> None:
        self.jerk_threshold: Final[float] = jerk_threshold
        self.entropy_min_bound: Final[float] = entropy_min_bound

    def compute_anomaly_score(self, features: KinematicFeatures) -> float:
        """
        Menghasilkan skor risiko normalisasi [0.0 - 1.0].
        Skor 1.0 mengindikasikan kecurangan non-manusia yang pasti.
        """
        score = 0.0

        # Pelanggaran Kinematik: Instant snapping menghasilkan jerk luar biasa
        if features.max_angular_jerk > self.jerk_threshold:
            excess = min((features.max_angular_jerk - self.jerk_threshold) / self.jerk_threshold, 2.0)
            score += 0.6 + (0.2 * (excess / 2.0))

        # Pelanggaran Entropi: Kontrol motorik sintetis/skrip tanpa micro-adjustments
        if features.pitch_entropy < self.entropy_min_bound and features.mean_angular_velocity > 0.5:
            entropy_deficit = (self.entropy_min_bound - features.pitch_entropy) / self.entropy_min_bound
            score += 0.3 * entropy_deficit

        # Pola anti-recoil terprogram (autokorelasi deterministik statis)
        if features.recoil_autocorrelation > 0.85:
            score += 0.4

        return float(np.clip(score, 0.0, 1.0))


# ============================================================================
# LIVEOPS RISK AGGREGATOR & ACTION DISPATCHER
# ============================================================================

@dataclass
class QuarantineDecision:
    player_id: str
    current_risk: float
    action: str
    reason: str


class LiveOpsDecisionEngine:
    """Akumulator risiko temporal untuk meminimalkan False Positive."""

    def __init__(
        self,
        risk_decay: float = 0.92,
        quarantine_threshold: float = 0.85,
        flag_threshold: float = 0.50
    ) -> None:
        self.risk_decay: Final[float] = risk_decay
        self.quarantine_threshold: Final[float] = quarantine_threshold
        self.flag_threshold: Final[float] = flag_threshold
        self._risk_state: dict[str, float] = {}

    def process_score(self, player_id: str, new_score: float) -> QuarantineDecision:
        prev_risk = self._risk_state.get(player_id, 0.0)
        # Bayesian temporal decay equation
        current_risk = (self.risk_decay * prev_risk) + ((1.0 - self.risk_decay) * new_score)
        
        # Amplifikasi penalti jika terdeteksi anomali kritis berulang
        if new_score > 0.8:
            current_risk = min(current_risk + 0.15, 1.0)
            
        self._risk_state[player_id] = current_risk

        action = "NOOP"
        reason = "Normal Gameplay Pattern"

        if current_risk >= self.quarantine_threshold:
            action = "QUARANTINE_MATCHMAKING"
            reason = f"Kinematic violations accumulated. Risk={current_risk:.3f}"
        elif current_risk >= self.flag_threshold:
            action = "ENABLE_HIGH_FIDELITY_AUDIT"
            reason = f"Suspicious movement profile. Risk={current_risk:.3f}"

        return QuarantineDecision(
            player_id=player_id,
            current_risk=current_risk,
            action=action,
            reason=reason
        )


# ============================================================================
# ASYNCHRONOUS PIPELINE ORCHESTRATOR
# ============================================================================

class TelemetryConsumerPipeline:
    """Mengonsumsi stream telemetri secara asinkron dan mengorkestrasi pipeline."""

    def __init__(self) -> None:
        self.extractor = KinematicFeatureExtractor()
        self.model = AnomalyInferenceModel()
        self.engine = LiveOpsDecisionEngine()
        self.telemetry_queue: asyncio.Queue[TelemetryFrame] = asyncio.Queue(maxsize=10000)
        self.buffers: dict[str, List[TelemetryFrame]] = {}
        self.is_running = False

    async def ingest_frame(self, frame: TelemetryFrame) -> None:
        """Endpoint ingestion: Memasukkan frame ke queue dengan non-blocking fallback."""
        try:
            self.telemetry_queue.put_nowait(frame)
        except asyncio.QueueFull:
            # Drop frame jika worker pipeline macet (menjaga ketersediaan memori server)
            pass

    async def start_consumer(self) -> None:
        self.is_running = True
        while self.is_running:
            try:
                frame = await asyncio.wait_for(self.telemetry_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            player_id = frame.player_id
            if player_id not in self.buffers:
                self.buffers[player_id] = []

            player_buffer = self.buffers[player_id]
            player_buffer.append(frame)

            # Analisis berbasis sliding window: 16 frame (~125ms pada 128Hz atau ~250ms pada 60Hz)
            if len(player_buffer) >= 16:
                features = self.extractor.extract(player_buffer)
                if features:
                    score = self.model.compute_anomaly_score(features)
                    decision = self.engine.process_score(player_id, score)
                    
                    if decision.action != "NOOP":
                        await self._dispatch_liveops_action(decision)

                # Slide window maju 8 frame (50% overlap stride)
                self.buffers[player_id] = player_buffer[8:]

            self.telemetry_queue.task_done()

    async def _dispatch_liveops_action(self, decision: QuarantineDecision) -> None:
        """Mengirimkan aksi mitigasi ke edge/routing service."""
        # Simulasi operasi network non-blocking ke state store/router
        await asyncio.sleep(0.001)
        # Logging terstruktur untuk audit pipeline
        print(f"[LIVEOPS DISPATCH] Player={decision.player_id} | "
              f"Action={decision.action} | Score={decision.current_risk:.3f} | "
              f"Context={decision.reason}")

    def stop(self) -> None:
        self.is_running = False
```

---

### 7. Edge Cases & Failure Modes

Pada implementasi skala enterprise, kegagalan menangani anomali teknis non-cheat dapat merusak pengalaman pemain yang sah (*legitimate players*).

#### 1. Network Jitter & Packet Compression Artifacts
*   **Kasus**: Pemain mengalami degradasi jaringan (*burst packet loss* diikuti transmisi cepat kumpulan paket oleh protokol transport). Ketika server menerima sekumpulan paket ini secara bersamaan (*delta timestamp* mendekati nol), kalkulasi menghasilkan nilai turunan akselerasi semu yang menyerupai *instant snapping*.
*   **Mitigasi**: Ekstraksi fitur wajib memeriksa metrik `server_arrival_delta` vs `client_timestamp_delta`. Jika rasio deviasi $\Delta t_{\text{arrival}} / \Delta t_{\text{client}} > 2.5$, jendela telemetri tersebut harus diberi anotasi `DIRTY_NETWORK` dan dikecualikan dari akumulator penalti inferensi.

#### 2. Hardware Variations (High DPI & Sub-Pixel Precision Sensor)
*   **Kasus**: Mouse gaming level profesional memiliki sensor dengan resolusi $> 20.000\text{ DPI}$ dan polling rate $8.000\text{ Hz}$. Pergerakan *flick-shot* manual berkecepatan tinggi oleh atlet e-Sports menghasilkan akselerasi sudut yang masif.
*   **Mitigasi**: Pengecekan *Spatial Trajectory Curvature* (Kelengkungan Trajektori). Tangan manusia selalu membentuk kurva gerak mikro akibat engsel pergelangan atau siku (*rotational biomechanics*). Aimbot direct memory injection menghasilkan pergerakan lurus 1 dimensi tanpa *micro-wobble*. Nilai Fréchet Distance digunakan untuk mengonfirmasi kelengkungan alami ini sebelum pemberian skor anomali.

#### 3. Cold Start & Ingestion Backpressure
*   **Kasus**: Ketika $100.000$ pemain masuk ke dalam match secara simultan (misalnya saat pembukaan season baru), throughput telemetri melonjak jutaan paket per detik. Beban inferensi dapat memicu latensi pemrosesan dan konsumsi memori berlebih (*OOM crash*).
*   **Mitigasi**: Implementasi *Load-shedding Circuit Breaker*. Jika queue telemetri terisi $> 85\%$, pipeline secara dinamis menurunkan laju sampling telemetri pemain berkategori risiko rendah (`risk < 0.15`), sembari memprioritaskan alokasi komputasi untuk entitas dengan riwayat anomali mencurigakan.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Server-Side Telemetry AI | Client-Side Kernel Anti-Cheat | Rule-Based Heuristics (Server) |
| :--- | :--- | :--- | :--- |
| **Resistensi Eksploitasi** | **Sangat Tinggi**: Kebal terhadap bypass memori lokal, DMA, atau hypervisor cheats. | **Rendah - Sedang**: Rentan terhadap *ring-0 driver abuse*, *signature evasion*, & *hardware spoofing*. | **Sedang**: Rentan terhadap cheat yang menambahkan interpolasi acak (*smoothing bot*). |
| **Overhead Komputasi** | **Tinggi**: Membutuhkan cluster Kafka, distributed stream worker, dan GPU/CPU inference nodes. | **Nol di Server**: Beban pemrosesan dilimpahkan ke PC/konsol klien pengguna. | **Sangat Rendah**: Hanya eksekusi logika percabangan kondisional standar pada CPU server. |
| **Latency Enforcement** | **Asinkron (Tertunda)**: Membutuhkan pengumpulan context window ($0.5\text{s} - 2.0\text{s}$) demi presisi. | **Instan / Real-Time**: Interupsi proses crash memori saat deteksi thread injection. | **Instan**: Validasi batas toleransi langsung pada game tick yang bersangkutan. |
| **False Positive Rate** | **Dapat Dikalibrasi Ketat**: Penggunaan ensemble thresholding memitigasi misklasifikasi. | **Rendah**: Menargetkan artefak biner yang jelas, bukan anomali probabilistik. | **Tinggi**: Batasan kaku (*hard-caps*) sering kali mengenai pemain berkemampuan tinggi (*pro flick*). |

---

### 9. Best Practices & Standar Industri

1.  **Strict Data Anonymization (GDPR/Compliance)**: Telemetri tidak boleh mengikat koordinat input langsung dengan identitas dunia nyata (*Personally Identifiable Information*). Gunakan *ephemeral session UUID* yang di-hash menggunakan algoritma HMAC-SHA256 berotasi harian saat memproses data di stream layer.
2.  **Deterministic Audit Recording**: Ketika LiveOps Decision Engine mengeluarkan tindakan `QUARANTINE_MATCHMAKING`, server wajib menyimpan cuplikan $1.000$ tick input mentah ke dalam *Cold Storage* (S3/GCS bucket). Snapshot ini bertindak sebagai bukti deterministik yang dapat di-replay persis pada server internal jika pemain mengajukan banding sanksi (*ticket appeal*).
3.  **Shadow Deployment Model Drift Strategy**: Model inferensi anti-cheat baru tidak boleh langsung mengeksekusi sanksi administratif. Model wajib beroperasi dalam mode `SHADOW_SILENT` selama minimal dua pekan pasca perilisan:
    ```
    Live Ingestion ---> Active Model (v1.2) --------> Enforcement
                   \
                    +-> Shadow Model (v1.3 Candidate) -> Metric Logging & Diff Audit
    ```
    Metrik *Divergence Metric* dihitung via evaluasi manual terhadap deviasi keputusan antara kedua versi tersebut guna memastikan model baru tidak mengalami degradasi akurasi (*concept drift*).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membangun harness validasi otomatis untuk memverifikasi apakah pipeline deteksi mampu menangkap injeksi kecurangan **Linear Snap Aimbot** dan **No-Recoil Script**, tanpa memicu false positive pada sesi pergerakan pemain profesional yang sah (**Human Pro Flick**).

#### Langkah Pelaksanaan

##### Langkah 1: Siapkan Environment Pengujian
Jalankan dependensi berikut pada lingkungan Python Anda:
```bash
pip install numpy pydantic
```

##### Langkah 2: Buat Skrip Harness Pengujian Komprehensif
Simpan kode berikut sebagai `test_anti_cheat_pipeline.py`. Skrip ini menginjeksikan tiga pola data sintetis ke dalam sistem pipeline yang telah kita bangun:

```python
# test_anti_cheat_pipeline.py
import asyncio
import time
from telemetry_pipeline import (
    TelemetryConsumerPipeline,
    TelemetryFrame,
    ViewAngle
)

def generate_pro_flick_telemetry(player_id: str) -> list[TelemetryFrame]:
    """Simulasi flick shot manusia: akselerasi biomekanik tinggi, diakhiri micro-adjustment."""
    frames = []
    base_time = time.time() * 1000.0
    # Posisi awal
    current_pitch = 0.0
    current_yaw = 0.0
    
    for tick in range(20):
        # Gerakan akselerasi manusia non-linier
        t = tick / 20.0
        # Sigmoid curve representing natural acceleration-deceleration profile
        sigmoid_weight = 1.0 / (1.0 + math.exp(-12.0 * (t - 0.5)))
        current_yaw = 0.0 + (45.0 * sigmoid_weight)
        
        # Tambahkan micro-jitter neuromuscular alami manusia (+/- 0.08 derajat)
        human_jitter = (math.sin(tick * 1.5) * 0.08)
        current_pitch = (10.0 * sigmoid_weight) + human_jitter

        frames.append(TelemetryFrame(
            player_id=player_id,
            tick=tick,
            timestamp_ms=base_time + (tick * 7.8125), # 128 Hz step
            view_angles=ViewAngle(pitch=current_pitch, yaw=current_yaw),
            world_position=(100.0, 200.0, 50.0),
            is_firing=tick > 15
        ))
    return frames

def generate_aimbot_snap_telemetry(player_id: str) -> list[TelemetryFrame]:
    """Simulasi memory aimbot snap: 0 delta pergerakan mendadak melompat 90 derajat dalam 1 tick."""
    frames = []
    base_time = time.time() * 1000.0
    
    for tick in range(20):
        if tick < 10:
            yaw = 0.0
            pitch = 0.0
        elif tick == 10:
            # Snap diskrit seketika dalam 1 tick
            yaw = 85.5
            pitch = -12.3
        else:
            yaw = 85.5
            pitch = -12.3

        frames.append(TelemetryFrame(
            player_id=player_id,
            tick=tick,
            timestamp_ms=base_time + (tick * 7.8125),
            view_angles=ViewAngle(pitch=pitch, yaw=yaw),
            world_position=(100.0, 200.0, 50.0),
            is_firing=tick >= 10
        ))
    return frames

def generate_recoil_script_telemetry(player_id: str) -> list[TelemetryFrame]:
    """Simulasi macro recoil: Penurunan sumbu pitch statis deterministik sempurna."""
    frames = []
    base_time = time.time() * 1000.0
    current_pitch = 20.0
    
    for tick in range(20):
        # Skrip mengoreksi -0.75 derajat tiap tick secara identik tanpa variasi
        current_pitch -= 0.75
        
        frames.append(TelemetryFrame(
            player_id=player_id,
            tick=tick,
            timestamp_ms=base_time + (tick * 7.8125),
            view_angles=ViewAngle(pitch=current_pitch, yaw=10.0),
            world_position=(100.0, 200.0, 50.0),
            is_firing=True
        ))
    return frames

async def main():
    import math # Digunakan di helper generasi data
    pipeline = TelemetryConsumerPipeline()
    
    # Jalankan consumer loop di background
    consumer_task = asyncio.create_task(pipeline.start_consumer())
    
    print("=== MEMULAI INJEKSI TELEMETRI UJI INTEGRITAS ===")
    
    # 1. Test Kasus Atlet Pro (Wajib Lolos / NOOP)
    print("\n[Uji 1] Injeksi Telemetri Human Pro Flick...")
    for frame in generate_pro_flick_telemetry("PRO_PLAYER_001"):
        await pipeline.ingest_frame(frame)
    await asyncio.sleep(0.1)

    # 2. Test Kasus Aimbot Snap (Wajib Tertangkap / Flag atau Quarantine)
    print("\n[Uji 2] Injeksi Telemetri Aimbot Snapping Injection...")
    for frame in generate_aimbot_snap_telemetry("BOTTER_SNAP_99"):
        await pipeline.ingest_frame(frame)
    await asyncio.sleep(0.1)

    # 3. Test Kasus Recoil Script (Wajib Terdeteksi Anomali Entropi Rendah)
    print("\n[Uji 3] Injeksi Telemetri Perfect Recoil Scripting...")
    for frame in generate_recoil_script_telemetry("SCRIPT_USER_404"):
        await pipeline.ingest_frame(frame)
    await asyncio.sleep(0.1)

    # Beri jeda pemrosesan event queue
    await asyncio.sleep(0.5)
    
    # Cleanup task
    pipeline.stop()
    await consumer_task
    print("\n=== VALIDASI SELESAI ===")

if __name__ == "__main__":
    asyncio.run(main())
```

##### Langkah 3: Eksekusi dan Analisis Output Audit
Jalankan skrip validasi:
```bash
python test_anti_cheat_pipeline.py
```

##### Kriteria Kelulusan Pengujian (Verification Threshold):
*   Pemain `PRO_PLAYER_001` tidak memicu pesan `[LIVEOPS DISPATCH]` aksi mitigasi agresif (`current_risk` berada jauh di bawah ambang batas $0.50$ berkat adanya variasi mikro biomekanik alami).
*   Entitas `BOTTER_SNAP_99` harus langsung membangkitkan log dispatch dengan tindakan mitigasi (`ENABLE_HIGH_FIDELITY_AUDIT` atau `QUARANTINE_MATCHMAKING`) yang dipicu oleh kalkulasi lonjakan nilai `max_angular_jerk` ekstrem.
*   Entitas `SCRIPT_USER_404` harus menghasilkan penurunan nilai `pitch_entropy` mendekati ambang batas kritis bawah yang disertai tingginya korelasi penekanan peluru berulang, mengonfirmasi aktivasi mitigasi makro.